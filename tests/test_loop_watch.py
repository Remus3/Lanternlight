"""Tests for the loop's session-watcher supervisor.

ROADMAP item ``4d``. The failure this module exists to stop is not a bug in
the watcher - ``lanternlight.armwatch`` works - it is that ARMING it was
something a human session had to remember, and twice it was forgotten:
2026-08-30 launched the client with nothing armed, and 2026-08-31 found the
successor log still single-copy.

So the headline test here is deliberately shaped like that failure. It runs a
session body that never mentions the watcher at all, and then demands that a
copy of the live log exists anyway.

Nothing here writes to ``ops/runtime/``. Every test is handed an explicit
``tmp_path`` record, because stomping the live record could let a second
watcher start against a running one. Nothing here calls the real spawn either:
every arming test injects ``spawn_fn``, so no test ever starts a detached
process.
"""

import ast
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight.savewatch import SaveWatcher  # noqa: E402
from ops.loop import guard as guard_mod, watch as watch_mod  # noqa: E402


@pytest.fixture
def record_file(tmp_path: Path) -> Path:
    """A watcher-record path inside tmp_path. The file does not exist yet."""
    return tmp_path / "armwatch.json"


def _dead_pid() -> int:
    """Return a pid that is genuinely no longer running.

    Spawning and reaping a real process beats picking a large number and
    hoping: a guessed pid can be reused, and this test would then flake in the
    one direction that matters - a live watcher declared stale and doubled.
    """
    with subprocess.Popen([sys.executable, "-c", ""]) as proc:
        proc.wait(timeout=60)
        return proc.pid


def _dated(dest_base, when: datetime) -> Path:
    """Stand-in for the dated destination resolver.

    Injected everywhere so no test depends on
    ``lanternlight.armwatch.dated_dest_root``, which is owned by a different
    slice of this item.
    """
    return Path(dest_base) / when.strftime("%Y-%m-%d")


def _record(pid: int, tmp_path: Path, *, started: str = "2026-09-01T12:00:00+00:00"):
    return watch_mod.WatchRecord(
        pid=pid,
        dest_base=str(tmp_path / "captures"),
        dest_root=str(tmp_path / "captures" / "2026-09-01"),
        started=started,
    )


# ---------------------------------------------------------------------------
# the headline acceptance - ROADMAP 4d names this test explicitly
# ---------------------------------------------------------------------------


def test_a_session_that_never_invokes_the_entry_point_still_archives_the_live_log(
    tmp_path: Path, record_file: Path
) -> None:
    """The acceptance criterion of ROADMAP 4d, stated as a test.

    ``session_body`` below is the whole point: it does ordinary, unrelated
    work and never touches ``lanternlight.armwatch``, ``ops.loop.watch``, or
    any watcher of any kind - exactly like the two sessions that lost data.
    The supervisor arms around it, and the live log is archived regardless.
    """
    saved_logs = tmp_path / "Saved" / "Logs"
    saved_logs.mkdir(parents=True)
    live_log = saved_logs / "MistfallHunter.log"
    live_log.write_text("LogMistfall: Display: launched\n", encoding="utf-8")

    dest_base = tmp_path / "captures"
    unrelated = tmp_path / "notes.txt"

    def spawn_fn(base, root) -> int:
        # A real one-pass copy through the real SaveWatcher, not a stand-in
        # for one, so this test exercises the archiving code itself.
        SaveWatcher(saved_logs, Path(root) / "logs").poll_once()
        return os.getpid()

    did: list[str] = []

    def session_body() -> None:
        unrelated.write_text("a cycle that never thought about the watcher\n", encoding="utf-8")
        did.append("unrelated work")

    when = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)
    with watch_mod.session_armed(
        dest_base,
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        now=when,
        path=record_file,
    ) as result:
        session_body()

    assert did == ["unrelated work"], "the session body must have run"
    assert result.armed is True, result.reason

    archived = sorted((dest_base / "2026-09-01" / "logs").glob("*MistfallHunter.log"))
    assert archived, "no copy of the live log under the dated destination"
    assert archived[0].read_bytes() == live_log.read_bytes()

    # And the arming is legible to a LATER session, which is the other half of
    # the criterion: continuity lives on disk, not in this session.
    persisted = watch_mod.read_record(record_file)
    assert persisted is not None
    assert persisted.pid == os.getpid()
    assert persisted.dest_root == str(dest_base / "2026-09-01")
    assert persisted.dest_base == str(dest_base)
    assert persisted.started == "2026-09-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# the refusal - never a second watcher
# ---------------------------------------------------------------------------


def test_ensure_armed_refuses_a_second_watcher_when_the_recorded_pid_is_alive(
    tmp_path: Path, record_file: Path
) -> None:
    """Two pollers on the same four sources double the snapshot traffic.

    ``OPS-14`` is open (9.87 GB across 19,162 files), so the refusal is a
    disk-budget property, not just tidiness.
    """
    incumbent = _record(os.getpid(), tmp_path, started="2026-09-01T09:00:00+00:00")
    watch_mod.write_record(incumbent, record_file)

    spawned: list[tuple] = []

    def spawn_fn(base, root) -> int:
        spawned.append((base, root))
        return 424242

    result = watch_mod.ensure_armed(
        tmp_path / "captures",
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        now=datetime(2026, 9, 2, 3, 0, 0, tzinfo=UTC),
        path=record_file,
    )

    assert spawned == [], "a second watcher must not be started"
    assert result.armed is False
    assert result.pid == os.getpid()
    assert result.dest_root == incumbent.dest_root
    assert str(os.getpid()) in result.reason

    # The incumbent's record is untouched - and, critically, the incumbent
    # itself is still running. This module refuses to start; it never stops.
    assert watch_mod.read_record(record_file) == incumbent
    assert guard_mod.pid_is_alive(os.getpid()) is True


