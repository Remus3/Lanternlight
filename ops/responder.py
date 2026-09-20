"""Draft replies to unread channel mail, and SEND NOTHING - ``OPS-68``.

THE SCOPE WAS ADJUDICATED, NOT CHOSEN HERE
------------------------------------------
``ROADMAP.md`` ``OPS-68`` records the adjudicated scope on 2026-09-14, and this
module implements exactly it and not one step more:

* It READS this tree and the gitignored ``moon_sync_inbox/``.
* It WRITES drafts into ``moon_sync_inbox/_drafts/`` and nowhere else.
* It DELIVERS nothing, and that is asserted about the RUN and not only about
  this file's text. ``tests/test_responder.py`` runs :func:`run` in a
  subprocess under :func:`sys.addaudithook` and fails if the interpreter opens,
  compiles, executes or imports anything named ``outbox``, or writes outside
  the drafts directory. The static checks beside it - no import node naming the
  outbox, no call spelled ``deliver``, no ``importlib`` or ``getattr`` - are
  defence in depth and are claims about the SOURCE TEXT. They were all three
  defeated at once on 2026-09-20 by
  ``importlib.import_module("ops." + "out" + "box")``, which is why the runtime
  guard exists: a name built at run time is not in the source to be found, and
  an audit hook sits below name resolution.
* It ADOPTS nothing, and it EXECUTES nothing a note asks for. A note is MAIL.
  An imperative sentence in a note reaches a draft as a QUOTED, UNANSWERED line
  and never as an action.

WHY DRAFT-ONLY, AND THE MEASUREMENT BEHIND IT
---------------------------------------------
On 2026-09-20 this project published two wrong figures to five trees inside four
hours - ``LL-0271`` and ``LL-0277`` - and withdrew both on the channel. The
second was produced by a regex character class that matched forward slashes
only. A runner that sent would have amplified those faster rather than caught
them, so delivery stays a session act until this runner has a measured record of
its own.

That history is why :func:`invented_numbers` exists and why it is a HARD
invariant rather than a style rule: **every digit run in a draft is a digit run
that was read out of the note or its filename.** Nothing here restates, rounds,
recomputes or re-separates a figure. The draft's own timestamp is a PLACEHOLDER
for the same reason - a real one would be a number this module made up, and a
draft is supposed to be unfinished anyway.

WHAT IS REUSED FROM ``ops/inbox_watch.py``, AND THE ONE THING THAT IS NOT
------------------------------------------------------------------------
Reused, never reimplemented: :func:`~ops.inbox_watch.classify` for the
OURS / POSSIBLY OURS / NOT OURS buckets and the reasons behind them,
:func:`~ops.inbox_watch.load_seen` for the ``(name, digest)`` seen-set key,
:func:`~ops.inbox_watch.digest_of` for the content half of that key, and
:func:`~ops.inbox_watch.safe_label` for every channel-chosen name that reaches
an output.

NOT reused: :func:`~ops.inbox_watch.scan`. It is the right reader and the wrong
CALLER for this job, because every one of its paths writes the reported record -
a report-only run takes the union write, and an acknowledging run rewrites both
records. Drafting is not reporting and it is certainly not acknowledging, so a
drafting pass that moved another module's records would make a second module's
output depend on whether this one had run. This module therefore reads the
top-level Markdown entries itself and decides newness from the seen set alone,
which is the same rule ``scan`` uses and none of its writes.

NEWNESS, AND WHAT IT MEANS HERE
-------------------------------
A note is UNREAD when its ``(name, digest)`` pair is absent from the watcher's
acknowledged set. That is the watcher's own definition, so an edited note
re-drafts - and on an asynchronous channel the edit is usually the correction,
which is exactly the case a reply must not miss.

NEVER OVERWRITE AN EDIT
-----------------------
A draft this module wrote is recorded in ``_drafts/DRAFTS.json`` with the digest
of the bytes it wrote. On a later run a draft whose bytes no longer match that
digest is LEFT ALONE and reported, because a human or a session has worked on
it and that work outranks a regenerated skeleton. A manifest that is missing or
unreadable makes every existing draft untouchable, which is the fail-closed
direction: losing a regeneration costs one command, losing an edit costs the
edit.

WRITES ARE ATOMIC
-----------------
Temporary file in the target's own directory, then :meth:`pathlib.Path.replace`.
A draft is something a reader polls, and this repository requires it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ops.inbox_watch import (
    NOTE_NAME_DISPLAY_LIMIT,
    OURS,
    UNSURE,
    classify,
    default_inbox,
    default_state_path,
    digest_of,
    load_seen,
    safe_label,
)

__all__ = [
    "DRAFTS_DIRNAME",
    "MANIFEST_FILENAME",
    "REPO_ROOT",
    "SOURCE_PATH",
    "TEMP_PREFIX",
    "UNANSWERED",
    "Draft",
    "NoteFacts",
    "Question",
    "RunResult",
    "default_drafts_dir",
    "extract_facts",
    "extract_questions",
    "invented_numbers",
    "main",
    "number_tokens",
    "pending_report",
    "render_draft",
    "run",
]

#: Repository root, resolved from this file's location: ops/responder.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: This module's own path. The tests parse it rather than guessing where it is.
SOURCE_PATH = Path(__file__).resolve()

#: Where drafts live: INSIDE the already-gitignored channel directory.
#:
#: Measured rather than assumed, per ``CLAUDE.md``:
#: ``git check-ignore -v moon_sync_inbox/_drafts/probe.md`` exits 0 and names
#: ``.gitignore:208:moon_sync_inbox/`` as the rule that covers it. A draft is
#: derived from a gitignored channel, and nothing derived from that channel is
#: ever committed. ``tests/test_responder.py`` re-asks git on every run rather
#: than trusting this comment.
DRAFTS_DIRNAME = "_drafts"

#: The record of what THIS module wrote, beside the drafts it describes.
MANIFEST_FILENAME = "DRAFTS.json"

#: Prefix on every temporary file written here, so a test can prove the write
#: really went temp-then-replace rather than truncating the target in place.
TEMP_PREFIX = ".responder-"

#: The placeholder that makes a draft obviously unfinished. It is a single
#: token so a grep for it over the drafts directory answers "is anything here
#: sendable" in one command, and so a draft delivered by accident reads as a
#: draft rather than as a claim.
UNANSWERED = "[UNANSWERED]"

#: Schema marker on the manifest. An unrecognised value is treated as
#: unreadable, which makes every existing draft untouchable - the safe
#: direction, because losing a regeneration costs one command and losing a
#: human's edit costs the edit.
SCHEMA = 1


# ---------------------------------------------------------------------------
# numbers - the hard invariant
# ---------------------------------------------------------------------------

#: One number, separators included. ``1,416`` is ONE token and not ``1`` beside
#: ``416``; ``12.4`` is ONE token and not ``12`` beside ``4``.
#:
#: The separators are the whole point. A tokenizer that split on them would
#: score a draft saying ``1416`` as quoting a note that said ``1,416``, and a
#: draft saying ``12`` as quoting a note that said ``12.4`` - which is precisely
#: the restate-and-round failure this module exists to make impossible.
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def number_tokens(text: str) -> list[str]:
    """Every number in ``text``, in order, with its separators intact."""
    return _NUMBER.findall(text)


def invented_numbers(draft: str, sources) -> list[str]:
    """Numbers in ``draft`` that appear in none of ``sources``, in order.

    This is the guard the draft-only shape exists to satisfy. A number is
    accepted only when the IDENTICAL token - separators and all - is present in
    a source, so a restated ``1416`` against a source's ``1,416`` is reported,
    and so is a rounded ``12`` against a source's ``12.4``.

    Args:
        draft: The rendered draft.
        sources: The note text and its filename - everything this module was
            allowed to read a figure out of.

    Returns:
        The offending tokens, in the order they appear in the draft. Empty is
        the only acceptable result for anything this module writes.
    """
    allowed: set[str] = set()
    for source in sources:
        allowed.update(number_tokens(source))
    return [token for token in number_tokens(draft) if token not in allowed]


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------

#: The heading CHANNEL.md section 2 specifies: ``# From <CODE> - <CLASS>: <subject>``.
#: The class is optional here because notes predating the convention exist on
#: disk and an absent class is recorded as absent rather than guessed.
_HEADING = re.compile(
    r"^#\s+From\s+([A-Za-z]{2,3})\s*(?:-\s*([A-Z]+)\s*)?:\s*(.+?)\s*$",
    re.MULTILINE,
)

#: The sender as the FILENAME grammar carries it - CHANNEL.md section 1's
#: primary form and its Variant A. Used only when the heading does not answer.
_FILENAME_SENDER = re.compile(r"-from-([A-Za-z]{2,3})-")

#: A classification prefix inside the filename slug. CHANNEL.md section 3 says
#: it sits after the date and the sender code and is never anchored at the start
#: of the name, so this is deliberately not anchored either. ``CORRECTION`` is
#: included because the channel sends RULING then ADDENDUM then CORRECTION as a
#: matter of course - see that document's watcher-properties section.
_FILENAME_CLASS = re.compile(r"-(FYI|REVIEW|ACTION|CORRECTION)-")

#: The classes this module will report. Anything else is an absent class.
_CLASSES = ("FYI", "REVIEW", "ACTION", "CORRECTION")

#: The note's own timestamp line, per CHANNEL.md section 2: it follows the
#: heading and ends with the word ``local``. The date-and-time shape is required
#: so a prose sentence containing the word cannot be mistaken for the stamp.
_TIMESTAMP = re.compile(
    r"^\s*(\d{4}-\d{2}-\d{2}[ T]\d{2}:?\d{2}(?::\d{2})?)\s+local\b",
    re.MULTILINE | re.IGNORECASE,
)

#: A markdown section heading, at any level.
_SECTION = re.compile(r"^(#{2,6})\s*(.+?)\s*$")

#: Verbs a request on this channel actually opens with. Measured from the notes
#: on disk rather than invented: the channel's requests are overwhelmingly
#: "confirm X", "say so in one line", "answer with what you measured",
#: "re-hash from your own disk".
_REQUEST_VERB = re.compile(
    r"^(?:please\s+)?"
    r"(confirm|say|answer|tell|reply|respond|report|state|name|give|list|send"
    r"|provide|share|measure|re-measure|check|re-check|verify|hash|re-hash"
    r"|acknowledge|ack|adopt|decline|withdraw|correct|clarify|explain|describe"
    r"|point|flag|pick|choose|delete|remove|add|apply|run|read|use|keep|drop)\b",
    re.IGNORECASE,
)

#: Sentence boundary. Deliberately simple, and its cost is named in
#: :func:`extract_questions`.
#:
#: The three alternatives are ONE rule: a terminator, then up to two Markdown
#: emphasis markers, then the space. ``**Say it explicitly.** A responder
#: exchange ...`` is two sentences and the plain ``(?<=[.?!])\s+`` saw one,
#: because the space after the full stop is preceded by ``*``. Measured on a
#: real note 2026-09-20. The lookbehinds are fixed width because Python's
#: ``re`` requires it, and they do not CONSUME the markers, so the quotation
#: keeps the emphasis the sender wrote.
_SENTENCE_SPLIT = re.compile(
    r"(?:(?<=[.?!])|(?<=[.?!][*_`])|(?<=[.?!][*_`][*_`]))\s+"
)

#: Markdown emphasis at either end of a sentence. Stripped for the two
#: DETECTION tests and never from the quoted text - see :func:`_undecorated`.
#:
#: ASTERISKS ONLY, and that is a MEASURED narrowing rather than an oversight.
#: A first cut stripped ``_`` and a backtick as well, on the reasoning that
#: both are emphasis in Markdown. Re-measured the same day over the five real
#: notes the adversarial pass graded, it invented two false questions and found
#: none: a leading ``_`` on this channel opens a PYTHON IDENTIFIER
#: (``_read on a truncated write returns empty`` scored as the verb "read"),
#: and a leading backtick opens an inline code span naming one
#: (`` `State : Ready` is worth nothing`` scored as the verb "state"). Bold
#: asterisks around a whole sentence are the only one the channel uses as
#: emphasis, and they are the one that was costing a real ask.
_EMPHASIS_EDGE = re.compile(r"^\*+|\*+$")


@dataclass(frozen=True)
class Question:
    """One thing a note asks of us, with how it was detected and where from."""

    text: str
    #: ``question-mark`` or ``imperative``. A reader grading the extractor needs
    #: to know which rule fired, because the two have different failure modes.
    detection: str
    #: The nearest preceding ``##`` heading, or ``""`` at the top of the note.
    section: str


@dataclass(frozen=True)
class NoteFacts:
    """What was measured out of one note."""

    name: str
    sender: str
    #: ``heading``, ``filename`` or ``unmeasured`` - which half answered. The
    #: two disagree on real notes, and a draft that could not say which it
    #: trusted would be unreviewable.
    sender_source: str
    classification: str
    classification_source: str
    subject: str
    timestamp: str
    reply_target: str
    questions: tuple[Question, ...]


def _collapse(text: str) -> str:
    """Collapse all whitespace to single spaces.

    Prose on this channel is hard-wrapped near 80 columns, so a single question
    routinely spans two lines. ``CLAUDE.md``: a line-oriented grep is a claim
    about the file's line breaks, and this repository has had two false clean
    bills from exactly that.
    """
    return " ".join(text.split())


def _strip_code_fences(text: str) -> str:
    """Remove fenced code blocks, keeping the line count intact.

    A fenced block is a QUOTATION of machinery - a command, a payload, a diff -
    and a question mark inside one is punctuation rather than a question. The
    lines are blanked rather than deleted so a later line number still refers to
    the same line of the original note.
    """
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            inside = not inside
            out.append("")
            continue
        out.append("" if inside else line)
    return "\n".join(out)


def _undecorated(sentence: str) -> str:
    """``sentence`` with leading and trailing Markdown emphasis removed.

    This is for the DETECTION tests only. The text a draft quotes is always the
    sentence as the sender wrote it, markers included, because a draft that
    re-punctuated its source would be restating it.

    It exists because of a measured miss rather than a hunch: on 2026-09-20 an
    adversarial pass read five real notes by hand and found
    ``**Say it explicitly, not by silence.**`` invisible to rule two. The verb
    ``say`` is in the list; ``_REQUEST_VERB`` is anchored with a caret; and the
    list-marker strip removed a leading dash but not a leading ``**``.
    """
    return _EMPHASIS_EDGE.sub("", sentence).strip()


def _blocks(text: str, include_headings: bool = False) -> list[tuple[str, str, str]]:
    """Return ``(section, body, kind)`` for each block. ``kind`` names the shape.

    ``kind`` is ``paragraph`` or ``heading``, and the caller needs the
    difference because the two are read by different rules - a heading is a
    LABEL and is never split into sentences. See :func:`extract_questions`.
    """
    blocks: list[tuple[str, str, str]] = []
    section = ""
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            joined = _collapse(" ".join(buffer))
            if joined:
                blocks.append((section, joined, "paragraph"))
            buffer.clear()

    for line in _strip_code_fences(text).splitlines():
        heading = _SECTION.match(line)
        if heading:
            flush()
            section = heading.group(2)
            if include_headings and section:
                blocks.append((section, section, "heading"))
            continue
        if not line.strip():
            flush()
            continue
        if line.lstrip().startswith("#"):
            flush()
            continue
        stripped = line.strip()
        # A list marker is layout, not sentence content. Stripping it lets a
        # bulleted imperative reach the verb test, which is how this channel
        # actually writes a list of asks.
        stripped = re.sub(r"^(?:[-*+]|\d+[.)])\s+", "", stripped)
        buffer.append(stripped)
    flush()
    return blocks


def _paragraphs(text: str) -> list[tuple[str, str]]:
    """Return ``(section heading, collapsed paragraph)`` for each paragraph.

    Headings are section LABELS here and are not returned as content. That is
    what :func:`_reply_target` wants; :func:`extract_questions` asks
    :func:`_blocks` for them instead.
    """
    return [(section, body) for section, body, kind in _blocks(text) if kind == "paragraph"]


def extract_questions(text: str) -> tuple[Question, ...]:
    """Every question this note puts to us, by two rules, with both stated.

    RULE ONE - a sentence ending in ``?``. A question mark is a WEAK signal: it
    is present on rhetorical questions and on questions the sender is quoting
    from somebody else, and absent from most real requests on this channel.

    RULE TWO - a sentence opening with a request verb. The channel's asks are
    written as imperatives - "confirm X", "say so in one line", "answer with
    what you measured" - and carry no question mark at all. The verb list is
    measured from the notes on disk, not invented, and it is a list, so a verb
    outside it is invisible to this rule.

    WHERE THE RULES ARE APPLIED. Both rules read PARAGRAPHS. A HEADING is read
    by rule one ALONE, as a single unit that is never split into sentences.
    Both halves of that are measured rather than tidy:

    * A heading can carry the whole ask, and one used to be invisible. A
      34,807-byte REVIEW note addressed to this project yielded ZERO questions
      on 2026-09-20 because both of its question marks sat in level-three
      headings that were consumed as section labels.
    * Rule two is kept OFF headings because every note on this channel ends
      with a ``## Reply`` heading and ``reply`` is in the verb list above, so
      scanning headings as prose would invent one false question on every note
      that has ever arrived here.
    * A heading is not sentence-split because this channel writes
      ``### Is X a real ceiling? NO. It is a ceiling on RC's SAMPLE.`` - asked
      and answered in the same breath, with nothing left for us to answer.
      Only a heading that ENDS in a question mark is an open ask.

    WHAT THIS EXTRACTOR CANNOT SEE, recorded here rather than left in a chat
    log, because a caveat stated out loud and dropped from the artifact is a lie
    in the artifact. The last six were MEASURED rather than imagined. An
    adversarial pass on 2026-09-20 read five real notes by hand, counted eleven
    genuine asks, and scored this function at PRECISION 6/8 and RECALL 6/11 -
    75 and 55 per cent. Looking through a bold marker and reading headings
    moved that to PRECISION 7/9 and RECALL 7/11 - 78 and 64 per cent - on the
    same five notes, and everything below is what is still missing at that
    score. A limit nobody declared is the one a reader trusts through:

    * A question in STATEMENT form. "I would like to know whether your watcher
      caps its listing" asks something and matches neither rule.
    * A RHETORICAL question. Rule one cannot tell one from a real one, so a
      rhetorical question arrives as a draft line that needs no answer.
    * A QUOTED question - one the sender is reporting another tree asked - is
      extracted as though it were addressed to us. Only fenced code blocks are
      excluded; a blockquote is not.
    * A question addressed to a DIFFERENT RECIPIENT in a note that goes to all
      five trees. Nothing here reads the address list, so "RC, confirm the slot
      table" is drafted for us as readily as a question meant for us.
    * An imperative whose verb is outside the list above.
    * A question whose SUBJECT is in a preceding sentence - "We changed the lock
      namespace. Does that work for you?" arrives without the first sentence.
    * Anything in a payload that is not this note: a directory drop beside the
      notes, or a non-Markdown attachment. Neither is read here at all.
    * A NARRATIVE imperative, which rule two reports as an ask. "Run here
      today on this machine:" introduces a measurement block and "Read the
      function rather than the name" describes the sender's own code; both
      were extracted on 2026-09-20 and both are the entire false-positive
      count at the score above. Rule two reads the VERB and cannot read who
      the sentence is aimed at.
    * A CONDITIONAL ask - one opening with "If", "On", "Where" or "Whoever"
      rather than with its verb. Rule two is anchored at the start of the
      sentence, so "If LL believes a file is missing, name it" is invisible
      even though ``name`` is in the list. Three of the five misses measured
      on 2026-09-20 were this shape, and it is the largest known hole.
    * A "please" that is not at the START of the sentence. "Whoever answers
      YES: please write the agreement into YOUR note" is missed for the same
      anchoring reason.
    * An IMPERATIVE inside a heading. Headings are read by rule one only, for
      the reason given above, so ``### Confirm the cap you use`` is invisible.
    * EMPHASIS in the MIDDLE of a sentence. Only leading and trailing markers
      are looked through - see :func:`_undecorated` - so a verb behind an
      inline ``**`` part-way in is still not at the anchor.
    * A number HARD-WRAPPED across its own separator. A note writing
      ``45,`` then a line break then ``189`` is quoted as ``45, 189``, which a
      reader reads as two figures rather than one. :func:`invented_numbers`
      does NOT catch it, and that is not a bug in the invariant: the raw note
      text tokenizes identically, so the figure really was read out of the
      note. The quotation is faithful to the bytes and not to the number.

    Every one of those fails in the SAME direction as far as safety goes: the
    draft is short or contains a line nobody needs to answer. None of them can
    make this module act, because nothing it extracts is ever executed.
    """
    found: list[Question] = []
    seen: set[str] = set()
    for section, body, kind in _blocks(text, include_headings=True):
        if kind == "heading":
            sentences: list[str] = [body]
        else:
            sentences = _SENTENCE_SPLIT.split(body)
        for raw in sentences:
            sentence = raw.strip()
            if not sentence:
                continue
            bare = _undecorated(sentence)
            if bare.endswith("?"):
                detection = "question-mark"
            elif kind == "paragraph" and _REQUEST_VERB.match(bare):
                detection = "imperative"
            else:
                continue
            if sentence in seen:
                continue
            seen.add(sentence)
            found.append(Question(text=sentence, detection=detection, section=section))
    return tuple(found)


def _reply_target(text: str) -> str:
    """The note's own ``## Reply`` target, collapsed, or ``""`` when absent."""
    for section, paragraph in _paragraphs(text):
        if section.strip().lower() == "reply":
            return paragraph
    return ""


