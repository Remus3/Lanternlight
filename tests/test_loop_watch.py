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
import importlib
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

#: The roster of modules that can hold a handle to another process lives in
#: ``tests/test_process_capability.py`` and is IMPORTED, never restated here.
#: ``ops/lanes.py`` and the lane contracts were bitten by a second copy of one
#: roster; a second copy of THIS one would let a module added to the capability
#: allowlist escape the access-mask check below, which is the hole ``OPS-20``
#: was opened to close. pytest already prepends this directory to ``sys.path``,
#: but the insert is explicit so the import does not depend on that - the same
#: sibling-import shape ``tests/test_ascii_hygiene.py`` uses for ``_tracked``.
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from test_process_capability import SCOPE  # noqa: E402  (sits beside this file in tests/)


@pytest.fixture
def record_file(tmp_path: Path) -> Path:
    """A watcher-record path inside tmp_path. The file does not exist yet."""
    return tmp_path / "armwatch.json"


#: Every reaped child whose pid this module has handed out, kept REFERENCED on
#: purpose. Dropping one of these returns its pid to the OS allocator, which is
#: the whole of ``OPS-17``, so the list is appended to and never cleared. The
#: price is one exited process object and one handle per call for the length of
#: the run - eight or so, all of them already dead.
_PINNED_DEAD_PROCESSES: list[subprocess.Popen] = []


def _dead_pid() -> int:
    """Return a pid that is dead AND cannot be reissued while this run lasts.

    Spawning and reaping a real process still beats picking a large number and
    hoping - that reasoning is unchanged and is why this helper exists: a
    guessed pid can be reused, and a test would then flake in the one direction
    that matters, a live watcher declared stale and doubled. ``OPS-17`` is a
    NARROWING of it, not a reversal. What was wrong was everything after the
    spawn:

        with subprocess.Popen([sys.executable, "-c", ""]) as proc:
            proc.wait(timeout=60)
            return proc.pid

    That reaps the child and then lets the last reference to ``proc`` die at
    the ``return``, and on Windows that is the moment the pid becomes eligible
    for reuse - so the helper reopened the hole its own docstring warned about.
    Not theory: pid 16264 went OPENABLE between being reaped and being probed
    and reddened the creation-time test below during an unrelated run. Whether
    the number had been reissued, or the old process object was merely
    lingering under a handle somebody else still held, is NOT recorded - the
    assertion was ``is None`` and kept no creation time to tell them apart. A
    refutation pass measured 7 lingers and 0 reuses in 300 trials on this
    machine 2026-09-04, so linger is the likelier of the two. The pin closes
    both.

    THE MECHANISM ``OPS-17`` FILED IS WRONG IN ITS DETAIL, measured here
    2026-09-04, and it matters because a fix aimed at it would have changed
    nothing. The item says the ``with`` block closes the process handle on
    exit. It does not. With the block exited and the name still bound,
    :func:`ops.loop.watch.process_creation_time` still answered with a real
    datetime; dropping the last reference is what turned it to ``None``. The
    REFCOUNT alone does it - 60 of 60 with no collection anywhere in the loop -
    so a fix reasoning about the garbage collector would miss too.
    ``Popen.__exit__`` closes the standard streams and waits - it never touches
    the handle. What frees the pid is the REFCOUNT reaching zero, so dropping
    the ``with`` on its own would have fixed nothing at all.

    So the pin is a REFERENCE rather than a context manager: the ``Popen`` goes
    into :data:`_PINNED_DEAD_PROCESSES` before anything can drop it and stays
    there. On Windows a pid cannot be reissued while a process object still
    exists under it, and that object outlives the process itself for exactly as
    long as one handle to it stays open.

    The two properties pull against each other, and holding both at once is the
    point. The obvious way to keep a process object alive - never reaping the
    child - would make the pid read as ALIVE and break all four callers. A
    reaped child with an open handle is the one state that is both: gone, and
    not reissuable. (``python -c ""`` exits ``0``, which is what makes the
    reaped half readable. That USED to matter for a second reason: the guard
    called a process alive when ``GetExitCodeProcess`` reported
    ``STILL_ACTIVE``, ``259``, so a child that chose 259 as its exit code read
    as alive for as long as anything held its process object open - which a
    pinned child does. ``OPS-18`` removed that trap: the guard now reads the
    exit TIME, so any exit code is safe here. The exit-0 child is kept because
    it is the cheapest thing to spawn, not because it is load-bearing.)

    THE PIN IS A WINDOWS PROPERTY AND DOES NOT EXIST ON POSIX, written down
    rather than implied. There ``wait()`` reaps the zombie and frees the pid
    outright, and the only way to keep the number reserved - leaving the child
    unreaped - makes ``os.kill(pid, 0)`` succeed, so the pid would read as
    alive and every caller would break. The helper degrades to the old
    behaviour there, and the mechanism test below skips rather than pretending
    otherwise.
    """
    proc = subprocess.Popen([sys.executable, "-c", ""])
    # Pinned BEFORE the reap and before any return path, so no exception can
    # leave the only reference sitting on a frame that is about to unwind.
    _PINNED_DEAD_PROCESSES.append(proc)
    proc.wait(timeout=60)
    return proc.pid


#: A pid the allocator can never issue, for the one place that needs the
#: creation-time probe's cannot-tell branch rather than a dead process.
#:
#: This IS a guessed pid, and :func:`_dead_pid` exists because guesses are
#: wrong, so the exemption is argued rather than assumed. The guess that helper
#: refuses to make is "this number is free right now", which is a claim about
#: an instant and expires immediately. The claim here is a different kind: NT
#: allocates client ids out of a table with four-byte granularity, so every pid
#: is a multiple of four and a number that is not has never named a process and
#: never will. Measured on this machine 2026-09-04 - ``EnumProcesses`` reported
#: 296 live pids, every one a multiple of four, the largest 31,604. The premise
#: is ASSERTED at the point of use, so a machine that breaks it reddens a test
#: instead of flaking one.
UNALLOCATABLE_PID = 999_999


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
# the _dead_pid helper itself - ROADMAP OPS-17
# ---------------------------------------------------------------------------


#: How far the reported creation time may sit EARLIER than the wall clock read
#: just before the spawn. Measured over 30 spawns on this machine 2026-09-04:
#: the reported time led that reading by 236 to 380 MICROseconds every time, so
#: a second is three orders of magnitude of headroom for a machine whose
#: creation FILETIME comes off a coarser clock than :func:`datetime.now`. It
#: costs nothing, because the bound that rules out a reissued pid is the LATE
#: one - see the test below.
_CREATION_CLOCK_SLACK = timedelta(seconds=1)


@pytest.mark.skipif(
    sys.platform != "win32",
    reason=(
        "the pin is a Windows guarantee and only Windows can be asked about it: "
        "POSIX frees a pid the instant the zombie is reaped, and the one way to keep "
        "the number reserved there would make it read as alive"
    ),
)
def test_the_dead_pid_helper_hands_back_a_pid_that_is_dead_and_cannot_be_reissued() -> None:
    """Both halves of :func:`_dead_pid`, asserted at the moment it returns.

    ``OPS-17`` says the honest acceptance here is a test on the MECHANISM
    rather than on the symptom, because the symptom is a race nobody can
    schedule. So this asserts the invariant directly: the pid is reaped
    (``pid_is_alive`` is False, which is what the four callers below need) AND
    the OS still holds a process object under it (a creation time comes back,
    which on Windows is exactly the condition that stops the allocator handing
    the number out again).

    THE INSTRUMENT IS THE MODULE UNDER TEST, deliberately rather than
    carelessly. ``process_creation_time`` is the probe the reuse actually
    reddened, so it is the right thing to ask, and a broken probe cannot hide
    here in either direction: one that always answered ``None`` fails this
    test, and one that always answered a datetime fails
    :func:`test_process_creation_time_is_none_rather_than_a_guess_when_it_cannot_tell`
    on the sentinel. Its ability to say ``None`` is checked on the last line
    rather than assumed, so neither assertion rests on the other's good faith.

    Two pids, because pinning only the most recent one would satisfy a
    single-pid check while letting every earlier pid escape.

    NO MIRROR TEST IS WRITTEN, and the omission is the point rather than an
    oversight. The natural mirror - hand back an UNPINNED pid and assert it
    reads as ``None`` - is precisely the race ``OPS-17`` opened for, so it
    would be a flake shipped as a guard. That direction was watched by hand
    instead: dropping the pin turns the assertions below red.
    """
    assert watch_mod.process_creation_time(os.getpid()) is not None, (
        "no creation-time probe on this Windows machine, so nothing below proves anything"
    )

    before = datetime.now(UTC)
    first = _dead_pid()
    second = _dead_pid()
    after = datetime.now(UTC)

    assert first != second
    assert guard_mod.pid_is_alive(first) is False
    assert guard_mod.pid_is_alive(second) is False

    for label, pid in (("first", first), ("second", second)):
        created = watch_mod.process_creation_time(pid)
        assert created is not None, (
            f"the {label} pid was released back to the allocator and can be reissued"
        )
        # And it is still OUR process rather than a reissue. This is the bound
        # that does the work: a process that took the number over would have
        # had to start after the window closed.
        assert created <= after, f"the {label} pid names a process created after the spawn"
        assert created >= before - _CREATION_CLOCK_SLACK, (
            f"the {label} pid names a process that started before the spawn"
        )

    # The instrument can say None, or every assertion above is decoration.
    assert watch_mod.process_creation_time(UNALLOCATABLE_PID) is None


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

    ``OPS-14``, the disk-pressure question, is open, so the refusal is a
    disk-budget property and not just tidiness. The capture tree's size is
    deliberately not recited here - it has gone stale twice, and the dated
    measurements live in the item.
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

    THIS IS A DENYLIST OF CALL NAMES, and that shape has a hard ceiling: it
    can only refuse a spelling someone thought to add to ``forbidden`` below.
    ``OPS-16`` catalogued three real spellings that predate this test and
    still walk straight through it, none of them hypothetical:

    - **A string, not a name.** ``subprocess.run(["taskkill", "/F", "/PID",
      pid])``, and the same through ``Popen``. ``taskkill`` is banned as a
      call NAME, so the identical word as a STRING inside an argument list
      sails past - and ``Popen`` cannot simply join ``forbidden``, because
      the module's own detached spawn needs it and the anchor below requires
      it to be present.
    - **An assembled name.** ``getattr(kernel32, "Open" + "Process")``, and
      any other dynamically built attribute access, defeats a name-based AST
      check BY CONSTRUCTION - there is no literal name in the source for
      ``ast.walk`` to collect.
    - **An unlisted entry point.** ``ntdll.NtSuspendProcess`` and the other
      undocumented NT calls were never added to ``forbidden`` in the first
      place; a denylist only stops what someone remembered to name.

    All three predate the cycle-38 change; the refutation that opened
    ``OPS-16`` replayed both the old and the new guard logic over HEAD's
    module to confirm it. ``tests/test_process_capability.py`` is what closes
    them - a capability ALLOWLIST over what ``ops/loop/watch.py`` and
    ``ops/loop/guard.py`` may import and call, rather than a list of what
    they may not. Read the two tests together; this one alone is not the
    whole guard.
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
    start?" - and it is the only right ``ops/loop/watch.py`` asks for.

    THIS TEST READS ``ops/loop/watch.py`` AND NOTHING ELSE, and until ``OPS-20``
    it was the only mask check in the repo while
    ``tests/test_process_capability.py`` told the reader the right was "checked
    separately" here - for both of the modules in its :data:`SCOPE`. It was not:
    ``ops/loop/guard.py``'s mask was tested by nothing, and planting
    ``_PROCESS_QUERY_LIMITED_INFORMATION | 0x0001`` in it changed zero test
    outcomes. It is kept, unweakened, for two reasons beyond history: it is
    ``watch.py``'s own per-file non-vacuity anchor - the ``assert opens`` below
    reddens if this module's probe is deleted, which the roster-wide check
    deliberately does not do - and losing a check while replacing it is the
    cycle-38 failure this repo has already paid for once. The roster-wide check
    is :func:`test_no_in_scope_module_asks_for_a_wider_process_right`.
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


