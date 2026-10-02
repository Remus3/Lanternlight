"""Report which channel notes have been READ and NOT ANSWERED - three buckets.

This module READS and nothing else. It opens two records plus this project's own
copies of the notes it sent, and it writes nothing, creates nothing and mutates
nothing. ``tests/test_answered.py`` asserts that by snapshotting a synthetic tree
before and after a run.

THE QUESTION, AND WHY IT NEEDS THREE ANSWERS RATHER THAN TWO
-----------------------------------------------------------
Two records exist here and neither one links a reply to the note it answers:

* ``ops/runtime/inbox_seen.json`` - the ``(name, digest)`` pairs the watcher has
  acknowledged. That set is what READ means in this module.
* ``moon_sync_inbox/_outbox/DELIVERIES.json`` - one row per note this project
  SENT. Some rows carry an ``answers`` list naming the inbound notes that reply
  answers. Older rows do not carry the key at all.

A row with no ``answers`` key has not said "this reply answered nothing". It has
said NOTHING. ``CLAUDE.md``'s measurement doctrine is explicit that a missing
field is ABSENT rather than a measured zero, and that "unmeasured" has to stay
distinguishable from "measured zero". So every inbound note lands in exactly one
of three buckets:

``RECORDED-ANSWERED``
    An ``answers`` list somewhere in the manifest names this note.
``RECORDED-UNANSWERED``
    EVERY sent row that could have answered it - strictly later than the note -
    carries an ``answers`` field, there is at least one such row, and none of
    those lists name it. The record covers the whole period and says no.
``UNKNOWN-THE-RECORD-CANNOT-SAY``
    Some sent row later than the note carries no ``answers`` field, or no row is
    later than it at all. The record is silent about part of that period, so
    there is no answer to report. See :func:`_period_is_covered` for why this is
    "every" and not "any".

Collapsing UNKNOWN into either neighbour is the defect this module exists to
prevent, so the shape resists it: :class:`RecordVerdict` carries all three
buckets as required fields, refuses construction when they overlap, exposes no
attribute that answers "how many answered" without naming the record it came
from, and prints all three lines even when two of them are zero.

THE LABELLED FALLBACK, AND WHY IT IS SECOND-CLASS
-------------------------------------------------
For the legacy window the record cannot speak, so an INFERENCE is offered beside
it - never merged into it. The rule is Amberstone's, published on the note
channel on 2026-10-02 and adopted here VERBATIM rather than reinvented, and it
is restated in :data:`INFERENCE_RULE`. It is a text test with no semantic
matching, and its third clause is loose on purpose. See :data:`INFERENCE_BIAS`
for the direction that looseness pushes the figure, which is the only thing a
reader of the number actually needs from us.

WHAT THIS MODULE WILL NOT DO
----------------------------
It reads no sibling tree: every path it opens is under this repository's own
root. It returns no note body and no operator identifier - a note's text is
searched for a match and then dropped, and only names, codes and counts reach
the output.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

__all__ = [
    "INFERENCE_BIAS",
    "INFERENCE_RULE",
    "KNOWN_SENDERS",
    "RECORDED_ANSWERED",
    "RECORDED_UNANSWERED",
    "UNKNOWN",
    "AnsweredReport",
    "Inference",
    "NoteRef",
    "RecordVerdict",
    "SentRow",
    "classify_record",
    "code_near_stamp",
    "infer",
    "load_read_notes",
    "load_sent_rows",
    "main",
    "parse_note_name",
    "reply_path_codes",
    "report",
    "sent_rows_from",
]


# ---------------------------------------------------------------------------
# bucket names
# ---------------------------------------------------------------------------

RECORDED_ANSWERED = "RECORDED-ANSWERED"
RECORDED_UNANSWERED = "RECORDED-UNANSWERED"
UNKNOWN = "UNKNOWN-THE-RECORD-CANNOT-SAY"

RECORD_BUCKETS = (RECORDED_ANSWERED, RECORDED_UNANSWERED, UNKNOWN)

INFERRED_ANSWERED = "INFERRED-ANSWERED"
INFERRED_UNANSWERED = "INFERRED-UNANSWERED"

INFERENCE_RULE = (
    "Amberstone's published rule, 2026-10-02, adopted verbatim: a sent note "
    "answers an inbound note only if it is strictly later AND it contains the "
    "inbound note's filename, or its full slug, or the sender's CODE within 15 "
    "characters of the STAMP on one line. No semantic matching."
)

INFERENCE_BIAS = (
    "BIAS: the code-plus-stamp clause matches loosely, so a false match moves a "
    "note from unanswered to answered. The inferred unanswered figure is "
    "therefore a FLOOR and not a ceiling - the true number of unanswered notes "
    "is at least this and may be higher. Measured example, kept so the size of "
    "the effect is not imagined: a note of RC's from 2026-09-06 is credited as "
    "answered by a reply of ours sent fifteen days later, on a coincidence "
    "between that reply's text and the note's code and stamp."
)


# ---------------------------------------------------------------------------
# senders
# ---------------------------------------------------------------------------

#: Channel codes this module can parse out of a note filename.
#:
#: ``CS``, ``LW``, ``RC``, ``RSC`` and ``SS`` are the carriers on the map in
#: ``docs/REPLY_PATHS.md``. ``MAIN`` is on this channel and has NO row on that
#: map - it writes into this inbox but this project has no recorded directory to
#: write back to. That asymmetry is why the list is kept here rather than taken
#: from ``ops/outbox.py``: the outbox map is a list of DESTINATIONS, and this is
#: a list of ORIGINS, and the two are not the same set.
KNOWN_SENDERS = ("CS", "LW", "MAIN", "RC", "RSC", "SS")

_REPLY_PATH_ROW = re.compile(r"^\|\s*`([A-Z]{2,4})`\s*\|", re.MULTILINE)


def reply_path_codes(text: str) -> tuple[str, ...]:
    """Return the channel codes in the ``docs/REPLY_PATHS.md`` table.

    Used by the test that fails if a sibling is added to that map and not to
    :data:`KNOWN_SENDERS`, in which case its notes would silently become
    unclassifiable rather than counted.
    """
    return tuple(sorted(set(_REPLY_PATH_ROW.findall(text))))


# ---------------------------------------------------------------------------
# inbound note filenames
# ---------------------------------------------------------------------------

_NOTE_NAME = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:-(?P<stamp>\d{4}))?"
    r"-from-(?P<sender>[A-Za-z]{2,4})-"
    r"(?P<slug>.+?)"
    r"\.md$"
)


@dataclass(frozen=True)
class NoteRef:
    """One inbound note, as far as its FILENAME can be trusted."""

    name: str
    sender: str
    date: str
    stamp: str | None
    slug: str
    when: datetime

    @property
    def stamp_known(self) -> bool:
        return self.stamp is not None


def parse_note_name(name: str) -> NoteRef | None:
    """Parse a channel note filename, or return ``None`` if we cannot.

    ``None`` is a statement about THIS PARSER and not about the file. Callers
    report such names under ``unclassifiable_by_our_parser`` for that reason.

    Two filename shapes are on this channel: ``DATE-HHMM-from-CODE-slug.md`` and
    a dateless ``DATE-from-CODE-slug.md``. A note with no stamp is placed at the
    START of its day, which is the earliest time consistent with the name, and
    :attr:`NoteRef.stamp_known` stays ``False`` so the inference's code-plus-stamp
    clause does not fire on a stamp we invented.
    """
    match = _NOTE_NAME.match(name)
    if match is None:
        return None
    sender = match.group("sender").upper()
    if sender not in KNOWN_SENDERS:
        return None
    stamp = match.group("stamp")
    # The stamp is inside the try as well as the date, because four digits are
    # not necessarily a time. An adversarial pass at the 2026-10-02 wrap found
    # that 2026-09-06-9999-from-RC-x.md raised "hour must be in 0..23" and took
    # the whole report down, in a function whose own docstring promises None for
    # anything it cannot read. No such name is on the channel today; the defect
    # was the gap between the promise and the code.
    try:
        day = datetime.strptime(match.group("date"), "%Y-%m-%d")
        when = day if stamp is None else day.replace(hour=int(stamp[:2]), minute=int(stamp[2:]))
    except ValueError:
        return None
    return NoteRef(
        name=name,
        sender=sender,
        date=match.group("date"),
        stamp=stamp,
        slug=match.group("slug"),
        when=when,
    )


# ---------------------------------------------------------------------------
# sent rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SentRow:
    """One row of ``DELIVERIES.json``, reduced to what this question needs."""

    name: str
    when: datetime | None
    time_source: str
    has_answers: bool
    answers: tuple[str, ...]

    @property
    def time_is_arrival_not_send(self) -> bool:
        """True when the only time available is when the file LANDED somewhere.

        A reconstructed row's ``earliest_seen_local`` is the moment a copy was
        found, not the moment the note was sent, and the manifest says so in its
        own ``note`` field. Treating it as a send time can only make the row look
        LATER than it was, which pushes the inference toward answered.
        """
        return self.time_source == "earliest_seen_local"


def _strip_md(name: str) -> str:
    return name[:-3] if name.endswith(".md") else name


def _row_time(row: Mapping[str, object]) -> tuple[datetime | None, str]:
    for key in ("sent_local", "earliest_seen_local"):
        raw = row.get(key)
        if isinstance(raw, str) and raw:
            try:
                return datetime.fromisoformat(raw), key
            except ValueError:
                return None, "unparsable"
    raw = row.get("sent_utc")
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw.rstrip("Z")), "sent_utc_read_as_naive"
        except ValueError:
            return None, "unparsable"
    return None, "none"


def sent_rows_from(rows: Iterable[Mapping[str, object]]) -> tuple[SentRow, ...]:
    """Build :class:`SentRow` objects from raw manifest rows.

    ``has_answers`` is the presence of the KEY, never the truth of the list. An
    empty ``answers`` list is a reply that answered no inbound note and is a
    measured zero; an absent key is not a zero at all.
    """
    out: list[SentRow] = []
    for row in rows:
        when, source = _row_time(row)
        raw = row.get("answers")
        has = "answers" in row and isinstance(raw, list)
        answers = tuple(str(a) for a in raw) if isinstance(raw, list) else ()
        out.append(
            SentRow(
                name=str(row.get("name", "")),
                when=when,
                time_source=source,
                has_answers=has,
                answers=answers,
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# the RECORD
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RecordVerdict:
    """What the RECORD says, in three buckets that cannot be collapsed to two.

    There is deliberately no ``answered`` or ``unanswered`` attribute here. A
    caller that wants a number has to name which bucket it means, so no caller
    can read a two-way figure out of a three-way fact by accident.
    """

    recorded_answered: tuple[str, ...]
    recorded_unanswered: tuple[str, ...]
    unknown: tuple[str, ...]
    unclassifiable_by_our_parser: tuple[str, ...]
    by_sender: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    problems: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        buckets = (
            set(self.recorded_answered),
            set(self.recorded_unanswered),
            set(self.unknown),
        )
        for i, left in enumerate(buckets):
            for right in buckets[i + 1 :]:
                overlap = sorted(left & right)
                if overlap:
                    raise ValueError(
                        "the three record buckets must be disjoint; "
                        f"{len(overlap)} name(s) appear in more than one"
                    )

    def counts(self) -> dict[str, int]:
        """All three buckets, always, including the zeros."""
        return {
            RECORDED_ANSWERED: len(self.recorded_answered),
            RECORDED_UNANSWERED: len(self.recorded_unanswered),
            UNKNOWN: len(self.unknown),
        }

    def format(self) -> str:
        lines = ["RECORD - what DELIVERIES.json can and cannot say"]
        for bucket, n in self.counts().items():
            lines.append(f"  {bucket}: {n}")
        lines.append(
            f"  unclassifiable_by_our_parser: {len(self.unclassifiable_by_our_parser)}"
            " (a limit of OUR filename parser, not a property of the note)"
        )
        if self.by_sender:
            lines.append("  by sender:")
            for sender in sorted(self.by_sender):
                row = self.by_sender[sender]
                lines.append(
                    f"    {sender}: "
                    + ", ".join(f"{b}={row.get(b, 0)}" for b in RECORD_BUCKETS)
                )
        for problem in self.problems:
            lines.append(f"  PROBLEM: {problem}")
        return "\n".join(lines)


def _empty_tally() -> dict[str, int]:
    return dict.fromkeys(RECORD_BUCKETS, 0)


def classify_record(
    notes: Iterable[NoteRef],
    rows: Sequence[SentRow],
    unclassifiable: Iterable[str] = (),
    problems: Iterable[str] = (),
) -> RecordVerdict:
    """Place every inbound note in exactly one of the three record buckets."""
    named: set[str] = set()
    for row in rows:
        for answer in row.answers:
            named.add(_strip_md(answer))

    answered_names: list[str] = []
    unanswered_names: list[str] = []
    unknown_names: list[str] = []
    by_sender: dict[str, dict[str, int]] = {}

    for note in notes:
        if _strip_md(note.name) in named:
            bucket = RECORDED_ANSWERED
            answered_names.append(note.name)
        elif _period_is_covered(note, rows):
            bucket = RECORDED_UNANSWERED
            unanswered_names.append(note.name)
        else:
            bucket = UNKNOWN
            unknown_names.append(note.name)
        by_sender.setdefault(note.sender, _empty_tally())[bucket] += 1

    # A CITATION WE CANNOT PLACE IS A STATEMENT ABOUT OUR POPULATION, so it is
    # reported rather than dropped. Found by an adversarial pass at the
    # 2026-10-02 wrap: the first real recording row cited TWO notes and the
    # report showed ONE, silently, because the population is the SEEN set and the
    # other note was on disk but unseen. A recorded answer that vanishes is the
    # same failure as a suggestion filed outside ROADMAP.md - it exists and
    # nothing will ever surface it.
    placed = {_strip_md(note.name) for note in notes}
    extra = sorted(named - placed)
    reported = list(problems)
    for name in extra:
        reported.append(
            f"a manifest row records an answer to {name}, which is NOT in the "
            "population this report covers - the citation is kept here rather "
            "than dropped, and it counts in no bucket"
        )

    return RecordVerdict(
        recorded_answered=tuple(answered_names),
        recorded_unanswered=tuple(unanswered_names),
        unknown=tuple(unknown_names),
        unclassifiable_by_our_parser=tuple(unclassifiable),
        by_sender=by_sender,
        problems=tuple(reported),
    )


def _period_is_covered(note: NoteRef, rows: Sequence[SentRow]) -> bool:
    """Does the record carry an ``answers`` field across this note's WHOLE period?

    The period that matters for one inbound note is everything a reply could have
    been sent in: strictly after the note. Coverage means EVERY sent row in that
    window carries the field, plus at least one row being in it at all.

    "Every", not "any", and the difference is the whole point. A reply sent in
    the modern era that does not name a note from 2026-09-06 says nothing about
    that note, because one of the legacy replies in between - the ones with no
    ``answers`` key - may well have been the answer. Requiring only ONE later
    annotated row would silently reclassify the entire legacy backlog as
    RECORDED-UNANSWERED the moment a single modern reply went out, which is
    exactly the confident-wrong-number failure this module exists to prevent.

    A row with no usable timestamp cannot be placed in or out of the window, so
    it is treated as a hole rather than as coverage. That is the fail-closed
    direction: it lands the note in UNKNOWN instead of inventing a verdict.
    """
    in_period = 0
    for row in rows:
        if row.when is None:
            return False
        if row.when > note.when:
            in_period += 1
            if not row.has_answers:
                return False
    return in_period > 0


# ---------------------------------------------------------------------------
# the INFERENCE - Amberstone's rule, kept separate
# ---------------------------------------------------------------------------

_LINE_SPLIT = re.compile(r"\r\n|\r|\n")


def code_near_stamp(text: str, code: str, stamp: str, window: int = 15) -> bool:
    """Clause three of the rule: CODE within ``window`` characters of STAMP.

    "Within 15 characters" is measured as the gap between the two tokens on ONE
    line - the characters strictly between them - so an adjacent pair has a gap
    of zero. A line break ends the window, which is what "on one line" means.
    Both orders count, because "RC's 1745 note" and "the 1745 note from RC" say
    the same thing.
    """
    code_re = re.compile(r"(?<![A-Za-z])" + re.escape(code) + r"(?![A-Za-z])")
    stamp_re = re.compile(r"(?<!\d)" + re.escape(stamp) + r"(?!\d)")
    for line in _LINE_SPLIT.split(text):
        codes = [(m.start(), m.end()) for m in code_re.finditer(line)]
        if not codes:
            continue
        stamps = [(m.start(), m.end()) for m in stamp_re.finditer(line)]
        for c_start, c_end in codes:
            for s_start, s_end in stamps:
                gap = s_start - c_end if s_start >= c_end else c_start - s_end
                if 0 <= gap <= window:
                    return True
    return False


def _sent_text_answers(text: str, note: NoteRef) -> bool:
    if note.name in text:
        return True
    if note.slug and note.slug in text:
        return True
    return note.stamp is not None and code_near_stamp(
        text, note.sender, note.stamp
    )


@dataclass(frozen=True)
class Inference:
    """A labelled, second-class guess. Never merged into :class:`RecordVerdict`.

    HOW SENSITIVE THIS NUMBER IS TO CLAUSE THREE, measured 2026-10-02 over this
    tree and recorded because the figure is useless without it.

    THE DOMINANT VARIABLE IS THE STAMP TOKEN, not the window - adjudicated after
    two implementations of one published rule disagreed by more than a factor of
    two on the same tree. This module admits ONLY the four-digit HHMM. A sibling
    implementation also admitted the ten-character DATE, and that single change
    moved the answered count from 51 to 152 at the same population. A ten-char
    date inside a thirty-char window is far easier to hit than a four-char time,
    so admitting it is not a small widening.

    Amberstone's own words exclude the date reading, three times over, which is
    why this module is strict: its note says the window admits coincidental
    FOUR-DIGIT matches; it says some notes have no stamp in the filename at all
    so the rule cannot apply to them, which is only true if a date is not a
    stamp, since every filename on this channel carries a date; and it says a
    code-and-stamp hit can COLLIDE with another note from the same sender, which
    only a reused HHMM does. Its worked example ``LL 2026-09-20 1330`` is still
    admitted under the HHMM reading, because the gap from the code to 1330 is
    twelve characters and fits inside fifteen.

    Second, smaller axis: dropping the one-line fifteen-character window moves
    roughly a seventh of the population. Third: the sent-note timestamp source is
    UNSPECIFIED by the published rule and is worth 19 to 20 notes here, and the
    arrival-timed rows can only push toward answered. Fourth: the population
    itself is undefined by the rule, and is worth about one note.

    So the figure this class prints is a statement about four unstated choices as
    much as about the channel, and two trees quoting "Amberstone's rule" can
    differ by a factor of two while both believing they implemented it. This
    project published a figure under the date reading and WITHDREW it. Re-measure
    rather than quoting a number from here; the counts move with every note.
    """

    inferred_answered: tuple[str, ...]
    inferred_unanswered: tuple[str, ...]
    by_sender: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    sent_notes_considered: int = 0
    sent_text_missing: tuple[str, ...] = ()
    rows_without_time: tuple[str, ...] = ()
    rows_timed_by_arrival: tuple[str, ...] = ()
    rule_source: str = INFERENCE_RULE
    bias: str = INFERENCE_BIAS

    def counts(self) -> dict[str, int]:
        return {
            INFERRED_ANSWERED: len(self.inferred_answered),
            INFERRED_UNANSWERED: len(self.inferred_unanswered),
        }

    def format(self) -> str:
        lines = [
            "INFERENCE - NOT the record. A text guess over the legacy window.",
            f"  rule: {self.rule_source}",
            f"  {self.bias}",
            f"  sent notes considered: {self.sent_notes_considered}",
        ]
        for bucket, n in self.counts().items():
            lines.append(f"  {bucket}: {n}")
        if self.sent_text_missing:
            lines.append(
                "  sent notes with a manifest row but no local copy: "
                f"{len(self.sent_text_missing)} (they can match nothing)"
            )
        if self.rows_without_time:
            lines.append(
                "  sent rows with no usable timestamp, excluded from the rule: "
                f"{len(self.rows_without_time)}"
            )
        if self.rows_timed_by_arrival:
            lines.append(
                "  sent rows timed by ARRIVAL rather than send: "
                f"{len(self.rows_timed_by_arrival)}"
            )
        if self.by_sender:
            lines.append("  by sender:")
            for sender in sorted(self.by_sender):
                row = self.by_sender[sender]
                lines.append(
                    f"    {sender}: "
                    + f"{INFERRED_ANSWERED}={row.get(INFERRED_ANSWERED, 0)}, "
                    + f"{INFERRED_UNANSWERED}={row.get(INFERRED_UNANSWERED, 0)}"
                )
        return "\n".join(lines)


def infer(
    notes: Iterable[NoteRef], rows: Sequence[SentRow], outbox_dir: Path
) -> Inference:
    """Apply Amberstone's rule over this project's own copies of what it sent.

    The sent note's TEXT is read, searched, and dropped. No body, no line and no
    excerpt reaches the result - only the inbound note's own name.
    """
    usable: list[tuple[SentRow, str]] = []
    missing: list[str] = []
    no_time: list[str] = []
    by_arrival: list[str] = []
    for row in rows:
        if row.when is None:
            no_time.append(row.name)
            continue
        if row.time_is_arrival_not_send:
            by_arrival.append(row.name)
        path = outbox_dir / row.name
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            missing.append(row.name)
            continue
        usable.append((row, text))

    answered_names: list[str] = []
    unanswered_names: list[str] = []
    by_sender: dict[str, dict[str, int]] = {}
    for note in notes:
        hit = any(
            row.when is not None
            and row.when > note.when
            and _sent_text_answers(text, note)
            for row, text in usable
        )
        bucket = INFERRED_ANSWERED if hit else INFERRED_UNANSWERED
        (answered_names if hit else unanswered_names).append(note.name)
        by_sender.setdefault(
            note.sender, {INFERRED_ANSWERED: 0, INFERRED_UNANSWERED: 0}
        )[bucket] += 1

    return Inference(
        inferred_answered=tuple(answered_names),
        inferred_unanswered=tuple(unanswered_names),
        by_sender=by_sender,
        sent_notes_considered=len(usable),
        sent_text_missing=tuple(missing),
        rows_without_time=tuple(no_time),
        rows_timed_by_arrival=tuple(by_arrival),
    )


# ---------------------------------------------------------------------------
# loading this repository's own records
# ---------------------------------------------------------------------------


def _repo_root(root: Path | str | None) -> Path:
    if root is not None:
        return Path(root)
    return Path(__file__).resolve().parents[1]


def seen_path(root: Path | str | None = None) -> Path:
    return _repo_root(root) / "ops" / "runtime" / "inbox_seen.json"


def outbox_dir(root: Path | str | None = None) -> Path:
    return _repo_root(root) / "moon_sync_inbox" / "_outbox"


def manifest_path(root: Path | str | None = None) -> Path:
    return outbox_dir(root) / "DELIVERIES.json"


def _load_json(path: Path) -> tuple[object | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None, f"unreadable or absent: {path.name}"
    try:
        return json.loads(raw), None
    except ValueError as exc:
        return None, f"not valid JSON: {path.name}: {exc.__class__.__name__}"


def load_read_notes(root: Path | str | None = None) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(names, problems)`` for the notes the watcher has acknowledged.

    READ means present in the seen set. A name appearing twice with two digests
    is one note that was edited, so names are de-duplicated while order is kept.
    """
    payload, problem = _load_json(seen_path(root))
    if problem is not None:
        return (), (f"no seen record ({problem})",)
    if not isinstance(payload, dict) or not isinstance(payload.get("seen"), list):
        return (), ("no seen record (unexpected shape in inbox_seen.json)",)
    names: list[str] = []
    for entry in payload["seen"]:
        if isinstance(entry, (list, tuple)) and entry:
            name = str(entry[0])
        elif isinstance(entry, str):
            name = entry
        else:
            continue
        if name not in names:
            names.append(name)
    return tuple(names), ()