def test_ensure_armed_rearms_when_the_recorded_pid_is_dead(
    tmp_path: Path, record_file: Path
) -> None:
    dead = _dead_pid()
    watch_mod.write_record(_record(dead, tmp_path), record_file)
    assert watch_mod.is_armed(record_file) is False
    assert watch_mod.armed_pid(record_file) is None

    spawned: list[tuple] = []

    def spawn_fn(base, root) -> int:
        spawned.append((Path(base), Path(root)))
        return os.getpid()

    dest_base = tmp_path / "captures"
    result = watch_mod.ensure_armed(
        dest_base,
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        now=datetime(2026, 9, 2, 3, 0, 0, tzinfo=UTC),
        path=record_file,
    )

    assert spawned == [(dest_base, dest_base / "2026-09-02")]
    assert result.armed is True
    assert result.pid == os.getpid()
    assert result.dest_root == str(dest_base / "2026-09-02")
    assert "stale" in result.reason.lower()

    # The dated destination is derived per run, so the re-arm did not inherit
    # yesterday's directory.
    written = watch_mod.read_record(record_file)
    assert written is not None
    assert written.pid == os.getpid()
    assert written.dest_root == str(dest_base / "2026-09-02")
    assert written.started == "2026-09-02T03:00:00+00:00"


def test_ensure_armed_arms_when_there_is_no_record_at_all(
    tmp_path: Path, record_file: Path
) -> None:
    result = watch_mod.ensure_armed(
        tmp_path / "captures",
        spawn_fn=lambda base, root: 4321,
        dest_root_fn=_dated,
        now=datetime(2026, 9, 1, 0, 0, 0, tzinfo=UTC),
        path=record_file,
    )

    assert result.armed is True
    assert result.pid == 4321
    assert record_file.exists()


# ---------------------------------------------------------------------------
# the record - round trip, and a read that never raises
# ---------------------------------------------------------------------------


def test_record_round_trips_through_write_and_read(tmp_path: Path, record_file: Path) -> None:
    original = _record(4242, tmp_path)
    written = watch_mod.write_record(original, record_file)

    assert written == record_file
    assert watch_mod.read_record(record_file) == original

    payload = json.loads(record_file.read_text(encoding="utf-8"))
    assert payload["pid"] == 4242
    assert payload["dest_base"] == original.dest_base
    assert payload["dest_root"] == original.dest_root
    assert payload["started"] == original.started


def test_read_record_returns_none_for_an_absent_file(tmp_path: Path) -> None:
    assert watch_mod.read_record(tmp_path / "nothing-here.json") is None


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("truncated json", "{"),
        ("not json at all", "armed pid 1234"),
        ("empty file", ""),
        ("json but a list", '["pid", 1234]'),
        ("json but a bare number", "1234"),
        ("object missing pid", '{"dest_base": "a", "dest_root": "b", "started": "c"}'),
        ("pid is a string", '{"pid": "12", "dest_base": "a", "dest_root": "b", "started": "c"}'),
        ("pid is a bool", '{"pid": true, "dest_base": "a", "dest_root": "b", "started": "c"}'),
        ("pid is zero", '{"pid": 0, "dest_base": "a", "dest_root": "b", "started": "c"}'),
        ("dest_root missing", '{"pid": 12, "dest_base": "a", "started": "c"}'),
        ("started is a number", '{"pid": 12, "dest_base": "a", "dest_root": "b", "started": 9}'),
    ],
)
def test_read_record_returns_none_and_never_raises(
    record_file: Path, label: str, body: str
) -> None:
    record_file.write_text(body, encoding="utf-8")
    assert watch_mod.read_record(record_file) is None, label
    # The evidence survives - a diagnosing session needs to see what was there.
    assert record_file.read_text(encoding="utf-8") == body


def test_read_record_returns_none_when_the_path_is_a_directory(tmp_path: Path) -> None:
    """An OSError that is not FileNotFoundError still has to fail soft."""
    directory = tmp_path / "armwatch.json"
    directory.mkdir()
    assert watch_mod.read_record(directory) is None


def test_armed_pid_is_none_for_a_dead_owner_but_the_record_survives(
    tmp_path: Path, record_file: Path
) -> None:
    dead = _record(_dead_pid(), tmp_path)
    watch_mod.write_record(dead, record_file)

    assert watch_mod.armed_pid(record_file) is None
    assert watch_mod.is_armed(record_file) is False
    assert watch_mod.read_record(record_file) == dead


def test_armed_pid_reports_a_live_owner(tmp_path: Path, record_file: Path) -> None:
    watch_mod.write_record(_record(os.getpid(), tmp_path), record_file)
    assert watch_mod.armed_pid(record_file) == os.getpid()
    assert watch_mod.is_armed(record_file) is True