# ---------------------------------------------------------------------------
# ROADMAP ``OPS-20`` - the same mask check, over the WHOLE roster.
#
# Everything above this line reads ``ops/loop/watch.py``. ``ops/loop/guard.py``
# opens a process handle too, and its mask was checked by nothing at all while
# ``tests/test_process_capability.py``'s docstring said otherwise. That is the
# ``OPS-16`` failure mode - a mis-stated coverage is worse than a declared
# hole, because a later session RELIES on it, and it nearly landed: the
# rejected ``OPS-18`` design widened ``guard.py``'s mask with ``SYNCHRONIZE``
# and no test would have noticed.
#
# So the check below is parametrized over :data:`SCOPE`, imported from the file
# that owns that roster. A third module added there cannot escape this.
# ---------------------------------------------------------------------------

#: Access rights that grant a power to AFFECT a process rather than to ask
#: about it. Inherited verbatim from the watch-only check above, and it is a
#: DENYLIST with a denylist's ceiling - it only refuses a spelling someone
#: named. The structural check is the load-bearing half; this one catches the
#: named constant arriving as text before it is ever wired to a call.
_RIGHTS_TO_AFFECT = ("PROCESS_TERMINATE", "PROCESS_VM_WRITE", "PROCESS_SUSPEND_RESUME")

#: The one right an in-scope module may ask for, by name and by value.
_QUERY_LIMITED_NAME = "_PROCESS_QUERY_LIMITED_INFORMATION"
_QUERY_LIMITED_VALUE = 0x1000


def _assigned_values(tree: ast.AST, name: str) -> list[ast.expr]:
    """Every value bound to ``name`` anywhere in ``tree``, at any nesting depth.

    Module level is not special-cased on purpose. A FUNCTION-LOCAL
    ``_PROCESS_QUERY_LIMITED_INFORMATION = 0x1F0FFF`` shadows the module
    constant at the call site while the module attribute still reads 0x1000, so
    a runtime check on the module alone would wave it through and the call site
    would still spell the legal name.
    """
    values: list[ast.expr] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign | ast.AugAssign):
            targets = [node.target]
        else:
            continue
        if node.value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                values.append(node.value)
    return values


def _wider_right_problems(relative: str, source: str, resolved: object) -> list[str]:
    """Every way ``source`` asks for a process right wider than query-only.

    Pure over its inputs, so the logic that judges the shipped modules can be
    replayed over synthetic source without touching a production file. That is
    not a convenience: proving this check reddens by editing ``ops/loop/guard.py``
    means editing a production file to test a test.

    ``resolved`` is what the module's own :data:`_QUERY_LIMITED_NAME` evaluates
    to at import time, or ``None`` when the module defines no such name. Three
    independent halves, because each covers the others' blind spot:

    1. STRUCTURAL - every ``OpenProcess`` call must pass the constant BY NAME.
       An integer literal, a bitwise OR that folds a wider right in, or a
       keyword-only call all fail. This is what catches
       ``_PROCESS_QUERY_LIMITED_INFORMATION | 0x0001``.
    2. VALUE - a call site can spell the legal name while the name means
       something else. So the resolved value must be 0x1000, and every
       assignment of that name in the source must be the literal 0x1000.
    3. TEXT - the named rights to affect must not appear at all.

    AN IN-SCOPE MODULE WITH NO ``OpenProcess`` IS CLEAN HERE, NOT RED. There is
    no right to be wrong about, so a probe-less module returns an empty list;
    a per-file "it must open something" anchor would turn every future
    in-scope module into a false alarm. Non-vacuity is anchored once across the
    roster by :func:`test_at_least_one_in_scope_module_opens_a_process_handle`,
    and per file for ``watch.py`` by the ``assert opens`` above.
    """
    problems: list[str] = []
    tree = ast.parse(source)

    opens = _open_process_calls(tree)
    for node in opens:
        if not _asks_only_for_query_limited_information(node):
            problems.append(f"{relative}:{node.lineno}: wider right: {ast.dump(node)}")

    if opens and resolved != _QUERY_LIMITED_VALUE:
        problems.append(f"{relative}: {_QUERY_LIMITED_NAME} resolves to {resolved!r}, not 0x1000")

    for value in _assigned_values(tree, _QUERY_LIMITED_NAME):
        if not (isinstance(value, ast.Constant) and value.value == _QUERY_LIMITED_VALUE):
            problems.append(f"{relative}:{value.lineno}: {_QUERY_LIMITED_NAME} is not 0x1000")

    for banned in _RIGHTS_TO_AFFECT:
        if banned in source:
            problems.append(f"{relative}: names {banned}, a right to affect rather than to ask")

    return problems


def _in_scope_module(relative: str):
    """Import the module a :data:`SCOPE` path names, and prove the mapping.

    The path-to-module translation is ASSERTED rather than assumed. Without
    that assertion this check could read one file while reporting on another -
    the same shape of lie as the docstring ``OPS-20`` was opened to correct.
    """
    module = importlib.import_module(relative.removesuffix(".py").replace("/", "."))
    imported = Path(module.__file__).resolve()
    expected = (REPO_ROOT / relative).resolve()
    assert imported == expected, f"{relative} imports to {imported}, not {expected}"
    return module