def load_sent_rows(
    root: Path | str | None = None,
) -> tuple[tuple[SentRow, ...], tuple[str, ...]]:
    """Return ``(rows, problems)`` for the delivery manifest."""
    payload, problem = _load_json(manifest_path(root))
    if problem is not None:
        return (), (f"no delivery manifest ({problem})",)
    if not isinstance(payload, dict) or not isinstance(payload.get("deliveries"), list):
        return (), ("no delivery manifest (unexpected shape in DELIVERIES.json)",)
    rows = [r for r in payload["deliveries"] if isinstance(r, dict)]
    return sent_rows_from(rows), ()


# ---------------------------------------------------------------------------
# the whole report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnsweredReport:
    """The RECORD, and optionally the INFERENCE beside it. Never merged."""

    record: RecordVerdict
    inference: Inference | None = None
    notes_read: int = 0

    def format(self) -> str:
        lines = [
            "READ AND NOT ANSWERED",
            f"  inbound notes marked READ: {self.notes_read}",
            "",
            self.record.format(),
        ]
        if self.inference is not None:
            lines.extend(["", self.inference.format()])
        return "\n".join(lines)


def report(
    root: Path | str | None = None, *, with_inference: bool = True
) -> AnsweredReport:
    """Read both records and return the three-bucket verdict.

    Writes nothing. Reads nothing outside ``root``, which defaults to this
    repository.
    """
    names, seen_problems = load_read_notes(root)
    rows, row_problems = load_sent_rows(root)

    refs: list[NoteRef] = []
    unclassifiable: list[str] = []
    for name in names:
        ref = parse_note_name(name)
        if ref is None:
            unclassifiable.append(name)
        else:
            refs.append(ref)

    record = classify_record(
        refs, rows, unclassifiable=unclassifiable, problems=seen_problems + row_problems
    )
    inference = infer(refs, rows, outbox_dir(root)) if with_inference else None
    return AnsweredReport(record=record, inference=inference, notes_read=len(names))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report which READ channel notes the record says are unanswered."
    )
    parser.add_argument("--root", default=None, help="repository root to read")
    parser.add_argument(
        "--no-inference",
        action="store_true",
        help="print the RECORD only, with no fallback guess",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    print(report(root=args.root, with_inference=not args.no_inference).format())
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