def test_write_record_goes_through_a_temp_file_and_never_truncates_the_target(
    tmp_path: Path, record_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A later session may poll this record at any instant.

    A plain ``open(path, "w")`` truncates first, so a poll landing in that
    window reads no pid and concludes nothing is armed - which would start a
    second watcher, the one outcome this module exists to prevent. Assert the
    temp-then-replace path instead.
    """
    first = _record(1111, tmp_path)
    watch_mod.write_record(first, record_file)
    before = record_file.read_text(encoding="utf-8")
    assert json.loads(before)["pid"] == 1111

    observed: list[dict] = []
    real_replace = Path.replace

    def spy_replace(self: Path, target) -> Path:
        target_path = Path(target)
        observed.append(
            {
                "source": self,
                "target": target_path,
                "source_contents": self.read_text(encoding="utf-8"),
                "target_contents": (
                    target_path.read_text(encoding="utf-8") if target_path.exists() else None
                ),
            }
        )
        return real_replace(self, target)

    monkeypatch.setattr(Path, "replace", spy_replace)
    watch_mod.write_record(_record(2222, tmp_path), record_file)

    assert len(observed) == 1, "exactly one atomic move per write"
    move = observed[0]
    assert move["target"] == record_file
    assert move["source"] != record_file
    assert move["source"].name.startswith(watch_mod.temp_prefix_for(record_file))
    # Same directory, or the move is not a rename and is not atomic.
    assert move["source"].parent == record_file.parent
    assert json.loads(move["source_contents"])["pid"] == 2222
    # The critical one: mid-write the target was still the whole old document.
    assert move["target_contents"] == before
    assert json.loads(move["target_contents"])["pid"] == 1111

    assert json.loads(record_file.read_text(encoding="utf-8"))["pid"] == 2222


def test_write_record_leaves_no_temp_debris(tmp_path: Path, record_file: Path) -> None:
    for pid in (1, 2, 3):
        watch_mod.write_record(_record(pid, tmp_path), record_file)

    leftovers = [p.name for p in record_file.parent.iterdir() if p != record_file]
    assert leftovers == [], f"temp files left behind: {leftovers}"


def test_write_record_creates_the_parent_directory(tmp_path: Path) -> None:
    nested = tmp_path / "runtime" / "deeper" / "armwatch.json"
    watch_mod.write_record(_record(7, tmp_path), nested)
    assert nested.exists()


def test_record_path_points_into_the_gitignored_runtime_dir() -> None:
    default = watch_mod.record_path()
    assert default.name == watch_mod.WATCH_RECORD_FILENAME
    assert default.parent == guard_mod.runtime_dir()
    assert default.parent.parent.name == "ops"


# ---------------------------------------------------------------------------
# session_armed
# ---------------------------------------------------------------------------


def test_session_armed_leaves_the_watcher_running_after_an_exception(
    tmp_path: Path, record_file: Path
) -> None:
    """A crashed cycle must not take the archive down with it.

    The watcher outliving its arming session is the entire design, so the
    context manager's exit is deliberately a no-op - and it certainly does not
    stop anything.
    """
    boom = RuntimeError("cycle blew up")

    with (
        pytest.raises(RuntimeError) as excinfo,
        watch_mod.session_armed(
            tmp_path / "captures",
            spawn_fn=lambda base, root: os.getpid(),
            dest_root_fn=_dated,
            now=datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC),
            path=record_file,
        ) as result,
    ):
        assert result.armed is True
        raise boom

    assert excinfo.value is boom
    assert watch_mod.armed_pid(record_file) == os.getpid()
    assert guard_mod.pid_is_alive(os.getpid()) is True


def test_session_armed_reports_a_refusal_rather_than_raising(
    tmp_path: Path, record_file: Path
) -> None:
    watch_mod.write_record(_record(os.getpid(), tmp_path), record_file)

    def spawn_fn(base, root) -> int:
        raise AssertionError("session_armed must not spawn over a live watcher")

    with watch_mod.session_armed(
        tmp_path / "captures",
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        path=record_file,
    ) as result:
        assert result.armed is False
        assert result.pid == os.getpid()


# ---------------------------------------------------------------------------
# structural prohibitions
# ---------------------------------------------------------------------------


def _module_source() -> str:
    return Path(watch_mod.__file__).read_text(encoding="utf-8")


def _open_process_calls(tree: ast.AST) -> list[ast.Call]:
    """Every ``OpenProcess`` call in ``tree``, by EITHER spelling.

    The blanket prohibition above walks BOTH ``ast.Attribute`` and ``ast.Name``
    callees, so ``kernel32.OpenProcess(...)`` and a bare ``OpenProcess(...)``
    after a rebinding were equally caught by it while the name was simply
    banned. When item ``4e`` narrowed that ban to a check on the RIGHT, the
    replacement collector matched attributes only - and quietly handed the bare
    spelling back. That is the difference between narrowing a prohibition and
    losing one, and it was found by the refutation pass rather than by the
    green suite, which is exactly the failure mode a green suite cannot see.
    """
    found: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Attribute) and func.attr == "OpenProcess") or (
            isinstance(func, ast.Name) and func.id == "OpenProcess"
        ):
            found.append(node)
    return found


def _asks_only_for_query_limited_information(node: ast.Call) -> bool:
    """True when this ``OpenProcess`` call asks for exactly the query-only right.

    Deliberately structural and deliberately strict. The access right must be
    the NAME of the module's own constant: an integer literal, a bitwise OR
    that folds a wider right in, or a keyword-only call all fail here, because
    each is a way to acquire a power to affect while still reading like a
    request to ask.
    """
    if not node.args:
        return False
    access = node.args[0]
    return isinstance(access, ast.Name) and access.id == "_PROCESS_QUERY_LIMITED_INFORMATION"


def test_watch_exposes_no_termination_path() -> None:
    """It refuses to start a second watcher; it never stops the first.

    Structural, over the parsed module rather than its text - the docstring
    names what it refuses to do, and a raw text scan would flag its own
    documentation.
    """
    exported = set(watch_mod.__all__)
    assert not (exported & {"kill", "terminate", "stop", "stop_watcher", "taskkill", "disarm"})

    tree = ast.parse(_module_source())
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            names.add(func.attr)
        elif isinstance(func, ast.Name):
            names.add(func.id)

    forbidden = {
        "kill",
        "killpg",
        "terminate",
        "send_signal",
        "taskkill",
        "TerminateProcess",
        "system",
    }
    assert not (names & forbidden), f"watch must not call {sorted(names & forbidden)}"

    # Anchors, so the assertion above is about a module that really does start
    # processes and really does ask about liveness - a module that did neither
    # would pass the negative check vacuously.
    assert "Popen" in names, "expected the detached spawn to be present"
    assert "pid_is_alive" in names, "expected liveness to be delegated to the guard's probe"


def test_the_only_process_right_this_module_asks_for_is_query_limited_information() -> None:
    """``OpenProcess`` left the blanket prohibition above - narrowed, not dropped.

    Item ``4e`` needs a process CREATION TIME to tell the watcher apart from an
    unrelated process that inherited its pid, and ``GetProcessTimes`` needs a
    handle, so ``OpenProcess`` had to become legal in this module. What was
    ever dangerous about it was not the call, it was the RIGHT: a handle opened
    with ``PROCESS_TERMINATE`` is a termination path no matter what the
    surrounding code claims to be doing with it. So the prohibition is restated
    as the thing it actually protects rather than deleted.

    ``PROCESS_QUERY_LIMITED_INFORMATION`` (0x1000) grants no power to affect
    the process - it is the weakest right that can answer "when did this
    start?" - and it is the only right this module asks for.
    """
    source = _module_source()
    tree = ast.parse(source)

    opens = _open_process_calls(tree)
    # Non-vacuous: if the probe were deleted this list would be empty and the
    # per-call assertions below would never run.
    assert opens, "expected the creation-time probe to open a process handle"

    for node in opens:
        assert _asks_only_for_query_limited_information(node), ast.dump(node)

    assert watch_mod._PROCESS_QUERY_LIMITED_INFORMATION == 0x1000
    for banned in ("PROCESS_TERMINATE", "PROCESS_VM_WRITE", "PROCESS_SUSPEND_RESUME"):
        assert banned not in source, f"{banned} would be a right to affect, not to ask"


#: Ways of asking for a wider process right than this module is allowed to
#: hold. Each is a real spelling, not a strawman: a rebound bare name, an
#: integer literal, a mask that folds PROCESS_TERMINATE in beside the legal
#: right, and a keyword-only call that leaves ``args`` empty.
WIDER_RIGHT_SPELLINGS = (
    "kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)",
    "OpenProcess(PROCESS_ALL_ACCESS, False, pid)",
    "kernel32.OpenProcess(0x0001, False, pid)",
    "kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION | 0x0001, False, pid)",
    "kernel32.OpenProcess(dwDesiredAccess=0x0001, bInheritHandle=False, dwProcessId=pid)",
)


@pytest.mark.parametrize("spelling", WIDER_RIGHT_SPELLINGS)
def test_the_process_right_guard_catches_every_spelling_it_is_meant_to(spelling: str) -> None:
    """A guard for the guard, over synthetic source rather than this module.

    The test above can only ever see the code that is actually shipped, so it
    proves the CURRENT probe is well behaved and says nothing about what the
    check would do with a badly behaved one. That gap is not hypothetical: the
    first version of this guard matched attribute callees only, and the bare
    ``OpenProcess(...)`` spelling on line two below walked straight through it
    while every test stayed green. A negative check that has never been shown a
    positive is decoration.

    Both halves are exercised deliberately - the collector must SEE the call,
    and the right-check must REJECT it - because a collector that misses the
    call produces exactly the same green as a right-check that waves it
    through.
    """
    calls = _open_process_calls(ast.parse(spelling))
    assert calls, f"the collector never saw {spelling!r}, so nothing judged its right"
    assert not _asks_only_for_query_limited_information(calls[0]), (
        f"{spelling!r} acquires a power to affect and must not read as query-only"
    )


def test_the_process_right_guard_still_accepts_the_legitimate_spelling() -> None:
    """The mirror of the above - a guard that rejects everything is no guard.

    Without this, every assertion in the parametrized test would still pass if
    :func:`_asks_only_for_query_limited_information` were replaced by
    ``return False``.
    """
    legal = "kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)"
    calls = _open_process_calls(ast.parse(legal))
    assert calls
    assert _asks_only_for_query_limited_information(calls[0])


def test_liveness_is_delegated_to_the_guard_rather_than_reimplemented() -> None:
    """``os.kill(pid, 0)`` maps onto ``TerminateProcess`` on Windows CPython.

    The guard already solved that with ``OpenProcess`` plus
    ``GetExitCodeProcess``. Re-deriving a probe here is how the trap gets
    walked into twice.
    """
    tree = ast.parse(_module_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            attr = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            assert attr != "kill", ast.dump(node)

    assert watch_mod.guard.pid_is_alive is guard_mod.pid_is_alive


def test_the_default_dated_destination_is_imported_lazily() -> None:
    """Importing this module must not require ``armwatch``'s dated helper.

    The helper is owned by a different slice of item 4d. A module-scope import
    of it would make this supervisor unimportable while that slice is in
    flight, and would make every test here depend on another agent's file.
    """
    tree = ast.parse(_module_source())

    module_level = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            module_level.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_level.add(alias.name)
    assert "lanternlight.armwatch" not in module_level
    assert not any(name.startswith("lanternlight") for name in module_level)

    nested = [
        node
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef)
        for node in ast.walk(fn)
        if isinstance(node, ast.ImportFrom) and node.module == "lanternlight.armwatch"
    ]
    assert nested, "expected the armwatch import to sit inside a function body"


def test_the_default_dated_destination_uses_the_local_day_not_the_utc_one(
    tmp_path: Path,
) -> None:
    """The one test here that calls the real ``armwatch`` resolver.

    Everything else injects, but this seam is where a cross-module contract
    can rot silently: ``dated_dest_root`` takes ``now`` keyword-only and reads
    a LOCAL clock, while :attr:`WatchRecord.started` is UTC. Handing it a UTC
    instant unconverted would file the last five hours of every local day under
    tomorrow, which is the mislabelled archive item 4d exists to prevent.
    """
    dest_base = tmp_path / "captures"
    # 03:00 UTC is the previous day at any negative offset, this machine
    # included (UTC-5).
    when = datetime(2026, 9, 2, 3, 0, 0, tzinfo=UTC)

    resolved = watch_mod._default_dest_root_fn(dest_base, when)

    local = when.astimezone()
    assert resolved == dest_base / local.strftime("%Y-%m-%d")
    if local.utcoffset() != when.utcoffset():
        assert resolved != dest_base / "2026-09-02", "the UTC day was used, not the local one"


def test_the_default_spawn_is_never_reached_when_one_is_injected(
    tmp_path: Path, record_file: Path
) -> None:
    """No test in this file may start a real detached watcher.

    Guarded here rather than trusted: a default that leaked through would
    spawn a poller that outlives the suite, against the operator's real
    ``Saved/`` directory.
    """
    calls: list[int] = []

    def spawn_fn(base, root) -> int:
        calls.append(1)
        return os.getpid()

    watch_mod.ensure_armed(
        tmp_path / "captures",
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        path=record_file,
    )
    assert calls == [1]
# ---------------------------------------------------------------------------
# the wiring itself - a doc that quietly loses the arming is the whole failure
# ---------------------------------------------------------------------------


#: Every document that tells a session how to START one. Arming is wired into
#: the start-up step in each, and this list is what stops a future edit from
#: dropping it silently. `ops/loop/guard.py` deliberately does NOT arm - it is
#: a lock and nothing else - so the wiring lives in prose, and prose with no
#: test on it is a comment.
SESSION_ENTRY_DOCS = (
    ".claude/commands/loop.md",
    ".claude/commands/continue.md",
    "docs/HEADLESS.md",
)


@pytest.mark.parametrize("relpath", SESSION_ENTRY_DOCS)
def test_every_session_entry_document_still_wires_the_arming(relpath: str) -> None:
    """A session-entry doc that stops naming the arming has undone item 4d.

    This is the honest limit of the mechanism, pinned rather than papered over.
    Nothing in code FORCES a session to arm: taking the loop lock and arming
    are two calls, and a cycle that writes only the first runs unwatched. What
    is enforceable is that every document telling a session how to start says
    to arm, so dropping it is a red test rather than a silent regression.
    """
    text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert "session_armed" in text, (
        f"{relpath} no longer names session_armed, so a session following it "
        "would start with no watcher armed - the exact failure ROADMAP 4d closed"
    )


# ---------------------------------------------------------------------------
# ROADMAP 4e - the WRAP-side check
#
# Everything above this line asks "was a watcher armed on the way IN". Item 4e
# is the next failure along: on 2026-09-01 a watcher was armed as pid 17568,
# correctly refused two re-arm attempts while it was alive, and was found DEAD
# at the wrap. A refusal to re-arm is only as good as the process it deferred
# to, and nothing re-checked that process.
#
# No test below starts a real process either. ``creation_time_fn`` is injected
# wherever the verdict is the thing under test, and the two tests that use the
# real ctypes probe point it at this interpreter, which is already running.
# ---------------------------------------------------------------------------


def _heartbeat_file(
    tmp_path: Path,
    *,
    pid: int,
    written: str,
    surfaces: dict | None = None,
    passes: int = 42,
) -> Path:
    """Write a heartbeat in the shape pinned with the armwatch slice.

    Fixed size, rewritten in place, four surfaces keyed by name. Written here
    by hand rather than by calling the watcher, so this file does not depend on
    a module another agent owns.
    """
    stamps = dict.fromkeys(("savegames", "standalonelevel", "savedroot", "logs"), written)
    payload = {
        "pid": pid,
        "written": written,
        "passes": passes,
        "surfaces": stamps if surfaces is None else surfaces,
    }
    target = tmp_path / watch_mod.HEARTBEAT_FILENAME
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _fixed_creation(when: datetime):
    """A ``creation_time_fn`` that answers ``when`` for any pid."""

    def creation_time_fn(pid: int):
        return when

    return creation_time_fn


NOW = datetime(2026, 9, 3, 5, 0, 0, tzinfo=UTC)
ARMED_AT = "2026-09-02T01:26:36+00:00"

#: The creation time this machine really reported for the armed watcher, pid
#: 23628, on 2026-09-02, against an ``armwatch.json`` recording
#: ``started: 2026-09-02T01:26:36+00:00``. Kept as a literal because it is the
#: only measurement that pins the SIGN of the offset: the process starts a
#: fraction of a second AFTER the stamp the record carries.
MEASURED_CREATION = datetime(2026, 9, 2, 1, 26, 36, 56876, tzinfo=UTC)


# ---------------------------------------------------------------------------
# the creation-time probe
# ---------------------------------------------------------------------------


def test_process_creation_time_is_none_rather_than_a_guess_when_it_cannot_tell() -> None:
    """Cannot-tell is a third answer, and it must never look like a verdict.

    A probe that returned a plausible datetime on failure would settle the
    identity question with fiction. Item 4e's whole hazard is that a wrong
    IMPOSTOR verdict re-arms alongside a live watcher.
    """
    assert watch_mod.process_creation_time(None) is None
    assert watch_mod.process_creation_time(0) is None
    assert watch_mod.process_creation_time(-1) is None
    assert watch_mod.process_creation_time(True) is None
    assert watch_mod.process_creation_time(_dead_pid()) is None


def test_process_creation_time_reads_this_process_on_the_platform_that_can() -> None:
    before = datetime.now(UTC)
    created = watch_mod.process_creation_time(os.getpid())
    if created is None:
        pytest.skip("no creation-time probe on this platform; the injected tests pin the logic")

    assert created.tzinfo is not None, "an aware UTC datetime, never a naive one"
    assert created.utcoffset() == timedelta(0)
    # This interpreter started before now and long after the FILETIME epoch. A
    # conversion that dropped the 1601 epoch, or that read the wrong FILETIME
    # field of the four, lands outside this pair.
    assert datetime(2000, 1, 1, tzinfo=UTC) < created <= before


# ---------------------------------------------------------------------------
# identity - a live pid is a weaker statement than "the watcher is running"
# ---------------------------------------------------------------------------


def test_the_wrap_refuses_to_treat_a_live_but_unrelated_pid_as_armed(
    tmp_path: Path, record_file: Path
) -> None:
    """The named acceptance criterion of ROADMAP 4e, stated as a test.

    The record names a pid that is genuinely ALIVE - this test's own process,
    exactly as the item suggests - but the arming stamp sits six hours from
    when that process really started. A check that stopped at liveness would
    report it as armed and the wrap would hand the machine back with nothing
    polling. A test that only ever sees a dead pid does not pin this.
    """
    created = watch_mod.process_creation_time(os.getpid())
    if created is None:
        pytest.skip("no creation-time probe on this platform; the injected twin below pins it")

    # Derived from the real creation time rather than hard-coded, so the gap is
    # six hours whenever the suite happens to run.
    started = watch_mod._stamp(created - timedelta(hours=6))
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=started), record_file)

    # Liveness alone says yes. That is the weaker statement, and it is what
    # every check in this repo before item 4e stopped at.
    assert watch_mod.is_armed(record_file) is True
    assert guard_mod.pid_is_alive(os.getpid()) is True

    status = watch_mod.check_watcher(path=record_file, heartbeat=tmp_path / "absent.json")

    assert status.state == watch_mod.STATE_IMPOSTOR, status.reason
    assert status.armed is False, status.reason
    assert status.pid == os.getpid()
    assert str(os.getpid()) in status.reason
    assert any("creation" in item for item in status.evidence), status.evidence


def test_check_watcher_reports_impostor_for_a_creation_time_outside_the_window(
    tmp_path: Path, record_file: Path
) -> None:
    """The platform-independent twin of the test above.

    The real probe only exists on Windows, so the VERDICT is pinned here with
    an injected creation time and runs everywhere.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    recycled = datetime(2026, 9, 3, 4, 0, 0, tzinfo=UTC)  # 26.5 hours after the arming

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(recycled),
    )

    assert status.state == watch_mod.STATE_IMPOSTOR
    assert status.armed is False
    assert str(os.getpid()) in status.reason