def _in_scope_source(relative: str) -> str:
    """Read an in-scope module's source from the file its module object names."""
    return Path(_in_scope_module(relative).__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", SCOPE)
def test_no_in_scope_module_asks_for_a_wider_process_right(relative: str) -> None:
    """No module that can hold a process handle asks for a right to affect one.

    ``PROCESS_TERMINATE`` (0x0001) is the right THE HARD BOUNDARY exists to
    keep out of this repo, so it is the mutation this check was watched going
    red against - not a harmless bit. See ADR-001.
    """
    module = _in_scope_module(relative)
    source = Path(module.__file__).read_text(encoding="utf-8")
    resolved = getattr(module, _QUERY_LIMITED_NAME, None)

    problems = _wider_right_problems(relative, source, resolved)
    assert problems == [], "\n".join(problems)


def test_at_least_one_in_scope_module_opens_a_process_handle() -> None:
    """The roster-wide clean bill is a verdict, not an empty walk.

    :func:`_wider_right_problems` is vacuously clean on a module with no
    ``OpenProcess``, which is right per file and would be wrong for the whole
    roster: if no in-scope module opened a handle at all, every parametrized
    case above would pass while judging nothing.

    Per-file presence is pinned separately and for BOTH files by
    ``tests/test_process_capability.py::test_the_scanner_actually_saw_the_module``,
    which asserts ``OpenProcess`` is among each module's observed capabilities.
    Stated here rather than relied on silently: that test is parametrized over
    the same :data:`SCOPE`, so it - not this one - is what would redden if a
    probe-less module joined the roster.
    """
    counts = {
        relative: len(_open_process_calls(ast.parse(_in_scope_source(relative))))
        for relative in SCOPE
    }
    assert sum(counts.values()) > 0, f"nothing to judge across SCOPE: {counts}"


# ---------------------------------------------------------------------------
# The guard for the roster-wide guard, over synthetic source. The shipped
# modules are clean, so the parametrized test above can only ever prove the
# CURRENT text passes - it says nothing about what the check would do with a
# badly behaved module. A negative check that has never been shown a positive
# is decoration.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spelling", WIDER_RIGHT_SPELLINGS)
def test_the_roster_wide_check_rejects_every_wider_spelling(spelling: str) -> None:
    """The same five spellings the watch-only guard is shown, through the roster check.

    Replayed over the SAME corpus deliberately. Cycle 38 shipped a replacement
    collector that silently caught LESS than the one it replaced, and the only
    way to know a generalisation did not lose a case is to hand both the same
    input. None of these five names a banned right as text - four spell a
    number or an unrelated constant - so a pass here is the STRUCTURAL half
    firing, not the substring denylist.
    """
    source = f"{_QUERY_LIMITED_NAME} = 0x1000\n\n\ndef probe(pid):\n    {spelling}\n"
    assert _wider_right_problems("synthetic/wide.py", source, _QUERY_LIMITED_VALUE)


def test_the_roster_wide_check_still_accepts_the_legitimate_probe() -> None:
    """The mirror - a check that rejects everything is not a check.

    Without this, every assertion above would still pass if
    :func:`_wider_right_problems` were replaced by ``return ["x"]``.
    """
    source = (
        f"{_QUERY_LIMITED_NAME} = 0x1000\n\n\ndef probe(pid):\n"
        f"    kernel32.OpenProcess({_QUERY_LIMITED_NAME}, False, pid)\n"
    )
    assert _wider_right_problems("synthetic/legit.py", source, _QUERY_LIMITED_VALUE) == []


def test_a_rebound_constant_is_caught_even_though_the_call_site_reads_clean() -> None:
    """The call site spells the legal name; the name has been widened underneath it.

    The structural half passes this source. Only the value half fails it, so
    this is the case that proves the two halves are not one check written
    twice.
    """
    source = (
        f"{_QUERY_LIMITED_NAME} = 0x1000 | 0x0001\n\n\ndef probe(pid):\n"
        f"    kernel32.OpenProcess({_QUERY_LIMITED_NAME}, False, pid)\n"
    )
    calls = _open_process_calls(ast.parse(source))
    assert _asks_only_for_query_limited_information(calls[0]), "the call site must read clean"
    assert _wider_right_problems("synthetic/rebound.py", source, 0x1001)


def test_a_locally_shadowed_constant_is_caught_though_the_module_still_reads_0x1000() -> None:
    """A function-local rebinding, with the module attribute left honest.

    ``resolved`` is handed 0x1000 here on purpose - that is what
    ``getattr(module, ...)`` would return for this source - so the value half's
    runtime arm passes and only the ASSIGNMENT arm can fail it.
    """
    source = (
        f"{_QUERY_LIMITED_NAME} = 0x1000\n\n\ndef probe(pid):\n"
        f"    {_QUERY_LIMITED_NAME} = 0x1F0FFF\n"
        f"    kernel32.OpenProcess({_QUERY_LIMITED_NAME}, False, pid)\n"
    )
    assert _wider_right_problems("synthetic/shadow.py", source, _QUERY_LIMITED_VALUE)


def test_an_in_scope_module_with_no_process_handle_is_clean_rather_than_red() -> None:
    """A module in :data:`SCOPE` that opens nothing has no right to get wrong.

    Asserted rather than left as a property of the code, because the obvious
    generalisation of the watch-only check - lifting its ``assert opens``
    anchor into the loop - would redden on this input and turn a harmless new
    roster member into a false alarm. A check that cries wolf gets deleted.
    """
    source = (
        '"""An in-scope module that never opens a process handle."""\n\n'
        "import json\n\n\ndef load(path):\n    return json.loads(path.read_text())\n"
    )
    assert _wider_right_problems("synthetic/quiet.py", source, None) == []


def test_liveness_is_delegated_to_the_guard_rather_than_reimplemented() -> None:
    """``os.kill(pid, 0)`` maps onto ``TerminateProcess`` on Windows CPython.

    The guard already solved that with ``OpenProcess`` plus the exit time out
    of ``GetProcessTimes`` - it read ``GetExitCodeProcess`` until ``OPS-18``.
    Re-deriving a probe here is how the trap gets walked into twice.

    Also structural, and it shares the denylist shape above: the scan below
    forbids exactly the call NAME ``kill``, so ``getattr(os, "kill")(pid, 0)``
    or a rebound alias (``f = os.kill; f(pid, 0)``) reaches this module as
    unseen as the three ``OPS-16`` spellings reach the wider ban. The real
    work is the assertion on the last line - it proves
    ``watch_mod.guard.pid_is_alive`` really IS the guard's own function, not
    a look-alike - but identity is not a call-graph proof: nothing here shows
    this module actually CALLS it anywhere, only that the name resolves
    correctly if it is used. A private probe rebuilt from the same
    ``OpenProcess``/``GetProcessTimes`` pair the guard already uses, kept
    local and never named ``kill``, satisfies every assertion below - and
    ``tests/test_process_capability.py`` does not close this one either,
    since it permits this module the same ``OpenProcess`` right the guard
    itself holds.
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
    intervals: dict | None = None,
) -> Path:
    """Write a heartbeat in the shape pinned with the armwatch slice.

    Fixed size, rewritten in place, four surfaces keyed by name. Written here
    by hand rather than by calling the watcher, so this file does not depend on
    a module another agent owns.

    ``intervals`` is item ``4f``'s self-describing key and is OMITTED unless a
    test asks for it, so every call written before ``4f`` still produces the
    exact cycle-38 payload - which is the shape the fallback path has to keep
    working against.
    """
    stamps = dict.fromkeys(("savegames", "standalonelevel", "savedroot", "logs"), written)
    payload = {
        "pid": pid,
        "written": written,
        "passes": passes,
        "surfaces": stamps if surfaces is None else surfaces,
    }
    if intervals is not None:
        payload["intervals"] = intervals
    target = tmp_path / watch_mod.HEARTBEAT_FILENAME
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target


def _all_surfaces_at(when: datetime) -> dict:
    """The four surface names, every one stamped ``when``.

    A named helper rather than an inline dict comprehension because item ``4f``
    turns this map into the thing under test, and a test that has to be read
    twice to see which surface is frozen is a test nobody will trust.
    """
    return dict.fromkeys(SURFACE_NAMES, watch_mod._stamp(when))


def _fixed_creation(when: datetime):
    """A ``creation_time_fn`` that answers ``when`` for any pid."""

    def creation_time_fn(pid: int):
        return when

    return creation_time_fn


NOW = datetime(2026, 9, 3, 5, 0, 0, tzinfo=UTC)
ARMED_AT = "2026-09-02T01:26:36+00:00"

#: The four surfaces the watcher polls, in the order ``session_plan`` builds
#: them. Named here so a test can freeze ONE of them by name; the INTERVALS are
#: never re-typed in this file - they are read from the plan or declared in the
#: heartbeat under test.
SURFACE_NAMES = ("savegames", "standalonelevel", "savedroot", "logs")

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

    THE LAST ASSERTION IS THE ONLY ONE THAT REACHES CTYPES - the four above it
    are turned away by the guard clause before any handle is opened - so it is
    the one that pins ``OpenProcess`` failing, and ``OPS-17`` is about how it
    used to be spelled. It said ``_dead_pid()``, and a reaped pid is a FREE
    pid, which is the exact state the allocator reissues from: pid 16264 went
    openable under this assertion during an unrelated run and reddened it.

    ``_dead_pid`` now PINS its pid against reuse, and that makes the pid
    permanently openable - which would fail this assertion deterministically
    rather than occasionally. The two needs cannot be served by one pid, and
    the reason is not a limitation of this file: on Windows the same single
    condition, a process object still referenced, is what both reserves the
    number and keeps ``OpenProcess`` succeeding. "Cannot be reissued" and
    "cannot be opened" are the two faces of it. So this test stops asking for a
    dead process and asks instead for a number that was never a process at all.
    See :data:`UNALLOCATABLE_PID` for why that guess is admissible here and
    nowhere else.
    """
    assert watch_mod.process_creation_time(None) is None
    assert watch_mod.process_creation_time(0) is None
    assert watch_mod.process_creation_time(-1) is None
    assert watch_mod.process_creation_time(True) is None

    # The sentinel's premise, checked rather than trusted. If a Windows ever
    # hands out a pid that is not a multiple of four, this reddens here and
    # names the reason instead of flaking on the line below.
    assert UNALLOCATABLE_PID % 4 != 0
    if sys.platform == "win32":
        assert os.getpid() % 4 == 0, "this pid is not a multiple of four"
        assert _dead_pid() % 4 == 0, "a spawned pid is not a multiple of four"

    assert watch_mod.process_creation_time(UNALLOCATABLE_PID) is None


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
    """The COMBINED boundary is inclusive, so exactly-at-threshold is not stale.

    The ``surfaces`` map is stated explicitly here, and item ``4f`` is why. It
    used to inherit ``written``, which meant this test also, silently, asserted
    that four surfaces frozen for 900 s read as ARMED - the exact blindness
    ``4f`` exists to remove. Pinning the surfaces fresh leaves this test saying
    only what its name says: that the COMBINED threshold's boundary is
    inclusive. The per-surface boundary is pinned separately below.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    written = NOW - timedelta(seconds=watch_mod.HEARTBEAT_STALE_AFTER_S - inside_by_s)
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(written),
        surfaces=_all_surfaces_at(NOW - timedelta(seconds=4)),
    )

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
    """The state pid 23628 was in when this test was written.

    It had been armed before the heartbeat existed and it passed the identity
    check. Re-arming it would spawn the second poller ``ensure_armed`` refuses.

    That pid died at the next wrap and was re-armed (``LL-0124``), so this is a
    worked example rather than a claim about the machine - which is the point:
    any watcher armed before the heartbeat shipped lands here, and one still
    could after a rollback.
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
    assert watch_mod.STATE_SURFACE_STALE not in watch_mod.REARM_STATES
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


# ---------------------------------------------------------------------------
# ROADMAP 4f - one wedged surface out of four
#
# check_watcher used to decide STALE from the combined ``written`` stamp alone,
# so the two 3 s surfaces kept it fresh while the 300 s ``logs`` surface - the
# one guarding the 5,080,313-byte log that 4d exists to protect - could be
# wedged for an hour and still read ARMED. Nothing below re-types a poll
# interval: the numbers come from the heartbeat under test or from the
# watcher's own plan.
# ---------------------------------------------------------------------------


def _declared_intervals() -> dict:
    """The four intervals as the watcher itself reports them.

    Read from ``session_plan`` rather than written out, so a cadence change in
    ``lanternlight/armwatch.py`` moves these tests with it instead of leaving
    them asserting against a number the watcher stopped using. That is the
    defect ``test_the_slowest_poll_interval_is_the_one_armwatch_actually_uses``
    was written for, and re-typing four of them here would reintroduce it four
    times.
    """
    from lanternlight.armwatch import session_plan

    plans = session_plan(saved_dir=Path("plan-placeholder"), dest_root=Path("plan-placeholder"))
    return {plan.name: plan.poll_seconds for plan in plans}


def _threshold_for(name: str) -> float:
    """That surface's own staleness threshold, derived, never typed."""
    from lanternlight.armwatch import HEARTBEAT_FLUSH_INTERVAL_S

    return watch_mod.surface_stale_after_s(_declared_intervals()[name], HEARTBEAT_FLUSH_INTERVAL_S)


def _wedged_logs_status(
    tmp_path: Path,
    record_file: Path,
    *,
    intervals: dict | None,
) -> watch_mod.WatcherStatus:
    """One surface frozen, the other three and the combined stamp fresh."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = NOW - timedelta(seconds=4)
    surfaces = _all_surfaces_at(fresh)
    surfaces["logs"] = watch_mod._stamp(NOW - timedelta(seconds=3600))
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(fresh),
        surfaces=surfaces,
        intervals=intervals,
    )
    return watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )


def _writer_shaped_beat(
    tmp_path: Path,
    *,
    recorded: tuple[str, ...],
    when: datetime,
    written: datetime | None = None,
) -> Path:
    """A heartbeat in the only shape the real writer can produce.

    ``surfaces`` and ``intervals`` are keyed IDENTICALLY, because
    ``lanternlight.armwatch.Heartbeat.record`` sets both in one call per
    completed pass. A surface that has NEVER completed a pass is therefore
    absent from BOTH maps - and that, not "absent from surfaces while intervals
    still names it", is what a dead thread looks like on disk.

    The three grace-window tests below used to hand ``intervals`` all four names
    while deleting one from ``surfaces``. Nothing can write that payload, so
    they were green against a shape that does not exist while the rule they
    were guarding could not run at all. ``_writer_shaped_beat`` exists so a test
    cannot make that mistake silently, and
    ``test_the_writer_cannot_declare_an_interval_for_a_surface_it_never_stamped``
    measures the claim rather than asserting it here.
    """
    declared = _declared_intervals()
    stamped = watch_mod._stamp(when)
    return _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(when if written is None else written),
        surfaces=dict.fromkeys(recorded, stamped),
        intervals={name: declared[name] for name in recorded},
    )


def test_the_writer_cannot_declare_an_interval_for_a_surface_it_never_stamped(
    tmp_path: Path,
) -> None:
    """The premise the missing-surface rule rests on, MEASURED not assumed.

    ``Heartbeat.record`` writes the stamp and the interval in the same call, so
    ``intervals`` is always a SUBSET of ``surfaces``. A rule that derives the
    surfaces it EXPECTS from those two maps therefore expects exactly the
    surfaces that already reported, and its missing-key branch is unreachable on
    every payload the writer can emit. That is why the expectation has to come
    from the PLAN: a heartbeat cannot be the authority on which surfaces should
    have reported, because the whole failure being watched for is a surface that
    wrote nothing.
    """
    from lanternlight.armwatch import Heartbeat

    target = tmp_path / "premise-heartbeat.json"
    beat = Heartbeat(target)
    declared = _declared_intervals()
    for name in ("savegames", "standalonelevel", "savedroot"):
        beat.record(name, declared[name])
    beat.flush()

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert set(payload["intervals"]) == set(payload["surfaces"]), payload
    assert "logs" not in payload["surfaces"], payload
    assert "logs" not in payload["intervals"], payload
    # Which is the whole point: the union of the two maps names three surfaces,
    # so a check deriving its expectations from them never asks after the fourth.
    assert set(payload["surfaces"]) | set(payload["intervals"]) == set(payload["surfaces"])


def test_one_wedged_surface_out_of_four_is_named_while_the_other_three_stay_fresh(
    tmp_path: Path, record_file: Path
) -> None:
    """The WATCHED-GOING-RED acceptance ROADMAP 4f names in terms.

    ``logs`` has not completed a pass in an hour. The other three surfaces AND
    the combined ``written`` stamp are four seconds old, so every ``4e`` check
    passes and the old code said ARMED. The whole point of the item is that
    this must fail, and that it must say WHICH surface.
    """
    status = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())

    assert status.state == watch_mod.STATE_SURFACE_STALE, status.reason
    assert status.stale_surfaces == ("logs",), status.evidence
    # Named in the sentence an operator reads, not only in a machine field.
    assert "logs" in status.reason
    assert f"{_threshold_for('logs'):.0f} s" in status.reason
    # And named in the evidence, which is where the grounds live.
    assert any("logs STALE" in item for item in status.evidence), status.evidence
    # The three healthy ones are not accused of anything.
    for name in ("savegames", "standalonelevel", "savedroot"):
        assert name not in status.stale_surfaces
    # Still armed, still nothing re-armed, still nothing stopped.
    assert status.armed is True
    assert status.state not in watch_mod.REARM_STATES
    assert status.heartbeat_age_s == pytest.approx(4.0)


def test_all_four_surfaces_frozen_is_a_different_sentence_from_one(
    tmp_path: Path, record_file: Path
) -> None:
    """"A test that freezes all four passes today and pins nothing" - 4f.

    So this one keeps the all-four case AND proves it is distinguishable from
    the one-surface case. They are different failures: all four points at the
    watcher, one points at a thread, and a verdict that renders them the same
    way loses the interesting one.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = NOW - timedelta(seconds=4)
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(fresh),
        surfaces=_all_surfaces_at(NOW - timedelta(seconds=3600)),
        intervals=_declared_intervals(),
    )

    every = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )
    one = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())

    assert every.state == watch_mod.STATE_SURFACE_STALE, every.reason
    assert every.stale_surfaces == tuple(sorted(SURFACE_NAMES))
    assert one.stale_surfaces == ("logs",)
    # The distinction has to survive into the prose, not just the tuple.
    assert every.reason != one.reason
    assert "ALL 4" in every.reason
    assert "ALL" not in one.reason
    assert "1 of its 4" in one.reason
    # Neither is STALE: the combined stamp is fresh in both, so the process is
    # flushing. Collapsing SURFACE_STALE into STALE would say the opposite.
    assert every.state != watch_mod.STATE_STALE
    assert every.armed is True and one.armed is True


