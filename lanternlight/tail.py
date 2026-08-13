"""Follow the live MistfallHunter.log and emit redacted, parsed events.

ROADMAP item 3. The game appends to this file while it runs - 567 KB in the
first ten minutes - and a tail that follows it is the spine of every live
feature this project could ever have.

**This is a library. It binds nothing.** Port 8811 is reserved for a log-tail
service, and no socket is opened here, at import time or at any other time.
The acceptance for item 3 asks for a tailer, not a server.

The API deliberately separates one deterministic pass (:meth:`LogTailer.
poll_once`, which a test calls directly) from the looping wrapper
(:meth:`LogTailer.run`, which takes an injectable sleep function so no caller -
including a test - ever blocks on a real poll interval). That is the shape
``lanternlight.savewatch`` already uses; the idiom is copied, the code is not.

Four hazards, all of them measured rather than imagined
-------------------------------------------------------

**1. The partial trailing line.** A live-appended UE log routinely ends
mid-line, and a fragment is not merely useless - it is dangerous. Cut
``setClassGender inclassid  ==12, inGender ==10`` one byte early and it parses
into a complete, well-formed ``ClassSelectionEvent`` reporting gender 1. So
this module holds back every byte not yet terminated by a newline and emits a
line only once its newline has arrived. The held bytes are counted in
:attr:`LogTailer.offset` - they have been read - but they have not been seen.

The buffer holds BYTES rather than text, which is the second half of the same
hazard. Decoding each read in isolation would split a multi-byte UTF-8
sequence across two polls and drop a replacement character into the middle of
a line. The game's log carries CJK player names, so that is a real shape.

**Do not decode first and reach for ``str.splitlines()``.** Splitting is done
on ``b"\\n"`` at byte level, and that is load-bearing rather than incidental.
``str.splitlines`` treats a dozen further code points as line breaks -
vertical tab, form feed, the file/group/record separators, NEL - and the real
log is measured to carry more than 594 of them embedded INSIDE lines (98 VT,
106 FF, 113 FS, 85 GS, 97 RS, 95 NEL). The file considers none of them a line
break, so decoding and then calling it would shatter real lines and hand the
parser records the game never wrote.

The precise spelling matters, and was measured rather than assumed:
``bytes.splitlines()`` does NOT split on any of those - only on CR, LF and
CRLF - so it is the DECODE-then-split order that is dangerous, not the name.
``tests/test_tail.py`` pins this with a line carrying an embedded record
separator and vertical tab; note there that the event COUNT does not catch the
mutation, because the first shard still carries a complete header and still
parses. Only the exact text does.

**2. Truncation and rotation.** The game restarts and the file is emptied, or
replaced under the same name. These are two different events and only one of
them is visible in the size:

- **Truncated in place.** ``st_size`` drops below the offset already held.
  MEASURED on this machine: an in-place truncation KEEPS the file's identity,
  so identity cannot see this and the size comparison is what catches it.
- **Replaced.** A new file takes the name. MEASURED on this machine
  (Windows 10, NTFS): ``os.stat`` populates a non-zero ``st_ino`` - the NTFS
  file index - it is stable across repeated stats and across an in-place
  truncation, it CHANGES when the file is deleted and recreated, and a renamed
  file carries its own index into the new name. 200 delete-and-recreate cycles
  produced 200 distinct values with none recycled.

  That last measurement is why identity is a SECONDARY check and not the only
  one. A file index is reused eventually - NTFS is free to recycle it - so a
  design resting on identity alone would be resting on an observation of a
  short run. Both checks are kept, and either one triggers the same reset.

``st_ino`` is documented as zero on platforms that cannot supply it, so
:func:`file_identity` returns ``None`` there and the module falls back to the
size comparison alone. That fallback is stated rather than hidden: a
replacement by a LARGER file is invisible to size, and on such a platform this
module would seek into the middle of the new file. It is not a hypothetical
this machine can reproduce, and it is not papered over either.

A reset discards the pending fragment as well as the offset. Keeping it would
weld the tail of the old file onto the head of the new one and emit a line
that was never written.

**3. It must never hold a lock the game could feel.** Mistfall Hunter ships
kernel-level anti-cheat and the hard boundary in ``CLAUDE.md`` governs
everything here. This module opens read-only, reads, and closes, every pass -
it holds no handle between polls at all. ``tests/test_tail.py`` exercises both
halves rather than asserting the intent: a separate writer appends while
:func:`open_for_read` has the file open, and the file is deleted immediately
after a poll, which on Windows a retained handle would refuse.

**4. Redaction is SCOPE-DEPENDENT, and this is the sharpest trap here.**
ROADMAP item 0 records it: persona discovery learns a display name from a
KEYED occurrence, and returns empty on an isolated excerpt that has none. One
log line is the smallest possible excerpt.

So a tailer that calls ``redact(line)`` per line runs discovery on the worst
possible scope, and it does not fail loudly. Measured with authored fixtures::

    line = "...server_refreshKnightFeature <first> <second> class-12 holding-30402"
    redact(line)            -> unchanged, the name still in it
    assert_clean(that)      -> reports CLEAN

The name sits in no key and in no slot :data:`lanternlight.redact.RULES`
enumerates, so nothing detects it and nothing objects. It would ship.

**Stated plainly: this is a guard against a shape that exists, not a fix for a
leak happening today.** Re-measured against the real log by an independent
pass: of the lines that both carry a persona and yield a recognised event,
there are 4, and naive per-line redaction masks all 4 - the KEYED rules do the
whole job on them, and this module learns no persona in the process. The one
line genuinely leaking a bare name is not a shape ``logparse`` recognises, so
it cannot reach a sink today at all. The accumulation below therefore buys
nothing measurable on the current log. It is kept because the leaking shape is
real and already in the file, and the day a new recogniser covers it the leak
becomes reachable with no other code changing - which is precisely the sort of
change nobody would think to re-audit redaction for.

The remedy here is ACCUMULATION. Every raw line is passed through
:func:`lanternlight.redact.discover_personas` before it is redacted, and every
candidate found is added to a set that only grows. Every line is then redacted
against the whole accumulated set, so one keyed login line near the top of the
file cleans every bare occurrence for the rest of the session - including
after a rotation, because the offset resets and the learned names do not.
:meth:`LogTailer.__init__` also takes ``personas`` for a tail attached
mid-session, which has missed the login line and can never discover the name.

Certification is deliberately doubled, and the reason is a real hole rather
than belt and braces. :func:`lanternlight.redact.assert_clean` has a third
outcome - CANNOT CERTIFY - for text sitting in a slot the log fills with a
bare display name from which nothing could be determined. **Supplying
``personas`` switches that outcome off**, because a caller that names the
personas is asserting it has a basis. So a tailer that only ever supplied its
accumulated set would silently stop refusing anything the moment it learned
its first name. Every line is therefore certified twice: once against the
accumulated personas, and once with ``personas=None`` so the cannot-certify
state stays armed for the whole session. Either refusal withholds the event
and increments :attr:`LogTailer.withheld`.

The cost is stated rather than hidden: a line carrying a risky anchor with an
empty or unrecognised name slot is withheld even though it may be harmless.
Withheld events are counted so the cost is visible rather than silent, and
there is no flag to turn the refusal off - a guard with an off switch is a
guard that gets switched off.

**Redaction runs BEFORE parsing, not after.** The parser is only ever handed
text the redactor produced, so there is no code path by which unredacted text
becomes an event. Redacting an event's fields afterwards would leave the
choice of which fields to clean to whoever added the next event type.

What this module does not do
----------------------------

It emits an event only for the line shapes :mod:`lanternlight.logparse`
already recognises. A line that parses but matches no event shape is counted
in :attr:`LogTailer.lines_seen` and emitted to nobody; a line that does not
parse at all is counted and dropped. This is a recogniser, not a validator,
for the same reason ``logparse.iter_events`` is.

It persists nothing. There is no offset file, no journal and no sink - a
caller decides where events go. Nothing here needs an atomic write because
nothing here is written for a reader to poll.
"""