def test_the_measured_sub_second_offset_confirms_identity_rather_than_refuting_it(
    tmp_path: Path, record_file: Path
) -> None:
    """Ground truth from this machine, 2026-09-02.

    ``armwatch.json`` recorded ``started`` at second resolution and pid 23628's
    real creation time was 0.056876 s LATER. A window that did not admit that
    offset would call the live incumbent an impostor and re-arm a second poller
    beside it - the doubling ``ensure_armed`` exists to refuse.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state != watch_mod.STATE_IMPOSTOR, status.reason
    assert status.armed is True, status.reason


@pytest.mark.parametrize("offset_s", [-119.0, -1.0, 0.0, 0.056876, 1.0, 119.0])
def test_a_creation_time_inside_the_window_is_the_watcher(
    tmp_path: Path, record_file: Path, offset_s: float
) -> None:
    """Both directions are inside, and both directions are reachable.

    ``_now()`` truncates microseconds, so the recorded stamp can sit up to a
    second EARLIER than the real call; a caller that injects its own ``now``
    can put it either side. Neither is an impostor.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    created = datetime.fromisoformat(ARMED_AT) + timedelta(seconds=offset_s)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(created),
    )
    assert status.state != watch_mod.STATE_IMPOSTOR, status.reason


def test_an_unavailable_creation_time_reads_as_the_incumbent_not_as_an_impostor(
    tmp_path: Path, record_file: Path
) -> None:
    """The two error directions are not symmetric, and this is which way to err.

    A false IMPOSTOR re-arms beside a live watcher and doubles the snapshot
    traffic. A missed impostor leaves one poller running under a wrong name.
    So cannot-tell resolves toward believing the incumbent.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=lambda pid: None,
    )

    assert status.state != watch_mod.STATE_IMPOSTOR
    assert status.armed is True
    assert any("unavailable" in item for item in status.evidence), status.evidence


def test_an_unparseable_started_stamp_also_reads_as_the_incumbent(
    tmp_path: Path, record_file: Path
) -> None:
    """Half the comparison missing is still cannot-tell, not a verdict."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started="whenever"), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state != watch_mod.STATE_IMPOSTOR
    assert status.armed is True