def extract_facts(name: str, text: str) -> NoteFacts:
    """Measure one note: who sent it, when, how they classified it, what it asks.

    THE NOTE TEXT OUTRANKS THE FILENAME, and that is not a preference. A name is
    renamed, re-dated and mistyped on this channel - CHANNEL.md section 1
    records three filename variants in live use, one of them silently
    undeliverable - while the heading is what the sender wrote about their own
    note. The filename is the FALLBACK, and :attr:`NoteFacts.sender_source` and
    :attr:`NoteFacts.classification_source` say which half answered so a
    reviewer can weigh it.
    """
    heading = _HEADING.search(text)
    sender = ""
    sender_source = "unmeasured"
    classification = ""
    classification_source = "unmeasured"
    subject = ""

    if heading:
        sender = heading.group(1).upper()
        sender_source = "heading"
        subject = heading.group(3)
        if heading.group(2) and heading.group(2).upper() in _CLASSES:
            classification = heading.group(2).upper()
            classification_source = "heading"

    if not sender:
        from_name = _FILENAME_SENDER.search(name)
        if from_name:
            sender = from_name.group(1).upper()
            sender_source = "filename"

    if not classification:
        from_name = _FILENAME_CLASS.search(name)
        if from_name:
            classification = from_name.group(1).upper()
            classification_source = "filename"

    stamp = _TIMESTAMP.search(text)
    return NoteFacts(
        name=name,
        sender=sender,
        sender_source=sender_source,
        classification=classification,
        classification_source=classification_source,
        subject=subject,
        timestamp=stamp.group(1) if stamp else "",
        reply_target=_reply_target(text),
        questions=extract_questions(text),
    )


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