@pytest.mark.parametrize(
    ("since_arming_s", "expected"),
    [
        (100.0, watch_mod.STATE_ARMED),
        (2000.0, watch_mod.STATE_SURFACE_STALE),
        (100000.0, watch_mod.STATE_SURFACE_STALE),
    ],
)
def test_a_logs_thread_that_never_recorded_is_caught_once_its_window_closes(
    tmp_path: Path, record_file: Path, since_arming_s: float, expected: str
) -> None:
    """The refutation's measurement, turned into the guard it was missing.

    ``logs`` never completes a pass, so it is absent from ``surfaces`` AND from
    ``intervals`` - the only shape the writer can produce for a thread that died
    before its first pass. The rule derived the surfaces it expected from the
    payload's own two maps, so ``set(present) | set(known) == set(present)`` and
    the missing-key branch was DEAD CODE: this payload was measured reading
    ARMED at 100 s, 2000 s and 100000 s past arming.

    100 s is inside the 960 s grace window and ARMED is the right answer there.
    The other two are the wolf that nobody was crying, and the reason has to
    name ``logs`` rather than leave an operator guessing between a 3 s save
    watcher and the 300 s surface guarding the 5,080,313-byte log.
    """
    started = NOW - timedelta(seconds=since_arming_s)
    watch_mod.write_record(
        _record(os.getpid(), tmp_path, started=watch_mod._stamp(started)), record_file
    )
    beat = _writer_shaped_beat(
        tmp_path,
        recorded=("savegames", "standalonelevel", "savedroot"),
        when=NOW - timedelta(seconds=2),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(started),
    )

    assert status.state == expected, status.reason
    # The expectation is sourced OUT LOUD, because a verdict about a surface
    # that left no trace has to say where the surface's name came from.
    assert any("expected surfaces" in item for item in status.evidence), status.evidence
    if expected == watch_mod.STATE_SURFACE_STALE:
        assert status.stale_surfaces == ("logs",), status.evidence
        assert "logs" in status.reason
        assert "NEVER recorded a completed pass" in status.reason
        assert "logs" not in status.unjudged_surfaces
        # The three that ARE reporting are the evidence that anything still is.
        assert status.fresh_surfaces == ("savedroot", "savegames", "standalonelevel")
        assert status.all_surfaces_stale is False
    else:
        assert status.stale_surfaces == ()
        assert any(
            "logs no completed pass yet" in item for item in status.evidence
        ), status.evidence


def test_a_missing_surface_key_inside_the_grace_window_reads_as_armed(
    tmp_path: Path, record_file: Path
) -> None:
    """The first heartbeat after arming carries fewer than four keys.

    A watcher ten seconds old has not completed a 300 s ``logs`` pass and
    cannot have. Reading that as stale would make every wrap in a watcher's
    first half-minute cry wolf, which the 4f acceptance forbids by name.

    The payload is the one the WRITER can emit - ``logs`` absent from both maps.
    It used to be handed an ``intervals`` map naming all four while ``surfaces``
    named three, which nothing can write, so this test passed against a shape
    that does not exist.
    """
    started = NOW - timedelta(seconds=10)
    watch_mod.write_record(
        _record(os.getpid(), tmp_path, started=watch_mod._stamp(started)), record_file
    )
    beat = _writer_shaped_beat(
        tmp_path,
        recorded=("savegames", "standalonelevel", "savedroot"),
        when=NOW - timedelta(seconds=2),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(started),
    )

    assert status.state == watch_mod.STATE_ARMED, status.reason
    assert status.stale_surfaces == ()
    # Innocent, but not silently: the evidence says a pass is still awaited
    # rather than pretending a stamp was seen.
    assert any("logs no completed pass yet" in item for item in status.evidence), status.evidence
    # And it is not filed as unmeasurable either - the window is being timed.
    assert "logs" not in status.unjudged_surfaces