# ---------------------------------------------------------------------------
# the states that mean nothing is polling
# ---------------------------------------------------------------------------


def test_check_watcher_reports_no_record_when_there_is_none(tmp_path: Path) -> None:
    status = watch_mod.check_watcher(
        path=tmp_path / "nothing-here.json",
        heartbeat=tmp_path / "absent.json",
        now=NOW,
    )
    assert status.state == watch_mod.STATE_NO_RECORD
    assert status.armed is False
    assert status.pid is None
    assert status.heartbeat_age_s is None


def test_check_watcher_reports_dead_which_is_the_ll_0117_failure(
    tmp_path: Path, record_file: Path
) -> None:
    """Armed as pid 17568, refused two re-arms, found DEAD at the wrap.

    The heartbeat here is FRESH on purpose: a stamp left behind by a watcher
    that has since died must not resurrect it. Liveness is decided first.
    """
    dead = _dead_pid()
    watch_mod.write_record(_record(dead, tmp_path, started=ARMED_AT), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=_heartbeat_file(tmp_path, pid=dead, written=watch_mod._stamp(NOW)),
        now=NOW,
    )

    assert status.state == watch_mod.STATE_DEAD
    assert status.armed is False
    assert status.pid == dead
    assert str(dead) in status.reason


# ---------------------------------------------------------------------------
# the states that are REPORTED but must never re-arm
# ---------------------------------------------------------------------------