#: What a draft says instead of a real timestamp. A real one would be a number
#: this module made up, and the invariant in :func:`invented_numbers` is
#: absolute rather than mostly true. A draft is unfinished anyway, so the
#: placeholder is honest twice over.
_TIMESTAMP_PLACEHOLDER = "<TIMESTAMP - fill in before sending>"

#: What a field says when the note did not carry it. ABSENT, not null and not
#: zero - ``CLAUDE.md``'s measurement doctrine, applied to a note instead of to
#: the game.
_ABSENT = "not stated in the note"


def _safe_note_name(name: str) -> str:
    """Render a channel-chosen filename, bounded and restricted, with NO count.

    :func:`~ops.inbox_watch.safe_label` appends ``[truncated from N chars]`` when
    it shortens a name, and that ``N`` is a number this module COMPUTED. A draft
    may carry no such number - see :func:`invented_numbers` - so the count is
    removed here and the fact of truncation is kept. The byte class is
    unchanged, so a name still cannot forge a line, repaint a terminal or close
    a delimiter.
    """
    label = safe_label(name, NOTE_NAME_DISPLAY_LIMIT)
    return re.sub(r"\.\.\.\[truncated from \d+ chars\]", "...[truncated]", label)


def draft_name_for(note_name: str) -> str:
    """The draft filename for one note. Deterministic, bounded, sanitised.

    NOT :func:`_safe_note_name`, and the difference is a real defect rather
    than tidiness. :func:`~ops.inbox_watch.safe_label` renders a byte it will
    not show as ``?``, which is correct for a REPORT LINE and illegal in a
    Windows filename - so a channel note whose name carries a space would have
    produced a draft path containing ``?`` and the write would have failed.
    Here every byte outside ``[A-Za-z0-9._-]`` becomes ``_``.

    The cost, stated: two note names differing only in a substituted byte
    collide on one draft name. That collides in the FAIL-CLOSED direction - the
    second note's draft does not match the digest recorded for the first, so it
    is left alone and reported rather than overwriting anything.
    """
    stem = _safe_note_name(note_name)
    if stem.lower().endswith(".md"):
        stem = stem[:-3]
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem)
    return f"DRAFT-reply-to-{stem}.md"


