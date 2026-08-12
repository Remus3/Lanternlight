"""The repository ledger writer - `OPS-1`, which was a real gap.

`ops/loop/ledger.py` is the only sanctioned writer of `docs/LEDGER.md`, the
file this project's whole continuity design rests on: a cleared session reads
the top few entries and knows where it is. It had **no test module of its own**.
It was exercised incidentally - `tests/test_lane_state.py` calls it to build
fragments, `tests/test_loop_state.py` and `tests/test_loop_guard.py` import it -
but incidental exercise tests the caller's path, not the module's promises.

Two of those promises are load-bearing and neither was pinned anywhere:

**Newest on top, and nothing below the marker is disturbed.** The module
self-checks this and raises rather than writing. That check had no test, so it
could have been deleted silently - which is exactly how `integrate()`'s
`reversed()` was found to be decoration in an earlier session.

**The write is atomic.** A reader polling this file must never see half an
entry, and `CLAUDE.md` mandates tmp-then-replace for anything pollable.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops.loop import ledger  # noqa: E402

PREAMBLE = "# Ledger\n\nSome preamble.\n\n" + ledger.ENTRIES_MARKER + "\n"


def _book(tmp_path, body=""):
    target = tmp_path / "LEDGER.md"
    target.write_text(PREAMBLE + body, encoding="utf-8")
    return target


def _entry(item_id="LL-0001", summary="did a thing", **over):
    fields = {
        "item_id": item_id,
        "summary": summary,
        "evidence": ["pytest -> 1 passed"],
        "date": "2026-08-12",
    }
    fields.update(over)
    return ledger.LedgerEntry(**fields)


class TestAnEntryMustBeFitToRecord:
    """"Done" with nothing to check is a claim, not a record."""

    def test_an_entry_with_no_evidence_is_refused(self):
        with pytest.raises(ValueError, match="evidence"):
            _entry(evidence=[]).validate()

    def test_an_entry_with_no_id_is_refused(self):
        with pytest.raises(ValueError):
            _entry(item_id="   ").validate()

    def test_an_entry_with_no_summary_is_refused(self):
        with pytest.raises(ValueError):
            _entry(summary="  ").validate()

    def test_a_multi_line_summary_is_refused(self):
        # A summary needing two lines was two items.
        with pytest.raises(ValueError, match="single line"):
            _entry(summary="first\nsecond").validate()

    def test_a_good_entry_validates(self):
        _entry().validate()


class TestAsciiIsEnforcedAtTheWrite:
    """Caught here it names the FIELD; caught by the hygiene test, only the file.

    Every character below is built with an escape rather than typed, because
    this repository is 7-bit ASCII in every authored file and writing one here
    would fail `tests/test_ascii_hygiene.py` - which it did, in this same
    session, in a different test.
    """

    EM_DASH = chr(0x2014)
    SMART_QUOTE = chr(0x201C)

    def test_a_non_ascii_summary_is_refused(self):
        with pytest.raises(ValueError, match="non-ASCII"):
            _entry(summary=f"a{self.EM_DASH}b").validate()

    def test_a_non_ascii_evidence_line_is_refused(self):
        with pytest.raises(ValueError, match="non-ASCII"):
            _entry(evidence=[f"said {self.SMART_QUOTE}hello"]).validate()

    def test_a_non_ascii_note_is_refused(self):
        with pytest.raises(ValueError, match="non-ASCII"):
            _entry(notes=[f"a{self.EM_DASH}b"]).validate()

    def test_the_error_names_the_codepoint(self):
        with pytest.raises(ValueError) as caught:
            _entry(summary=f"a{self.EM_DASH}b").validate()
        assert "U+2014" in str(caught.value)

    def test_ch_repr_renders_the_codepoint(self):
        assert "U+2014" in ledger.ch_repr(self.EM_DASH)


class TestRendering:
    def test_the_heading_carries_id_date_and_summary(self):
        text = ledger.render_entry(_entry())
        assert text.splitlines()[0] == "### LL-0001 - 2026-08-12 - did a thing"

    def test_every_evidence_line_becomes_a_bullet(self):
        text = ledger.render_entry(_entry(evidence=["one", "two"]))
        assert "- one" in text and "- two" in text

    def test_notes_are_rendered_after_the_evidence(self):
        text = ledger.render_entry(_entry(notes=["a caveat"]))
        assert text.index("**Evidence:**") < text.index("a caveat")

    def test_rendering_validates_first(self):
        with pytest.raises(ValueError):
            ledger.render_entry(_entry(evidence=[]))

    def test_rendering_is_deterministic(self):
        assert ledger.render_entry(_entry()) == ledger.render_entry(_entry())


class TestAppendingPreservesWhatIsAlreadyThere:
    """The one promise the module makes, and it had no test."""

    def test_the_entry_lands_below_the_marker(self, tmp_path):
        book = _book(tmp_path)
        ledger.append_entry(_entry(), book)
        text = book.read_text(encoding="utf-8")
        assert text.index(ledger.ENTRIES_MARKER) < text.index("### LL-0001")

    def test_the_newest_entry_is_on_top(self, tmp_path):
        book = _book(tmp_path)
        ledger.append_entry(_entry("LL-0001"), book)
        ledger.append_entry(_entry("LL-0002"), book)
        text = book.read_text(encoding="utf-8")
        assert text.index("### LL-0002") < text.index("### LL-0001")

    def test_existing_entries_survive_byte_for_byte(self, tmp_path):
        book = _book(tmp_path)
        ledger.append_entry(_entry("LL-0001"), book)
        before = book.read_text(encoding="utf-8")
        existing = before[before.index("### LL-0001") :]
        ledger.append_entry(_entry("LL-0002"), book)
        assert book.read_text(encoding="utf-8").endswith(existing)

    def test_the_preamble_survives(self, tmp_path):
        book = _book(tmp_path)
        ledger.append_entry(_entry(), book)
        assert book.read_text(encoding="utf-8").startswith("# Ledger\n\nSome preamble.")

    def test_a_ledger_with_no_marker_is_refused(self, tmp_path):
        book = tmp_path / "LEDGER.md"
        book.write_text("# Ledger\n\nno marker here\n", encoding="utf-8")
        with pytest.raises(ledger.MarkerMissingError):
            ledger.append_entry(_entry(), book)

    def test_a_refused_write_changes_nothing(self, tmp_path):
        book = tmp_path / "LEDGER.md"
        book.write_text("# Ledger\n\nno marker here\n", encoding="utf-8")
        before = book.read_text(encoding="utf-8")
        with pytest.raises(ledger.MarkerMissingError):
            ledger.append_entry(_entry(), book)
        assert book.read_text(encoding="utf-8") == before

    def test_an_invalid_entry_never_touches_the_file(self, tmp_path):
        book = _book(tmp_path)
        before = book.read_text(encoding="utf-8")
        with pytest.raises(ValueError):
            ledger.append_entry(_entry(evidence=[]), book)
        assert book.read_text(encoding="utf-8") == before


class TestTheWriteIsAtomicAndClean:
    def test_no_temporary_file_is_left_behind(self, tmp_path):
        book = _book(tmp_path)
        ledger.append_entry(_entry(), book)
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != book.name]
        assert not leftovers, leftovers

    def test_the_file_is_written_with_lf_endings(self, tmp_path):
        # Windows write_text turns LF into CRLF and read_text hides it, so this
        # is asserted on the BYTES. A CR in this file breaks nothing loudly and
        # everything quietly.
        book = _book(tmp_path)
        ledger.append_entry(_entry(), book)
        assert b"\r\n" not in book.read_bytes()

    def test_appending_returns_the_path_written(self, tmp_path):
        book = _book(tmp_path)
        assert ledger.append_entry(_entry(), book) == book

    def test_the_commit_step_really_is_a_replace(self, monkeypatch, tmp_path):
        """Atomicity itself, not just its side effects.

        Added because a mutation survived: deleting `tmp_path.replace(target)`
        from the only sanctioned writer of `docs/LEDGER.md` left the whole
        suite green. The debris and LF tests happen to pass either way, so
        nothing pinned the one property that makes a polled file safe to read.

        Breaking the replace must leave the ledger UNTOUCHED. A writer that
        wrote in place would have already modified it by this point.
        """
        book = _book(tmp_path)
        ledger.append_entry(_entry("LL-0001"), book)
        before = book.read_bytes()

        real_replace = Path.replace

        def refuse(self, target):
            raise OSError("replace refused")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(OSError):
            ledger.append_entry(_entry("LL-0002"), book)
        monkeypatch.setattr(Path, "replace", real_replace)

        assert book.read_bytes() == before, (
            "the ledger changed even though the commit step failed, so the "
            "write is not atomic - a reader could see a half-written entry"
        )
        assert "LL-0002" not in book.read_text(encoding="utf-8")

    def test_a_failed_commit_leaves_no_debris(self, monkeypatch, tmp_path):
        book = _book(tmp_path)

        def refuse(self, target):
            raise OSError("replace refused")

        monkeypatch.setattr(Path, "replace", refuse)
        with pytest.raises(OSError):
            ledger.append_entry(_entry(), book)
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != book.name]
        assert not leftovers, leftovers


class TestTheDefaultTargetIsTheRealLedger:
    def test_it_points_at_docs_ledger_md(self):
        assert ledger.default_ledger_path() == REPO_ROOT / "docs" / "LEDGER.md"

    def test_the_real_ledger_exists_and_carries_the_marker(self):
        # If this ever fails, every append in the project is about to raise.
        book = ledger.default_ledger_path()
        assert book.is_file()
        assert ledger.ENTRIES_MARKER in book.read_text(encoding="utf-8")