def test_a_missing_heartbeat_is_reported_but_still_reads_as_armed(
    tmp_path: Path, record_file: Path
) -> None:
    """Not hypothetical: pid 23628 was armed before the heartbeat existed.

    Treating an absent heartbeat as a dead watcher would re-arm beside a live
    poller on the same four sources - a REGRESSION dressed as a stricter check.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "never-written.json",
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_NO_HEARTBEAT
    assert status.armed is True, status.reason
    assert status.heartbeat_age_s is None
    assert status.state not in watch_mod.REARM_STATES


@pytest.mark.parametrize(
    ("label", "body"),
    [
        ("truncated json", "{"),
        ("not json at all", "written just now, honest"),
        ("empty file", ""),
        ("json but a list", '["written", "2026-09-03T05:00:00+00:00"]'),
        ("json but a bare number", "1234"),
        ("written missing", '{"pid": 1, "passes": 2}'),
        ("written is a number", '{"pid": 1, "written": 17}'),
        ("written is not a stamp", '{"pid": 1, "written": "just now"}'),
    ],
)
def test_an_unreadable_heartbeat_is_reported_but_still_reads_as_armed(
    tmp_path: Path, record_file: Path, label: str, body: str
) -> None:
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    beat = tmp_path / watch_mod.HEARTBEAT_FILENAME
    beat.write_text(body, encoding="utf-8")

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_NO_HEARTBEAT, label
    assert status.armed is True, label
    # The evidence survives - a diagnosing session needs to see what was there.
    assert beat.read_text(encoding="utf-8") == body


def test_a_heartbeat_naming_a_different_pid_proves_nothing_about_this_one(
    tmp_path: Path, record_file: Path
) -> None:
    """A fresh stamp written by some other watcher is not this watcher polling."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    beat = _heartbeat_file(tmp_path, pid=os.getpid() + 1, written=watch_mod._stamp(NOW))

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_NO_HEARTBEAT
    assert status.armed is True


def test_a_frozen_heartbeat_reads_as_stale(tmp_path: Path, record_file: Path) -> None:
    """The other WATCHED-GOING-RED acceptance of ROADMAP 4e.

    Liveness is not function. Pid 23628 was alive AND identity-confirmed at the
    cycle 37 wrap and had archived nothing for over 24 hours - correct with the
    client closed, and indistinguishable from a wedge. The heartbeat is what
    separates them, and a check that only ever sees a fresh one pins this no
    better than a dead-pid-only test pins the liveness half.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    frozen = NOW - timedelta(seconds=watch_mod.HEARTBEAT_STALE_AFTER_S + 60)
    beat = _heartbeat_file(tmp_path, pid=os.getpid(), written=watch_mod._stamp(frozen))

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_STALE, status.reason
    assert status.heartbeat_age_s == pytest.approx(watch_mod.HEARTBEAT_STALE_AFTER_S + 60)
    # Reported, not acted on. STALE is still armed and nothing is stopped.
    assert status.armed is True
    assert status.state not in watch_mod.REARM_STATES
    assert str(os.getpid()) in status.reason


def test_a_fresh_heartbeat_reads_as_armed(tmp_path: Path, record_file: Path) -> None:
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    beat = _heartbeat_file(
        tmp_path, pid=os.getpid(), written=watch_mod._stamp(NOW - timedelta(seconds=12))
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_ARMED, status.reason
    assert status.armed is True
    assert status.heartbeat_age_s == pytest.approx(12.0)
    # The reason names the pid and the destination, the way ArmResult.reason
    # does, because that string is what an operator reads at the wrap.
    assert str(os.getpid()) in status.reason
    assert str(status.dest_root) in status.reason
    assert any("surfaces" in item for item in status.evidence), status.evidence


@pytest.mark.parametrize("inside_by_s", [0.0, 1.0, 300.0])
def test_a_heartbeat_at_or_inside_the_threshold_is_not_stale(
    tmp_path: Path, record_file: Path, inside_by_s: float
) -> None:
    """The boundary is inclusive, so exactly-at-threshold is not yet stale."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    written = NOW - timedelta(seconds=watch_mod.HEARTBEAT_STALE_AFTER_S - inside_by_s)
    beat = _heartbeat_file(tmp_path, pid=os.getpid(), written=watch_mod._stamp(written))

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )
    assert status.state == watch_mod.STATE_ARMED, status.reason