import stat as stat_module
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from lanternlight import logparse, redact as redact_module

__all__ = [
    "DEFAULT_POLL_SECONDS",
    "LogTailer",
    "TailEvent",
    "file_identity",
    "open_for_read",
]

#: Default gap between passes. The game writes far faster than this; the
#: number is chosen so an idle tail is cheap rather than so a busy one is
#: prompt, and every caller can override it.
DEFAULT_POLL_SECONDS = 0.5

#: How the file is opened, in one place. ``tests/test_tail.py`` calls this
#: function rather than writing its own ``open`` call, so the no-lock test
#: exercises the real open mode instead of a copy of it that could drift.
#:
#: Binary, read-only, no sharing flags of any kind. Python's default on
#: Windows leaves the file open for other writers, which is exactly what is
#: needed: the process appending to this file is the game.
_READ_MODE = "rb"


def open_for_read(path: Path | str):
    """Open ``path`` the way this module reads it - read-only, no locking.

    ``Path.open`` is ``io.open`` underneath, so this carries exactly the
    sharing semantics the builtin does - nothing here is asking for exclusive
    access, and nothing must ever start to.
    """
    return Path(path).open(_READ_MODE)


def file_identity(st) -> tuple[int, int] | None:
    """Return a stable identity for a stat result, or ``None`` if unavailable.

    ``(st_dev, st_ino)`` is the portable spelling of "the same file". On
    Windows ``st_ino`` is the NTFS file index and IS populated - measured on
    this machine, see the module docstring - but the standard library
    documents it as zero where the platform cannot supply one. A zero index is
    not an identity, and treating it as one would make every file on such a
    platform look like every other file, so this returns ``None`` and the
    caller falls back to the size comparison.
    """
    if not st.st_ino:
        return None
    return (st.st_dev, st.st_ino)