def test_a_missing_surface_key_past_the_grace_window_is_named_as_never_recorded(
    tmp_path: Path, record_file: Path
) -> None:
    """The hole in the obvious version of the missing-key rule.

    A surface whose thread died BEFORE its first pass has a permanently missing
    key, so a rule that only ever forgives a missing key reads it as healthy
    for the life of the process. The grace window is timed from the record's
    ``started`` stamp, and past it the verdict is stale with a DISTINCT reason -
    "never recorded a pass" is a different fact from "stopped advancing", and
    an operator needs to be told which.

    The payload is writer-shaped: ``logs`` is absent from ``surfaces`` and from
    ``intervals`` alike, which is what a thread that died before its first pass
    really leaves behind.
    """
    grace = _threshold_for("logs")
    started = NOW - timedelta(seconds=grace + 600.0)
    watch_mod.write_record(
        _record(os.getpid(), tmp_path, started=watch_mod._stamp(started)), record_file
    )
    beat = _writer_shaped_beat(
        tmp_path,
        recorded=("savegames", "standalonelevel", "savedroot"),
        when=NOW - timedelta(seconds=2),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(started),
    )

    assert status.state == watch_mod.STATE_SURFACE_STALE, status.reason
    assert status.stale_surfaces == ("logs",)
    assert "NEVER recorded a completed pass" in status.reason
    assert "grace window" in status.reason
    # Distinct from the frozen-stamp reason, which is the point of having two.
    frozen = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())
    assert frozen.state == watch_mod.STATE_SURFACE_STALE
    assert "last completed a pass" in frozen.reason
    assert "NEVER recorded a completed pass" not in frozen.reason


def test_the_grace_window_boundary_is_inclusive_the_way_the_combined_one_is(
    tmp_path: Path, record_file: Path
) -> None:
    """Exactly-at-window is still innocent, and one second past it is not.

    ``started`` is stamped just BEFORE the child spawns, so ``now - started``
    overstates the watcher's age and the window closes about a second early -
    the crying-wolf direction. An inclusive boundary is the cheap half of not
    compounding that.
    """
    grace = _threshold_for("logs")
    for offset, expected in ((0.0, watch_mod.STATE_ARMED), (1.0, watch_mod.STATE_SURFACE_STALE)):
        started = NOW - timedelta(seconds=grace + offset)
        watch_mod.write_record(
            _record(os.getpid(), tmp_path, started=watch_mod._stamp(started)), record_file
        )
        beat = _writer_shaped_beat(
            tmp_path,
            recorded=("savegames", "standalonelevel", "savedroot"),
            when=NOW - timedelta(seconds=2),
        )
        status = watch_mod.check_watcher(
            path=record_file,
            heartbeat=beat,
            now=NOW,
            creation_time_fn=_fixed_creation(started),
        )
        assert status.state == expected, f"at {offset} s past the window: {status.reason}"


def test_a_heartbeat_with_no_intervals_key_is_still_judged_through_the_plan(
    tmp_path: Path, record_file: Path
) -> None:
    """A cycle-38 heartbeat carries ``surfaces`` and no ``intervals``.

    Those exist on disk right now, so the fallback is not a hypothetical. It
    reads ``lanternlight.armwatch.session_plan`` rather than re-typing four
    numbers here, and the verdict has to be the same one the self-describing
    payload gets.
    """
    fallback = _wedged_logs_status(tmp_path, record_file, intervals=None)
    declared = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())

    assert fallback.state == watch_mod.STATE_SURFACE_STALE, fallback.reason
    assert fallback.stale_surfaces == ("logs",)
    assert fallback.stale_surfaces == declared.stale_surfaces
    # The evidence says WHERE the intervals came from, because a verdict that
    # cannot say what it measured against is a status code with extra syllables.
    # Matched on the INTERVAL-source line specifically, not on the bare token
    # "session_plan": the expected-surface line names the plan too, and an
    # assertion that either line could satisfy would stop distinguishing the
    # fallback from the self-describing payload.
    assert any(
        "poll intervals read from lanternlight.armwatch.session_plan" in item
        for item in fallback.evidence
    ), fallback.evidence
    assert any("'intervals' map" in item for item in declared.evidence), declared.evidence


def test_a_surface_with_no_determinable_interval_is_unjudged_not_assumed(
    tmp_path: Path, record_file: Path
) -> None:
    """Unmeasured and measured-fresh are different facts.

    A surface the heartbeat names but declares no interval for cannot be given
    a threshold, so it gets no verdict. Assuming it fresh hides a wedge;
    assuming it stale cries wolf about a number nobody has. It is reported as
    UNJUDGED and it is reported OUT LOUD, in the reason an operator reads.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = NOW - timedelta(seconds=4)
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(fresh),
        surfaces={
            "logs": watch_mod._stamp(fresh),
            "mystery": watch_mod._stamp(NOW - timedelta(seconds=99999)),
        },
        intervals={"logs": _declared_intervals()["logs"]},
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_ARMED, status.reason
    assert status.unjudged_surfaces == ("mystery",)
    assert status.stale_surfaces == ()
    assert "mystery" in status.reason, status.reason
    assert any("mystery UNJUDGED" in item for item in status.evidence), status.evidence


def test_an_unreadable_surface_stamp_is_unjudged_rather_than_stale(
    tmp_path: Path, record_file: Path
) -> None:
    """Cannot-tell is the third answer here too, exactly as it is for identity."""
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = NOW - timedelta(seconds=4)
    surfaces = _all_surfaces_at(fresh)
    surfaces["logs"] = "not a timestamp"
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(fresh),
        surfaces=surfaces,
        intervals=_declared_intervals(),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_ARMED, status.reason
    assert status.unjudged_surfaces == ("logs",)
    assert status.stale_surfaces == ()


def test_a_heartbeat_with_no_surfaces_map_at_all_judges_nothing(
    tmp_path: Path, record_file: Path
) -> None:
    """A payload with no per-surface map is a cannot-tell, not a wedge.

    Reading it as SURFACE_STALE would be crying wolf about a FORMAT. The check
    says so in the evidence instead, which is the honest report.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = watch_mod._stamp(NOW - timedelta(seconds=4))
    beat = tmp_path / watch_mod.HEARTBEAT_FILENAME
    beat.write_text(
        json.dumps({"pid": os.getpid(), "written": fresh, "passes": 7}) + "\n",
        encoding="utf-8",
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_ARMED, status.reason
    assert status.stale_surfaces == ()
    assert any("no per-surface map" in item for item in status.evidence), status.evidence


def test_the_combined_stale_verdict_still_wins_over_the_per_surface_one(
    tmp_path: Path, record_file: Path
) -> None:
    """Order matters: nothing-is-flushing is decided before which-thread-died.

    When the whole file has stopped advancing, naming four stale surfaces would
    describe the symptom and bury the cause. STALE is the cause.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    frozen = NOW - timedelta(seconds=watch_mod.HEARTBEAT_STALE_AFTER_S + 60)
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(frozen),
        surfaces=_all_surfaces_at(frozen),
        intervals=_declared_intervals(),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_STALE, status.reason
    assert status.state != watch_mod.STATE_SURFACE_STALE


def test_a_whole_watcher_stall_is_not_reported_as_a_process_that_is_still_flushing(
    tmp_path: Path, record_file: Path
) -> None:
    """DEFECT 2: the SURFACE_STALE prose asserted a mechanism it had not checked.

    A real heartbeat has ``written >= every surface stamp``, because ``written``
    is set at flush time and the stamps at or before it. So the combined age is
    the age of the FRESHEST surface, and any combined age over the smallest
    surface threshold (69 s) puts those surfaces past their own thresholds while
    the combined age is still under the 900 s combined one. A whole-watcher
    stall of 70 to 900 seconds therefore landed in SURFACE_STALE, whose reason
    said the combined stamp was "still fresh, so the process IS alive and
    flushing" - false, because nothing had flushed for the length of the stall.

    The payload here is a genuine 800 s stall: the three fast surfaces stamped
    800 s ago, ``logs`` stamped one 300 s cycle before that, and ``written``
    equal to the freshest stamp. Every threshold is passed and the combined
    stamp is still inside its own.
    """
    stall_s = 800.0
    assert stall_s < watch_mod.HEARTBEAT_STALE_AFTER_S, "the stall must not read as STALE"
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    surfaces = _all_surfaces_at(NOW - timedelta(seconds=stall_s))
    surfaces["logs"] = watch_mod._stamp(
        NOW - timedelta(seconds=stall_s + _declared_intervals()["logs"])
    )
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(NOW - timedelta(seconds=stall_s)),
        surfaces=surfaces,
        intervals=_declared_intervals(),
    )

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )

    assert status.state == watch_mod.STATE_SURFACE_STALE, status.reason
    assert status.stale_surfaces == tuple(sorted(SURFACE_NAMES))
    # The explicit all-vs-some answer, and the evidence it is derived from.
    assert status.all_surfaces_stale is True
    assert status.fresh_surfaces == ()

    collapsed = " ".join(status.reason.split())
    # The falsehood, gone - and pinned POSITIVELY as well, because a negative
    # assertion rules something out without pinning anything down.
    assert "alive and flushing" not in collapsed, collapsed
    assert "NO judged surface is inside its own threshold" in collapsed, collapsed
    # The combined stamp is stated as the measurement it is, not as a mechanism.
    assert f"{stall_s:.0f} s ago" in collapsed, collapsed
    assert f"{watch_mod.HEARTBEAT_STALE_AFTER_S:.0f} s" in collapsed, collapsed
    # Still a report. Nothing re-armed, nothing stopped, REARM_STATES untouched.
    assert status.armed is True
    assert status.state not in watch_mod.REARM_STATES


def test_one_wedged_surface_names_the_fresh_ones_as_the_evidence_it_is_flushing(
    tmp_path: Path, record_file: Path
) -> None:
    """The other half of the all-vs-some split: SOME stale is a different claim.

    When a surface IS still inside its own threshold, saying the process is
    flushing is supported - by that surface, which is named. That is the whole
    difference from the stall above, and it is why the two cases must not share
    one sentence.
    """
    status = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())

    assert status.state == watch_mod.STATE_SURFACE_STALE, status.reason
    assert status.stale_surfaces == ("logs",)
    assert status.all_surfaces_stale is False
    assert status.fresh_surfaces == ("savedroot", "savegames", "standalonelevel")

    collapsed = " ".join(status.reason.split())
    # The claim is made, and the evidence for it is named in the same breath.
    assert "still flushing" in collapsed, collapsed
    for name in status.fresh_surfaces:
        assert name in collapsed, collapsed


def test_the_stall_sentence_and_the_wedged_thread_sentence_are_not_the_same(
    tmp_path: Path, record_file: Path
) -> None:
    """Collapsing them loses the interesting one - the 4f acceptance, in terms.

    A stall says nothing is advancing and offers the combined stamp's age as the
    only measurement it has. A wedged thread says three surfaces are advancing
    and names them. A reader who cannot tell those apart cannot tell a dead
    watcher from a dead thread.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    stall_s = 800.0
    surfaces = _all_surfaces_at(NOW - timedelta(seconds=stall_s))
    surfaces["logs"] = watch_mod._stamp(
        NOW - timedelta(seconds=stall_s + _declared_intervals()["logs"])
    )
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(NOW - timedelta(seconds=stall_s)),
        surfaces=surfaces,
        intervals=_declared_intervals(),
    )
    stalled = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )
    wedged = _wedged_logs_status(tmp_path, record_file, intervals=_declared_intervals())

    assert stalled.state == wedged.state == watch_mod.STATE_SURFACE_STALE
    assert stalled.reason != wedged.reason
    assert stalled.all_surfaces_stale is True and wedged.all_surfaces_stale is False
    assert "still flushing" in " ".join(wedged.reason.split())
    assert "still flushing" not in " ".join(stalled.reason.split())


