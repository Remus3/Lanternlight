"""A reserved-floor lane governor, re-implemented from an observed protocol.

Several projects share this one machine and one Anthropic account, so their
headless loops contend for the same concurrency budget. The sibling projects
coordinate through a directory of lock files and describe the scheme on the
``moon_sync_inbox/`` channel. The operator ruled on 2026-09-07 that Lanternlight
takes a lane slot in that scheme, with the repository key ``ll``. See
``ROADMAP.md`` items ``OPS-35``, ``OPS-36`` and ``OPS-42``, and
``docs/adr/ADR-007-lane-slot-root-is-ours.md``.

**Re-implemented, never vendored.** No file was copied in and nothing is
imported from a sibling tree. What is deliberately held in common is the WIRE:
the lock namespace shape, the key strings and the payload shape. That is a
protocol fact, not source, and this module is written from the protocol as
reconstructed in the ADR rather than from anyone's file.

The scheme
----------

A bucket directory holds two naming schemes at once, because a reservation
cannot be expressed by index alone::

    <bucket>/reserved-rc.lock     only the repo keyed `rc` may take this
    <bucket>/reserved-lw.lock
    <bucket>/reserved-rsc.lock
    <bucket>/reserved-cs.lock
    <bucket>/reserved-ll.lock     ours
    <bucket>/0.lock               surplus, first-come
    <bucket>/1.lock

:func:`try_acquire` tries its OWN reserved slot first and the surplus second.
The consequence is the guarantee: a repository starved of surplus by a busy
neighbour can still always start one lane, and a busy repository can burst into
the surplus.

Four properties carry the design, and every one of them is a test in
``tests/test_lane_slot.py`` rather than a sentence here:

* A repository can never hold more than one RESERVED slot - its own.
* A repository starved of surplus still gets its floor.
* An unknown repository key is REFUSED, never silently given surplus. A silent
  fallback presents exactly as "busy", which hides the misconfiguration behind
  the symptom it causes.
* Reaping understands BOTH naming schemes. A stale reserved lock that cannot be
  reclaimed costs its owner the floor for the whole stale window, which is the
  orphan bug wearing a new address.

Identity, not path
------------------

The reservation is keyed on the repository KEY - a short, lowercase, stable
token - and never on the filesystem path. A sibling measured the alternative:
its locks carried the full checkout path, and a root rename mid-run would have
abandoned the held reservation and claimed a second one while the first sat
orphaned until the stale arm fired. Two repositories would then have been one
reservation short between them. Keying on identity is the fix we adopt; the
defect is not.

Where the bucket lives
----------------------

**The shared machine-wide bucket, by operator ruling of 2026-09-10.** The
default root is the all-users bucket the sibling loops already ration between
themselves, resolved from the ``PROGRAMDATA`` environment variable rather than
written here as an absolute path, and still overridable by the environment
variable named in :data:`ROOT_ENV_VAR`. ADR-007 put the root inside this
repository; ADR-008 supersedes it. Nothing here binds a port and nothing here
is acquired at import time.

Surplus-only until the widening lands
-------------------------------------

Joining is NOT one environment variable, which is what ADR-007 expected it to
be. Measured on 2026-09-10, the shared bucket held one lock, ``0.lock``, and no
reserved name of any kind. Pointing this module at it while keeping the
reserved-first order of :func:`slot_order` would create ``reserved-ll.lock`` on
essentially every acquire: a file no other participant's reaper recognises, so
a leak of ours would sit there until our own stale arm fired, AND we would
never contend for surplus, so we would not ration with anybody. That is the
opposite of joining.

So the order is decided by LOOKING at the bucket, in
:func:`reserved_scheme_state`, and the look has three answers rather than two:

``RESERVED_PRESENT``
    Some other participant's ``reserved-<key>.lock`` is there, so the widening
    has landed and our own floor is tried first, exactly as the agreed protocol
    says. No code change is needed on the day this becomes true, because it
    will become true in somebody else's tree on a day nobody tells us about.
``RESERVED_ABSENT``
    The bucket is readable and holds no reserved name. We contend for surplus
    slots ONLY, on the same terms as everyone else, and never write a name the
    others do not recognise.
``RESERVED_UNKNOWN``
    We could not look - the bucket is missing, unreadable, or the listing was
    refused. This is NOT the same fact as ``RESERVED_ABSENT`` and is not
    collapsed into it, even though both take the same branch. It takes the
    surplus-only branch because the conservative direction is the one that does
    not write an unrecognised file into a directory other projects share: a
    failed look must never be the reason a stray ``reserved-ll.lock`` appears.

Our OWN reserved lock is deliberately not counted as evidence. Evidence the
observer produced is not evidence about the world, and counting it would latch
the detector at ``RESERVED_PRESENT`` after a single write.

Detection reads a WIDER alphabet than claiming does
---------------------------------------------------

``OPS-73`` hole 1, and the two alphabets are separate on purpose:

* CLAIMING uses :data:`REPO_KEYS`, the five short codes the channel agreed. A
  key outside that set is still REFUSED - see :class:`UnknownRepoKey`.
* DETECTION uses :data:`DETECTION_REPO_KEYS`, a strict superset of it. Before
  the widening, a bucket whose only reserved name was ``reserved-ds.lock`` read
  as ``RESERVED_ABSENT``, so the reserved-floor widening could have landed
  without our noticing, and the miss looked exactly like correct pre-widening
  behaviour.

The reaper's alphabet is NOT widened with it. :func:`is_slot_name` stays narrow
so a reaper never removes a file it does not understand.

Busy is not the same as unusable
--------------------------------

``OPS-73`` hole 2. ``None`` from :func:`try_acquire`, :func:`acquire_lane` and
:func:`hold_lane` means exactly ONE thing: every candidate slot is currently
taken. A bucket that cannot be created, listed or written to raises
:class:`BucketUnusable` instead, because a caller that cannot start has to be
able to say why. Folding the two together reproduced, one level down in root
resolution, the silent-fallback shape :class:`UnknownRepoKey` exists to refuse:
a ``PROGRAMDATA`` naming a FILE made every acquire answer "busy" forever.

A width of zero is an OPT-OUT, and it is never busy either
----------------------------------------------------------

``OPS-77``, the same defect one layer up from the paragraph above and reachable
since the width became configurable. A surplus width of zero produced an EMPTY
candidate order in every bucket where the reserved-floor widening has not
landed. :func:`try_acquire` then walked nothing, returned ``None``, and a
healthy, empty, WRITABLE bucket reported permanent contention.

Zero is a legitimate value and stays one: :func:`shared_surplus_width` accepts
it while refusing a negative and a non-numeric width, and that acceptance is a
separate decision this item does not reopen. What changed is the ANSWER.
:func:`acquire_lane` and :func:`hold_lane` now raise
:class:`LaneContentionOptedOut` before they resolve, create, read or reap a
bucket, and the exception's message opens with :data:`OPT_OUT_STATUS` so the
words a reader sees NAME the opt-out. An undisclosed opt-out is the cheapest way
for a future operator to take this project out of the shared scheme while every
status line still reads as though it were participating.

Both entry points - the ``surplus`` parameter and :data:`SURPLUS_ENV_VAR` -
resolve through the single predicate :func:`is_contention_opt_out`, so they
cannot disagree about zero. :func:`try_acquire` is deliberately unchanged: a
width of zero there still yields the floor-only order, so its ``None`` still
means the floor is taken, and a caller passing an explicit ``order`` is stating
its own terms.

Reclaiming is wired into the acquire, and is narrower than reaping by hand
-------------------------------------------------------------------------

``OPS-76``. :func:`reap` had NO CALLER anywhere in this tree until 2026-09-11.
Measured against the real shared bucket that day: it held one lock stale by both
arms - holder pid dead, timestamp about 33 hours old - and a real acquire took
the next slot and left the stale one byte for byte as it found it. The stale
arm, :data:`STALE_SECONDS`, the two-scheme reaper and every test covering them
were correct and unreachable from production, which is this repository's own
lesson in a new costume: a green suite proves a behaviour is implemented, never
that it is WIRED.

:func:`acquire_lane` now calls :func:`reap_for_acquire` before it does anything
else with the bucket. That reaper is narrower than :func:`reap` in exactly one
way: it never removes another participant's ``reserved-<key>.lock``. See
:func:`is_ours_to_reclaim` for the reasoning and for the blind spot it accepts.

:func:`acquire_lane` and :func:`hold_lane` are the operational entry points and
apply all of the above. :func:`try_acquire` keeps its original contract - own
floor, then surplus - for callers that state an order themselves, and refuses
any order naming a file outside the scheme or another repository's floor.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "BucketUnusable",
    "DETECTION_ONLY_REPO_KEYS",
    "DETECTION_REPO_KEYS",
    "Held",
    "LaneContentionOptedOut",
    "LaneSlotError",
    "LOCK_SUFFIX",
    "NoSlotAvailable",
    "OPT_OUT_STATUS",
    "OPT_OUT_WIDTH",
    "PROGRAMDATA_ENV_VAR",
    "REPO_KEY",
    "REPO_KEYS",
    "RESERVED_ABSENT",
    "RESERVED_PREFIX",
    "RESERVED_PRESENT",
    "RESERVED_UNKNOWN",
    "ROOT_ENV_VAR",
    "SHARED_BUCKET_RELATIVE",
    "SHARED_SURPLUS_WIDTH",
    "STALE_SECONDS",
    "SURPLUS_ENV_VAR",
    "SURPLUS_WIDTH",
    "UnknownRepoKey",
    "acquire_lane",
    "bucket_slot_order",
    "decode_payload",
    "default_root",
    "encode_payload",
    "hold",
    "hold_lane",
    "holders",
    "is_contention_opt_out",
    "is_detectable_reserved_name",
    "is_ours_to_reclaim",
    "is_reserved_name",
    "is_slot_name",
    "is_stale",
    "reap",
    "reap_for_acquire",
    "release",
    "repo_local_root",
    "reserved_name",
    "reserved_scheme_state",
    "shared_root",
    "shared_surplus_width",
    "slot_order",
    "surplus_names",
    "try_acquire",
]

#: This repository's key in the cross-project scheme. Assigned in the round the
#: operator ruled on; short, lowercase, no spaces and no path separators.
REPO_KEY = "ll"

#: The agreed set, and the CLAIMING alphabet. A key outside it is a
#: configuration error, not a fallback.
REPO_KEYS: tuple[str, ...] = ("rc", "lw", "rsc", "cs", "ll")

#: The two codes DETECTION recognises on top of :data:`REPO_KEYS`.
#:
#: PROVENANCE, stated honestly because a key with no provenance becomes an
#: agreed key by attrition: ``rm`` (Red Moon) and ``ds`` (Daemon Slayer) are
#: read off the machine-wide ports table in ``CLAUDE.md`` - the same document
#: that assigned this repository ``ll`` - and they are NOT confirmed lock keys
#: agreed by those two projects. Nobody from either has told us what short code
#: their governor would write. They are a reasonable reading of the only roster
#: this machine keeps, and that is all they are.
DETECTION_ONLY_REPO_KEYS: tuple[str, ...] = ("rm", "ds")

#: The DETECTION alphabet: a strict superset of :data:`REPO_KEYS`.
#:
#: Why the two sets are separate, and why this one is not simply "any token
#: after the prefix". The asymmetry runs one way. A false ABSENT costs us our
#: floor for an acquire and self-corrects the moment a recognised reserved name
#: is visible. A false PRESENT is the EXPENSIVE direction: it makes us write
#: ``reserved-ll.lock`` into a shared directory where, per ADR-008, nobody
#: else's reaper recognises it, so our leak sits there until our own stale arm
#: fires. Stray litter named ``reserved-anything.lock`` must therefore not flip
#: the detector, which a wide-open pattern would let it do.
#:
#: Widening this does NOT widen :func:`is_slot_name`, and must not: the reaper
#: stays narrow so it never deletes a file it does not understand.
DETECTION_REPO_KEYS: tuple[str, ...] = (*REPO_KEYS, *DETECTION_ONLY_REPO_KEYS)

RESERVED_PREFIX = "reserved-"
LOCK_SUFFIX = ".lock"

#: Surplus width - the free-for-all slots above the five reserved floors, as
#: the reserved-floor design describes them. This is the width :func:`slot_order`
#: uses, and it is the PROPOSED scheme's width rather than the deployed one.
SURPLUS_WIDTH = 2

#: Environment variable that overrides the shared surplus width below, so a
#: width correction needs no code change.
SURPLUS_ENV_VAR = "LL_LANE_SLOT_SURPLUS"

#: Surplus width to contend for in the SHARED bucket.
#:
#: PROVENANCE, because a number without one becomes a measurement by attrition:
#: this is NOTE-SOURCED and was never measured here. The cross-project channel
#: describes the deployed bucket as rationing three first-come slots. The only
#: first-party look this project has taken at that bucket, on 2026-09-10, found
#: a single lock in it, and one lock cannot reveal a width - so the channel's
#: figure is adopted as a working default and not as an observation.
#:
#: Getting this wrong is not symmetric. Too small only costs us lanes we could
#: have taken; too large creates a surplus index the deployed scheme may not
#: hand out. :func:`is_slot_name` and :func:`reap` accept any digit index for
#: that reason, so an index above anyone's width is still reclaimable by any
#: implementation of this scheme rather than being litter forever.
SHARED_SURPLUS_WIDTH = 3

#: The width that means "do not contend at all", and the one line a status
#: report prints when it is set. ``OPS-77``.
#:
#: Zero is a legitimate value - :func:`shared_surplus_width` accepts it while
#: refusing a negative and a non-numeric width - so it is treated as a declared
#: OPT-OUT rather than as a refusal. What it may never do is wear the BUSY
#: wording, and that is why the words live here rather than being composed at
#: each call site: BUSY is the one condition a caller is expected to shrug off
#: and retry past, and a zero width is a permanent configuration state that
#: clears only when somebody changes it. An opt-out nobody can see in a printed
#: line is the cheapest possible way to leave the shared scheme silently.
OPT_OUT_WIDTH = 0
OPT_OUT_STATUS = "OPTED OUT - surplus width 0, this session contends for no lane slot"

#: The stale arm, in seconds. Four and a half hours, matching the window the
#: siblings' governor uses, so a lock this repository leaves behind is reclaimed
#: on the same schedule a sibling would apply to it.
STALE_SECONDS = 16200.0

#: Set this to point the governor at a different bucket - a private one for a
#: test, or a relocated shared one. It wins over every default below.
ROOT_ENV_VAR = "LL_LANE_SLOT_ROOT"

#: The Windows all-users application-data root. The shared bucket is resolved
#: THROUGH this rather than written out as an absolute path: a drive-rooted
#: literal is both unportable and the shape of a hardcoded dependency, and
#: ``tests/test_lane_slot.py`` pins that no such literal appears here.
PROGRAMDATA_ENV_VAR = "PROGRAMDATA"

#: The shared bucket's namespace under the all-users root. This spelling is a
#: WIRE fact - the namespace every participant computes - and is the one thing
#: we deliberately hold in common. It is not a dependency on a sibling's tree.
SHARED_BUCKET_RELATIVE = Path("lw-loop") / "slots"

#: The three answers :func:`reserved_scheme_state` may give. Three, not two:
#: "I looked and found none" and "I could not look" are different facts, and a
#: codebase that collapses them eventually acts on the wrong one.
RESERVED_PRESENT = "present"
RESERVED_ABSENT = "absent"
RESERVED_UNKNOWN = "unknown"

_REPO_ROOT = Path(__file__).resolve().parents[1]

#: Relative to the repository root. ``ops/runtime/`` is gitignored, so the
#: bucket never reaches a commit. This is the FALLBACK now rather than the
#: default: it is used only when the all-users root cannot be resolved at all.
_DEFAULT_RELATIVE = Path("ops") / "runtime" / "lane_slots"

_STILL_ACTIVE = 259

#: Windows access right that is enough to ask whether a process exists without
#: acquiring any right to affect it. Declared at MODULE scope, and under this
#: exact name, because the roster-wide access-mask check resolves it on the
#: module object: a function-local copy shadows the call site while the module
#: attribute still reads 0x1000, which is a hole that check exists to close.
#: ``ops/loop/guard.py`` and ``ops/loop/watch.py`` spell the same constant out
#: for themselves - it is a Windows API number rather than a derivation, so
#: there is nothing to keep in sync and nothing to import.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

#: ``GetLastError`` after a failed ``OpenProcess``. 87 is
#: ``ERROR_INVALID_PARAMETER``, which is what Windows returns when no process
#: bears the pid at all. Every other code - access denied, most of all - says
#: nothing about whether the process is there.
_ERROR_INVALID_PARAMETER = 87


class LaneSlotError(Exception):
    """Base for every error this module raises deliberately."""


class UnknownRepoKey(LaneSlotError):
    """The caller's repository key is not in the agreed set.

    Raised rather than falling back to surplus. A silent fallback is
    indistinguishable from a busy bucket, so the misconfiguration would present
    as contention and be debugged as contention.
    """


class BucketUnusable(LaneSlotError):
    """The bucket cannot be created, listed or written to at all.

    Raised rather than answering ``None``, and the distinction is the whole
    point of this class: ``None`` from :func:`try_acquire` means every candidate
    slot is TAKEN, which is a normal, self-clearing condition. This means the
    governor could not operate the bucket at all, which is a configuration or
    permission fault and clears only when somebody fixes it.

    Measured cause, ``OPS-73``: a ``PROGRAMDATA`` naming a FILE resolved the
    shared root underneath that file, ``mkdir`` failed, and every acquire
    answered ``None`` forever. A caller could not tell that from a full bucket
    and would have debugged a permanent misconfiguration as contention. That is
    the same silent-fallback shape :class:`UnknownRepoKey` refuses, one level
    down. The general case is the same: a read-only volume, a directory we may
    not write, or a listing we are refused.
    """


class LaneContentionOptedOut(LaneSlotError):
    """The configured surplus width is zero, so this session does not contend.

    ``OPS-77``, and it is a third answer rather than a flavour of either of the
    two that already existed. ``None`` means every candidate slot is TAKEN.
    :class:`BucketUnusable` means the bucket could not be operated. This means
    the bucket was never asked: a width of :data:`OPT_OUT_WIDTH` produces no
    candidate to try, and walking an empty candidate list and answering ``None``
    reported a healthy, empty, writable bucket as permanently busy.

    Measured before the fix, against an empty bucket under ``tmp_path``:
    ``acquire_lane(..., surplus=0)`` and ``LL_LANE_SLOT_SURPLUS=0`` both
    answered ``None``, and the loop's status line therefore read
    ``BUSY - no slot free`` forever.

    DELIBERATELY NOT A SUBCLASS OF :class:`BucketUnusable`, in either direction.
    A caller writing ``except BucketUnusable`` would otherwise report a perfectly
    good bucket as broken, which is the same two-conditions-one-class collapse
    ``OPS-73`` hole 2 removed - and the honest fact here is about our own
    configuration rather than about the directory.

    The words a reader sees are :data:`OPT_OUT_STATUS`, and they are the first
    thing in this exception's message so that a status line can carry them
    verbatim. An opt-out that is not NAMED where a reader looks is the blind
    spot ``OPS-70`` closed wearing a configuration hat.
    """


class NoSlotAvailable(LaneSlotError):
    """Every slot this repository may take is held. Not raised by default."""


@dataclass(frozen=True)
class Held:
    """One acquired slot.

    ``reserved`` distinguishes the floor from a surplus lane, because "did I get
    my guarantee or did I get lucky" is the question an operator asks when the
    machine is busy.
    """

    path: Path
    name: str
    key: str
    reserved: bool


def repo_local_root() -> Path:
    """The private in-repository bucket, kept as a fallback.

    ADR-007 made this the default. ADR-008 supersedes that, but the path stays
    reachable, because a machine with no all-users root would otherwise have no
    bucket at all and the governor would stop bounding even our own loop.
    """
    return _REPO_ROOT / _DEFAULT_RELATIVE


def shared_root() -> Path | None:
    """The shared machine-wide bucket, or ``None`` if it cannot be resolved.

    ``None`` is a real answer rather than a guess. If the all-users root is not
    in the environment, this function does not invent a drive letter for it.

    ``None`` is also the answer when the all-users root EXISTS AND IS NOT A
    DIRECTORY - ``OPS-73`` hole 2, part (a). The bucket would otherwise resolve
    to a path underneath a file, which no ``mkdir`` can ever create, so the
    in-repository bucket is used instead and the loop stays GOVERNED rather than
    permanently busy. A root that is simply absent is NOT this case: it is
    created on first use, as it always was.

    Nothing is created here, and a stat that cannot be taken - a malformed path,
    a device that is not there - answers ``None`` rather than propagating.
    """
    base = os.environ.get(PROGRAMDATA_ENV_VAR)
    if not base or not base.strip():
        return None
    root = Path(base)
    try:
        if root.exists() and not root.is_dir():
            return None
    except OSError:
        return None
    return root / SHARED_BUCKET_RELATIVE


def default_root() -> Path:
    """The bucket this repository uses, resolved but NOT created.

    Order: the explicit override, then the shared machine-wide bucket, then the
    in-repository fallback. Creating anything here would make merely importing
    something that reads the default enough to materialise a bucket, which is
    the import-time side effect this module refuses to have.

    The override and :func:`shared_root` agree about whitespace - ``OPS-73``
    acceptance criterion 4. They disagreed: an override of ``"   "`` yielded
    ``Path("   ")`` and a bucket literally named three spaces, while the same
    value in the all-users variable was ignored. Two readers of the same kind of
    value must not mean different things by blank.
    """
    override = os.environ.get(ROOT_ENV_VAR)
    if override and override.strip():
        return Path(override)
    shared = shared_root()
    if shared is not None:
        return shared
    return repo_local_root()


def shared_surplus_width() -> int:
    """The surplus width to contend for, override first.

    An override that is not a usable width falls back to the documented default
    rather than propagating. A governor that refuses to start because somebody
    typed a word into an environment variable turns a typo into an outage, and
    the fallback is a published number rather than an invented one.
    """
    raw = os.environ.get(SURPLUS_ENV_VAR)
    if raw is None:
        return SHARED_SURPLUS_WIDTH
    try:
        width = int(raw.strip())
    except (AttributeError, ValueError):
        return SHARED_SURPLUS_WIDTH
    if width < 0:
        return SHARED_SURPLUS_WIDTH
    return width


def is_contention_opt_out(surplus: int | None) -> bool:
    """Does this configuration say "do not contend for a lane at all"?

    ``OPS-77`` acceptance criterion 2. THE ONE RESOLVER, and that is the point
    of it rather than a convenience: ``acquire_lane``'s ``surplus`` parameter
    and the :data:`SURPLUS_ENV_VAR` override cannot disagree about zero, because
    neither of them decides - this does, for both, from the same resolution
    order the module already used. Two agreeing implementations of the same rule
    are a pair that will eventually disagree, which is the shape ``OPS-73``
    criterion 4 found in the two whitespace branches.

    ``None`` means "no parameter was given", so the environment decides through
    :func:`shared_surplus_width`. A parameter that IS given wins, exactly as it
    does in :func:`bucket_slot_order` - so a caller asking for a real width is
    never dragged into an opt-out by an environment variable, and a caller
    asking for zero is never dragged out of one.

    A width that cannot be read as an integer at all is not an opt-out. It is
    the typo case :func:`shared_surplus_width` already answers with the
    published default, and turning it into a silent withdrawal from the scheme
    would be the opposite of naming it.
    """
    if surplus is None:
        width = shared_surplus_width()
    else:
        try:
            width = int(surplus)
        except (TypeError, ValueError):
            return False
    return width == OPT_OUT_WIDTH


def _opt_out_reason(surplus: int | None) -> str:
    """The sentence :class:`LaneContentionOptedOut` carries. Written out, never inferred.

    It opens with :data:`OPT_OUT_STATUS` so a status line can print that prefix
    verbatim, then names WHICH of the two entry points set the width, because an
    operator who did not expect to be opted out has to know where to go and
    change it. The two entry points agree on the answer and still say which one
    spoke.

    It says nothing about the bucket - not even its path. Nothing was read from
    or written to one, so there is nothing to report about it, and a reason that
    described a bucket it never touched would be this repository's own trap of a
    claim about the tool wearing the costume of a claim about the world.
    """
    if surplus is None:
        source = f"the {SURPLUS_ENV_VAR} environment override"
    else:
        source = "the surplus width passed to this call"
    return (
        f"{OPT_OUT_STATUS}. The width of {OPT_OUT_WIDTH} came from {source}. No "
        "bucket was created, read or written, no lock was taken and no stale "
        "lock was reclaimed, so this session rations with nobody and is counted "
        "against no other project's concurrency budget. This is a configuration "
        "state and not contention: it does not clear on its own and no retry "
        f"changes it. Set {SURPLUS_ENV_VAR} to a positive width, or pass a "
        "positive surplus, to rejoin the shared lane scheme."
    )


def reserved_name(key: str) -> str:
    """The reserved lock filename for ``key``."""
    return f"{RESERVED_PREFIX}{key}{LOCK_SUFFIX}"


def surplus_names(width: int) -> tuple[str, ...]:
    """The surplus lock filenames, zero-based and in try order."""
    return tuple(f"{index}{LOCK_SUFFIX}" for index in range(max(0, int(width))))


def slot_order(key: str, surplus: int = SURPLUS_WIDTH) -> tuple[str, ...]:
    """Slot names in the order this repository may try them.

    Own floor first. No other repository's reserved name ever appears.
    """
    _require_known_key(key)
    return (reserved_name(key), *surplus_names(surplus))


def is_slot_name(name: str) -> bool:
    """True for a filename this scheme owns, in either naming scheme.

    Deliberately narrow: a stray file in the bucket is left alone, because a
    reaper that deletes what it does not recognise is a reaper that eventually
    deletes someone's notes.
    """
    if not name.endswith(LOCK_SUFFIX):
        return False
    stem = name[: -len(LOCK_SUFFIX)]
    if stem.startswith(RESERVED_PREFIX):
        return stem[len(RESERVED_PREFIX) :] in REPO_KEYS
    # Any digit index, deliberately - including one above the width we ourselves
    # contend for. A shared bucket is wider than our contention window, and a
    # reaper blind to `2.lock` leaves somebody's leak there forever.
    return stem.isdigit()


def is_reserved_name(name: str) -> bool:
    """True for a reserved lock filename belonging to any agreed CLAIM key.

    This is the reaper's and the claimer's question, so it uses the narrow
    :data:`REPO_KEYS` alphabet. :func:`is_detectable_reserved_name` is the
    wider, detection-only one.
    """
    if not is_slot_name(name):
        return False
    return name.startswith(RESERVED_PREFIX)


def is_ours_to_reclaim(name: str, key: str = REPO_KEY) -> bool:
    """Whether the AUTOMATIC acquire path may remove this lock once it is stale.

    ``OPS-76`` acceptance criterion 3, and the answer is deliberately narrower
    than :func:`is_slot_name`. Three cases:

    * a SURPLUS name - ``0.lock``, ``7.lock`` - yes, whoever wrote it. The
      surplus namespace is first-come, every participant's reaper understands
      it, and reclaiming a leaked one is the scheme working exactly as
      ``ADR-008`` describes it.
    * OUR OWN reserved floor - yes. It is ours; nobody else can lose anything.
    * ANOTHER participant's reserved floor - NO, however stale it looks.

    The asymmetry is in who pays for an error, and it is the whole reasoning.
    :func:`is_stale` requires its evidence rather than guessing, but it treats
    an UNREADABLE payload as stale, and a lock is briefly unreadable in the
    window between an exclusive create and the payload write - a window our own
    :func:`_claim` has, so a sibling's very likely does too. A surplus lock
    removed in that window costs its owner one lane it will take again next
    cycle. A FLOOR removed in that window costs its owner the single guarantee
    the reserved scheme sells, which is that a starved repository can always
    start one lane. No reserved name of any key has ever been observed in the
    shared bucket, so removing one would be exercising judgement about a
    protocol nobody here has watched anybody else run.

    The disclosed cost of choosing this way: another participant's genuinely
    leaked floor is left in the bucket by us forever. That costs nobody a
    surplus slot - a floor is not a slot we could have taken - and the explicit
    :func:`reap` still removes it when an operator asks for it by hand.
    """
    if not is_slot_name(name):
        return False
    if not is_reserved_name(name):
        return True
    return name == reserved_name(key)


def is_detectable_reserved_name(name: str) -> bool:
    """True for a reserved lock filename in the wider DETECTION alphabet.

    Used only by :func:`reserved_scheme_state`, to answer "has the reserved
    widening landed in this bucket". It recognises every key in
    :data:`DETECTION_REPO_KEYS`, which includes two codes read off a ports table
    rather than agreed with the projects they name.

    It is NOT used by :func:`is_slot_name`, :func:`reap` or :func:`holders`.
    Seeing a name is a cheaper act than deleting one, so the set that decides
    what we may DELETE stays narrower than the set that decides what we may
    NOTICE. It is also not an arbitrary token, because a false PRESENT is the
    expensive direction - see :data:`DETECTION_REPO_KEYS`.
    """
    if not name.endswith(LOCK_SUFFIX):
        return False
    stem = name[: -len(LOCK_SUFFIX)]
    if not stem.startswith(RESERVED_PREFIX):
        return False
    return stem[len(RESERVED_PREFIX) :] in DETECTION_REPO_KEYS


def reserved_scheme_state(root: Path | str, key: str = REPO_KEY) -> str:
    """Has the reserved-floor widening landed in this bucket? Three answers.

    Returns :data:`RESERVED_PRESENT`, :data:`RESERVED_ABSENT` or
    :data:`RESERVED_UNKNOWN`. The third is not a flavour of the second: absent
    means the bucket was read and held no reserved name, while unknown means the
    read did not happen - the directory is missing, or the listing was refused.
    Both take the same branch in :func:`bucket_slot_order`, and they are still
    reported apart, because an operator debugging a bucket needs to know which
    of the two they are looking at.

    Two deliberate narrownesses:

    * Only NAMES are examined. No lock is opened, so a half-written or
      unreadable payload cannot take detection down, and reading cannot hold a
      handle that blocks its owner's unlink.
    * ``reserved_name(key)`` - our own floor - does not count. Evidence the
      observer produced is not evidence about the world; counting it would latch
      this at ``RESERVED_PRESENT`` after a single write of our own and the check
      would then be measuring our own footprint.

    And one deliberate WIDTH, ``OPS-73`` hole 1: the names it recognises come
    from :data:`DETECTION_REPO_KEYS`, not from :data:`REPO_KEYS`. A bucket whose
    only reserved name was ``reserved-ds.lock`` used to read ``RESERVED_ABSENT``,
    so the widening could land and we would go on taking surplus slots while
    everyone else had moved to floors - a wrong answer that looked exactly like
    the right one. Claiming is unaffected and still refuses every key outside
    the agreed five.

    Creates nothing. A bucket that is not there stays not there.
    """
    bucket = Path(root)
    ours = reserved_name(key) if key in REPO_KEYS else None
    try:
        entries = list(bucket.iterdir())
    except OSError:
        # FileNotFoundError, NotADirectoryError and PermissionError all land
        # here, and all three mean the same thing to a caller: we did not look.
        return RESERVED_UNKNOWN
    for entry in entries:
        if entry.name == ours:
            continue
        if is_detectable_reserved_name(entry.name):
            return RESERVED_PRESENT
    return RESERVED_ABSENT


def bucket_slot_order(
    root: Path | str,
    key: str = REPO_KEY,
    surplus: int | None = None,
    *,
    state: str | None = None,
) -> tuple[str, ...]:
    """Slot names in try order for THIS bucket, decided by looking at it.

    Reserved-first when the widening has landed there, surplus-only otherwise -
    and surplus-only when we could not look, because the conservative direction
    is the one that does not write an unrecognised file into a directory other
    projects share. The transition needs no code change here: it happens when
    somebody else's tree starts writing reserved names, on a day nobody tells
    us about.

    ``surplus`` defaults to :func:`shared_surplus_width`. ``state`` is for a
    caller that already measured it and does not want a second listing.

    AN EMPTY RESULT IS A REAL ANSWER and it is not contention - ``OPS-77``. A
    width of zero with no reserved name in the bucket leaves nothing to try.
    This function stays a pure computation and still returns ``()`` for that,
    because a caller that asks what the order WOULD be is entitled to see it;
    what it must not do is walk that emptiness and call the result busy.
    :func:`acquire_lane` refuses the walk instead, through
    :func:`is_contention_opt_out`, before it ever reaches here.
    """
    _require_known_key(key)
    width = shared_surplus_width() if surplus is None else int(surplus)
    resolved = reserved_scheme_state(root, key) if state is None else state
    if resolved == RESERVED_PRESENT:
        return (reserved_name(key), *surplus_names(width))
    return surplus_names(width)


def encode_payload(*, pid: int, repo: str, run_id: str, cycle: int, ts: float | None = None) -> str:
    """Serialise the shared payload.

    The five fields are the wire. ``repo`` is a free-form label for a human
    reading the bucket - it is NOT what the reservation keys on, and writing a
    path there does not move anyone's slot.
    """
    body = {
        "pid": int(pid),
        "ts": float(time.time() if ts is None else ts),
        "repo": str(repo),
        "run_id": str(run_id),
        "cycle": int(cycle),
    }
    return json.dumps(body, sort_keys=True)


def decode_payload(text: str) -> dict | None:
    """Parse a payload, or ``None`` if it is not one.

    ``None`` means unreadable, which callers treat as stale. A lock nobody can
    read is a lock nobody can account for.
    """
    try:
        body = json.loads(text)
    except (ValueError, TypeError):
        return None
    return body if isinstance(body, dict) else None


def _read_payload(path: Path) -> dict | None:
    """Read one lock WITHOUT leaving a handle that blocks its owner's unlink.

    Windows refuses ``unlink`` while any handle is open without
    ``FILE_SHARE_DELETE``, and a reader is exactly what a waiter is. The read is
    therefore opened and closed inside this function and nowhere else, and every
    failure answers ``None`` rather than propagating - an unreadable lock is
    stale, not fatal.
    """
    try:
        with path.open(encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, ValueError):
        return None
    return decode_payload(text)


def _pid_alive(pid: int) -> bool:
    """Best-effort liveness.

    Fails toward ALIVE. A wrong "dead" answer reaps a running session's lane and
    lets a second holder in; a wrong "alive" answer only delays the reclaim
    until the stale arm fires. The costs are not symmetric, so neither is this.

    ``os.kill(pid, 0)`` is NOT portable here: on Windows CPython routes any
    signal other than the two console events to ``TerminateProcess``, so the
    liveness probe would kill the process it is asking about.

    ``restype`` and ``argtypes`` are declared on every entry point, matching
    ``ops/loop/guard.py`` and ``ops/loop/watch.py``, and the reason is measured
    rather than stylistic. A ctypes function with no ``restype`` defaults to
    ``c_int``, so a 64-bit ``HANDLE`` comes back truncated to a signed 32-bit
    value: measured on this machine 2026-09-07, the same kernel32 handle
    answered ``GetModuleHandleW`` with ``-323551232`` under the default and
    with ``0x7ff6ecb70000`` under an explicit ``restype``, and
    ``GetCurrentProcess`` answered ``-1`` rather than
    ``0xffffffffffffffff``. Handle VALUES on this box are currently small
    enough that ``OpenProcess`` was returning an intact number anyway - 388
    under both spellings in the same run - so the defect was latent, not
    visible, and the ``CloseHandle`` that follows would have been handed a
    truncated handle the day it stopped being.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:  # pragma: no cover - ctypes is always present here
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            # ERROR_INVALID_PARAMETER means no such process. Anything else
            # (access denied, for instance) is not evidence of death.
            return ctypes.get_last_error() != _ERROR_INVALID_PARAMETER
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == _STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def is_stale(payload: Mapping | None, *, now: float | None = None, pid_alive=None) -> bool:
    """Whether a lock may be reclaimed.

    Two arms, and a missing field fires them rather than suppressing them:

    * no readable payload, or no usable ``ts``, is stale - an absent timestamp
      is absent, never "now";
    * a ``ts`` older than :data:`STALE_SECONDS` is stale;
    * otherwise a dead ``pid`` is stale.

    The pid arm is deliberately the LAST one consulted and the weakest. A
    long-lived controller that runs many cycles under one pid keeps that pid
    alive across a leak, so the pid arm answers "not stale" for exactly the
    orphan it was meant to catch. The ts arm is what actually reclaims those.
    """
    if not isinstance(payload, Mapping):
        return True
    raw_ts = payload.get("ts")
    if not isinstance(raw_ts, (int, float)) or isinstance(raw_ts, bool):
        return True
    reference = time.time() if now is None else now
    if reference - float(raw_ts) > STALE_SECONDS:
        return True
    raw_pid = payload.get("pid")
    if not isinstance(raw_pid, int) or isinstance(raw_pid, bool):
        return True
    alive = _pid_alive if pid_alive is None else pid_alive
    return not alive(raw_pid)