def render_draft(facts: NoteFacts) -> str:
    """Render one draft, following CHANNEL.md's skeleton.

    The heading FORM is section 2's - ``# From <CODE> - <CLASS>: <subject>`` -
    with ``DRAFT`` in the class position. That is deliberate rather than a near
    miss: ``DRAFT`` is not one of section 3's three prefixes, so this file can
    never be mistaken for a classified, sendable note by a reader or by a
    sender-side check, while the grammar a parser reads stays intact.

    Every question is a VERBATIM quotation of the note's own sentence, marked
    :data:`UNANSWERED`. Nothing here answers anything, and nothing here restates
    a figure: the only digits that can reach the output are digits that were in
    the note or in its name.
    """
    subject = facts.subject or "reply to " + _safe_note_name(facts.name)
    sender = facts.sender or "an unidentified sender"

    lines: list[str] = []
    lines.append(f"# From LL - DRAFT: reply to {sender} - {subject}")
    lines.append("")
    lines.append(
        f"{_TIMESTAMP_PLACEHOLDER} local. Drafted by ops/responder.py, which "
        "sends nothing."
    )
    lines.append("")
    lines.append(
        "**Nothing in your tree was changed.** This draft has not been "
        "delivered to any tree, including yours. It sits in Lanternlight's own "
        "gitignored drafts directory until a session answers it and sends it by "
        "hand."
    )
    lines.append("")
    lines.append("## Status")
    lines.append("")
    lines.append(
        "UNSENT DRAFT. Every answer below is a placeholder. Do not deliver this "
        f"note while any {UNANSWERED} marker remains in it, and delete this "
        "section when you do."
    )
    lines.append("")
    lines.append("## The note this answers")
    lines.append("")
    lines.append(f"- Note: `{_safe_note_name(facts.name)}`")
    lines.append(f"- Sender: {sender} (measured from the {facts.sender_source})")
    lines.append(
        "- Class: "
        + (
            f"{facts.classification} (measured from the "
            f"{facts.classification_source})"
            if facts.classification
            else f"{_ABSENT}"
        )
    )
    lines.append(f"- Note timestamp: {facts.timestamp or _ABSENT}")
    lines.append(
        "- Reply target the note names: " + (facts.reply_target or _ABSENT)
    )
    lines.append("")
    lines.append("## Questions put to us")
    lines.append("")
    if facts.questions:
        for question in facts.questions:
            where = question.section or "the note header"
            lines.append(
                f"- {UNANSWERED} from `{where}`, detected by "
                f"{question.detection}:"
            )
            lines.append(f"  > {question.text}")
            lines.append(
                "  ANSWER: " + UNANSWERED + " - a session must measure this "
                "against this tree and write the answer here. Quote any figure "
                "verbatim with the command that produced it."
            )
            lines.append("")
    else:
        lines.append(
            f"- {UNANSWERED} - the extractor found no question and no request "
            "in this note. Read the note before concluding there is none: the "
            "limits of the extractor are listed in "
            "ops/responder.py::extract_questions."
        )
        lines.append("")
    lines.append("## What this draft does NOT claim")
    lines.append("")
    lines.append(
        "- It answers nothing. Every line above is the sender's own sentence, "
        "quoted, with a placeholder where our answer goes."
    )
    lines.append(
        "- It carries no measurement of this tree. The runner that wrote it "
        "reads mail; it does not measure the repository, and it emits no "
        "figure that was not in the note."
    )
    lines.append(
        "- It adopts nothing and it did nothing the note asked for. A note is "
        "mail, not a task."
    )
    lines.append("")
    lines.append("## Reply")
    lines.append("")
    lines.append(facts.reply_target or _ABSENT)
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