def test_the_real_healthy_bound_and_its_precondition_are_written_down() -> None:
    """A caveat stated in chat but dropped from the artifact is a lie in it.

    The module's formula keeps the conservative ``2 * flush`` - it costs nothing
    and absorbs scheduling jitter and one skipped flush - but the TRUE worst
    case for a healthy surface is ``poll + flush``, because a flush fires
    whenever any surface records and the two 3 s surfaces record ten times per
    30 s throttle window. The precondition is the interesting half and is the
    argument for keeping STALE and SURFACE_STALE separate: it holds only while
    some surface still records, and if every surface stops then no flush fires
    at all. Both have to survive into the module the next session reads.
    """
    collapsed = " ".join(_module_source().split())
    assert "true bound is poll + flush" in collapsed
    assert "2.1x, 2.5x and 2.9x" in collapsed
    assert "no flush fires at all" in collapsed


def test_the_documented_true_bound_matches_the_plan_it_describes() -> None:
    """The correction is a set of NUMBERS in prose, and prose goes stale silently.

    ``poll + flush`` is 33 / 60 / 330 s against thresholds of 69 / 150 / 960 s,
    so the real margins are 2.1x / 2.5x / 2.9x. Both triples are written into
    the module, so both are re-derived here from the plan the module claims to
    be describing. Without this, a cadence change in ``lanternlight/armwatch.py``
    leaves the ops docstring confidently quoting figures nobody measures any
    more - the same defect as the re-typed ``300.0``, wearing prose.
    """
    from lanternlight.armwatch import HEARTBEAT_FLUSH_INTERVAL_S, session_plan

    plans = session_plan(saved_dir=Path("plan-placeholder"), dest_root=Path("plan-placeholder"))
    bounds = sorted({p.poll_seconds + HEARTBEAT_FLUSH_INTERVAL_S for p in plans})
    assert bounds == [33.0, 60.0, 330.0], bounds

    margins = sorted(
        {
            round(
                watch_mod.surface_stale_after_s(p.poll_seconds, HEARTBEAT_FLUSH_INTERVAL_S)
                / (p.poll_seconds + HEARTBEAT_FLUSH_INTERVAL_S),
                1,
            )
            for p in plans
        }
    )
    assert margins == [2.1, 2.5, 2.9], margins

    collapsed = " ".join(_module_source().split())
    assert "33 s, 60 s and 330 s" in collapsed, "the true bound is not written down"
    assert "2.1x, 2.5x and 2.9x" in collapsed


