"""Session-scoped lane governor - the wiring that arms :mod:`ops.lane_slot`.

``ops/lane_slot.py`` re-implements the cross-project lane protocol: the lock
namespace, the key strings and the five-field payload. It was complete and
UNARMED. Measured on 2026-09-11, nothing in this tree called ``acquire_lane``
or ``hold_lane`` - the two names appeared only in that module, its own tests
and ``docs/adr/ADR-008-join-the-shared-bucket.md``. A protocol nobody calls
rations nothing, so the operator's ruling of 2026-09-10 ("yes, join the shared
bucket") was recorded in code and not yet in behaviour. This module is the
wiring that closes that gap.

Why the lane is held for a SESSION and not for a cycle
------------------------------------------------------

The budget being rationed is the machine's - and the account's - concurrency,
and this project consumes it continuously for as long as a loop session is
alive. It is not consumed in bursts that happen to line up with cycle
boundaries: a session between cycles is still holding a worktree, still about
to run a suite, and still the thing a sibling's loop would be contending with.
Releasing at the end of every cycle would therefore hand back a slot this
session is still effectively using, and inviting somebody else to take it.

The second reason is what a per-cycle acquire would do when the answer came
back BUSY. Mid-loop, there is no good response: the session cannot stop (it
holds the single-instance lock and has work in flight), and it must not spin
waiting (a governor that blocks turns a coordination miss into a hang). A
session-scoped acquire asks the question once, at the only moment when
"somebody else is using the machine, so this session does not start" is an
answer a caller can actually act on.

Session scope also makes this the exact PEER of the two governors already in
this package, which is why it reads like them and is documented beside them:

* :func:`ops.loop.guard.released` - the single-instance lock, one per session;
* :func:`ops.loop.watch.session_armed` - the session watcher, armed once;
* :func:`session_lane` - the lane slot, held once.

All three are taken in one ``with`` statement at the top of a loop, all three
answer a refusal in words rather than by raising, and none of them terminates
anything.

What this module promises
-------------------------

* **It never blocks and never spins.** One attempt. BUSY is a first-class
  answer carried in :class:`LaneStatus`, not an exception.
* **It answers in THREE states, not two.** HELD, BUSY and UNUSABLE. The third
  is a bucket that cannot be operated at all, and it is reported loudly and
  separately rather than folded into BUSY - see :func:`session_lane` for why
  the loop then proceeds ungoverned and why the wording may never be shared.
* **It DELETES STALE LOCKS THAT IT DID NOT WRITE.** This is the behaviour that
  changed under ``OPS-76`` and it is stated here, first, rather than as a
  footnote, because three shipped documents asserted the opposite of it for a
  day. Every acquire runs :func:`ops.lane_slot.reap_for_acquire` before it
  walks the candidate slots, so a STALE lock in the first-come SURPLUS
  namespace is reclaimed regardless of which project wrote it. That is the
  scheme working exactly as ``docs/adr/ADR-008-join-the-shared-bucket.md``
  describes it - the surplus namespace is first-come and every participant's
  reaper is expected to understand it - and not a unilateral deletion.

  Four limits bound it, and each one is a test rather than a promise here:

  - it NEVER reclaims another participant's ``reserved-<key>.lock``, however
    stale that lock looks - only our own floor and the surplus names. See
    :func:`ops.lane_slot.is_ours_to_reclaim`. The accepted blind spot follows
    directly: a sibling's genuinely leaked FLOOR is never reclaimed by us, and
    sits in the bucket until an operator runs :func:`ops.lane_slot.reap` by
    hand;
  - it NEVER removes a lock that is not stale, whoever owns it;
  - STALE is not an age check. :func:`ops.lane_slot.is_stale` demands evidence
    in three arms: an unreadable payload or a missing or non-numeric timestamp
    counts as stale, a timestamp older than
    :data:`ops.lane_slot.STALE_SECONDS` - four and a half hours - counts as
    stale, and otherwise the lock is stale only when the pid it records is not
    alive;
  - it never touches a filename outside the scheme, because
    :func:`ops.lane_slot.reap` applies :func:`ops.lane_slot.is_slot_name` first
    and the narrowing predicate second.

  **The honest consequence, written out because it is new and it is shared
  state:** this project now DELETES FILES from a directory other projects' live
  loops depend on - the all-users bucket at ``PROGRAMDATA/lw-loop/slots``.
  Measured on 2026-09-11, that bucket holds one lock, ``0.lock``, which is stale
  by BOTH arms: the pid it records is dead and its timestamp is about 33 hours
  old. The next real acquire this project makes on this machine will therefore
  remove it. The release path itself is unchanged and still narrow -
  :func:`ops.lane_slot.release` unlinks the single lock it was handed, nothing
  else - but it is no longer the only unlink on the acquire path.
* **It releases on the way out even when the body raises**, because the
  ``finally`` that does it lives in :func:`ops.lane_slot.hold_lane` and this
  module composes on that rather than reimplementing it.
* **Nothing happens at import time.** No directory, no lock, no port, no
  network, no clock read. The run id is computed on first use.

The repository path, and why it is on the wire but never in a report
--------------------------------------------------------------------

The payload's ``repo`` field carries this checkout's filesystem path. That is a
deliberate match to the observed wire - the sibling lock read on 2026-09-10
carried its own checkout path in the same field - and the lock it goes into is
not committed, not sent anywhere, and lives in a directory on this machine.

It is still a path on the operator's machine, so it goes exactly one place and
no further. It is NOT a field of :class:`LaneStatus` and it is NOT in
:meth:`LaneStatus.status_line`.

NO ABSOLUTE PATH REACHES A PRINTED LINE AT ALL, which is wider than the repository
root and is wider than this module's first attempt at the rule. Corrected on
2026-09-11: :func:`_display_bucket` used to rewrite only a bucket lying INSIDE
this checkout and printed every other one verbatim, which is backwards, because
the bucket this project actually contends in is outside the checkout and
``LL_LANE_SLOT_ROOT`` - recommended by ``docs/HEADLESS.md`` for withdrawing from
the shared budget - can point anywhere, including under the operator's profile,
where a path segment is the operator's ACCOUNT NAME. That rendering now
enumerates the safe cases and elides everything else, and it is the only
rendering that ``status_line`` and every ``reason`` string use. See the
redaction rules in ``CLAUDE.md``: the scope is a class of data and a direction,
not a file format, and a line printed every cycle and pasted into a hand-off is
a direction.

The honest caveat about ``order``
---------------------------------

:attr:`LaneStatus.order` is the try order this module measured immediately
before the acquire. :func:`ops.lane_slot.hold_lane` looks at the bucket again
for itself, so if another participant writes the first reserved name into the
bucket between the two looks, the reported order is the earlier of two
readings. The slot actually taken is never a guess - it comes back from the
acquire - so ``order`` is advisory and ``slot`` is evidence.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from ops import lane_slot
from ops.loop import state

__all__ = [
    "LaneStatus",
    "current_cycle",
    "repo_root",
    "session_lane",
    "session_run_id",
]

#: Repository root, resolved from this file's location: ops/loop/lane.py.
_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Computed on first use, never at import. ``None`` until then.
_RUN_ID: str | None = None


def repo_root() -> Path:
    """This checkout's root directory.

    Exposed so a test can ask what must NOT appear in a status line without
    writing the answer down as a literal - a guard that hardcodes the value it
    protects is scoped to one value, which is the same defect one level down.
    """
    return _REPO_ROOT


def session_run_id() -> str:
    """A run id that is stable for this session and distinct between sessions.

    Stability matters because the field is how an operator reading the bucket
    tells one session holding two lanes from two sessions holding one each. If
    it changed per acquire, that question would become unanswerable from the
    bucket alone.

    Distinctness comes from two independent sources rather than one: the
    process id, and a nanosecond clock reading taken the first time this is
    called. A pid alone repeats - Windows reuses them freely - and a clock
    alone collides between two interpreters started in the same nanosecond,
    which is unlikely rather than impossible. Neither is a cryptographic
    identifier and neither is claimed to be.

    Computed lazily. Reading a clock at import time is a side effect, and this
    module promises to have none.
    """
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = f"ll-{os.getpid()}-{time.time_ns():x}"
    return _RUN_ID


def current_cycle() -> int:
    """The loop's cycle number from ``ops/runtime/loop_state.json``.

    :func:`ops.loop.state.load` is documented never to raise - a missing or
    corrupt state file comes back as cycle 0 with a recovery note - so this is
    a thin read rather than a defensive one. Cycle 0 is an honest answer here:
    it means nothing has run yet, which is exactly the situation at the top of
    a fresh loop, and a lock recording cycle 0 is not lying about anything.
    """
    return int(state.load().cycle)


def _bucket_fingerprint(text: str) -> str:
    """A short, stable, non-reversible label for a bucket path.

    It exists so that eliding a path does not also destroy the operator's
    ability to tell two buckets apart, or to see that the bucket changed
    between one cycle and the next. It is a truncated digest of the path and
    nothing else: it carries no segment of it, it is not a secret, and it is
    not claimed to be a cryptographic identifier.
    """
    digest = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()
    return digest[:8]


def _display_bucket(bucket: Path) -> str:
    """Render a bucket so that NO absolute path can reach a printed line.

    Three renderings, and the fallback is the strict one:

    * a bucket under this checkout becomes ``<repo>/...``, because the
      in-repository fallback bucket lives there and the repository root is a
      path on the operator's machine;
    * the shared machine bucket becomes ``<all-users>/lw-loop/slots``. Only the
      NAMESPACE is named, never the all-users root it hangs under, and that
      namespace is a wire fact held in this tree's own source
      (:data:`ops.lane_slot.SHARED_BUCKET_RELATIVE`) rather than a string read
      off the operator's machine;
    * anything else is ELIDED entirely, down to a fingerprint.

    WHY THE FALLBACK IS ELISION AND NOT THE PATH, which is the correction made
    on 2026-09-11. This function used to return ``str(bucket)`` unchanged for
    every bucket that was not under the repository root, and that is backwards
    for the two buckets this project actually uses. The shared machine bucket is
    outside the checkout by definition, and ``LL_LANE_SLOT_ROOT`` - which
    ``docs/HEADLESS.md`` recommends as the way to withdraw from the shared
    budget - can point anywhere at all, including under the operator's profile,
    where a path segment IS the operator's account name. ``CLAUDE.md`` names an
    account name an operator identifier, and the redaction rule there is scoped
    to a CLASS OF DATA and a DIRECTION rather than to a file format: a status
    line printed every cycle, pasted into a hand-off and read back by a later
    session is a direction. So the safe set is enumerated and everything
    outside it is elided, rather than the unsafe set being enumerated and
    everything outside THAT being printed.

    ``status.bucket`` still carries the real path for code that needs it. It is
    this rendering, and only this rendering, that is printed.
    """
    try:
        resolved = bucket.resolve()
    except OSError:  # pragma: no cover - resolve() is non-strict here
        resolved = bucket
    try:
        relative = resolved.relative_to(_REPO_ROOT)
    except (ValueError, OSError):
        pass
    else:
        return "<repo>/" + relative.as_posix()
    shared = lane_slot.shared_root()
    if shared is not None:
        try:
            shared_resolved = shared.resolve()
        except OSError:  # pragma: no cover - resolve() is non-strict here
            shared_resolved = shared
        if resolved == shared_resolved:
            return "<all-users>/" + lane_slot.SHARED_BUCKET_RELATIVE.as_posix()
    return f"<elided bucket #{_bucket_fingerprint(str(resolved))}>"


@dataclass(frozen=True)
class LaneStatus:
    """What actually happened when this session asked for a lane.

    Read this and you know whether Lanternlight is rationing with anybody:
    ``held`` says whether a lane was taken, ``slot`` and ``reserved`` say which
    one, ``bucket`` says where, ``scheme`` says whether the reserved-floor
    widening has landed there, and ``order`` says what was tried.

    ``repo`` is deliberately absent. It is on the wire because the protocol
    puts it there, and it is not in this object because this object is what
    gets printed, logged and pasted into a hand-off.

    Attributes:
        held: Whether a lane is held for the duration of the block.
        slot: The lock filename taken, or ``None`` when busy.
        reserved: Whether the slot taken is this repository's own floor, as
            opposed to a first-come surplus slot. "Did I get my guarantee or
            did I get lucky" is the question an operator asks on a busy
            machine.
        bucket: The bucket directory that was contended for.
        scheme: One of :data:`ops.lane_slot.RESERVED_PRESENT`,
            :data:`ops.lane_slot.RESERVED_ABSENT` or
            :data:`ops.lane_slot.RESERVED_UNKNOWN`. Three answers, not two:
            "I looked and found no reserved name" and "I could not look" are
            different facts about the bucket.
        order: The slot names in the order this module measured just before the
            acquire. Advisory; see the module docstring.
        key: This repository's key in the cross-project scheme.
        run_id: The session run id written into the payload.
        cycle: The loop cycle number written into the payload.
        reason: One sentence, in words, saying what happened. A BUSY answer
            says BUSY here rather than being inferable from ``held is False``,
            and an UNUSABLE answer says UNUSABLE for the same reason.
        usable: Whether the bucket could be operated at all. ``False`` is the
            THIRD state - see :func:`session_lane` - and it is never the same
            fact as a busy bucket. ``held`` and ``usable`` together are the
            whole answer: held is HELD, not held but usable is BUSY, and not
            usable is UNUSABLE. Defaulted to ``True`` so that constructing a
            status by hand describes a working bucket unless it says otherwise,
            which is the reading a cold session will guess.
    """

    held: bool
    slot: str | None
    reserved: bool
    bucket: Path
    scheme: str
    order: tuple[str, ...]
    key: str
    run_id: str
    cycle: int
    reason: str
    usable: bool = True

    def status_line(self) -> str:
        """One line a loop can print, carrying no repository path.

        Names the bucket, the slot taken or the refusal, and the
        reserved-scheme state - the three things that decide whether a reader
        needs to do anything. See ``docs/HEADLESS.md`` for what to do about a
        BUSY one and what to do about an UNUSABLE one, which are different
        actions.

        FOUR BRANCHES, NOT THREE, and the words are deliberately unalike.
        HELD, BUSY, UNUSABLE and OPTED OUT have to be distinguishable by a
        reader skimming a cycle's output, not merely by a caller reading two
        booleans, because the only place the last two are ever seen is this
        line. A shared phrase between BUSY and either of them would be the
        silent-fallback defect with better manners: the operator would read
        familiar words and act on the wrong condition, and only one of the four
        clears by itself.

        THE FOURTH ARRIVED LATE AND THAT IS THE LESSON, ``OPS-77``. The opt-out
        branch was added to :func:`session_lane` and this method still built
        BUSY from ``held`` and ``usable`` alone, so the reason field said OPTED
        OUT while the line a human actually reads said BUSY. A status line
        derived from two booleans cannot represent a third refusal, and the
        wrong half is the half that gets printed.
        """
        if not self.usable:
            took = "UNUSABLE - bucket cannot be operated, running ungoverned"
        elif not self.held and lane_slot.OPT_OUT_STATUS in self.reason:
            took = lane_slot.OPT_OUT_STATUS
        elif self.held and self.slot is not None:
            floor = "own reserved floor" if self.reserved else "surplus"
            took = f"HELD {self.slot} ({floor})"
        else:
            took = "BUSY - no slot free"
        return (
            f"lane[{self.key}]: {took} | bucket {_display_bucket(self.bucket)} "
            f"| reserved scheme {self.scheme}"
        )


def _busy_reason(bucket: Path, order: tuple[str, ...], scheme: str) -> str:
    """The words a BUSY answer carries. Written out, never inferred."""
    tried = ", ".join(order) if order else "(no slot names to try)"
    return (
        "BUSY - every lane slot this repository may take is held. Tried "
        f"{tried} in {_display_bucket(bucket)}; reserved scheme is {scheme}. "
        "This is not an error and nothing was written. Another project on this "
        "machine is using the concurrency budget."
    )


def _opt_out_reason(scheme: str) -> str:
    """The words an OPTED OUT answer carries. Never the words BUSY carries.

    ``OPS-77``. A zero surplus width is a configuration choice, and a choice
    that never clears by retrying must not wear BUSY - BUSY is the one condition
    a caller is expected to shrug off. It must not wear UNUSABLE either: the
    bucket is fine and nobody asked to contend for it.

    No bucket path appears here. The exception raised one layer down puts an
    absolute path in its message and this branch deliberately does not pass that
    through, for the reason ADR-004 gives about an identifier leaving the
    machine in a hand-off.
    """
    return (
        f"{lane_slot.OPT_OUT_STATUS}. Nothing was written and no slot was "
        f"reserved; the reserved scheme would have been {scheme}. This does not "
        "clear by retrying - set a non-zero surplus width to rejoin."
    )


def _unusable_reason(bucket: Path, detail: str) -> str:
    """The words an UNUSABLE answer carries. Never the words BUSY carries.

    ``detail`` is the CLASS NAME of the underlying operating-system error and
    nothing else - deliberately not the message. The message raised by
    :mod:`ops.lane_slot` contains the absolute path it failed on, and that path
    is either this checkout's root (the in-repository fallback bucket) or a
    directory under the operator's profile, both of which are exactly what a
    status line printed into a loop's output must not carry. The class name says
    what kind of fault it was without saying where.

    THAT WAS ONLY HALF THE LEAK, and the other half stood for a day. Suppressing
    the exception's message never stopped the BUCKET from being interpolated on
    the line below, and until :func:`_display_bucket` was corrected on
    2026-09-11 that interpolation printed the failing path verbatim for every
    bucket outside this checkout - which is every bucket this project actually
    uses. The promise that an UNUSABLE answer names no absolute path is kept by
    the rendering, not by this docstring; what this function contributes is only
    that the error's own message is never quoted. See the redaction rules in
    ``CLAUDE.md``: the scope is a class of data and a direction.
    """
    return (
        "UNUSABLE - this bucket could not be created, listed or written, so no "
        f"lane was requested and none was taken. {_display_bucket(bucket)} "
        f"failed with {detail}; reserved scheme reads unknown because the "
        "directory was never successfully read. This session is running "
        "UNGOVERNED: it is rationing with nobody and is not counted against "
        "the machine's concurrency budget by anyone else. It does NOT clear on "
        "its own - a busy bucket does, and this one waits for a person. Check "
        "that the bucket's parent is a directory this account may write."
    )


def _held_reason(held: lane_slot.Held, bucket: Path, scheme: str) -> str:
    """The words a successful answer carries."""
    floor = "this repository's own reserved floor" if held.reserved else "a surplus slot"
    return (
        f"held {held.name}, which is {floor}, in {_display_bucket(bucket)}; "
        f"reserved scheme is {scheme}."
    )


@contextlib.contextmanager
def session_lane(
    *,
    cycle: int | None = None,
    root: Path | str | None = None,
    key: str = lane_slot.REPO_KEY,
    surplus: int | None = None,
    repo: str | None = None,
    run_id: str | None = None,
    log=None,
) -> Iterator[LaneStatus]:
    """Hold one lane slot for the duration of a session.

    The peer of :func:`ops.loop.guard.released` and
    :func:`ops.loop.watch.session_armed`, and taken in the same ``with``
    statement as both. See the module docstring for why the scope is a session
    and not a cycle.

    Never blocks, never retries in a spin, and never deletes a lock it did not
    create. A full bucket yields a :class:`LaneStatus` with ``held`` False and
    a ``reason`` that says BUSY in words; the body still runs, because what a
    busy machine means is the caller's decision and not this module's. That
    mirrors :func:`ops.loop.guard.released`'s posture in the one way that
    matters - a governor that blocks by default turns a coordination miss into
    a hang - while differing in the other: the guard RAISES ``LockBusy``
    because a second loop must not start at all, and this yields, because a
    session with no lane is merely unrationed rather than incorrect.

    THE THIRD STATE - UNUSABLE, and why it is never collapsed into BUSY
    -------------------------------------------------------------------

    :class:`ops.lane_slot.BucketUnusable` is raised one layer down when the
    bucket cannot be created, listed or written at all - a root whose parent is
    a file, a read-only volume, a directory this account may not write, a
    listing that is refused. That is a configuration fault, and it is an
    exception rather than a ``None`` precisely so that it cannot be mistaken
    for contention: ``None`` means every candidate slot is taken, which is
    normal and self-clearing, while this clears only when somebody fixes it.

    This function CATCHES it and yields a status with ``held`` False,
    ``usable`` False, and a ``reason`` that says UNUSABLE in words, naming what
    could not be done. It does not re-raise, and it does not reuse the BUSY
    wording. Both halves of that are deliberate.

    It does not re-raise because an unattended loop that refuses to start
    because a lock directory is misconfigured has converted a coordination
    problem into an outage. The operator is playing the game and is the one
    person who cannot fix a permission on a shared directory right now, and a
    loop that will not run does no work at all, where a loop that runs
    unrationed does all of its work and merely does it without coordinating.
    The failure mode of proceeding is a busy machine; the failure mode of
    refusing is no machine.

    It does not reuse the BUSY wording because a session rationing with nobody
    has to SAY SO, in its own status line, every single cycle. That is the
    whole price of proceeding. Collapsing the two would reintroduce here, one
    layer up, the exact silent-fallback defect that ``OPS-73`` hole 2 removed
    from the layer below: the reader sees a familiar busy bucket, waits for it
    to clear, and it never does. Loud and ungoverned is a state somebody fixes.
    Quiet and ungoverned is a state that rots.

    Args:
        cycle: Cycle number for the payload. Defaults to
            :func:`current_cycle`, which reads ``ops.loop.state``.
        root: Bucket to contend in. Defaults to
            :func:`ops.lane_slot.default_root` - the shared machine-wide
            bucket, by the operator's ruling of 2026-09-10. Pass a private
            directory to bound only this project's own concurrency.
        key: This repository's key in the scheme. An unknown key raises
            :class:`ops.lane_slot.UnknownRepoKey` rather than falling back to
            surplus, because a silent fallback presents as a busy bucket and
            gets debugged as one.
        surplus: Surplus width to contend for. Defaults to
            :func:`ops.lane_slot.shared_surplus_width`.
        repo: Label for the payload's ``repo`` field. Defaults to this
            checkout's root, matching the observed wire.
        run_id: Run id for the payload. Defaults to :func:`session_run_id`.
        log: Optional one-argument callable for release messages.

    Yields:
        :class:`LaneStatus` - always, held or not.
    """
    bucket = lane_slot.default_root() if root is None else Path(root)
    # Measured once, here, so the status object reports the same look that the
    # acquire below is about to take. hold_lane looks again for itself; the
    # caveat is written out in the module docstring rather than hidden.
    scheme = lane_slot.reserved_scheme_state(bucket, key)
    order = lane_slot.bucket_slot_order(bucket, key, surplus, state=scheme)

    resolved_cycle = current_cycle() if cycle is None else int(cycle)
    resolved_run_id = session_run_id() if run_id is None else str(run_id)
    resolved_repo = str(_REPO_ROOT) if repo is None else str(repo)

    # An ExitStack rather than a bare ``with``, so that the acquire can be
    # attempted inside a ``try`` without hand-rolling __enter__ and __exit__.
    # enter_context registers the context manager only AFTER it has entered, so
    # a BucketUnusable raised on the way in leaves nothing to unwind, and the
    # held case still gets ops.lane_slot.hold_lane's own ``finally`` release -
    # including when the body raises.
    with contextlib.ExitStack() as stack:
        unusable: Exception | None = None
        opted_out = False
        held: lane_slot.Held | None = None
        try:
            held = stack.enter_context(
                lane_slot.hold_lane(
                    repo=resolved_repo,
                    run_id=resolved_run_id,
                    cycle=resolved_cycle,
                    key=key,
                    root=bucket,
                    surplus=surplus,
                    log=log,
                )
            )
        except lane_slot.BucketUnusable as error:
            # Caught, named and reported. NOT converted into a busy answer, and
            # NOT re-raised - see the docstring for both halves of that.
            unusable = error
        except lane_slot.LaneContentionOptedOut:
            # OPS-77. Deliberately a separate clause rather than a wider except:
            # LaneContentionOptedOut is not kin to BucketUnusable in either
            # direction, on purpose, so that neither branch can ever answer for
            # the other. Catching it here is what stops a configuration choice
            # taking an unattended loop down.
            opted_out = True

        if opted_out:
            yield LaneStatus(
                held=False,
                slot=None,
                reserved=False,
                bucket=bucket,
                scheme=scheme,
                order=tuple(order),
                key=key,
                run_id=resolved_run_id,
                cycle=resolved_cycle,
                reason=_opt_out_reason(scheme),
                usable=True,
            )
        elif unusable is not None:
            cause = unusable.__cause__
            # The class name only. The message carries an absolute path.
            detail = type(cause).__name__ if cause is not None else "an OS error"
            yield LaneStatus(
                held=False,
                slot=None,
                reserved=False,
                bucket=bucket,
                scheme=scheme,
                order=tuple(order),
                key=key,
                run_id=resolved_run_id,
                cycle=resolved_cycle,
                reason=_unusable_reason(bucket, detail),
                usable=False,
            )
        elif held is None:
            yield LaneStatus(
                held=False,
                slot=None,
                reserved=False,
                bucket=bucket,
                scheme=scheme,
                order=tuple(order),
                key=key,
                run_id=resolved_run_id,
                cycle=resolved_cycle,
                reason=_busy_reason(bucket, tuple(order), scheme),
                usable=True,
            )
        else:
            yield LaneStatus(
                held=True,
                slot=held.name,
                reserved=held.reserved,
                bucket=bucket,
                scheme=scheme,
                order=tuple(order),
                key=key,
                run_id=resolved_run_id,
                cycle=resolved_cycle,
                reason=_held_reason(held, bucket, scheme),
                usable=True,
            )