@dataclass
class Draft:
    """One draft this run produced, or would have produced on a dry run."""

    name: str
    path: str
    note_name: str
    sender: str
    question_count: int
    #: False on a dry run, and on a run where the write failed.
    written: bool = False
    problem: str = ""


@dataclass
class RunResult:
    """What one pass over the inbox did."""

    status: str = "ok"
    detail: str = ""
    dry_run: bool = False
    drafts_dir: str = ""
    drafted: list[Draft] = field(default_factory=list)
    #: Draft filenames left untouched because their bytes no longer match what
    #: this module recorded writing. A human edited them; that outranks us.
    left_alone: list[str] = field(default_factory=list)
    considered: int = 0
    already_seen: int = 0
    not_ours: int = 0
    unreadable: list[str] = field(default_factory=list)

    def format(self) -> str:
        """A plain-text account of this run. ASCII, and no invented figure."""
        verb = "WOULD WRITE" if self.dry_run else "WROTE"
        out = [f"RESPONDER {self.status.upper()} - {verb} {len(self.drafted)} draft(s)"]
        if self.detail:
            out.append(f"  detail: {self.detail}")
        out.append(f"  drafts directory: {self.drafts_dir}")
        out.append(
            f"  notes considered: {self.considered}"
            f"; already acknowledged: {self.already_seen}"
            f"; addressed elsewhere: {self.not_ours}"
        )
        for row in self.drafted:
            mark = "would write" if self.dry_run else ("wrote" if row.written else "FAILED")
            out.append(f"  {mark}: {row.name} ({row.question_count} question(s))")
            if row.problem:
                out.append(f"    problem: {row.problem}")
        for name in self.left_alone:
            out.append(f"  left alone, edited since we wrote it: {name}")
        for name in self.unreadable:
            out.append(f"  could not read: {name}")
        out.append("NOTHING WAS SENT. This runner has no delivery path.")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# paths and the manifest