def test_the_wrap_never_rearms_a_watcher_with_one_wedged_surface(
    tmp_path: Path, record_file: Path
) -> None:
    """SURFACE_STALE is a REPORT. Re-arming it is the failure, not the fix.

    A watcher with one wedged thread is still one watcher. Arming a second one
    would double the traffic on the three surfaces that ARE working in order to
    chase the one that is not, while ``OPS-14`` is open. Nothing is stopped
    either: killing is out of scope, inherited from 4e and 4d.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    fresh = NOW - timedelta(seconds=4)
    surfaces = _all_surfaces_at(fresh)
    surfaces["logs"] = watch_mod._stamp(NOW - timedelta(seconds=3600))
    beat = _heartbeat_file(
        tmp_path,
        pid=os.getpid(),
        written=watch_mod._stamp(fresh),
        surfaces=surfaces,
        intervals=_declared_intervals(),
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

    assert result.status.state == watch_mod.STATE_SURFACE_STALE, result.reason
    assert calls == [], f"the wrap spawned over a live watcher: {calls}"
    assert result.arm is None
    assert result.rearmed is False
    assert result.status.armed is True
    # The incumbent is untouched, record and process alike.
    survivor = watch_mod.read_record(record_file)
    assert survivor is not None
    assert survivor.pid == os.getpid()
    assert guard_mod.pid_is_alive(os.getpid()) is True


# ---------------------------------------------------------------------------
# the per-surface threshold itself - a number with no argument is a guess
# ---------------------------------------------------------------------------


def test_the_surface_threshold_has_the_shape_its_derivation_claims() -> None:
    """``k * poll + 2 * flush``, with both flush terms present.

    The second flush term is the one an implementation counting only "the
    watcher's own worst case" forgets: the file being READ may itself have been
    written a flush interval ago. Dropping it would put the threshold below a
    healthy surface's honest worst case and turn this check into a false-alarm
    generator.
    """
    assert watch_mod.surface_stale_after_s(300.0, 30.0) == (
        watch_mod.SURFACE_STALE_MULTIPLE * 300.0 + 2.0 * 30.0
    )
    assert watch_mod.surface_stale_after_s(300.0, 30.0) == 960.0
    assert watch_mod.surface_stale_after_s(3.0, 30.0) == 69.0


def test_the_surface_threshold_clears_every_surfaces_own_honest_worst_case() -> None:
    """A healthy surface can read as ``poll + 2 * flush`` old. All four of them.

    Asserted across the real plan rather than for the slowest surface alone,
    because the fast surfaces are the ones where the margin is thinnest.
    """
    from lanternlight.armwatch import HEARTBEAT_FLUSH_INTERVAL_S, session_plan

    plans = session_plan(saved_dir=Path("plan-placeholder"), dest_root=Path("plan-placeholder"))
    for plan in plans:
        honest = plan.poll_seconds + 2.0 * HEARTBEAT_FLUSH_INTERVAL_S
        threshold = watch_mod.surface_stale_after_s(plan.poll_seconds, HEARTBEAT_FLUSH_INTERVAL_S)
        assert threshold > honest, (
            f"{plan.name}: threshold {threshold} s does not clear the {honest} s a healthy "
            "surface can legitimately take"
        )


def test_the_surface_multiple_is_the_same_k_as_the_combined_one() -> None:
    """One argument, one number. Two literals would drift and nothing would go red."""
    assert watch_mod.SURFACE_STALE_MULTIPLE == watch_mod.HEARTBEAT_STALE_MULTIPLE
    assert watch_mod.SURFACE_STALE_MULTIPLE >= 3


def test_the_flush_interval_this_module_documents_is_the_one_armwatch_uses() -> None:
    """``HEARTBEAT_FLUSH_THROTTLE_S`` is a MIRROR, and a mirror can drift.

    It was shipped as a re-typed literal with nothing coupling it to the number
    the watcher actually flushes at - the same shape as the re-typed ``300.0``
    that ``test_the_slowest_poll_interval_is_the_one_armwatch_actually_uses``
    exists to catch. The 4f derivation reads the lanternlight value directly, so
    this pins the leftover copy rather than trusting two comments to be edited
    together.
    """
    from lanternlight import armwatch as armwatch_mod

    assert watch_mod.HEARTBEAT_FLUSH_THROTTLE_S == armwatch_mod.HEARTBEAT_FLUSH_INTERVAL_S
    assert watch_mod._watcher_flush_interval_s() == armwatch_mod.HEARTBEAT_FLUSH_INTERVAL_S


def test_the_four_intervals_are_read_from_the_plan_and_not_re_typed_here() -> None:
    """The ops layer must not carry a second copy of four lanternlight numbers.

    One re-typed copy of ``300.0`` was already caught and pinned. Four more
    would be the same defect four times, so the fallback reads the plan and this
    asserts that it really is the plan it read.
    """
    from lanternlight.armwatch import session_plan

    plans = session_plan(saved_dir=Path("plan-placeholder"), dest_root=Path("plan-placeholder"))
    assert watch_mod._plan_poll_intervals() == {p.name: p.poll_seconds for p in plans}


def test_the_fast_surface_limit_is_written_down_rather_than_only_known() -> None:
    """A caveat stated in chat but dropped from the artifact is a lie in the artifact.

    For a 3 s surface the threshold is 69 s, of which 60 s is flush, so a fast
    surface cannot be caught any faster than the flush cadence allows. That is
    a real limit of the design and it has to survive in the module the next
    session reads, not only in the commit message.
    """
    source = _module_source()
    collapsed = " ".join(source.split())
    assert "flush cadence allows" in collapsed, "the fast-surface limit is not stated in the module"
    assert "STATED COST" in collapsed


def test_the_lanternlight_imports_added_for_4f_are_still_lazy() -> None:
    """Item 4f added two more lanternlight reads. Neither may reach module scope.

    ``test_the_default_dated_destination_is_imported_lazily`` already forbids a
    module-scope lanternlight import, but it only proves ONE nested import
    exists. Three do now, and a later edit could hoist two of them and leave
    that test green.
    """
    tree = ast.parse(_module_source())
    nested_names: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, ast.FunctionDef):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.ImportFrom) and node.module == "lanternlight.armwatch":
                nested_names.update(alias.name for alias in node.names)

    assert {"dated_dest_root", "session_plan", "HEARTBEAT_FLUSH_INTERVAL_S"} <= nested_names

    module_level = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name.startswith("lanternlight") for name in module_level)


# ---------------------------------------------------------------------------
# ROADMAP OPS-23 - a recycled pid this token cannot OPEN is not the watcher
#
# ``OPS-19`` made an access-denied ``OpenProcess`` read ALIVE, which is right
# for the loop lock and wrong for these consumers. Our watcher is spawned by
# this session under this session's own token, so a RECORDED pid that has gone
# access-denied is a pid something foreign inherited - and until this section
# the check believed it, landed on ``NO_HEARTBEAT``, and reported ARMED with
# nothing archiving.
#
# THE PREMISE, MEASURED RATHER THAN REASONED, on this machine 2026-09-05, with
# ``SeDebugPrivilege`` REMOVED from the probing token and the removal asserted
# (transcript: scratchpad/c44_ops23/):
#
#   * 40 of 40 children spawned the way ``default_spawn`` spawns - detached,
#     new process group, DEVNULL streams - had a READABLE creation time.
#   * The live watcher of the moment, pid 21452, read 2026-09-03T23:53:54.252209Z
#     against a record saying 23:53:54 - 0.25 s, inside the window.
#   * 12 of 307 live pids were alive-but-unreadable, EVERY one of them failing
#     ``OpenProcess`` with error 5, and every one owned by SYSTEM, LOCAL
#     SERVICE, UMFD-0/1 or DWM-1. Not one ran as this user.
#
# So the premise holds for the DENIED case, and only for it. It does NOT hold
# for "creation time unreadable" in general, which is why the fix keys on the
# error code rather than on ``process_creation_time`` returning ``None`` - see
# ``test_a_cannot_tell_that_is_not_a_denial_still_believes_the_incumbent``.
#
# THE SAME SWEEP WITH THE PRIVILEGE STILL HELD FOUND 0 OF 305 DENIED. That is
# why every test below INJECTS the denial: this suite runs under a token that
# holds ``SeDebugPrivilege``, so there is no pid on this machine it can be
# refused, and a test that went looking for one would pass by finding nothing.
# ---------------------------------------------------------------------------


class _DeniedCall:
    """A fake ctypes entry point with a fixed result and a call count."""

    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.restype = None
        self.argtypes = None

    def __call__(self, *args):
        self.calls += 1
        return self.result


class _DeniedOpenProcess(_DeniedCall):
    """``OpenProcess``, failing, carrying the error it left behind.

    The handle and the error live on ONE object because ``GetLastError`` is
    only meaningful immediately after the call that set it. Reading the error
    off the same object the call went through means a probe that never
    consulted the error cannot make these tests pass by accident, and
    :attr:`error_reads` records that it was consulted.
    """

    def __init__(self, result, last_error):
        super().__init__(result)
        self.last_error = last_error
        self.error_reads = 0

    def read_last_error(self):
        """Stand in for ``ctypes.get_last_error()``. Counts, never raises.

        A spy that raised would be vacuous the moment any caller wrapped it in
        ``except Exception`` - ``AssertionError`` is an ``Exception`` - which is
        a trap this repo has already paid for. A counter cannot be swallowed.
        """
        self.error_reads += 1
        return self.last_error


class _DeniedKernel32:
    def __init__(self, *, open_result, last_error):
        self.OpenProcess = _DeniedOpenProcess(open_result, last_error)
        self.GetProcessTimes = _DeniedCall(0)
        self.CloseHandle = _DeniedCall(1)


#: The two ``OpenProcess`` failure codes this section turns on, and one that is
#: neither. Spelled out here rather than imported from the module under test:
#: an instrument that shares a constant with the thing it measures inherits
#: that thing's mistakes. 5 is ``ERROR_ACCESS_DENIED`` - the process EXISTS and
#: this token may not ask. 87 is ``ERROR_INVALID_PARAMETER`` - no process bears
#: the pid. 8 is ``ERROR_NOT_ENOUGH_MEMORY``, a real way for the call to fail
#: while saying nothing whatever about the pid.
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87
_ERROR_NOT_ENOUGH_MEMORY = 8

#: A pid for the injected tests. The fake ignores it, so it stands for "the
#: number in the record" and nothing else. Deliberately NOT this process's pid:
#: our own pid is the one number that could never be denied to us, and a test
#: that used it would read as a contradiction.
_RECYCLED_PID = 4321


def _deny(monkeypatch, *, last_error):
    """Install a fake kernel32 whose ``OpenProcess`` fails with ``last_error``.

    ONE fake serves both modules on purpose. ``guard.pid_is_alive`` and
    ``watch.process_creation_time`` each build their own ``kernel32`` and each
    call the same ``OpenProcess``, so a single injected failure reproduces the
    whole ``OPS-23`` shape end to end - the guard reading ALIVE and the
    creation-time probe reading nothing - rather than asserting the two halves
    separately and hoping they meet.

    ``ctypes.get_last_error`` is patched alongside ``ctypes.WinDLL``, because
    with the library faked no real call happens and the genuine accessor would
    hand back whatever some earlier, unrelated call left in the slot.
    """
    import ctypes

    fake = _DeniedKernel32(open_result=0, last_error=last_error)
    monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **k: fake)
    monkeypatch.setattr(ctypes, "get_last_error", fake.OpenProcess.read_last_error)
    return fake


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_an_alive_but_unopenable_recorded_pid_gets_a_verdict_that_rearms(
    monkeypatch, tmp_path: Path, record_file: Path
) -> None:
    """The whole of ``OPS-23``, driven through the real probes.

    Nothing here is stubbed above the ctypes layer: ``guard.pid_is_alive``,
    ``watch.process_creation_time`` and the denial probe all run their real
    code against one fake ``OpenProcess`` that fails with error 5. That is the
    recycled pid exactly - alive by the ``OPS-19`` reading, unopenable, and
    therefore not a process this session could have spawned.

    The assertion that matters is the last one. ``IMPOSTOR`` is not the point;
    being in :data:`REARM_STATES` is, because that is what makes the wrap put a
    watcher back rather than hand the machine over reporting ARMED with nothing
    archiving the log, the saves or the market cache.
    """
    watch_mod.write_record(_record(_RECYCLED_PID, tmp_path, started=ARMED_AT), record_file)
    fake = _deny(monkeypatch, last_error=_ERROR_ACCESS_DENIED)

    # The two readings this verdict has to reconcile, taken through the real
    # functions rather than assumed.
    assert guard_mod.pid_is_alive(_RECYCLED_PID) is True, "OPS-19: denied reads ALIVE"
    assert watch_mod.process_creation_time(_RECYCLED_PID) is None, "denied tells no time"

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
    )

    assert status.state == watch_mod.STATE_IMPOSTOR, status.reason
    assert status.armed is False, status.reason
    assert status.state in watch_mod.REARM_STATES, status.state
    assert fake.OpenProcess.error_reads > 0, "the error code was never consulted"
    assert any("denied" in item.lower() for item in status.evidence), status.evidence


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_a_cannot_tell_that_is_not_a_denial_still_believes_the_incumbent(
    monkeypatch, tmp_path: Path, record_file: Path
) -> None:
    """The non-vacuity mirror, and the reason the fix keys on the ERROR CODE.

    Same injection, same missing creation time, same ALIVE reading - only the
    failure code differs, and it is one nobody has characterised. Nothing here
    establishes the process is foreign, so ``4e``'s rule stands: cannot-tell
    believes the incumbent, because a false ``IMPOSTOR`` re-arms beside a live
    watcher.

    Without this test the branch above would pass just as happily against an
    implementation that routed EVERY unreadable creation time to ``IMPOSTOR``.
    That implementation is the one the ``OPS-23`` item proposed, and it would
    call a healthy watcher an impostor on every non-Windows platform and on
    every handle that opens but will not answer.
    """
    watch_mod.write_record(_record(_RECYCLED_PID, tmp_path, started=ARMED_AT), record_file)
    fake = _deny(monkeypatch, last_error=_ERROR_NOT_ENOUGH_MEMORY)

    assert guard_mod.pid_is_alive(_RECYCLED_PID) is True, "uncharacterised fails CLOSED"
    assert watch_mod.process_creation_time(_RECYCLED_PID) is None, "still no creation time"
    assert watch_mod.pid_open_denied(_RECYCLED_PID) is None, "uncharacterised is cannot-tell"

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
    )

    assert status.state == watch_mod.STATE_NO_HEARTBEAT, status.reason
    assert status.armed is True, status.reason
    assert status.state not in watch_mod.REARM_STATES
    assert status.identity == watch_mod.IDENTITY_UNCHECKED, status.identity
    assert fake.OpenProcess.error_reads > 0, "the error code was never consulted"


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_the_same_injection_with_the_gone_code_reads_dead_rather_than_impostor(
    monkeypatch, tmp_path: Path, record_file: Path
) -> None:
    """The second mirror: the fake can produce the OPPOSITE reading too.

    ``ERROR_INVALID_PARAMETER`` is the one code that means no process bears the
    pid, so the guard reports DEAD and the identity question is never asked.
    Without this, both tests above would pass against a fake that was simply
    incapable of ever reporting a live process, which is the shape of an
    injection that proves nothing.
    """
    watch_mod.write_record(_record(_RECYCLED_PID, tmp_path, started=ARMED_AT), record_file)
    _deny(monkeypatch, last_error=_ERROR_INVALID_PARAMETER)

    assert guard_mod.pid_is_alive(_RECYCLED_PID) is False

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
    )

    assert status.state == watch_mod.STATE_DEAD, status.reason
    assert status.state in watch_mod.REARM_STATES
    assert status.identity == watch_mod.IDENTITY_NOT_REACHED, (
        "DEAD never reaches the identity question, and saying UNCHECKED there would "
        "conflate 'asked and unanswerable' with 'never asked'"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="the ctypes probe is Windows-only")
def test_the_wrap_rearms_the_alive_but_unopenable_pid_rather_than_reporting_armed(
    monkeypatch, tmp_path: Path, record_file: Path
) -> None:
    """``OPS-23``'s consequence, not just its verdict: a watcher comes back.

    A verdict that re-arms is only worth something if the wrap acts on it, and
    the wrap has one more hurdle - ``ensure_armed`` refuses when the recorded
    pid is alive, which this one is. It re-arms only because ``IMPOSTOR``
    passes ``disqualified_pid`` down. This asserts the record that came out,
    not just the state that went in.
    """
    watch_mod.write_record(_record(_RECYCLED_PID, tmp_path, started=ARMED_AT), record_file)
    _deny(monkeypatch, last_error=_ERROR_ACCESS_DENIED)

    spawned: list[tuple] = []

    def spawn_fn(dest_base, dest_root) -> int:
        spawned.append((dest_base, dest_root))
        return 5150

    result = watch_mod.ensure_armed_at_wrap(
        tmp_path / "captures",
        spawn_fn=spawn_fn,
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
        heartbeat=tmp_path / "absent.json",
    )

    assert result.status.state == watch_mod.STATE_IMPOSTOR, result.reason
    assert result.rearmed is True, result.reason
    assert len(spawned) == 1, "the wrap did not actually start anything"
    assert watch_mod.read_record(record_file).pid == 5150, "the record still names the old pid"
    assert "REFUSED access" in result.reason, result.reason


def test_pid_open_denied_answers_three_ways_and_never_guesses() -> None:
    """The probe's own contract, against real pids where real pids exist.

    ``None`` is a third answer here for the same reason it is one in
    :func:`process_creation_time`: a probe that invented ``False`` on a pid it
    could not evaluate would hand the identity check a clean bill it never
    measured, and ``False`` is the answer that lets a verdict stand.

    The last assertion needs a number no process bears. ``UNALLOCATABLE_PID``
    is that number and its premise is asserted where it is defined - a pid that
    is not a multiple of four has never named a process on NT.
    """
    assert watch_mod.pid_open_denied(None) is None
    assert watch_mod.pid_open_denied(0) is None
    assert watch_mod.pid_open_denied(-1) is None
    assert watch_mod.pid_open_denied(True) is None

    if sys.platform != "win32":
        assert watch_mod.pid_open_denied(os.getpid()) is None, "cannot-tell off Windows"
        return

    # Our own process is the one pid that can never be refused to us, and it is
    # the shape every watcher this module arms has: spawned by a session
    # running under this token.
    assert watch_mod.pid_open_denied(os.getpid()) is False
    # Nothing bears this number, so there is nothing to be refused BY. That is
    # a different fact from a refusal and must not read as one.
    assert watch_mod.pid_open_denied(UNALLOCATABLE_PID) is False


def test_check_watcher_distinguishes_a_verified_identity_from_an_unchecked_one(
    tmp_path: Path, record_file: Path
) -> None:
    """``OPS-23``'s first acceptance criterion: today both reach the same branch.

    Before this, a matched creation time and an unanswerable one produced the
    same state, the same ``armed``, and the same sentence - "pid N is the
    watcher" - so a consumer could not tell an observation from an assumption,
    and the ARMED reason asserted "identity-confirmed" in a case where nothing
    had been confirmed.

    Both halves run through the same record and the same heartbeat, so the ONLY
    variable is the identity probe's answer.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    beat = _heartbeat_file(tmp_path, pid=os.getpid(), written=watch_mod._stamp(NOW))

    verified = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
    )
    unchecked = watch_mod.check_watcher(
        path=record_file,
        heartbeat=beat,
        now=NOW,
        creation_time_fn=lambda pid: None,
        denied_fn=lambda pid: None,
    )

    # Same state, same verdict - which is why the distinction had to be carried
    # somewhere other than the state.
    assert verified.state == watch_mod.STATE_ARMED, verified.reason
    assert unchecked.state == watch_mod.STATE_ARMED, unchecked.reason
    assert verified.armed is True and unchecked.armed is True

    assert verified.identity == watch_mod.IDENTITY_VERIFIED
    assert unchecked.identity == watch_mod.IDENTITY_UNCHECKED
    assert verified.identity != unchecked.identity

    # And the prose stops claiming a confirmation that never happened.
    assert "identity-confirmed" in verified.reason, verified.reason
    assert "identity-confirmed" not in unchecked.reason, unchecked.reason
    assert "never confirmed, only believed" in unchecked.reason, unchecked.reason
    assert "BELIEVED to be the watcher" in unchecked.reason, unchecked.reason


