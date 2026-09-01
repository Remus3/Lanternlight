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
from datetime import UTC, datetime
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
        "OpenProcess",
        "system",
    }
    assert not (names & forbidden), f"watch must not call {sorted(names & forbidden)}"

    # Anchors, so the assertion above is about a module that really does start
    # processes and really does ask about liveness - a module that did neither
    # would pass the negative check vacuously.
    assert "Popen" in names, "expected the detached spawn to be present"
    assert "pid_is_alive" in names, "expected liveness to be delegated to the guard's probe"


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