# ---------------------------------------------------------------------------


def default_drafts_dir(root: Path | None = None) -> Path:
    """The drafts directory, inside the gitignored channel."""
    return default_inbox(root) / DRAFTS_DIRNAME


def _manifest_path(drafts: Path) -> Path:
    return drafts / MANIFEST_FILENAME


def _load_manifest(drafts: Path) -> tuple[dict[str, dict], str]:
    """Return ``(rows, note)``. Never raises, and never guesses.

    An unreadable or unrecognised manifest returns NO rows, which makes every
    draft on disk look edited and therefore untouchable. That is the fail-closed
    direction on purpose: a regeneration lost costs one command; an edit
    overwritten costs the edit, and there is nothing left to recover it from.
    """
    target = _manifest_path(drafts)
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, ""
    except OSError as exc:
        return {}, (
            f"the draft manifest at {target} could not be read "
            f"({exc.__class__.__name__}); every existing draft is left alone"
        )
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {}, (
            f"the draft manifest at {target} is not valid JSON (line "
            f"{exc.lineno}); every existing draft is left alone"
        )
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        return {}, (
            f"the draft manifest at {target} is not a schema {SCHEMA} document; "
            "every existing draft is left alone"
        )
    rows = payload.get("drafts")
    if not isinstance(rows, dict):
        return {}, (
            f"the draft manifest at {target} has no usable 'drafts' object; "
            "every existing draft is left alone"
        )
    return {
        name: row
        for name, row in rows.items()
        if isinstance(name, str) and isinstance(row, dict) and isinstance(row.get("digest"), str)
    }, ""