def test_a_platform_with_no_probe_at_all_still_believes_the_incumbent(
    tmp_path: Path, record_file: Path
) -> None:
    """The portability guarantee, stated as the case that would break it.

    Off Windows, :func:`process_creation_time` answers ``None`` for EVERY pid
    including a healthy watcher's, and :func:`pid_open_denied` answers ``None``
    for the same reason. That pair is what this test injects, and the verdict
    has to stay ARMED: a rule that read every unreadable creation time as
    ``IMPOSTOR`` would re-arm a second poller beside every live watcher on
    every non-Windows platform. That rule is what the ``OPS-23`` item proposed
    and it is the half of the hypothesis that does not hold.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)

    status = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=lambda pid: None,
        denied_fn=lambda pid: None,
    )

    assert status.state == watch_mod.STATE_NO_HEARTBEAT, status.reason
    assert status.armed is True
    assert status.state not in watch_mod.REARM_STATES
    assert status.identity == watch_mod.IDENTITY_UNCHECKED


def test_a_live_process_this_session_owns_never_reads_impostor(
    tmp_path: Path, record_file: Path
) -> None:
    """The ``4e`` guarantee, re-proved against the NEW path into IMPOSTOR.

    Subject: this interpreter. It is alive, it is ours, and it was started by
    this session - the same three properties an armed watcher has. Nothing is
    injected: the real creation-time probe and the real refusal probe both run,
    against a record whose ``started`` is derived from the process's own real
    creation time the way :func:`ensure_armed` derives it.

    ``IMPOSTOR`` is in :data:`REARM_STATES`, so a false one here would put a
    second poller on the same four sources - the failure ``ensure_armed``
    exists to refuse, and the reason ``4e`` chose a 120 s window on purpose.

    The wall-clock half of this - 33 samples over 330 s against the real live
    watcher AND a real detached child, the sampling ``4f`` used - cannot live
    in a suite that has to finish, and was run separately. See the section
    comment above for the numbers.
    """
    created = watch_mod.process_creation_time(os.getpid())
    if created is None:
        pytest.skip("no creation-time probe on this platform; the injected tests pin the logic")

    watch_mod.write_record(
        _record(os.getpid(), tmp_path, started=watch_mod._stamp(created)), record_file
    )

    status = watch_mod.check_watcher(path=record_file, heartbeat=tmp_path / "absent.json")

    assert status.state != watch_mod.STATE_IMPOSTOR, status.reason
    assert status.state not in watch_mod.REARM_STATES, status.reason
    assert status.identity == watch_mod.IDENTITY_VERIFIED, status.evidence
    assert watch_mod.pid_open_denied(os.getpid()) is False


def test_the_refusal_probe_is_never_consulted_once_identity_has_an_answer(
    tmp_path: Path, record_file: Path
) -> None:
    """Structural proof that a healthy watcher cannot reach the new branch.

    The test above shows one live process not reading ``IMPOSTOR``. This shows
    WHY no live process with a readable creation time ever can: the refusal
    probe is only asked when :func:`_identity_matches` returned ``None``, so a
    confirmed identity and a refuted one both bypass it entirely. A spy that
    COUNTS is used rather than one that raises, because ``AssertionError`` is
    an ``Exception`` and a raising spy goes vacuous under any caller that
    catches broadly - a trap this repo has already paid for.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)
    asked: list[int] = []

    def denied_fn(pid: int):
        asked.append(pid)
        return True  # the answer that would flip the verdict, if it were read

    inside = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(MEASURED_CREATION),
        denied_fn=denied_fn,
    )
    assert inside.state == watch_mod.STATE_NO_HEARTBEAT, inside.reason
    assert inside.identity == watch_mod.IDENTITY_VERIFIED
    assert asked == [], "a verified identity asked the refusal probe anyway"

    outside = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=_fixed_creation(datetime(2026, 9, 3, 4, 0, 0, tzinfo=UTC)),
        denied_fn=denied_fn,
    )
    assert outside.state == watch_mod.STATE_IMPOSTOR, outside.reason
    assert outside.identity == watch_mod.IDENTITY_REFUTED
    assert "identity window" in outside.reason, (
        "a refuted identity must keep citing the offset it measured, not a refusal "
        "probe it never asked"
    )
    assert asked == [], "a refuted identity asked the refusal probe anyway"

    # The mirror: the spy IS reachable, so the two empty lists above are facts
    # about the branch and not about a probe nothing could ever call.
    reached = watch_mod.check_watcher(
        path=record_file,
        heartbeat=tmp_path / "absent.json",
        now=NOW,
        creation_time_fn=lambda pid: None,
        denied_fn=denied_fn,
    )
    assert asked == [os.getpid()], asked
    assert reached.state == watch_mod.STATE_IMPOSTOR, reached.reason


def test_the_refusal_to_arm_no_longer_claims_a_watcher_is_running(
    tmp_path: Path, record_file: Path
) -> None:
    """``OPS-23``'s fourth acceptance criterion.

    :func:`ensure_armed` reads liveness and nothing else, and since ``OPS-19``
    liveness answers ALIVE for a pid this token may not open. So the old
    sentence - "a watcher is already running as pid N" - asserted an identity
    the function had never checked, and in the ``OPS-23`` case it was flatly
    false.

    The refusal itself is unchanged and must stay that way: not arming is still
    the right call, because the cost of being wrong the other way is a second
    poller on the same four sources while ``OPS-14`` is open.
    """
    watch_mod.write_record(_record(os.getpid(), tmp_path, started=ARMED_AT), record_file)

    result = watch_mod.ensure_armed(
        tmp_path / "captures",
        spawn_fn=lambda base, root: pytest.fail("a second watcher was spawned"),
        dest_root_fn=_dated,
        now=NOW,
        path=record_file,
    )

    assert result.armed is False
    assert result.pid == os.getpid()
    assert "a watcher is already running" not in result.reason, result.reason
    assert "is ALIVE" in result.reason, result.reason
    assert "NOT checked here" in result.reason, result.reason
