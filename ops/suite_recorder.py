"""Record every pytest session in this repository, so a cycle's cost is a fact.

``ROADMAP.md`` ``OPS-87`` criterion 4 asks for the number of full-suite runs
and the wall clock a refute-fix-refute cycle costs, MEASURED and not estimated,
before and after. Nothing in this tree recorded that. The before number had to
be reconstructed from a ledger entry and a recollection; the after number does
not, because from here on every ``pytest`` invocation writes one record of
itself and a later session counts instead of remembering.

THE RECORD SCHEMA IS THIS DOCSTRING. A sibling module reads these files, so the
field list is a contract rather than an implementation detail. One JSON object
per run, under ``ops/runtime/suite_runs/`` which is gitignored, named
``<UTC start, compact, to the microsecond>-<zero-padded pid>.json`` so two
concurrent runs cannot land on the same name and a plain filename sort is
chronological. Fields, all of them always present - see ``RECORD_FIELDS``:

``schema``
    Integer. ``SCHEMA_VERSION``. A reader that does not know the value it finds
    should say so rather than guess at the fields.
``started_utc``
    ISO-8601 with an explicit ``+00:00`` offset. UTC, because the game log is
    UTC and every other timestamp this project joins against is too.
``duration_s``
    Float seconds of WALL CLOCK, from ``pytest_configure`` to
    ``pytest_sessionfinish``, taken from a monotonic clock. It is the number
    criterion 4 wants. It excludes interpreter startup and the collection that
    happens before ``pytest_configure``, so it reads a little under what a shell
    stopwatch reports.
``collected``
    Integer. ``session.testscollected`` as pytest counted it.
``passed`` ``failed`` ``skipped`` ``errors`` ``xfailed`` ``xpassed``
    Integers, tallied from the reports rather than parsed out of the summary
    line. ``-q`` twice prints no summary line at all in this repository, which
    is exactly the trap a parser would fall into.
``exitstatus``
    Integer, pytest's own.
``full``
    Boolean. THE LOAD-BEARING FIELD. See the next section.
``filtered_reasons``
    List of strings, empty when ``full`` is true. Each names one reason the run
    was not a full suite, so a false negative can be argued with.
``nested``
    Boolean. True when this pytest was spawned from inside another pytest in
    this repository - several tests here run pytest as a subprocess, and an
    instrument that counts its own fixtures pollutes its own data. MEASURED
    rather than assumed - see the next section for what the measurement
    changed.
``root`` ``pid`` ``args`` ``modules_run`` ``modules_on_disk``
    The tree the run was rooted at, the process id, the invocation arguments as
    given, and the two module COUNTS the full-versus-filtered test compares.
    The counts rather than the lists, because a record is read far more often
    than it is diagnosed and 67 paths per record is 67 paths of noise.

HOW ``full`` IS DECIDED, AND WHAT THAT TEST CANNOT SEE. A run is full only when
every one of the following holds:

1. No ``-k`` and no ``-m``. Read off ``config.option``, so a filter that
   arrived through the configuration file's ``addopts`` is caught as well as
   one typed on the command line.
2. Not ``--collect-only``, not ``--lf``, not ``--ff``, not ``--sw``.
3. No target argument. ``config.invocation_params.args`` is scanned by
   :func:`target_arguments`, which drops anything beginning with ``-`` and the
   value that follows a known value-taking option.
4. Nothing was deselected.
5. Every ``tests/test_*.py`` ON DISK was actually entered during the run. This
   is the backstop and the strongest of the five, because it is a statement
   about what happened rather than about what was asked for.

What it cannot distinguish, stated rather than implied:

* A ``--deselect`` or a ``-x`` that removed individual TESTS while leaving
  every module still entered would pass test 5. Test 4 catches the deselect
  arm; an ``-x`` that fired mid-module is caught because the modules after it
  never ran, but an ``-x`` that fired in the LAST module is not.
* A value-taking option this module does not know about is misread as a target
  argument, so the run is called FILTERED. That is the safe direction and it is
  deliberate: under-counting full runs makes the AFTER number look worse, and
  an instrument should be biased against flattering itself.
* It says nothing about whether the run was FAST for a legitimate reason.
  A warm filesystem cache, another process competing for the machine, and a
  suite that genuinely got quicker all look identical in ``duration_s``.
* ``nested`` is decided by TWO signals, and the second exists because the first
  was measured and found wanting. The first is an inherited environment
  variable. On the first full-suite run after this module landed, three pytest
  runs that the suite itself had spawned still read as top-level, so the
  environment mark did not reach every child. A constructed environment is one
  way that happens - ``tools/false_red_probe.py`` spawns pytest with
  ``env=dict(env)``, and a constructed environment cannot carry a variable
  nobody copied into it - but the three runs measured here were not that case
  and their cause is NOT identified. The second signal is therefore one that
  does not travel through the environment at all: a live session stamps a
  marker file named by its own process id, and a starting session asks whether
  a marker exists for ITS parent. On the next measured full run that brought
  the undetected count to zero - 4 records, one full suite and three nested.
* What the marker still cannot see: a GRANDCHILD, because only one generation
  is checked, and a child rooted at a DIFFERENT tree, because the marker is
  looked up under the child's own root. Both fall back to the environment mark.
  A marker is believed for ``MARKER_TTL_S`` and then swept, because a killed
  process leaves its marker behind and process ids are eventually reused; it is
  also cleared at process exit, which was added after one marker was observed
  outliving a run.
* Neither signal was load-bearing for the number that matters on either run:
  every subprocess run was FILTERED on its own evidence, so :func:`full_runs`
  returned exactly one record regardless. ``nested`` is what keeps that true
  when a fixture one day spawns an unfiltered run.
* The record directory is SHARED. Another agent working in this tree at the
  same time writes its own runs here, and on the first measured run a
  concurrent mutation sweep contributed most of the records present. A reader
  counting cycles must therefore treat a record as evidence that SOME session
  ran a suite, not that this one did.

THIS MODULE RAISES. The pytest hooks that drive it are fail-soft - a recorder
must never turn a green suite red - but the swallowing lives in
``tests/conftest.py`` and NOT here, because ``CLAUDE.md`` records that a bare
``except Exception`` swallows ``AssertionError`` too and makes a raising spy
vacuous. Everything below reports failure by raising, and
``tests/test_suite_recorder.py`` drives it directly for that reason.
"""