# ---------------------------------------------------------------------------
# the thresholds themselves - a number with no argument is a guess
# ---------------------------------------------------------------------------


def test_the_staleness_threshold_clears_the_flush_throttle_by_a_wide_margin() -> None:
    """The heartbeat is flushed AT MOST once every 30 s by the watcher.

    A threshold anywhere near that would report STALE for a watcher that is
    simply throttling, so the throttle has to be a rounding error against it.
    """
    assert watch_mod.SLOWEST_POLL_INTERVAL_S == 300.0, "the logs surface polls at 300 s"
    assert watch_mod.HEARTBEAT_FLUSH_THROTTLE_S == 30.0, "pinned with the armwatch slice"
    assert watch_mod.HEARTBEAT_STALE_MULTIPLE >= 3
    assert watch_mod.HEARTBEAT_STALE_AFTER_S == (
        watch_mod.SLOWEST_POLL_INTERVAL_S * watch_mod.HEARTBEAT_STALE_MULTIPLE
    )
    assert watch_mod.HEARTBEAT_STALE_AFTER_S >= 10 * watch_mod.HEARTBEAT_FLUSH_THROTTLE_S


def test_the_identity_window_is_generous_enough_to_believe_the_incumbent() -> None:
    """Err toward the incumbent - a false IMPOSTOR is the expensive direction."""
    assert watch_mod.IDENTITY_TOLERANCE_S >= 60.0
    # A recycled pid's process began hours or days from the arming stamp, so a
    # generous window still catches it. Kept well under an hour anyway, so the
    # check is not decorative.
    assert watch_mod.IDENTITY_TOLERANCE_S <= 600.0


# ---------------------------------------------------------------------------
# the wrap entry point - re-arm on exactly three of the six states
# ---------------------------------------------------------------------------


def _spy_spawn(calls: list):
    """A RECORDING spy, never a raising one.

    A spy that raised would be vacuous the moment the code under test grew a
    bare ``except Exception``, because ``AssertionError`` is an ``Exception``.
    The assertion lives in the test body where nothing can swallow it.
    """

    def spawn_fn(base, root) -> int:
        calls.append((Path(base), Path(root)))
        return os.getpid()

    return spawn_fn


def test_the_wrap_rearms_a_dead_watcher(tmp_path: Path, record_file: Path) -> None:
    dead = _dead_pid()
    watch_mod.write_record(_record(dead, tmp_path, started=ARMED_AT), record_file)
    calls: list = []

    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=tmp_path / "absent.json",
    )

    assert result.status.state == watch_mod.STATE_DEAD
    assert len(calls) == 1, "a dead watcher must be replaced"
    assert result.arm is not None
    assert result.arm.armed is True
    assert result.rearmed is True
    written = watch_mod.read_record(record_file)
    assert written is not None
    assert written.pid == os.getpid()


def test_the_wrap_rearms_an_impostor(tmp_path: Path, record_file: Path) -> None:
    """The live-pid half, end to end - the state has to actually drive the re-arm."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    calls: list = []

    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        creation_time_fn=_fixed_creation(datetime(2026, 9, 3, 4, 0, 0, tzinfo=UTC)),
    )

    assert result.status.state == watch_mod.STATE_IMPOSTOR
    assert len(calls) == 1, "an impostor must not be left standing in for the watcher"
    assert result.rearmed is True


def test_the_wrap_arms_when_there_is_no_record_at_all(tmp_path: Path, record_file: Path) -> None:
    calls: list = []
    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=tmp_path / "absent.json",
    )

    assert result.status.state == watch_mod.STATE_NO_RECORD
    assert len(calls) == 1
    assert result.rearmed is True


@pytest.mark.parametrize("age_s", [12.0, 3600.0])
def test_the_wrap_never_rearms_a_watcher_it_can_still_see(
    tmp_path: Path, record_file: Path, age_s: float
) -> None:
    """ARMED at 12 s, STALE at 3600 s. Neither spawns, neither stops anything.

    STALE is the interesting one: it is a report, not a verdict on the process.
    Killing is explicitly out of scope for item 4e, and re-arming a wedged
    watcher would put a second poller on the same four sources - worse than the
    wedge, because now the disk fills too.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    beat = _heartbeat_file(
        tmp_path, pid=os.getpid(), written=watch_mod._stamp(NOW - timedelta(seconds=age_s))
    )
    calls: list = []

    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=beat,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert calls == [], f"the wrap spawned over a live watcher: {calls}"
    assert result.arm is None
    assert result.rearmed is False
    assert result.status.armed is True
    # And the incumbent is untouched, record and process alike.
    survivor = watch_mod.read_record(record_file)
    assert survivor is not None
    assert survivor.pid == os.getpid()
    assert guard_mod.pid_is_alive(os.getpid()) is True