@dataclass(frozen=True)
class TailEvent:
    """One recognised event, together with the redacted line it came from.

    ``text`` is what the redactor produced. ``event`` was parsed OUT of that
    text, so ``event.line.raw`` and ``text`` are the same string by
    construction rather than by convention.
    """

    text: str
    event: logparse.Event


def _order_personas(names: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate and order candidates longest first.

    Ordering is for the reader and for a stable :attr:`LogTailer.personas`;
    :func:`lanternlight.redact.redact` re-normalises whatever it is given, so
    nothing here depends on this being right. Longest first matches what that
    module does, so the two do not read as disagreeing.
    """
    return tuple(sorted({name for name in names if name}, key=lambda n: (-len(n), n)))


class LogTailer:
    """Follows one appending log file, emitting redacted events.

    ``path`` is never validated at construction time: the game may not be
    running, and surviving an absent file is about :meth:`poll_once`
    tolerating it at call time rather than about refusing to build a tailer
    for a file that does not exist yet.

    ``personas`` seeds the display names to mask. Leave it empty for a tail
    started before the game logs in, which will discover the name itself; pass
    it for a tail attached to an already-running session, which has missed the
    only line the name could have been learned from.
    """

    def __init__(self, path: Path | str, *, personas: Iterable[str] = ()) -> None:
        self.path = Path(path)
        self._offset = 0
        self._pending = b""
        self._identity: tuple[int, int] | None = None
        self._personas = _order_personas(personas)
        self._lines_seen = 0
        self._withheld = 0

    # -- observable state ---------------------------------------------------

    @property
    def offset(self) -> int:
        """Bytes read from the file so far, including any held fragment."""
        return self._offset

    @property
    def pending_bytes(self) -> int:
        """Bytes read but held back because no newline has arrived for them."""
        return len(self._pending)

    @property
    def personas(self) -> tuple[str, ...]:
        """Every display name seeded or discovered so far, longest first."""
        return self._personas

    @property
    def lines_seen(self) -> int:
        """Complete, non-blank lines consumed - recognised or not."""
        return self._lines_seen

    @property
    def withheld(self) -> int:
        """Lines the redactor refused to certify, and which were not emitted.

        A non-zero count is not an error. It is the visible price of the
        cannot-certify state described in the module docstring, and it is
        exposed rather than swallowed so that price is never silent.
        """
        return self._withheld

    # -- one pass -----------------------------------------------------------

    def poll_once(self) -> list[TailEvent]:
        """Do exactly one read-and-emit pass. Never raises on a missing file.

        Returns the events emitted during THIS pass only, not a running total.
        An absent file, a path that is not a regular file, and an unreadable
        one all return an empty list - the game may simply not be running,
        which is the normal case rather than an exceptional one.
        """
        st = self._stat()
        if st is None:
            return []

        self._reset_if_replaced_or_truncated(st)

        chunk = self._read_new_bytes()
        if chunk is None:
            return []
        self._offset += len(chunk)

        lines = self._take_complete_lines(chunk)
        return [
            event
            for line in lines
            for event in self._emit(line)
        ]

    def run(
        self,
        *,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        max_passes: int | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> int:
        """Call :meth:`poll_once` repeatedly, sleeping between passes.

        ``max_passes=None`` loops until interrupted, which is the production
        shape. A finite ``max_passes`` bounds the loop deterministically, and
        ``sleep_fn`` is the injection point that lets a test run it without
        blocking on a real interval.

        Sleeps happen BETWEEN passes only, never after the last one - so N
        passes sleep N-1 times, including over an absent or empty file. That
        is the anti-spin property: the loop's cost when there is nothing to
        read is one stat plus one sleep, not a busy wait.

        Returns the total number of events emitted across every pass.
        """
        total = 0
        passes = 0
        while max_passes is None or passes < max_passes:
            total += len(self.poll_once())
            passes += 1
            if max_passes is not None and passes >= max_passes:
                break
            sleep_fn(poll_seconds)
        return total

    # -- reading ------------------------------------------------------------

    def _stat(self):
        """Stat the path, or return ``None`` for anything not worth reading.

        ``None`` covers an absent file, a permission failure, and a path that
        is not a regular file - ``lanternlight.paths`` can hand back a
        directory, and opening one raises a different error on every platform.
        Deciding it here means the read path has one shape.
        """
        try:
            st = self.path.stat()
        except OSError:
            return None
        if not stat_module.S_ISREG(st.st_mode):
            return None
        return st

    def _reset_if_replaced_or_truncated(self, st) -> None:
        """Restart from byte zero when the file underneath us changed.

        Two independent triggers, because neither one sees both events. See
        the module docstring for the measurements behind each.
        """
        identity = file_identity(st)
        replaced = (
            self._identity is not None
            and identity is not None
            and identity != self._identity
        )
        truncated = st.st_size < self._offset
        if replaced or truncated:
            self._offset = 0
            self._pending = b""
        self._identity = identity

    def _read_new_bytes(self) -> bytes | None:
        """Read from the held offset to the end, then close. ``None`` on error.

        The handle is opened and closed inside this call and is never stored,
        so nothing this module holds can affect the process writing the file.
        A seek past the end - the file shrank between the stat above and this
        read - yields no bytes rather than an error.
        """
        try:
            with open_for_read(self.path) as handle:
                handle.seek(self._offset)
                return handle.read()
        except OSError:
            return None

    def _take_complete_lines(self, chunk: bytes) -> list[str]:
        """Return the newline-terminated lines in ``chunk``, holding the rest.

        Everything after the last newline goes back into the pending buffer
        and is emitted only when its newline arrives. Blank lines carry
        nothing and are dropped without being counted.
        """
        buffer = self._pending + chunk
        head, separator, remainder = buffer.rpartition(b"\n")
        if not separator:
            self._pending = buffer
            return []
        self._pending = remainder

        lines: list[str] = []
        for raw in head.split(b"\n"):
            text = raw.decode("utf-8", errors="replace").rstrip("\r")
            if not text:
                continue
            self._lines_seen += 1
            lines.append(text)
        return lines

    # -- redaction and emission --------------------------------------------

    def _emit(self, raw_line: str) -> Iterator[TailEvent]:
        """Redact one raw line, certify it, and yield any event in it.

        Order is load-bearing and is the whole answer to hazard 4:

        1. Harvest personas from the RAW line, because redaction destroys the
           keys discovery learns from.
        2. Redact against the ACCUMULATED set, not against this line alone.
        3. Certify twice - see :meth:`_certifies`.
        4. Parse the REDACTED text. The parser never sees the raw line.
        """
        self._learn_personas(raw_line)
        clean = redact_module.redact(raw_line, personas=self._personas)
        if not self._certifies(clean):
            self._withheld += 1
            return
        yield from (
            TailEvent(text=clean, event=event)
            for event in logparse.iter_events([clean])
        )

    def _learn_personas(self, raw_line: str) -> None:
        """Fold any display names in ``raw_line`` into the accumulated set.

        Harvesting happens on every line, not only on lines that become
        events. The one line the operator's name can be learned from - the
        login line - is not a recognised event shape at all, so harvesting
        from events would throw away the only source there is.
        """
        found = redact_module.discover_personas(raw_line)
        if found:
            self._personas = _order_personas(self._personas + found)

    def _certifies(self, text: str) -> bool:
        """Whether the redactor will vouch for ``text``, under both readings.

        The second call is not redundant. Passing ``personas`` tells
        :func:`lanternlight.redact.assert_clean` that the caller has a basis
        for the names in this text, which switches its cannot-certify state
        off; passing ``None`` leaves that state armed. A tailer needs both -
        the first proves the names it knows are gone, the second proves it is
        not standing in a name slot it cannot read.

        Only :class:`lanternlight.redact.RedactionError` is caught. A bare
        ``except Exception`` here would swallow programming errors and, worse,
        would swallow an ``AssertionError`` from any test spying on this path.
        """
        try:
            if self._personas:
                redact_module.assert_clean(text, personas=self._personas)
            redact_module.assert_clean(text, personas=None)
        except redact_module.RedactionError:
            return False
        return True
