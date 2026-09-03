"""Arm every session watcher from one entry point.

ROADMAP item 4c. This module adds **no copying**. ``lanternlight.savewatch``
already does all of it - copy every changed generation, never write to the
source, refuse a destination inside a git working directory - and the one
thing missing was that arming it was something each session had to REMEMBER.

Two losses came out of exactly that, and both are the reason this file exists
rather than a note in a hand-off:

- The **6.1 MB log of 2026-08-09 is gone.** The game empties
  ``MistfallHunter.log`` on launch. Measured across ONE launch, 2026-08-25:
  afterwards the live log still carried its original ``2026-08-09 08:18:56``
  creation time, so that launch emptied the file that was already there rather
  than making a new one. **One launch, watched once** - nothing here shows the
  timestamp survived any earlier launch, and on NTFS a delete-and-recreate
  inside about 15 seconds restores the original creation time anyway, so this
  evidence does not separate truncate-in-place from delete-and-recreate. See
  ``docs/FINDINGS.md`` 11.12.
- The **market cache emptied itself unobserved.** ``AvgPrice_<id>.ini`` had
  filled to 343 bytes and was back to its empty 37-byte state with nothing
  watching the transition.

MEASURED 2026-08-25, and it is why the plan watches DIRECTORIES rather than
files: the launch at 21:28:59 local left
``MistfallHunter-backup-2026.08.26-01.27.09.log`` beside the live log, created
at the instant of launch and byte-identical (sha256 ``1c44235c...``) to the
previous run's final 5,080,313-byte log. So a launch **copies before it
truncates**. That backup is NOT guaranteed - across 23 listings of ``Logs/``
during the previous session no backup file existed at all, and what decides it
is unmeasured - so it is a windfall to be captured, never a reason to skip
archiving. Watching the directory captures it for free; watching the log file
alone would walk straight past it.

Every interval below is chosen against an observed trigger and carries that
observation in its ``rationale``, because a number with no argument behind it
is what this project calls a confident guess.

ROADMAP item 4d - the dated root has to roll over
-------------------------------------------------

A destination named for a day has to BE that day. Arming on 2026-08-31 with a
literal ``--dest-root C:/ll-captures/2026-08-31`` keeps writing into
``2026-08-31/`` after midnight, so the directory claims to cover a day it does
not - and a MISLABELLED ARCHIVE IS WORSE THAN AN ABSENT ONE, because it gets
believed. ``--dest-base`` derives the dated root from the clock on every pass
instead, so a watcher left running past midnight begins writing into the new
day on its own.

STATED COST, and the reason a rollover RETARGETS a watcher instead of building
a fresh one: a :class:`~lanternlight.savewatch.SaveWatcher` remembers the
``(name, size, mtime_ns)`` identities it has already captured, and a new
instance forgets them. Forgetting would re-copy every unchanged file into
every new dated directory. MEASURED 2026-09-01, the live ``Saved/Logs/`` holds
3 files totalling 10,316,212 bytes (9.84 MB), so that is 10,316,212 bytes of
pure duplication per day - 3,765,417,380 bytes a year, roughly 45x the
80.12 MB across 115 files that the watchers have produced in total to date,
with OPS-14 (disk pressure) open. An unchanged 5 MB log is not a new fact just
because midnight passed. Keeping the instance and moving its destination
preserves savewatch's real contract - every CHANGED generation captured
exactly once - and lets a dated directory honestly answer "what was captured
on this day".

The caveat that buys, written down rather than left implied: a dated directory
then holds what CHANGED that day, not everything that existed that day. A day
whose sources never changed is empty or absent entirely, and reconstructing
the full state of a surface on such a day means reading back to the earlier
directory that last captured it.

ROADMAP item 4e - a watcher has to be able to say it is alive
-------------------------------------------------------------

MEASURED at the cycle 37 wrap: pid 23628 was alive for over 24 hours and had
archived nothing. With the game client shut that is the CORRECT result - and
it is indistinguishable from a wedged process. Nothing in this repo could tell
the two apart. ``armwatch.json`` is written once at arming and never touched
again, and the rollover above means a dated destination root only APPEARS when
something is archived, so the absence of one is equally consistent with "idle
and correct" and "hung since Tuesday".

:class:`Heartbeat` closes that gap, and the one property that makes it work is
that it advances because a poll pass COMPLETED, never because a file was
copied. It is opt-in via ``--heartbeat PATH``: a watcher armed by an older
session passes no such flag and must keep behaving exactly as it did, so with
the flag absent nothing here builds a heartbeat, writes a file, or makes a
syscall it did not make before.

ROADMAP item 4f - the heartbeat has to describe its own cadence
---------------------------------------------------------------

4e made a wedged surface VISIBLE. It did not make one FAIL, because a reader
holding four stamps still has to know each surface's own cadence before it can
call any of them late, and the four are 3 s, 3 s, 30 s and 300 s - one
threshold cannot judge them all. There are exactly two places that number can
come from: this file, or a literal re-typed in the reader.

The reader re-typed it once already. Cycle 38's ops layer carried its own
``SLOWEST_POLL_INTERVAL_S`` of ``300.0``; the refutation pass called that a
drift risk, and it now takes a test to hold the two copies together. Four
surfaces would be four more copies of the same defect. So ``Heartbeat.record``
takes the interval beside the surface name and the payload grows a parallel
``intervals`` map - the number that judges a stamp travels with it,
and re-tuning ``LOG_POLL_S`` moves both at once.

A surface recorded with no interval contributes NO entry, and when no surface
has supplied one the key is absent entirely rather than empty. A missing field
is absent - never ``null``, never ``{}``. That is this project's measurement
doctrine applied to its own instruments: conflating "not reported" with
"reported as nothing" is how a reader starts judging a healthy surface against
a cadence nobody measured.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lanternlight import paths
from lanternlight.savewatch import DestinationInsideRepoError, SaveWatcher

__all__ = [
    "DEST_DATE_FORMAT",
    "HEARTBEAT_FLUSH_INTERVAL_S",
    "Heartbeat",
    "WatchPlan",
    "arm",
    "dated_dest_root",
    "main",
    "run",
    "run_rolling",
    "session_plan",
]

#: Subdirectories of ``Saved/`` that carry something worth keeping. The
#: ``Saved/`` root itself is watched separately - see :func:`session_plan`.
LOGS_DIR_NAME = "Logs"
SAVE_GAMES_DIR_NAME = "SaveGames"
STANDALONE_LEVEL_DIR_NAME = "StandaloneLevel"

#: Poll intervals, seconds. Each one is argued in the matching rationale in
#: :func:`session_plan`; none of them is a round number chosen for looking
#: tidy.
MATCH_LIFETIME_POLL_S = 3.0
SAVED_ROOT_POLL_S = 30.0
LOG_POLL_S = 300.0

#: How a dated destination directory is named. ``%Y-%m-%d`` is the one common
#: date format whose lexical order and chronological order agree, so a plain
#: directory listing is already in session order, and it is what the capture
#: tree on this machine is named in.
DEST_DATE_FORMAT = "%Y-%m-%d"

#: How often the heartbeat file is rewritten, seconds. ARGUED, like every
#: other number in this module.
#:
#: WHY A THROTTLE AT ALL: :func:`run_rolling`'s production shape is one daemon
#: thread per surface, polling at 3 s, 3 s, 30 s and 300 s - which is
#: 28,800 + 28,800 + 2,880 + 288 = 60,768 completed passes a day. Flushing on
#: every one of them would rewrite this small file 60,768 times a day, and the
#: two 3-second surfaces alone would account for 57,600 of those. OPS-14 (disk
#: pressure) is open.
#:
#: WHY 30 AND NOT MORE: 30 s is a tenth of the slowest surface's own 300 s
#: cadence, so the throttle can never be the thing that makes a ``logs`` stamp
#: look stale - the lag it adds is small against the interval a reader already
#: has to tolerate for that surface.
#:
#: WHY 30 AND NOT LESS: 3 s would match the fastest surface and hand the
#: entire reduction back. At 30 s the file is rewritten at most 2,880 times a
#: day, 21x fewer.
#:
#: STATED COST: ``written`` can lag a surface's true last completed pass by up
#: to this interval, so a reader's staleness threshold must exceed
#: ``LOG_POLL_S + HEARTBEAT_FLUSH_INTERVAL_S`` (330 s) or it will call a
#: perfectly healthy watcher dead once every logs cycle. Exported so the
#: reader can import the number instead of re-typing it; ``ops`` imports
#: ``lanternlight``, never the reverse.
HEARTBEAT_FLUSH_INTERVAL_S = 30.0


@dataclass(frozen=True)
class WatchPlan:
    """One source directory, where its snapshots go, and how often to look.

    ``rationale`` is a field rather than a comment on purpose. The acceptance
    for ROADMAP 4c asks for intervals "chosen against measured triggers rather
    than guessed", and a comment drifts away from the number it explains while
    a field travels with it.
    """

    name: str
    source: Path
    dest: Path
    poll_seconds: float
    rationale: str


def session_plan(
    saved_dir: Path | str | None = None,
    dest_root: Path | str | None = None,
) -> tuple[WatchPlan, ...]:
    """Build the four-surface plan for one session.

    ``saved_dir`` defaults to the resolved live ``Saved/`` directory and
    ``dest_root`` has no default - a caller naming a destination is the point
    at which the guard in :class:`SaveWatcher` gets something to check.

    Nothing here touches the filesystem. The plan is data, so a test can
    assert against it without the game being installed.
    """
    saved = Path(paths.saved_dir()) if saved_dir is None else Path(saved_dir)
    if dest_root is None:
        raise ValueError("dest_root is required - see the PII HAZARD block in .gitignore")
    dest = Path(dest_root)

    return (
        WatchPlan(
            name="savegames",
            source=saved / SAVE_GAMES_DIR_NAME,
            dest=dest / "savegames",
            poll_seconds=MATCH_LIFETIME_POLL_S,
            rationale=(
                "StandaloneSlot_<roleId>.sav appears 17 s after EnterBattle, grows "
                "through at least 7 generations in about 70 s (2190 -> 44517 bytes), "
                "and the game deletes it roughly 13 minutes later. Sampling that "
                "slower than a few seconds records a handful of frames of a file "
                "that only exists once per run."
            ),
        ),
        WatchPlan(
            name="standalonelevel",
            source=saved / STANDALONE_LEVEL_DIR_NAME,
            dest=dest / "standalonelevel",
            poll_seconds=MATCH_LIFETIME_POLL_S,
            rationale=(
                "Shares the match lifecycle with the transient save, so it shares "
                "its 3 s cadence. Measured empty for the whole 36-minute training "
                "ground session of 2026-08-25, which is a result only because "
                "something was looking."
            ),
        ),
        WatchPlan(
            name="savedroot",
            source=saved,
            dest=dest / "savedroot",
            poll_seconds=SAVED_ROOT_POLL_S,
            rationale=(
                "AvgPrice_<id>.ini is a top-level file in Saved/, not in any "
                "subdirectory. It had filled to 343 bytes and was found back at its "
                "empty 37-byte state with nothing watching the transition, so the "
                "interval only has to be short enough to catch a state change, not "
                "to track growth."
            ),
        ),
        WatchPlan(
            name="logs",
            source=saved / LOGS_DIR_NAME,
            dest=dest / "logs",
            poll_seconds=LOG_POLL_S,
            rationale=(
                "The log reached 5,080,313 bytes in one session, so a 3 s cadence "
                "would copy gigabytes of mostly-identical prefix. A 300 s cadence "
                "took 23 generations across the 2026-08-25 session. The DIRECTORY "
                "is watched rather than the file so that a launch's "
                "MistfallHunter-backup-<UTC>.log is captured too."
            ),
        ),
    )


def dated_dest_root(dest_base: Path | str, *, now: datetime | None = None) -> Path:
    """Return ``dest_base`` with a local date appended, derived on every call.

    Never cached - a day computed once and reused is precisely the defect
    ROADMAP 4d exists to fix, so there is nowhere for a stale day to hide.

    The clock is the LOCAL one. Snapshot filenames are already stamped local
    by ``savewatch._stamp`` and the capture tree on this machine is named in
    local dates; this machine sits at UTC-5, so reading UTC here would file
    the last five hours of every local day under tomorrow.

    ``now`` is the injection point that lets a caller - chiefly a test - cross
    midnight without waiting for one.
    """
    when = datetime.now() if now is None else now
    return Path(dest_base) / when.strftime(DEST_DATE_FORMAT)


def _utc_now() -> datetime:
    """The heartbeat's own clock: UTC and aware.

    UTC here, even though :func:`dated_dest_root` is deliberately LOCAL, and
    the two are not in conflict. A dated directory is a NAME a human reads and
    the capture tree on this machine is named in local dates; a heartbeat
    stamp is a NUMBER a reader subtracts from. A local stamp goes ambiguous
    for one hour every autumn - inside the DST fold a single reading names two
    instants an hour apart, and a staleness check across it can come out
    negative and report a dead watcher as freshly alive. The game's own log
    timestamps in UTC for the same reason.
    """
    return datetime.now(UTC)


class Heartbeat:
    """A small JSON file that ADVANCES while the watcher is merely idle.

    MEASURED at the cycle 37 wrap: pid 23628 alive for over 24 hours, having
    archived nothing. With the game client shut that is the CORRECT result,
    and it is indistinguishable from a wedged process - see the 4e section of
    the module docstring. This class is the missing signal, and the property
    that makes it one is that it moves because a poll pass COMPLETED, never
    because a file was copied. A pass that copies nothing is exactly as much
    evidence that a thread is alive as one that copies a 5 MB log.

    PER-SURFACE STAMPS ARE NOT DECORATION. The four surfaces poll at 3 s, 3 s,
    30 s and 300 s. One aggregate stamp would be kept fresh by the two
    3-second threads while the 300-second ``logs`` thread - the slowest, and
    the one carrying the 5,080,313-byte log - sat wedged. A wedged single
    thread has to be visible on its own line, or the file lies by omission.

    AND THE INTERVAL TRAVELS WITH THE STAMP - ROADMAP 4f. That ``logs`` last
    completed a pass at 05:00 does not say whether it is late; only its own
    300 s cadence does, and the four surfaces do not share one. The only
    alternative was for the reader to re-type the four numbers, which it has
    already done once with ``300.0`` and had flagged as a drift risk.
    ``intervals`` is a PARALLEL map rather than a value folded in beside each
    stamp, because a reader already runs ``fromisoformat`` over those stamps
    and a shape change would break it on the first pass after an upgrade.

    NO ``fsync``, deliberately, and this is the considered contrast with
    ``ops.loop.watch.write_record``, which DOES fsync because it is a durable
    record a later cold session reads back as history. A heartbeat's entire
    value is FRESHNESS. One lost to a power cut is not a lost fact: the next
    reader correctly re-derives it as stale, which is the right answer,
    because a machine that just lost power is not running a watcher. Paying an
    fsync 2,880 times a day to durably persist a value whose only meaning is
    "recent" would buy nothing.

    THE WRITE IS STILL ATOMIC. A reader polls this file, and a torn read of a
    half-written JSON object would report a live watcher as unparseable -
    which is the same false alarm 4e exists to remove, arriving by another
    door. ``tmp.write_text(...)`` then ``tmp.replace(target)``, with the temp
    file in the target's own directory so the replace is a same-volume rename.

    LAYERING: nothing here imports from ``ops/``. ``ops.loop.watch`` imports
    ``lanternlight.armwatch``, so the reverse would be an import cycle. The
    heartbeat PATH is handed down from the ops layer as a CLI argument
    precisely so that direction holds, and this class knows nothing at all
    about who reads what it writes.

    THREAD SAFETY: the production shape gives each surface its own daemon
    thread and all four share one instance, so ``passes`` and the ``surfaces``
    map are guarded by a :class:`threading.Lock`. The ``max_passes`` shape is
    single-threaded and synchronous, so that lock is uncontended there and
    costs nothing. The lock is held ACROSS the write rather than released
    first: dropping it would let two threads interleave a stale payload over a
    fresh one and would race on the shared temporary filename, to save a
    sub-millisecond hold on threads that are about to sleep for between 3 and
    300 seconds.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        now_fn: Callable[[], datetime] = _utc_now,
        monotonic_fn: Callable[[], float] = time.monotonic,
        flush_interval_s: float = HEARTBEAT_FLUSH_INTERVAL_S,
    ) -> None:
        self.path = Path(path)
        #: Counted, not merely absorbed. A test asserting that a failing write
        #: did not stop the watcher has to know the write actually failed -
        #: otherwise it passes just as happily when the flush was never due,
        #: which is a guard that proves nothing.
        self.failed_writes = 0
        self._now_fn = now_fn
        # The throttle runs on a MONOTONIC clock, never the wall clock. An NTP
        # step backwards would otherwise freeze flushes for the length of the
        # correction, and a step forwards would spend the whole interval at
        # once. An interval is not a date.
        self._monotonic_fn = monotonic_fn
        self._flush_interval_s = flush_interval_s
        # Read once: a pid does not change, and reading it inside the flush
        # would suggest it might.
        self._pid = os.getpid()
        self._passes = 0
        self._surfaces: dict[str, str] = {}
        # Parallel to _surfaces, never merged into it: the stamps have a
        # reader that already parses them, and the cadences do not.
        self._intervals: dict[str, float] = {}
        self._last_flush: float | None = None
        self._lock = threading.Lock()

    def record(self, surface: str, poll_seconds: float | None = None) -> None:
        """Count one COMPLETED poll pass for ``surface``, flushing if due.

        Called after ``poll_once`` returns, whatever it returned. Treating an
        empty pass differently from a productive one is precisely the defect
        this class exists to remove.

        The FIRST record always writes, before the throttle has anything to
        measure against. An absent heartbeat file is ambiguous with "armed
        without ``--heartbeat``", and making a reader wait a full interval to
        resolve that would reintroduce a smaller copy of the same ambiguity.

        ``poll_seconds`` is this surface's OWN cadence, and it is what makes
        the stamp judgeable: three seconds late is a wedged ``savegames`` and
        a perfectly healthy ``logs``. It stays optional because a caller that
        does not know the cadence has to be able to say so - a default of
        ``0.0`` is a number a reader would divide by, and a default of 300
        would call a wedged 3-second surface healthy for five minutes.
        Omitted means omitted: no entry is stored and :meth:`_payload` leaves
        the key out.

        A supplied value is stored as a ``float``, because ``3`` and ``3.0``
        are the same number and different JSON tokens, and what lands in the
        file should follow the contract rather than how a caller spelled a
        literal. A value that is not a number raises here rather than being
        absorbed by :meth:`_flush_locked`, for the reason a naive clock does:
        it is a wiring error, not an environmental one.

        LAST REPORT WINS, not first. An interval re-tuned between passes is a
        new fact, and a file still quoting the old one would have a reader
        judging a 300-second surface against a 30-second window.
        """
        with self._lock:
            self._passes += 1
            self._surfaces[surface] = self._stamp()
            if poll_seconds is not None:
                self._intervals[surface] = float(poll_seconds)
            now = self._monotonic_fn()
            if self._last_flush is not None and now - self._last_flush < self._flush_interval_s:
                return
            self._flush_locked(now)

    def flush(self) -> None:
        """Write the file now, ignoring the throttle.

        Used when a run ends. The throttle exists to cap the rewrite RATE of a
        long-lived process; a process about to return has no rate left to cap,
        and withholding its final state would leave the file reporting a count
        that is knowably out of date.
        """
        with self._lock:
            self._flush_locked(self._monotonic_fn())

    def _flush_locked(self, now: float) -> None:
        """Write the file. The caller holds the lock.

        The catch names ``OSError`` and nothing wider. A watcher that dies
        because it could not write its own heartbeat is strictly worse than
        one with no heartbeat at all - but a bare ``except Exception`` would
        also swallow an ``AssertionError`` raised by a test spy, and that is
        exactly how a guard in this repo has previously been made silently
        vacuous.

        ``_last_flush`` RECORDS THE LAST SUCCESSFUL WRITE, never the last
        attempt, and that ordering is the whole of this method. The throttle
        caps the rate at which the FILE IS REWRITTEN; a flush that raised
        rewrote nothing, so it consumed none of that rate and must not spend
        any of the window. Stamping the attempt instead cost a measured false
        alarm, reproduced with every surface polling exactly on cadence:

            t=70  failed_writes=2  ->  SURFACE_STALE  stale=('savegames',)

        - a HEALTHY watcher reported as having a wedged surface. The 4f
        reader's per-surface threshold is ``k * poll + 2 * flush``, so for a
        3-second surface it is 69 s of which 60 s is flush slack, and two
        failed flushes ate that entire allowance and left about 6 s of honest
        headroom. A check that cries wolf on a healthy watcher is worse than
        no check, because it trains its reader to ignore it.

        NO BACKOFF, and here is the cost that buys. With the window left
        unspent, every subsequent :meth:`record` re-attempts the write, so a
        destination that stays broken is attempted once per completed poll
        pass - up to 60,768 times a day at the production cadence, with
        OPS-14 (disk pressure) open. That is accepted, on three arguments
        that are arithmetic rather than taste:

        - The retry ADDS NO NEW RATE. There is no retry loop here; an attempt
          rides a poll pass that was going to happen anyway, and by this line
          that pass has already run an ``iterdir`` plus a ``stat`` per entry
          inside ``SaveWatcher.poll_once``. The heartbeat attempt is a
          bounded constant on top of I/O the surface already performs.
        - The quantity the throttle exists to cap stays at ZERO while the
          destination is broken. The 60,768 figure was always a count of
          REWRITES of this file, and a failing flush rewrites it none. The
          realistic persistent failures - a parent that is a file, a removed
          volume, a denied ACL - all raise at the ``mkdir`` or the open,
          before a payload byte reaches the disk.
        - A bounded backoff needs a constant, and there is nothing to derive
          one FROM. Nobody has measured how long a heartbeat destination
          stays broken here, and this project omits a number rather than
          guessing one. The one retry interval that IS measured is the
          surface's own cadence, which a per-pass attempt already uses.

        THE CAVEAT, written down rather than left implied: one failure mode
        does put bytes on the disk per attempt - a payload written in full
        that then fails at ``tmp.replace``, which on Windows is what a reader
        holding the target open without share-delete produces. At roughly
        400 bytes a payload that is about 24 MB a day of writes immediately
        thrown away. It is also the mode where retrying is most obviously
        right, because that collision is transient by construction and the
        next attempt lands. A persistent ``replace``-stage failure has never
        been observed; if one ever is, that measurement is what a backoff
        constant would be derived from, and it does not exist yet.

        ``failed_writes`` therefore counts failed ATTEMPTS, not failed
        intervals, and under a broken destination it climbs at the pass rate.
        That is the intended reading: it is the number that separates "this
        watcher cannot write" from "this watcher is idle".
        """
        try:
            self._write(self._payload())
        except OSError:
            self.failed_writes += 1
            return
        self._last_flush = now

    def _payload(self) -> str:
        """The complete file contents. The caller holds the lock.

        ``ensure_ascii=True`` is stated rather than left to the default: the
        repo is 7-bit ASCII by rule, and it is also what makes this call
        unable to raise ``UnicodeEncodeError`` - which is not an ``OSError``
        and so would NOT be absorbed by :meth:`_flush_locked`.

        Surfaces are sorted so two heartbeats differ only where the facts
        differ. Insertion order would follow whichever thread happened to
        finish its first pass first, which is not a fact about anything.

        The result settles at a fixed width once every surface has reported
        once - at most four second-resolution stamps, at most four intervals,
        a pid and a counter - and after that only the digits of ``passes``
        move. It is REPLACED on every flush and never appended to, so it does
        not grow.
        """
        body: dict[str, object] = {
            "pid": self._pid,
            "written": self._stamp(),
            "passes": self._passes,
            "surfaces": dict(sorted(self._surfaces.items())),
        }
        # ABSENT, not empty. ``{}`` would assert that four surfaces have no
        # cadence, which is a claim nobody measured; leaving the key out says
        # only that none has reported one, which is the fact.
        if self._intervals:
            body["intervals"] = dict(sorted(self._intervals.items()))
        return json.dumps(body, ensure_ascii=True, indent=2) + "\n"

    def _stamp(self) -> str:
        """One UTC, second-resolution ISO 8601 reading. Caller holds the lock.

        Resolution and timezone are enforced HERE rather than trusted from
        ``now_fn``, so an injected clock cannot quietly widen the contract. A
        NAIVE reading is refused instead of guessed at: assuming local would
        be wrong for five hours of every day on this machine, and inside a DST
        fold one naive reading names two instants an hour apart. That is a
        wiring error rather than an environmental one, so it sits deliberately
        outside what :meth:`_flush_locked` absorbs.
        """
        when = self._now_fn()
        if when.tzinfo is None:
            raise ValueError(
                "a heartbeat clock must return an aware datetime - a naive stamp "
                "is ambiguous across the DST fold and a reader cannot subtract it"
            )
        return when.astimezone(UTC).replace(microsecond=0).isoformat()

    def _write(self, payload: str) -> None:
        """Atomically replace the heartbeat file. May raise ``OSError``.

        The temp file carries this process's pid, so two watchers pointed at
        one path cannot collide on it; within one process the lock already
        serialises the write. A failed write removes its own temp file rather
        than leaving litter beside a file a reader is polling.

        ``newline="\\n"`` because on Windows ``write_text`` otherwise turns
        every LF into CRLF: the bytes on disk would not be the bytes computed,
        and a reader measuring a size or a hash would get a different answer
        from the writer. Measured trap, see CLAUDE.md.
        """
        target = self.path
        tmp = target.with_name(f"{target.name}.{self._pid}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(payload, encoding="utf-8", newline="\n")
            tmp.replace(target)
        except OSError:
            with contextlib.suppress(OSError):
                tmp.unlink(missing_ok=True)
            raise


def arm(plans: Sequence[WatchPlan]) -> list[SaveWatcher]:
    """Construct one :class:`SaveWatcher` per plan, or refuse the whole set.

    Every watcher is built before any of them is returned, so a bad
    destination anywhere in the plan raises
    :class:`~lanternlight.savewatch.DestinationInsideRepoError` before a
    single directory has been created. Construction never touches the
    filesystem, which is what makes that all-or-nothing property free.
    """
    return [SaveWatcher(plan.source, plan.dest) for plan in plans]


def run(
    plans: Sequence[WatchPlan],
    *,
    max_passes: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    log_fn: Callable[[str], None] | None = None,
) -> list[SaveWatcher]:
    """Arm ``plans`` and poll them.

    ``max_passes=None`` is the production shape: one daemon thread per plan,
    each polling at its own interval, and this call blocks until interrupted.
    A finite ``max_passes`` runs every plan that many passes synchronously
    with no sleeping, which is how a test drives this without threads or
    wall-clock time.

    Returns the armed watchers so a caller can inspect what it got.
    """
    watchers = arm(plans)
    say = log_fn if log_fn is not None else (lambda message: print(message, flush=True))

    for plan in plans:
        say(f"armed {plan.name}: {plan.source} -> {plan.dest} every {plan.poll_seconds:g}s")

    if max_passes is not None:
        for plan, watcher in zip(plans, watchers, strict=True):
            watcher.run(
                poll_seconds=plan.poll_seconds,
                max_passes=max_passes,
                sleep_fn=lambda _seconds: None,
            )
        return watchers

    threads = [
        threading.Thread(
            target=watcher.run,
            kwargs={"poll_seconds": plan.poll_seconds, "sleep_fn": sleep_fn},
            name=f"armwatch-{plan.name}",
            daemon=True,
        )
        for plan, watcher in zip(plans, watchers, strict=True)
    ]
    for thread in threads:
        thread.start()
    say("watching - interrupt to stop")
    try:
        while True:
            sleep_fn(60.0)
    except KeyboardInterrupt:
        say("stopped")
    return watchers


class _RollingSurface:
    """One surface's watcher, RETARGETED when the local day rolls over.

    The watcher INSTANCE survives the rollover on purpose - see the STATED
    COST in the module docstring. Each surface also carries its own day and
    its own watcher rather than sharing one set of state, so the threaded
    shape needs no lock and a snapshot always lands in the directory named for
    the clock reading that produced it, not for whichever day some other
    thread happened to observe first.
    """

    def __init__(
        self,
        name: str,
        saved_dir: Path | str | None,
        dest_base: Path | str,
        *,
        now: datetime,
    ) -> None:
        self._name = name
        self._saved_dir = saved_dir
        self._dest_base = Path(dest_base)
        self.plan = self._plan_for(now)
        self.watcher = SaveWatcher(self.plan.source, self.plan.dest)
        self.day = now.strftime(DEST_DATE_FORMAT)

    def _plan_for(self, now: datetime) -> WatchPlan:
        """This surface's plan against the dated root for ``now``.

        Routed through :func:`session_plan` rather than reconstructing the
        layout here, so the mapping from surface to subdirectory has exactly
        one definition and a renamed surface fails loudly with a ``KeyError``
        instead of quietly archiving into a new directory nobody expected.
        """
        root = dated_dest_root(self._dest_base, now=now)
        return {plan.name: plan for plan in session_plan(self._saved_dir, root)}[self._name]

    def retarget(self, now: datetime) -> bool:
        """Adopt the dated root for ``now``. True when the day actually changed.

        The destination guard is re-run here, never skipped. Constructing a
        ``SaveWatcher`` is the ONLY sanctioned place that check lives, so a
        throwaway one is built purely to run it rather than re-implementing
        the check here where it could drift out of step with ``savewatch``.
        Construction touches no filesystem, so the throwaway costs nothing and
        leaves nothing behind. If it refuses, this surface keeps the
        destination it already had and the refusal propagates: a capture base
        that has acquired a git checkout is a reason to stop, not a reason to
        write roleId-bearing save files into it.
        """
        day = now.strftime(DEST_DATE_FORMAT)
        if day == self.day:
            return False
        plan = self._plan_for(now)
        self.watcher.dest_dir = SaveWatcher(plan.source, plan.dest).dest_dir
        self.plan = plan
        self.day = day
        return True


def _arm_rolling(
    saved_dir: Path | str | None,
    dest_base: Path | str,
    *,
    now: datetime,
) -> list[_RollingSurface]:
    """Build one rolling surface per plan, EAGERLY, or refuse the whole set.

    Eager on purpose. Deferring construction to the first poll would move the
    destination refusal from arm time to poll time - the same guard, fired
    after the operator has gone back to the game instead of while they are
    still watching the console. ``SaveWatcher.__init__`` touches no
    filesystem, so a refusal partway through this list still leaves nothing
    created.
    """
    plans = session_plan(saved_dir, dated_dest_root(dest_base, now=now))
    return [_RollingSurface(plan.name, saved_dir, dest_base, now=now) for plan in plans]


def run_rolling(
    saved_dir: Path | str | None,
    dest_base: Path | str,
    *,
    max_passes: int | None = None,
    now_fn: Callable[[], datetime] = datetime.now,
    sleep_fn: Callable[[float], None] = time.sleep,
    log_fn: Callable[[str], None] | None = None,
    heartbeat: Heartbeat | None = None,
) -> list[SaveWatcher]:
    """Arm the session under ``dest_base`` and keep the dated root current.

    Every pass derives the day from ``now_fn()``. When it differs from the day
    a surface is using, that surface is retargeted at the new dated root - not
    rebuilt - and polling continues.

    ``max_passes=None`` is the production shape: one daemon thread per
    surface, each polling at its own interval, blocking until interrupted. A
    finite ``max_passes`` runs every surface that many passes synchronously,
    with no threads and no sleeping, which is how a test drives a midnight
    crossing in no wall-clock time. ``max_passes=0`` arms and polls nothing,
    which is how a test asks whether the refusal really happens at arm time
    rather than on the first poll.

    ``heartbeat`` is optional and defaults to ``None``, which is the shape
    every caller before ROADMAP 4e used: with it absent this function builds
    nothing, writes nothing, and makes no syscall it did not make before.
    Given one, every surface records a pass against it AFTER ``poll_once``
    returns - whatever ``poll_once`` returned - because a pass that copied
    nothing is exactly as much evidence of liveness as one that copied a log.
    A bounded run flushes once at the end, and so does an interrupted
    threaded one, since the throttle exists to cap a rate and a run that is
    over has no rate left to cap. BOTH shapes hand the surface's own
    ``poll_seconds`` across with the name - a reader cannot call a stamp late
    without it, and a shape that passed only the name would leave the
    heartbeat describing three surfaces out of four.

    Returns the armed watchers so a caller can inspect what it got.
    """
    surfaces = _arm_rolling(saved_dir, dest_base, now=now_fn())
    say = log_fn if log_fn is not None else (lambda message: print(message, flush=True))

    for surface in surfaces:
        plan = surface.plan
        say(f"armed {plan.name}: {plan.source} -> {plan.dest} every {plan.poll_seconds:g}s")

    if max_passes is not None:
        for _ in range(max_passes):
            now = now_fn()
            for surface in surfaces:
                if surface.retarget(now):
                    say(f"rolled {surface.plan.name} over to {surface.plan.dest}")
                surface.watcher.poll_once(now=now)
                if heartbeat is not None:
                    heartbeat.record(surface.plan.name, surface.plan.poll_seconds)
        if heartbeat is not None:
            heartbeat.flush()
        return [surface.watcher for surface in surfaces]

    def poll_forever(surface: _RollingSurface) -> None:
        while True:
            now = now_fn()
            try:
                if surface.retarget(now):
                    say(f"rolled {surface.plan.name} over to {surface.plan.dest}")
            except DestinationInsideRepoError as exc:
                # A thread that dies silently takes a whole surface's archive
                # with it and nothing on the console says so.
                say(f"stopping {surface.plan.name} - {exc}")
                return
            surface.watcher.poll_once(now=now)
            # After the pass, never before: the stamp claims a COMPLETED pass.
            # A surface whose thread returned above (a destination that has
            # acquired a git checkout) correctly stops advancing here, which
            # is what makes a stopped surface visible to a reader.
            if heartbeat is not None:
                heartbeat.record(surface.plan.name, surface.plan.poll_seconds)
            sleep_fn(surface.plan.poll_seconds)

    threads = [
        threading.Thread(
            target=poll_forever,
            args=(surface,),
            name=f"armwatch-{surface.plan.name}",
            daemon=True,
        )
        for surface in surfaces
    ]
    for thread in threads:
        thread.start()
    say("watching - interrupt to stop")
    try:
        while True:
            sleep_fn(60.0)
    except KeyboardInterrupt:
        say("stopped")
    # One last honest reading on the way out. After this the file stops
    # advancing, which is exactly what a reader should see for a watcher that
    # has been stopped.
    if heartbeat is not None:
        heartbeat.flush()
    return [surface.watcher for surface in surfaces]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Arm every Lanternlight session watcher from one entry point."
    )
    parser.add_argument(
        "--saved-dir",
        type=Path,
        default=None,
        help="the game's Saved/ directory (default: resolved from LOCALAPPDATA)",
    )
    # Exactly one destination. Neither leaves the watchers with nowhere to
    # archive to; both is a question about which one the operator meant, and
    # guessing at that is how an archive ends up half in each place.
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--dest-root",
        type=Path,
        default=None,
        help=(
            "a LITERAL directory for snapshots, with nothing appended - must "
            "sit outside every git working directory"
        ),
    )
    destination.add_argument(
        "--dest-base",
        type=Path,
        default=None,
        help=(
            "a base directory; snapshots go under a <YYYY-MM-DD> subdirectory "
            "of it that rolls over at local midnight"
        ),
    )
    parser.add_argument(
        "--max-passes",
        type=int,
        default=None,
        help="stop after this many passes per watcher (default: run until interrupted)",
    )
    # A PATH, not a flag, and it comes from the layer above. ops.loop.watch
    # imports this module, so this module must not import ops - handing the
    # destination down as an argument is what keeps that direction one-way.
    # Not part of the mutually exclusive group above: it is not a destination,
    # and the one pairing it cannot honour is rejected in main() with a reason
    # rather than by a usage line that cannot explain itself.
    parser.add_argument(
        "--heartbeat",
        type=Path,
        default=None,
        help=(
            "write a small JSON liveness file at this path, advancing on every "
            "completed poll pass including passes that archive nothing "
            "(requires --dest-base)"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on a clean run, non-zero on a refused destination.

    ``--dest-base`` routes through :func:`run_rolling`, which re-derives the
    dated root as the day changes. ``--dest-root`` keeps its original literal
    meaning exactly: the directory named is the directory written to.

    ``--heartbeat`` is honoured on the ``--dest-base`` path and REFUSED with
    ``--dest-root``, rather than accepted and quietly ignored. A silently
    ignored flag is a trap: the reader would poll a path nothing ever writes
    and report a perfectly healthy watcher as dead, which is the same false
    signal ROADMAP 4e exists to remove, arriving from the opposite direction.
    """
    args = parse_args(argv)
    if args.heartbeat is not None and args.dest_root is not None:
        # Exit 2, matching both argparse's usage-error code and the refusal
        # below, because this IS a usage error.
        print(
            "refusing to arm: --heartbeat requires --dest-base, not --dest-root. "
            "The heartbeat is written by the rolling watcher; --dest-root runs "
            "the literal-destination path, which would accept the flag and never "
            "write the file. Re-run with --dest-base.",
            file=sys.stderr,
            flush=True,
        )
        return 2
    try:
        if args.dest_base is not None:
            # Constructing a Heartbeat touches no filesystem, so building it
            # before run_rolling has had its chance to refuse the destination
            # still leaves nothing behind if it does.
            beat = None if args.heartbeat is None else Heartbeat(args.heartbeat)
            run_rolling(
                args.saved_dir,
                args.dest_base,
                max_passes=args.max_passes,
                heartbeat=beat,
            )
        else:
            plans = session_plan(args.saved_dir, args.dest_root)
            run(plans, max_passes=args.max_passes)
    except DestinationInsideRepoError as exc:
        print(f"refusing to arm: {exc}", file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via main()
    raise SystemExit(main())