def test_the_wrap_never_rearms_a_watcher_with_no_heartbeat(
    tmp_path: Path, record_file: Path
) -> None:
    """The state pid 23628 is in on this machine right now.

    It was armed before the heartbeat existed and it passes the identity check.
    Re-arming it would spawn the second poller ``ensure_armed`` refuses.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    calls: list = []

    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=tmp_path / "never-written.json",
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert result.status.state == watch_mod.STATE_NO_HEARTBEAT
    assert calls == [], f"the wrap spawned over a live watcher: {calls}"
    assert result.rearmed is False


def test_rearm_states_are_exactly_the_three_that_mean_nothing_is_polling() -> None:
    expected = frozenset(
        {watch_mod.STATE_NO_RECORD, watch_mod.STATE_DEAD, watch_mod.STATE_IMPOSTOR}
    )
    assert expected == watch_mod.REARM_STATES
    assert watch_mod.STATE_NO_HEARTBEAT not in watch_mod.REARM_STATES
    assert watch_mod.STATE_STALE not in watch_mod.REARM_STATES
    assert watch_mod.STATE_ARMED not in watch_mod.REARM_STATES


def test_the_wrap_default_spawn_is_never_reached_when_one_is_injected(
    tmp_path: Path, record_file: Path
) -> None:
    """No test in this file may start a real detached watcher, wrap path included."""
    calls: list = []
    watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=_spy_spawn(calls),
        dest_root_fn=_dated,
        path=record_file,
        heartbeat=tmp_path / "absent.json",
    )
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# the heartbeat path, and handing it to the child
# ---------------------------------------------------------------------------


def test_heartbeat_path_sits_beside_the_arming_record_in_the_gitignored_runtime_dir() -> None:
    beat = watch_mod.heartbeat_path()
    assert beat.name == watch_mod.HEARTBEAT_FILENAME
    assert beat.parent == guard_mod.runtime_dir()
    assert beat.parent == watch_mod.record_path().parent
    assert beat != watch_mod.record_path()


def test_default_spawn_hands_the_child_the_heartbeat_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ops layer owns the path; the lanternlight layer never computes it.

    ``ops.loop.watch`` already imports ``lanternlight.armwatch``, so a reverse
    dependency would be an import cycle. Popen is faked here - this test must
    not start a detached poller against the operator's real ``Saved/``.
    """
    seen: list[list[str]] = []

    class _FakeChild:
        pid = 999999

    def fake_popen(argv, **kwargs):
        seen.append(list(argv))
        return _FakeChild()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    pid = watch_mod.default_spawn(tmp_path / "captures", tmp_path / "captures" / "2026-09-03")

    assert pid == 999999
    assert len(seen) == 1
    argv = seen[0]
    assert "--heartbeat" in argv, argv
    assert argv[argv.index("--heartbeat") + 1] == str(watch_mod.heartbeat_path())
    # The rest of the shape is unchanged - the BASE, never a dated path.
    assert argv[argv.index("--dest-base") + 1] == str(tmp_path / "captures")
    assert "-m" in argv
    assert "lanternlight.armwatch" in argv
    assert all(isinstance(item, str) for item in argv), "fixed argv, no shell"


# ---------------------------------------------------------------------------
# the wrap wiring - a doc that quietly loses the check is the whole failure
# ---------------------------------------------------------------------------


#: Every document that tells a session how to FINISH one. The sibling of
#: ``SESSION_ENTRY_DOCS`` above: entry arms, wrap re-checks, and a cold session
#: reading the headless contract has to learn both or it learns half of 4e.
SESSION_WRAP_DOCS = (
    ".claude/commands/done.md",
    "docs/HEADLESS.md",
)


@pytest.mark.parametrize("relpath", SESSION_WRAP_DOCS)
def test_every_session_wrap_document_names_the_wrap_side_check(relpath: str) -> None:
    """A wrap doc that stops naming the check has undone item 4e.

    Same honest limit as the entry-side twin: nothing in code FORCES a wrap to
    check. What is enforceable is that every document telling a session how to
    finish says to, so dropping it is a red test rather than silence.
    """
    text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert "check_watcher" in text, (
        f"{relpath} no longer names check_watcher, so a session following it "
        "would hand the machine back without re-checking the watcher it armed - "
        "the exact failure ROADMAP 4e closes"
    )


# ---------------------------------------------------------------------------
# cross-layer coupling - found by the cycle 38 refutation pass, not by the suite
# ---------------------------------------------------------------------------


def test_the_slowest_poll_interval_is_the_one_armwatch_actually_uses() -> None:
    """The ops layer must not carry its own COPY of a lanternlight number.

    ``SLOWEST_POLL_INTERVAL_S`` here and ``LOG_POLL_S`` there are the same
    fact, and this module's staleness threshold is derived from it. They were
    shipped as two independently re-typed literals, each asserted against a
    literal - so raising the log cadence in ``lanternlight/armwatch.py`` would
    leave this module confidently reporting ``STALE`` against a number the
    watcher stopped using, and nothing would go red.

    This repo has a name for that shape: a filed count is a hypothesis. So is
    a filed interval. Couple them here rather than trusting two comments to be
    edited together.
    """
    from lanternlight import armwatch as armwatch_mod

    assert watch_mod.SLOWEST_POLL_INTERVAL_S == armwatch_mod.LOG_POLL_S


def test_the_staleness_threshold_clears_the_watchers_own_worst_case() -> None:
    """A threshold below the watcher's worst honest delay is a false alarm generator.

    The slowest surface polls every ``LOG_POLL_S``, and the heartbeat flush is
    throttled by a further ``HEARTBEAT_FLUSH_INTERVAL_S``, so a perfectly
    healthy watcher can leave the ``written`` stamp untouched for the sum of
    the two. The threshold has to sit above that sum or ``STALE`` stops meaning
    anything.
    """
    from lanternlight import armwatch as armwatch_mod

    worst_honest_delay = armwatch_mod.LOG_POLL_S + armwatch_mod.HEARTBEAT_FLUSH_INTERVAL_S
    assert worst_honest_delay < watch_mod.HEARTBEAT_STALE_AFTER_S, (
        f"threshold {watch_mod.HEARTBEAT_STALE_AFTER_S} s does not clear the "
        f"{worst_honest_delay} s a healthy watcher can legitimately take"
    )


def test_ensure_armed_still_takes_the_keyword_the_impostor_rearm_depends_on() -> None:
    """``disqualified_pid`` is load-bearing and was named nowhere in the tests.

    The IMPOSTOR re-arm works only because ``ensure_armed`` can be told to
    disregard one live pid - without it, its own refusal would protect the
    impostor and the re-arm would silently never fire. The behaviour was
    tested; the NAME was not, so renaming the parameter would have left a
    green suite and a broken wrap.
    """
    import inspect

    params = inspect.signature(watch_mod.ensure_armed).parameters
    assert "disqualified_pid" in params
    assert params["disqualified_pid"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["disqualified_pid"].default is None