from __future__ import annotations

import atexit
import json
import os
import uuid
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, time

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Bumped when a field changes meaning. A reader that finds a value it does not
#: know should say so rather than guess.
SCHEMA_VERSION = 1

#: Under ``ops/runtime/``, which is gitignored - see the repository's ignore
#: file. A record is machine state, never a tracked artifact.
RECORD_DIR_PARTS = ("ops", "runtime", "suite_runs")

#: Set by the first session in a process tree and inherited by every subprocess
#: it spawns. That inheritance IS the nesting test.
NEST_ENV = "LANTERNLIGHT_SUITE_RECORDER_ACTIVE"

#: How long a marker file is believed. A process that died without clearing
#: its marker must not make an unrelated later run with the same parent id read
#: as nested, and a pid is reused eventually on every operating system.
MARKER_TTL_S = 12 * 3600

#: How many records survive a write. Enough to cover several cycles of the kind
#: ``OPS-87`` is measuring, small enough that the directory stays readable.
KEEP_RECORDS = 200

#: The contract, as a tuple, so a test can assert every field is present
#: instead of trusting the docstring to have been kept in step with the code.
RECORD_FIELDS = (
    "schema",
    "started_utc",
    "duration_s",
    "collected",
    "passed",
    "failed",
    "skipped",
    "errors",
    "xfailed",
    "xpassed",
    "exitstatus",
    "full",
    "filtered_reasons",
    "nested",
    "root",
    "pid",
    "args",
    "modules_run",
    "modules_on_disk",
)

#: Options whose VALUE is a separate argument. The value must not be mistaken
#: for a target path. An option missing from this set makes its value look like
#: a target, which calls the run FILTERED - the safe direction, see the module
#: docstring.
VALUE_OPTIONS = frozenset(
    {
        "-c",
        "-k",
        "-m",
        "-n",
        "-o",
        "-p",
        "-r",
        "-W",
        "--deselect",
        "--ignore",
        "--ignore-glob",
        "--import-mode",
        "--junitxml",
        "--log-level",
        "--maxfail",
        "--override-ini",
        "--rootdir",
        "--tb",
    }
)


@dataclass(frozen=True)
class Invocation:
    """What pytest was ASKED to do, flattened away from pytest's own objects.

    Flattened on purpose: a test can build one of these in a line, where
    standing up a real ``Config`` costs a subprocess. :func:`invocation_from_config`
    is the only place that touches pytest's shape.
    """

    args: tuple[str, ...] = ()
    keyword: str = ""
    markexpr: str = ""
    collect_only: bool = False
    last_failed: bool = False
    failed_first: bool = False
    stepwise: bool = False
    deselected: int = 0