def holders(root: Path | str) -> dict[str, dict]:
    """Every readable lock in the bucket, keyed by filename.

    Read-only, and an absent bucket answers ``{}`` rather than raising - a
    session that is not contending must never be blocked by the governor, and
    must not create the namespace merely by looking at it.
    """
    bucket = Path(root)
    report: dict[str, dict] = {}
    try:
        entries = sorted(bucket.iterdir())
    except OSError:
        return report
    for entry in entries:
        if not is_slot_name(entry.name):
            continue
        payload = _read_payload(entry)
        if payload is not None:
            report[entry.name] = payload
    return report


def reap(
    root: Path | str, *, now: float | None = None, pid_alive=None, only=None
) -> list[str]:
    """Remove stale locks in BOTH naming schemes. Returns the names removed.

    A reaper that knows only ``0.lock``-style names leaves a stale
    ``reserved-<key>.lock`` in place, and its owner loses the floor the whole
    design exists to guarantee. That is the orphan bug at a new address, and it
    is harder to see there, because a missing reservation reads as a policy
    decision rather than as a leak.

    ``only`` is an optional predicate taking a filename, applied ON TOP OF
    :func:`is_slot_name` and never instead of it, so no caller can widen what
    this function is willing to delete - it can only narrow it. The default of
    ``None`` is the unchanged two-scheme contract ``ADR-008`` section 6 lists,
    and :func:`reap_for_acquire` is the one narrowing this repository ships.
    """
    bucket = Path(root)
    removed: list[str] = []
    try:
        entries = sorted(bucket.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if not is_slot_name(entry.name):
            continue
        if only is not None and not only(entry.name):
            continue
        payload = _read_payload(entry)
        if not is_stale(payload, now=now, pid_alive=pid_alive):
            continue
        try:
            entry.unlink()
        except OSError:
            continue
        removed.append(entry.name)
    return removed


def reap_for_acquire(
    root: Path | str, key: str = REPO_KEY, *, now: float | None = None, pid_alive=None
) -> list[str]:
    """The reaper the ACQUIRE path runs, narrowed to what is ours to reclaim.

    ``OPS-76``. This exists so the stale arm has a caller: before this, ``reap``
    had none anywhere in the tree, so a lock leaked into the shared bucket was
    reclaimed by nothing and each one silently lowered our real concurrency by
    one while presenting as an ordinary busy answer.

    It differs from :func:`reap` in exactly one way - it never removes another
    participant's ``reserved-<key>.lock``. See :func:`is_ours_to_reclaim` for
    why, and for the blind spot that choice accepts. Everything else, including
    the narrow :func:`is_slot_name` alphabet and both arms of
    :func:`is_stale`, is unchanged.

    Answering ``[]`` on a bucket it cannot list is deliberate and is inherited
    from :func:`reap`. Reclaiming is opportunistic; deciding whether the bucket
    is usable at all is :func:`try_acquire`'s job, and doing it here as well
    would give ``OPS-73``'s ``BucketUnusable`` a second, quieter path to be
    swallowed on.
    """
    return reap(
        root,
        now=now,
        pid_alive=pid_alive,
        only=lambda name: is_ours_to_reclaim(name, key),
    )


def _require_known_key(key: str) -> None:
    if key not in REPO_KEYS:
        raise UnknownRepoKey(
            f"repository key {key!r} is not in the agreed set "
            f"{', '.join(REPO_KEYS)} - refusing to start rather than falling "
            "back to a surplus slot, because a silent fallback presents as a "
            "busy bucket and gets debugged as one. Keys are short, lowercase, "
            "and are never a filesystem path."
        )


def _claim(path: Path, payload: str) -> bool:
    """Create one lock atomically. ``False`` means somebody else holds it.

    ``False`` is reserved for exactly one cause - the exclusive create lost,
    which is what a held slot looks like. Every OTHER failure raises
    :class:`BucketUnusable`, because a bucket we cannot write into is not a
    bucket that is busy, and collapsing the two is ``OPS-73`` hole 2: the caller
    reads "full" and debugs contention that is not there.
    """
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError as error:
        raise BucketUnusable(
            f"could not create the lock {str(path)!r}: {error}. This is NOT a "
            "full bucket - a read-only volume, a directory we may not write, or "
            "a root that is not a directory all land here, and none of them "
            "clear on their own."
        ) from error
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
    except OSError as error:
        with contextlib.suppress(OSError):
            path.unlink()
        raise BucketUnusable(
            f"took the lock {str(path)!r} but could not write its payload: "
            f"{error}. The lock was removed again rather than left empty for "
            "somebody else's reader to find."
        ) from error
    return True


def _require_our_slot_names(order, key: str) -> tuple[str, ...]:
    """Refuse an order that would put a file we do not own into the bucket.

    Two refusals, both about a SHARED directory. A name outside the scheme is
    litter nobody's reaper will ever recognise, and another repository's
    reserved name is its floor - the one guarantee the whole design exists to
    give it. Neither is a thing to write by accident, and the only way to write
    either is to pass an explicit order, so the check lives here.
    """
    names = tuple(order)
    ours = reserved_name(key)
    for name in names:
        if not is_slot_name(name):
            raise LaneSlotError(
                f"{name!r} is not a name this scheme owns - refusing to create "
                "it, because an unrecognised file in a shared bucket is litter "
                "no participant's reaper will reclaim."
            )
        if is_reserved_name(name) and name != ours:
            raise LaneSlotError(
                f"{name!r} is another repository's reserved floor - refusing to "
                f"take it. This repository may only ever take {ours!r} or a "
                "surplus slot."
            )
    return names


def try_acquire(
    root: Path | str,
    key: str = REPO_KEY,
    *,
    repo: str,
    run_id: str,
    cycle: int,
    surplus: int = SURPLUS_WIDTH,
    order=None,
) -> Held | None:
    """Take a lane if one is available. Never blocks.

    ``None`` means exactly ONE thing: every candidate slot is currently taken.
    A bucket that cannot be created, listed or written to raises
    :class:`BucketUnusable` instead - ``OPS-73`` hole 2. A caller that cannot
    start has to be able to say why, and "busy" is a lie that clears by itself
    while a broken root does not.

    Order is own floor, then surplus, unless ``order`` states one - which is how
    :func:`acquire_lane` supplies a surplus-only order for a shared bucket that
    has no reserved names in it yet. The key is validated BEFORE the bucket is
    created, so a misconfigured caller leaves no trace behind, and so is the
    order, so a bad one leaves none either.
    """
    _require_known_key(key)
    candidates = _require_our_slot_names(
        slot_order(key, surplus) if order is None else order, key
    )
    bucket = Path(root)
    try:
        bucket.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise BucketUnusable(
            f"could not create the lane-slot bucket {str(bucket)!r}: {error}. "
            "Refusing to report this as a busy bucket: a root that is a file, "
            "or one under a file, would then present as permanent contention."
        ) from error
    try:
        list(bucket.iterdir())
    except OSError as error:
        raise BucketUnusable(
            f"the lane-slot bucket {str(bucket)!r} exists but cannot be listed: "
            f"{error}. A bucket we cannot read is not a bucket that is full."
        ) from error
    payload = encode_payload(pid=os.getpid(), repo=repo, run_id=run_id, cycle=cycle)
    for name in candidates:
        path = bucket / name
        if _claim(path, payload):
            return Held(
                path=path,
                name=name,
                key=key,
                reserved=name == reserved_name(key),
            )
    return None


def _neutralise(path: Path) -> None:
    """Rewrite an undeletable lock so the stale arm fires immediately.

    The direct answer to the orphan a live pid protects: if the lock cannot be
    removed, at least stop it claiming to be fresh. Written non-atomically on
    purpose - the file already exists and a replace would need the unlink that
    just failed.
    """
    body = encode_payload(
        pid=0,
        repo="neutralised",
        run_id="neutralised",
        cycle=0,
        ts=time.time() - (STALE_SECONDS * 2),
    )
    with contextlib.suppress(OSError), path.open("w", encoding="utf-8") as handle:
        handle.write(body)


def release(held: Held, *, retries: int = 5, backoff: float = 0.05, log=None) -> bool:
    """Release a slot. Returns whether the lock is actually gone.

    Three things this does NOT do, each because a sibling measured the cost:

    * it does not report success unconditionally - a release logged outside the
      failing branch makes an ACQUIRED/RELEASED pairing analysis read perfectly
      clean while a lane is stuck;
    * it does not give up on the first ``PermissionError`` - a concurrent
      reader's handle lives for microseconds, so a short bounded retry clears
      the common case;
    * it does not leave an undeletable lock claiming to be fresh.
    """
    attempts = max(1, int(retries))
    for attempt in range(attempts):
        try:
            held.path.unlink()
        except FileNotFoundError:
            if log is not None:
                log(f"lane slot released (already gone): {held.name}")
            return True
        except OSError:
            if attempt + 1 < attempts and backoff > 0:
                time.sleep(backoff)
            continue
        else:
            if log is not None:
                log(f"lane slot released: {held.name}")
            return True
    _neutralise(held.path)
    if log is not None:
        log(
            f"WARNING lane slot {held.name} could not be removed and was "
            "neutralised so it reaps immediately"
        )
    return False


@contextlib.contextmanager
def hold(
    root: Path | str,
    key: str = REPO_KEY,
    *,
    repo: str,
    run_id: str,
    cycle: int,
    surplus: int = SURPLUS_WIDTH,
    log=None,
) -> Iterator[Held | None]:
    """Hold a lane for the duration of the block, or yield ``None`` if busy.

    Yielding ``None`` rather than raising or waiting is deliberate: the caller
    decides what a busy machine means for it, and a governor that blocks by
    default turns a coordination miss into a hang.
    """
    held = try_acquire(
        root, key, repo=repo, run_id=run_id, cycle=cycle, surplus=surplus
    )
    try:
        yield held
    finally:
        if held is not None:
            release(held, log=log)


def acquire_lane(
    *,
    repo: str,
    run_id: str,
    cycle: int,
    key: str = REPO_KEY,
    root: Path | str | None = None,
    surplus: int | None = None,
) -> Held | None:
    """Take a lane in the bucket this repository actually uses.

    THE OPERATIONAL ENTRY POINT. It resolves :func:`default_root` - the shared
    machine-wide bucket, by the operator's ruling of 2026-09-10 - looks at that
    bucket's shape, and contends on whatever terms the shape implies. Callers
    that want to bound only their own concurrency pass ``root`` explicitly.

    ``None`` means busy - every candidate slot taken - exactly as
    :func:`try_acquire` means it, and nothing else means it. An unusable bucket
    raises :class:`BucketUnusable` rather than joining that answer, and a
    configured surplus width of zero raises :class:`LaneContentionOptedOut`
    rather than joining it either - ``OPS-77``. That check runs FIRST, before
    the bucket is resolved, created, reaped or listed: a session that is not
    participating asks nothing of a directory other projects share, and cannot
    report an opinion about a bucket it never touched.

    **It reaps before it walks the candidates**, through
    :func:`reap_for_acquire`. ``OPS-76``: until 2026-09-11 nothing in this tree
    called :func:`reap` at all, so a lock leaked into the shared bucket was
    reclaimed by nothing, and each permanently leaked lock lowered our real
    concurrency by one while presenting as an ordinary busy answer.

    WHY THE WIRING IS HERE AND NOT IN :func:`try_acquire`. This is the
    operational entry point: it is the function that resolves the bucket and
    decides the try order by looking at it, so it is also the one place that
    knows the acquire is an automatic, unattended act rather than a caller
    stating its own terms. :func:`try_acquire` keeps its documented contract of
    doing exactly what its ``order`` says and nothing more, because a caller
    that passes an explicit order is asserting knowledge about the bucket, and
    a primitive that silently deletes files underneath such a caller is a worse
    surprise than one that does not. Every production path in this tree reaches
    the bucket through here - ``ops/loop/lane.py`` uses :func:`hold_lane`, which
    is this function plus a release - so nothing operational loses the reclaim.
    The disclosed cost: :func:`hold` and a direct :func:`try_acquire` caller do
    NOT reap, and a future caller that reaches for the primitive instead of this
    entry point would reintroduce the hole for itself.

    The reap runs BEFORE the try order is computed as well as before the
    candidates are walked, so a stale lock cannot influence either decision.
    """
    if is_contention_opt_out(surplus):
        raise LaneContentionOptedOut(_opt_out_reason(surplus))
    bucket = default_root() if root is None else Path(root)
    reap_for_acquire(bucket, key)
    order = bucket_slot_order(bucket, key, surplus)
    return try_acquire(
        bucket, key, repo=repo, run_id=run_id, cycle=cycle, order=order
    )


@contextlib.contextmanager
def hold_lane(
    *,
    repo: str,
    run_id: str,
    cycle: int,
    key: str = REPO_KEY,
    root: Path | str | None = None,
    surplus: int | None = None,
    log=None,
) -> Iterator[Held | None]:
    """:func:`acquire_lane` for the duration of a block, released on the way out.

    Yields ``None`` when the bucket is full rather than blocking, for the same
    reason :func:`hold` does: a governor that blocks by default turns a
    coordination miss into a hang, and the caller is the one that knows what a
    busy machine means for it.

    An UNUSABLE bucket is not a full one and does not yield ``None``: it raises
    :class:`BucketUnusable` before the block runs. A caller that silently does
    nothing forever because a root is misconfigured is the failure ``OPS-73``
    exists to remove.

    A configured surplus width of zero is not a full bucket either, and raises
    :class:`LaneContentionOptedOut` before the block runs - ``OPS-77``. The
    block does NOT run under an opt-out: yielding ``None`` and letting the body
    proceed is what a busy bucket does, and a caller cannot tell the two apart
    from a ``None``. What a session should do when it is opted out of lane
    contention is the caller's decision to make explicitly, in words its own
    status line can carry.
    """
    held = acquire_lane(
        repo=repo, run_id=run_id, cycle=cycle, key=key, root=root, surplus=surplus
    )
    try:
        yield held
    finally:
        if held is not None:
            release(held, log=log)