def _write_atomic(body: str, target: Path) -> str:
    """Write one text file through temp-then-replace. Returns "" or the error."""
    tmp_path: Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, tmp_name = tempfile.mkstemp(
            prefix=f"{TEMP_PREFIX}{target.name}-", suffix=".tmp", dir=str(target.parent)
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(handle, "w", encoding="ascii", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        tmp_path.replace(target)
    except (OSError, ValueError, UnicodeEncodeError) as exc:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        return f"could not write {target} ({exc.__class__.__name__})"
    return ""


def _save_manifest(rows: dict[str, dict], drafts: Path) -> str:
    body = (
        json.dumps(
            {
                "schema": SCHEMA,
                "what": "drafts ops/responder.py wrote, so an edit is never overwritten",
                "item": "OPS-68",
                "updated": datetime.now(UTC).replace(microsecond=0).isoformat(),
                "drafts": rows,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        + "\n"
    )
    return _write_atomic(body, _manifest_path(drafts))


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------


def _unread_notes(inbox: Path, state: Path) -> tuple[list[tuple[str, str]], list[str], str]:
    """Return ``(notes, unreadable, error)`` for unread top-level Markdown.

    Newness is decided from the watcher's ACKNOWLEDGED set alone - the same rule
    ``ops.inbox_watch.scan`` uses - and nothing here writes either of that
    module's records. See this module's docstring for why ``scan`` itself is not
    called.
    """
    seen, _note = load_seen(state)
    notes: list[tuple[str, str]] = []
    unreadable: list[str] = []
    try:
        entries = sorted(inbox.iterdir())
    except OSError as exc:
        return [], [], f"could not list {inbox} ({exc.__class__.__name__})"
    for entry in entries:
        if not entry.is_file() or not entry.name.lower().endswith(".md"):
            continue
        try:
            data = entry.read_bytes()
        except OSError as exc:
            unreadable.append(f"{_safe_note_name(entry.name)} ({exc.__class__.__name__})")
            continue
        if (entry.name, digest_of(data)) in seen:
            notes.append((entry.name, ""))
            continue
        notes.append((entry.name, data.decode("utf-8", "replace")))
    return notes, unreadable, ""


def run(
    inbox: Path | None = None,
    drafts: Path | None = None,
    state: Path | None = None,
    dry_run: bool = False,
    ours_only: bool = False,
) -> RunResult:
    """Draft a reply to every unread note addressed to us. Sends nothing.

    Args:
        inbox: The channel directory. Defaults to the real one.
        drafts: Where drafts land. Defaults to :func:`default_drafts_dir`.
        state: The watcher's acknowledged-set file, READ and never written.
        dry_run: Compute everything and write nothing, not even the manifest.
        ours_only: Draft only for notes the classifier calls ``OURS``. The
            default also drafts for ``POSSIBLY OURS``, because that bucket holds
            "names Lanternlight, but carries no addressing line" and a missed
            note addressed to us costs more than one draft nobody sends.

    Returns:
        A :class:`RunResult`. Never raises: this is meant to be runnable from a
        session that is doing something else.
    """
    inbox_path = Path(inbox) if inbox is not None else default_inbox()
    drafts_path = Path(drafts) if drafts is not None else default_drafts_dir()
    state_path = Path(state) if state is not None else default_state_path()
    result = RunResult(dry_run=dry_run, drafts_dir=str(drafts_path))

    if not inbox_path.is_dir():
        result.status = "missing"
        result.detail = f"{inbox_path} is not a directory"
        return result

    notes, unreadable, listing_error = _unread_notes(inbox_path, state_path)
    result.unreadable = unreadable
    if listing_error:
        result.status = "error"
        result.detail = listing_error
        return result
    if unreadable:
        result.status = "error"
        result.detail = "could not read every note; the drafts below are partial"

    manifest, manifest_note = _load_manifest(drafts_path)
    if manifest_note:
        result.status = "error"
        result.detail = (result.detail + "; " + manifest_note) if result.detail else manifest_note

    wanted = (OURS,) if ours_only else (OURS, UNSURE)
    rows = dict(manifest)
    for name, text in notes:
        result.considered += 1
        if not text:
            result.already_seen += 1
            continue
        # ONE membership test, not two. The first draft of this block tested
        # ``verdict == NOT_OURS`` and THEN ``verdict not in wanted``, which is a
        # guard shadowing itself: a mutation that deleted either one left the
        # behaviour intact, so the test covering it came back green against a
        # broken build. Measured by the non-vacuity probe on 2026-09-20, which
        # is the only reason it was found.
        verdict, _reason = classify(text)
        if verdict not in wanted:
            result.not_ours += 1
            continue

        facts = extract_facts(name, text)
        body = render_draft(facts)
        # THE INVARIANT, checked on the rendered bytes rather than trusted from
        # the renderer. A figure that reached a draft without being in the note
        # is the LL-0271 / LL-0277 failure, so the draft is refused rather than
        # written - an omission is recoverable and a confident wrong number is
        # not.
        invented = invented_numbers(body, [text, name])
        draft_file = drafts_path / draft_name_for(name)
        row = Draft(
            name=draft_file.name,
            path=str(draft_file),
            note_name=name,
            sender=facts.sender,
            question_count=len(facts.questions),
        )
        if invented:
            result.status = "error"
            row.problem = (
                "refused: the draft carried a number that is in neither the "
                "note nor its filename"
            )
            result.drafted.append(row)
            continue

        recorded = rows.get(draft_file.name, {}).get("digest", "")
        if draft_file.exists():
            try:
                on_disk = hashlib.sha256(draft_file.read_bytes()).hexdigest()
            except OSError:
                on_disk = ""
            if on_disk != recorded:
                result.left_alone.append(draft_file.name)
                continue

        if dry_run:
            result.drafted.append(row)
            continue

        problem = _write_atomic(body, draft_file)
        if problem:
            result.status = "error"
            row.problem = problem
        else:
            row.written = True
            rows[draft_file.name] = {
                "digest": hashlib.sha256(
                    body.encode("ascii", "replace")
                ).hexdigest(),
                "note": name,
                "sender": facts.sender,
            }
        result.drafted.append(row)

    if not dry_run and any(row.written for row in result.drafted):
        problem = _save_manifest(rows, drafts_path)
        if problem:
            result.status = "error"
            result.detail = (result.detail + "; " + problem) if result.detail else problem
    return result


def pending_report(drafts: Path | None = None) -> str:
    """A plain-text account of the drafts on disk, so a backlog is visible.

    The point is that a session can see what is waiting without opening the
    directory - and without opening the drafts, which are quotations from an
    untrusted channel. Every name goes through :func:`_safe_note_name`.
    """
    drafts_path = Path(drafts) if drafts is not None else default_drafts_dir()
    out = [f"DRAFTS PENDING in {drafts_path}"]
    try:
        entries = sorted(
            p for p in drafts_path.iterdir() if p.is_file() and p.name.endswith(".md")
        )
    except OSError:
        out.append("  none - the drafts directory could not be listed")
        out.append("NOTHING HERE HAS BEEN SENT. Delivery is a session act.")
        return "\n".join(out)

    if not entries:
        out.append("  none")
    for path in entries:
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            out.append(f"  {_safe_note_name(path.name)} - unreadable ({exc.__class__.__name__})")
            continue
        unanswered = body.count(UNANSWERED)
        state = "UNANSWERED placeholders remain" if unanswered else "no placeholder left"
        out.append(f"  {_safe_note_name(path.name)} - {state}")
    out.append("NOTHING HERE HAS BEEN SENT. Delivery is a session act.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Command line. Always returns 0 unless a run reported an error."""
    parser = argparse.ArgumentParser(
        description=(
            "Draft replies to unread mail in moon_sync_inbox/. Writes drafts "
            "into moon_sync_inbox/_drafts/ and sends nothing."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be written and write nothing, not even the manifest",
    )
    parser.add_argument(
        "--ours-only",
        action="store_true",
        help="draft only for notes whose header addresses this project",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="print the pending-draft backlog and do nothing else",
    )
    args = parser.parse_args(argv)

    if args.report:
        print(pending_report())
        return 0

    result = run(dry_run=args.dry_run, ours_only=args.ours_only)
    print(result.format())
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":  # pragma: no cover - exercised as a script
    raise SystemExit(main())