@dataclass(frozen=True)
class Classification:
    """Whether a run was a full suite, and every reason it was not."""

    full: bool
    reasons: tuple[str, ...]


def invocation_from_config(config) -> Invocation:
    """Read an :class:`Invocation` off a live pytest ``Config``.

    Every attribute is read with a default, because a pytest plugin can remove
    an option and this module must not be the reason a suite cannot finish.
    """
    option = getattr(config, "option", None)
    params = getattr(config, "invocation_params", None)
    return Invocation(
        args=tuple(getattr(params, "args", ()) or ()),
        keyword=str(getattr(option, "keyword", "") or ""),
        markexpr=str(getattr(option, "markexpr", "") or ""),
        collect_only=bool(getattr(option, "collectonly", False)),
        last_failed=bool(getattr(option, "lf", False)),
        failed_first=bool(getattr(option, "failedfirst", False)),
        stepwise=bool(getattr(option, "stepwise", False)),
        # Deselections are counted by the ``pytest_deselected`` hook and fed in
        # through :meth:`SessionRecorder.note_deselected`. ``option.deselect``
        # holds the PATHS the caller named, not the number of tests removed.
        deselected=0,
    )


def target_arguments(args) -> tuple[str, ...]:
    """The arguments that narrow collection to particular paths or node ids.

    An argument beginning with ``-`` is an option. The argument AFTER a known
    value-taking option is that option's value. Everything else is a target.
    """
    targets: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg.startswith("-"):
            if arg in VALUE_OPTIONS:
                skip_next = True
            continue
        targets.append(arg)
    return tuple(targets)


def test_modules_on_disk(root: Path | str = REPO_ROOT) -> set[str]:
    """Every ``tests/test_*.py`` under ``root``, as repo-relative posix paths.

    Derived from the tree at call time rather than from a stored list, for the
    reason ``CLAUDE.md`` gives about filed counts: a constant here would go
    stale the first time a module was added and would then read as a full run
    that had skipped it.
    """
    root = Path(root)
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return set()
    return {path.relative_to(root).as_posix() for path in tests_dir.glob("test_*.py")}


def classify(
    invocation: Invocation,
    modules_run: set[str],
    modules_on_disk: set[str],
) -> Classification:
    """Decide full versus filtered, and say why when it is filtered."""
    reasons: list[str] = []
    if invocation.keyword:
        reasons.append(f"keyword filter (-k {invocation.keyword})")
    if invocation.markexpr:
        reasons.append(f"marker filter (-m {invocation.markexpr})")
    if invocation.collect_only:
        reasons.append("collect-only, so nothing was executed")
    if invocation.last_failed:
        reasons.append("last-failed selection (--lf)")
    if invocation.failed_first:
        reasons.append("failed-first selection (--ff)")
    if invocation.stepwise:
        reasons.append("stepwise selection (--sw)")
    if invocation.deselected:
        reasons.append(f"{invocation.deselected} tests were deselected")
    targets = target_arguments(invocation.args)
    if targets:
        reasons.append("target arguments narrowed collection: " + " ".join(targets))
    if not modules_on_disk:
        reasons.append("no test modules were found on disk under tests/")
    else:
        missing = modules_on_disk - set(modules_run)
        if missing:
            reasons.append(
                f"{len(missing)} of {len(modules_on_disk)} test modules on disk "
                "did not run"
            )
    return Classification(full=not reasons, reasons=tuple(reasons))


@dataclass
class Tally:
    """Outcomes counted from the reports, never parsed out of a summary line.

    Phase matters: a failure in ``setup`` or ``teardown`` is an ERROR and not a
    failure, and a passing ``setup`` is not a passing test. Folding either one
    in would make every number here disagree with pytest's own.
    """

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    xfailed: int = 0
    xpassed: int = 0

    def note(self, when: str, outcome: str, wasxfail: bool = False) -> None:
        if outcome == "failed":
            if when == "call":
                self.failed += 1
            else:
                self.errors += 1
            return
        if outcome == "skipped":
            if wasxfail:
                self.xfailed += 1
            elif when in ("setup", "call"):
                self.skipped += 1
            return
        if outcome == "passed" and when == "call":
            if wasxfail:
                self.xpassed += 1
            else:
                self.passed += 1

    def as_fields(self) -> dict:
        return {
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "errors": self.errors,
            "xfailed": self.xfailed,
            "xpassed": self.xpassed,
        }


def record_dir(root: Path | str = REPO_ROOT) -> Path:
    return Path(root).joinpath(*RECORD_DIR_PARTS)


def record_name(started: datetime, pid: int) -> str:
    """``<compact UTC to the microsecond>-<padded pid>.json``.

    The pid is in the name because two runs really can start in the same
    microsecond on this machine - the suite spawns pytest subprocesses - and a
    collision would silently lose a record rather than fail.
    """
    stamp = started.astimezone(UTC).strftime("%Y%m%dT%H%M%S%f")
    return f"{stamp}Z-{int(pid):06d}.json"


def marker_path(root: Path | str = REPO_ROOT, pid: int | None = None) -> Path:
    """Where a running session stamps the fact that it exists.

    Named by process id so a child can ask about its own parent by name. Under
    the record directory rather than beside it, because everything this module
    writes belongs in one gitignored place.
    """
    pid = os.getpid() if pid is None else pid
    return record_dir(root) / "active" / f"{int(pid)}.marker"


def _clear_stale_markers(root: Path | str = REPO_ROOT) -> int:
    """Delete markers older than :data:`MARKER_TTL_S`. Returns how many went.

    A marker outlives its process whenever a run is killed, and a stale one is
    worse than no marker at all: it makes a later unrelated run look nested and
    silently drops it out of :func:`full_runs`.
    """
    directory = marker_path(root).parent
    if not directory.is_dir():
        return 0
    cutoff = time() - MARKER_TTL_S
    removed = 0
    for path in directory.glob("*.marker"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:  # a marker another process removed between the two calls
            continue
    return removed


def _stamp_marker(root: Path | str, pid: int, started: datetime) -> Path:
    """Announce a live session to any pytest it spawns."""
    path = marker_path(root, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        started.isoformat() + "\n", encoding="ascii", newline="\n"
    )
    return path


def _cleanup_marker(root: Path | str, pid: int) -> None:
    """Remove one session's marker. Never raises, and absence is success."""
    with suppress(OSError):
        marker_path(root, pid).unlink(missing_ok=True)


def _parent_is_a_recorded_session(root: Path | str, ppid: int) -> bool:
    """Whether a live marker exists for this process's parent."""
    path = marker_path(root, ppid)
    try:
        return path.stat().st_mtime >= time() - MARKER_TTL_S
    except OSError:
        return False


def write_record(record: dict, root: Path | str = REPO_ROOT) -> Path:
    """Write one record atomically. Returns the path written.

    Temporary in the SAME directory, then ``replace``: a reader polling this
    directory must never catch a half-written record, and ``replace`` is only
    atomic within a filesystem.
    """
    directory = record_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    started = record.get("started_utc") or datetime.now(UTC).isoformat()
    target = directory / record_name(datetime.fromisoformat(started), record["pid"])
    tmp = target.with_name(f"{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
        newline="\n",
    )
    tmp.replace(target)
    return target


def prune(root: Path | str = REPO_ROOT, keep: int = KEEP_RECORDS) -> int:
    """Delete all but the newest ``keep`` records. Returns how many were removed.

    Newest by FILENAME, which sorts chronologically by construction - reading
    every record to sort by its own timestamp would make a prune cost more than
    the write it follows.
    """
    directory = record_dir(root)
    if not directory.is_dir():
        return 0
    names = sorted(path for path in directory.glob("*.json"))
    removed = 0
    for path in names[: max(0, len(names) - keep)]:
        path.unlink()
        removed += 1
    return removed


def load_records(root: Path | str = REPO_ROOT) -> list[dict]:
    """Every record, newest first, with ``full`` and ``nested`` preserved.

    A record that cannot be parsed is SKIPPED rather than raising. The
    directory is written concurrently by subprocess runs, and one unreadable
    file must not make the whole history unreadable - the alternative is a
    reader that fails at exactly the moment it is most needed.
    """
    directory = record_dir(root)
    if not directory.is_dir():
        return []
    records: list[dict] = []
    for path in directory.glob("*.json"):
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(parsed, dict):
            parsed.setdefault("_path", path.name)
            records.append(parsed)
    records.sort(key=lambda r: (str(r.get("started_utc", "")), r["_path"]), reverse=True)
    return records


def full_runs(root: Path | str = REPO_ROOT) -> list[dict]:
    """Only the real full-suite runs, newest first.

    Both filters matter. A filtered run is not the six-minute thing ``OPS-87``
    is measuring, and a NESTED run is a fixture's subprocess wearing a suite's
    clothes.
    """
    return [
        record
        for record in load_records(root)
        if record.get("full") is True and record.get("nested") is False
    ]


@dataclass
class SessionRecorder:
    """One pytest session's worth of measurement.

    Deliberately holds no pytest object. The hooks in ``tests/conftest.py``
    hand it primitives, which is what lets the tests drive it without standing
    up a nested pytest run.
    """

    root: Path = REPO_ROOT
    env: dict | None = None
    pid: int | None = None
    ppid: int | None = None
    clock: Callable[[], float] | None = None
    utcnow: Callable[[], datetime] | None = None
    nested: bool = False
    started_utc: datetime | None = None
    started_at: float | None = None
    deselected: int = 0
    modules_run: set[str] = field(default_factory=set)
    tally: Tally = field(default_factory=Tally)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if self.env is None:
            self.env = os.environ
        if self.pid is None:
            self.pid = os.getpid()
        if self.ppid is None:
            self.ppid = os.getppid()
        if self.clock is None:
            self.clock = monotonic
        if self.utcnow is None:
            self.utcnow = lambda: datetime.now(UTC)

    def begin(self) -> None:
        """Stamp the start, and mark the environment for any child pytest.

        The mark has to be set here rather than at finish, because the whole
        point of it is that a subprocess spawned DURING the run inherits it.
        """
        _clear_stale_markers(self.root)
        self.nested = self.env.get(NEST_ENV) == "1" or _parent_is_a_recorded_session(
            self.root, self.ppid
        )
        self.env[NEST_ENV] = "1"
        self.started_utc = self.utcnow()
        self.started_at = self.clock()
        # The marker is an AUXILIARY signal. Losing it degrades nesting
        # detection for this run's children back to the environment mark; it is
        # never a reason to drop the run's own record.
        with suppress(OSError):
            _stamp_marker(self.root, self.pid, self.started_utc)
        # Also at process exit. OBSERVED: one marker outlived a full suite run,
        # and a run that dies before pytest_sessionfinish would otherwise leave
        # its marker for the whole time-to-live, making a later unrelated run
        # with a matching parent id read as nested.
        atexit.register(_cleanup_marker, self.root, self.pid)

    def note_module(self, nodeid: str) -> None:
        head = nodeid.split("::")[0]
        if head.endswith(".py"):
            self.modules_run.add(head.replace("\\", "/"))

    def note_report(self, when: str, outcome: str, wasxfail: bool = False) -> None:
        self.tally.note(when, outcome, wasxfail)

    def note_deselected(self, count: int) -> None:
        """Tests pytest removed from the run after collection.

        Fed by the ``pytest_deselected`` hook rather than read off the options,
        because ``--deselect`` names PATHS and the question here is how many
        TESTS stopped being part of the run.
        """
        self.deselected += int(count)

    def build_record(
        self, invocation: Invocation, collected: int, exitstatus: int
    ) -> dict:
        if self.started_utc is None or self.started_at is None:
            raise RuntimeError("build_record before begin: there is no start time")
        on_disk = test_modules_on_disk(self.root)
        invocation = replace(
            invocation, deselected=invocation.deselected + self.deselected
        )
        verdict = classify(invocation, self.modules_run, on_disk)
        record = {
            "schema": SCHEMA_VERSION,
            "started_utc": self.started_utc.isoformat(),
            "duration_s": round(self.clock() - self.started_at, 3),
            "collected": int(collected),
            "exitstatus": int(exitstatus),
            "full": verdict.full,
            "filtered_reasons": list(verdict.reasons),
            "nested": bool(self.nested),
            "root": self.root.as_posix(),
            "pid": int(self.pid),
            "args": list(invocation.args),
            "modules_run": len(self.modules_run),
            "modules_on_disk": len(on_disk),
        }
        record.update(self.tally.as_fields())
        return record

    def finish(
        self, invocation: Invocation, collected: int, exitstatus: int
    ) -> Path:
        """Build, write and prune. RAISES on any failure - see the docstring."""
        record = self.build_record(invocation, collected, exitstatus)
        path = write_record(record, self.root)
        prune(self.root)
        _cleanup_marker(self.root, self.pid)
        return path
