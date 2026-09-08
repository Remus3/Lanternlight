"""An outgoing note must leave a trace in THIS tree - ``ROADMAP.md`` ``OPS-43``.

WHAT WAS BROKEN. Lanternlight replies to a sibling project by writing a note
straight into that sibling's ``moon_sync_inbox/`` directory and keeping no copy.
``moon_sync_inbox/`` is gitignored, so neither the working tree nor git history
carried any artifact saying a reply had ever been sent. On 2026-09-07 a session
reading only its own disk concluded - correctly from its evidence and wrongly in
fact - that this project had never replied to anyone. Measured the same day:
nineteen unique ``from-LL-*`` notes existed across the four sibling inboxes and
fourteen of them left no trace here at all.

Every cold session reads only its own disk. That is the design, so the missing
artifact is this project's problem and not the channel's.

WHAT THESE TESTS PIN, criterion by criterion.

1. :class:`TestTheOutboxCopyIsWrittenBeforeDelivery` - the local copy and its
   manifest record land BEFORE the sibling write is attempted, so a delivery
   that fails half way still leaves the evidence that it was tried. The failure
   is provoked with a real filesystem error rather than a patched function,
   because a patched writer proves a call was made and not that the bytes
   survived it.
2. :class:`TestTheWatcherClassifiesOurOwnOutboxAsOutgoing` - the outbox lives
   INSIDE ``moon_sync_inbox/``, which the operator ruled on 2026-09-07 is
   watched in its entirety. So it cannot be skipped; it must be classified.
   Without this every note this project sends comes straight back as unread
   mail, and the watcher that exists to surface siblings' notes would spend its
   report on our own.
3. :class:`TestAColdSessionCanAnswerFromItsOwnDiskAlone` - the acceptance
   criterion in its own words: a session with no memory answers "has this
   project replied to X, and when" without reading any sibling directory. The
   sibling tree is DELETED before the question is asked, so a lookup that
   secretly reached for it cannot pass.
4. :class:`TestTheReplyPathMapIsRecordedWhereAColdSessionFindsIt` - the map
   from sibling code to inbox directory was re-derived by listing ``C:\\*`` on
   2026-09-07 rather than read from anywhere. It is now recorded in
   ``docs/REPLY_PATHS.md`` and this test refuses to let that document and the
   code drift apart.

NON-VACUOUSNESS. These guards were watched going red before they were trusted -
the outbox copy removed, the classification reverted, the manifest lookup
pointed at nothing - and the run that did it is recorded in the ledger entry
that lands this work. A green test proves nothing until it has been seen red.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from lanternlight import redact
from ops import inbox_watch, outbox

REPO_ROOT = Path(__file__).resolve().parents[1]

NOTE_TEXT = "# to RC\n\nA note this project sent. Plain 7-bit ASCII.\n"


def _tree(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """A throwaway repo root plus a throwaway map of sibling inboxes."""
    (tmp_path / outbox.INBOX_DIRNAME).mkdir()
    siblings = tmp_path / "siblings"
    inboxes = {}
    for code in ("RC", "CS"):
        target = siblings / code / outbox.INBOX_DIRNAME
        target.mkdir(parents=True)
        inboxes[code] = str(target)
    return tmp_path, inboxes


class TestTheOutboxCopyIsWrittenBeforeDelivery:
    """Criterion 1. The local copy is the record, so it cannot land last."""

    def test_a_delivered_note_is_also_in_our_own_outbox(self, tmp_path: Path) -> None:
        root, inboxes = _tree(tmp_path)
        record = outbox.deliver(
            "2026-09-07-1900-from-LL-a-test-note.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        copy = outbox.default_outbox(root) / record.name
        assert copy.is_file()
        assert copy.read_text(encoding="utf-8") == NOTE_TEXT
        assert record.delivered == ("RC",)
        assert record.failed == ()
        landed = Path(inboxes["RC"]) / record.name
        assert landed.read_text(encoding="utf-8") == NOTE_TEXT

    def test_the_copy_survives_a_delivery_that_fails(self, tmp_path: Path) -> None:
        """A real OSError, not a patched writer.

        The recipient's inbox path is an ORDINARY FILE, so the write into it
        fails the way a missing or renamed sibling directory would. If the
        outbox copy were written after delivery this assertion could not pass.
        """
        root, inboxes = _tree(tmp_path)
        broken = tmp_path / "siblings" / "gone"
        broken.write_text("not a directory\n", encoding="utf-8")
        inboxes["RC"] = str(broken)

        record = outbox.deliver(
            "2026-09-07-1901-from-LL-undelivered.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )

        assert record.delivered == ()
        assert [code for code, _reason in record.failed] == ["RC"]
        copy = outbox.default_outbox(root) / record.name
        assert copy.read_text(encoding="utf-8") == NOTE_TEXT
        stored = outbox.load_manifest(root=root)
        assert [row["name"] for row in stored] == [record.name]
        assert stored[0]["delivered"] == []

    def test_the_local_record_is_written_before_any_sibling_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ORDER, pinned directly - "before or at the moment it is delivered".

        The sibling-failure test above proves the copy SURVIVES a failed
        delivery, which is a claim about bytes. This is the other half and a
        different claim: that the local record goes first. It was added after
        the byte test was watched staying green while the manifest write was
        deleted, because a later rewrite put the row back and nothing noticed
        the ordering had gone. A negative result that pins nothing down is how
        a vacuous guard looks from the outside.
        """
        root, inboxes = _tree(tmp_path)
        written: list[str] = []
        original = outbox._replace_atomically

        def watched(target: Path, data: bytes) -> None:
            written.append(str(target))
            original(target, data)

        monkeypatch.setattr(outbox, "_replace_atomically", watched)
        record = outbox.deliver(
            "2026-09-07-1906-from-LL-order.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )

        landed = str(Path(inboxes["RC"]) / record.name)
        assert landed in written
        sibling_at = written.index(landed)
        before = written[:sibling_at]
        assert str(outbox.default_outbox(root) / record.name) in before
        assert str(outbox.default_manifest(root)) in before

    def test_a_partial_delivery_records_both_halves(self, tmp_path: Path) -> None:
        root, inboxes = _tree(tmp_path)
        broken = tmp_path / "siblings" / "wall"
        broken.write_text("not a directory\n", encoding="utf-8")
        inboxes["CS"] = str(broken)

        record = outbox.deliver(
            "2026-09-07-1902-from-LL-half.md",
            NOTE_TEXT,
            ["RC", "CS"],
            root=root,
            inboxes=inboxes,
        )

        assert record.delivered == ("RC",)
        assert [code for code, _reason in record.failed] == ["CS"]

    def test_the_manifest_carries_the_digest_of_what_was_sent(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        record = outbox.deliver(
            "2026-09-07-1903-from-LL-digest.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        stored = outbox.load_manifest(root=root)
        assert stored[0]["digest"] == record.digest
        assert record.digest == inbox_watch.digest_of(NOTE_TEXT.encode("utf-8"))

    def test_a_non_ascii_note_is_refused_before_anything_is_written(
        self, tmp_path: Path
    ) -> None:
        """The authoring rule is 7-bit ASCII and a note is an authored file."""
        root, inboxes = _tree(tmp_path)
        with pytest.raises(ValueError):
            outbox.deliver(
                "2026-09-07-1904-from-LL-bad.md",
                "an em dash \u2014 sneaks in\n",
                ["RC"],
                root=root,
                inboxes=inboxes,
            )
        assert not outbox.default_manifest(root).exists()
        assert list(Path(inboxes["RC"]).iterdir()) == []

    def test_an_unknown_recipient_is_refused(self, tmp_path: Path) -> None:
        root, inboxes = _tree(tmp_path)
        with pytest.raises(KeyError):
            outbox.deliver(
                "2026-09-07-1905-from-LL-nowhere.md",
                NOTE_TEXT,
                ["ZZ"],
                root=root,
                inboxes=inboxes,
            )

    def test_a_name_with_a_path_separator_is_refused(self, tmp_path: Path) -> None:
        """A note name is a filename. It never steers where bytes land."""
        root, inboxes = _tree(tmp_path)
        for bad in ("../escape.md", "sub/note.md", "sub\\note.md"):
            with pytest.raises(ValueError):
                outbox.deliver(bad, NOTE_TEXT, ["RC"], root=root, inboxes=inboxes)

    def test_the_manifest_is_written_atomically(self, tmp_path: Path) -> None:
        """No temporary file survives a delivery, and none is left half written."""
        root, inboxes = _tree(tmp_path)
        for index in range(3):
            outbox.deliver(
                f"2026-09-07-19{index:02d}-from-LL-many.md",
                NOTE_TEXT,
                ["RC"],
                root=root,
                inboxes=inboxes,
            )
        leftovers = [
            path.name
            for path in outbox.default_outbox(root).iterdir()
            if path.name.startswith(".tmp") or path.suffix == ".tmp"
        ]
        assert leftovers == []
        assert len(outbox.load_manifest(root=root)) == 3


class TestTheWatcherClassifiesOurOwnOutboxAsOutgoing:
    """Criterion 2. The outbox is inside the watched folder, so it is classified."""

    def _seen(self, tmp_path: Path) -> Path:
        return tmp_path / "runtime" / "inbox_seen.json"

    def test_the_two_modules_agree_on_the_directory_name(self) -> None:
        """The string is duplicated rather than imported. So it is checked.

        ``ops/inbox_watch.py`` is run as a script by a ``SessionStart`` hook and
        a script's ``sys.path`` does not carry the repository root, so an
        ``ops.outbox`` import inside it would fail exactly where the watcher
        must not fail. The cost of that choice is drift, and this is the guard
        that charges for it.
        """
        assert inbox_watch.OUTBOX_DIRNAME == outbox.OUTBOX_DIRNAME

    def test_our_outbox_is_never_reported_as_an_unread_drop(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1910-from-LL-mine.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        result = inbox_watch.scan(
            inbox=outbox.default_inbox(root), state=self._seen(tmp_path)
        )
        assert result.status == "ok"
        assert [drop.name for drop in result.drops] == []
        assert result.outbox_present is True
        assert result.outbox_notes == 1

    def test_a_sibling_drop_is_still_reported_beside_our_outbox(
        self, tmp_path: Path
    ) -> None:
        """The skip is for OUR directory by name, not for directories."""
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1911-from-LL-mine.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        theirs = outbox.default_inbox(root) / "from-RC-verbatim"
        theirs.mkdir()
        (theirs / "payload.py").write_text("x = 1\n", encoding="utf-8")

        result = inbox_watch.scan(
            inbox=outbox.default_inbox(root), state=self._seen(tmp_path)
        )
        assert [drop.name for drop in result.drops] == ["from-RC-verbatim"]
        assert result.drops[0].is_new is True

    def test_the_report_names_the_outbox_as_ours_and_not_as_mail(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1912-from-LL-mine.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        result = inbox_watch.scan(
            inbox=outbox.default_inbox(root), state=self._seen(tmp_path)
        )
        text = inbox_watch.render(result)
        assert "OUR OWN OUTGOING NOTES" in text
        assert "2026-09-07-1912-from-LL-mine.md" not in text

    def test_the_outbox_never_enters_the_withdrawal_baseline(
        self, tmp_path: Path
    ) -> None:
        """An emptied outbox is not a withdrawn sibling drop."""
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1913-from-LL-mine.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        state = self._seen(tmp_path)
        inbox_watch.acknowledge_inbox(inbox=outbox.default_inbox(root), state=state)
        for path in outbox.default_outbox(root).iterdir():
            path.unlink()
        result = inbox_watch.scan(inbox=outbox.default_inbox(root), state=state)
        assert result.withdrawn == []


class TestAColdSessionCanAnswerFromItsOwnDiskAlone:
    """Criterion 3. The question is answered without any sibling directory."""

    def test_it_answers_whether_and_when_we_replied_with_the_siblings_gone(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1920-from-LL-to-rc.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
            now="2026-09-07T23:20:00Z",
        )
        outbox.deliver(
            "2026-09-07-1930-from-LL-to-both.md",
            NOTE_TEXT,
            ["RC", "CS"],
            root=root,
            inboxes=inboxes,
            now="2026-09-07T23:30:00Z",
        )

        # THE SIBLINGS ARE GONE. A lookup that reached for one cannot pass.
        for code in list(inboxes):
            for path in sorted(Path(inboxes[code]).iterdir()):
                path.unlink()
            Path(inboxes[code]).rmdir()
            Path(inboxes[code]).parent.rmdir()

        to_rc = outbox.replies_to("RC", root=root)
        assert [row["name"] for row in to_rc] == [
            "2026-09-07-1920-from-LL-to-rc.md",
            "2026-09-07-1930-from-LL-to-both.md",
        ]
        assert to_rc[0]["sent_utc"] == "2026-09-07T23:20:00Z"

        to_cs = outbox.replies_to("CS", root=root)
        assert [row["name"] for row in to_cs] == ["2026-09-07-1930-from-LL-to-both.md"]

    def test_a_sibling_we_never_wrote_to_answers_no_rather_than_raising(
        self, tmp_path: Path
    ) -> None:
        """"We have not replied" is a real answer and must be distinguishable."""
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1921-from-LL-to-rc.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        assert outbox.replies_to("LW", root=root) == []

    def test_an_absent_outbox_answers_nothing_rather_than_raising(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / outbox.INBOX_DIRNAME).mkdir()
        assert outbox.replies_to("RC", root=tmp_path) == []
        assert outbox.load_manifest(root=tmp_path) == []

    def test_a_corrupt_manifest_is_reported_and_not_silently_empty(
        self, tmp_path: Path
    ) -> None:
        """A store that cannot be read must never read as "we never replied"."""
        root, _inboxes = _tree(tmp_path)
        outbox.default_outbox(root).mkdir(parents=True)
        outbox.default_manifest(root).write_text("{not json", encoding="utf-8")
        with pytest.raises(ValueError):
            outbox.load_manifest(root=root)

    def test_the_answer_survives_a_reread_from_a_fresh_process_view(
        self, tmp_path: Path
    ) -> None:
        """Nothing is held in memory - the manifest on disk is the whole record."""
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1922-from-LL-persisted.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        raw = json.loads(outbox.default_manifest(root).read_text(encoding="utf-8"))
        assert raw["deliveries"][0]["recipients"] == ["RC"]


class TestTheBackfillRecoversRepliesSentBeforeAnyOfThisExisted:
    """The twenty five replies already sent are the case the item is about.

    An empty outbox fixes only the future. Twenty five ``from-LL-*`` notes were
    already sitting in four sibling directories when this landed, and a cold
    session still could not account for them. :func:`ops.outbox.backfill` reads
    OUR OWN notes back out and records them.

    WHAT IT MUST NOT DO is pretend the result is the same fact as a delivery it
    watched. A reconstructed row carries no ``sent_utc`` at all - a missing
    number is recoverable and a confident wrong one is not - and is marked
    ``reconstructed`` so nothing downstream can quietly average the two kinds
    together. The only time available is the file's mtime on the sibling's
    disk, which is when the note LANDED and not when we sent it.
    """

    def _plant(self, inboxes: dict[str, str], code: str, name: str) -> Path:
        path = Path(inboxes[code]) / name
        path.write_text(NOTE_TEXT, encoding="utf-8")
        return path

    def test_it_recovers_our_own_notes_and_marks_them_reconstructed(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        self._plant(inboxes, "RC", "2026-09-06-2307-from-LL-early.md")
        self._plant(inboxes, "CS", "2026-09-06-2307-from-LL-early.md")
        self._plant(inboxes, "CS", "2026-09-07-0800-from-LL-wave.md")
        self._plant(inboxes, "RC", "2026-09-07-0801-from-RC-not-ours.md")

        rows = outbox.backfill(inboxes=inboxes, root=root)

        assert sorted(row["name"] for row in rows) == [
            "2026-09-06-2307-from-LL-early.md",
            "2026-09-07-0800-from-LL-wave.md",
        ]
        early = next(r for r in rows if r["name"].endswith("early.md"))
        assert sorted(early["recipients"]) == ["CS", "RC"]
        assert early["reconstructed"] is True
        assert "sent_utc" not in early
        assert "sent_local" not in early
        assert early["earliest_seen_local"]

    def test_a_recovered_note_answers_the_cold_session_question(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        self._plant(inboxes, "RC", "2026-09-06-2307-from-LL-early.md")
        outbox.backfill(inboxes=inboxes, root=root)
        answered = outbox.replies_to("RC", root=root)
        assert [row["name"] for row in answered] == [
            "2026-09-06-2307-from-LL-early.md"
        ]
        assert answered[0]["reconstructed"] is True

    def test_it_never_overwrites_a_delivery_it_actually_watched(
        self, tmp_path: Path
    ) -> None:
        """An observed send outranks a reconstruction of the same note."""
        root, inboxes = _tree(tmp_path)
        outbox.deliver(
            "2026-09-07-1940-from-LL-real.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
            now="2026-09-07T23:40:00Z",
        )
        rows = outbox.backfill(inboxes=inboxes, root=root)
        assert rows == []
        stored = outbox.load_manifest(root=root)
        assert len(stored) == 1
        assert stored[0]["sent_utc"] == "2026-09-07T23:40:00Z"
        assert "reconstructed" not in stored[0]

    def test_running_it_twice_adds_nothing_the_second_time(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        self._plant(inboxes, "RC", "2026-09-06-2307-from-LL-early.md")
        first = outbox.backfill(inboxes=inboxes, root=root)
        second = outbox.backfill(inboxes=inboxes, root=root)
        assert len(first) == 1
        assert second == []
        assert len(outbox.load_manifest(root=root)) == 1

    def test_a_missing_sibling_directory_is_skipped_not_fatal(
        self, tmp_path: Path
    ) -> None:
        root, inboxes = _tree(tmp_path)
        self._plant(inboxes, "RC", "2026-09-06-2307-from-LL-early.md")
        inboxes["LW"] = str(tmp_path / "siblings" / "LW" / outbox.INBOX_DIRNAME)
        rows = outbox.backfill(inboxes=inboxes, root=root)
        assert [row["name"] for row in rows] == [
            "2026-09-06-2307-from-LL-early.md"
        ]

    def test_the_copy_is_written_into_our_outbox_too(self, tmp_path: Path) -> None:
        root, inboxes = _tree(tmp_path)
        self._plant(inboxes, "RC", "2026-09-06-2307-from-LL-early.md")
        outbox.backfill(inboxes=inboxes, root=root)
        copy = outbox.default_outbox(root) / "2026-09-06-2307-from-LL-early.md"
        assert copy.read_text(encoding="utf-8") == NOTE_TEXT


class TestTheReplyPathMapIsRecordedWhereAColdSessionFindsIt:
    """Criterion 4. The map was re-derived by listing the disk. Not any more."""

    def _doc(self) -> str:
        return (REPO_ROOT / "docs" / "REPLY_PATHS.md").read_text(encoding="utf-8")

    def test_the_document_exists_and_names_every_sibling_code(self) -> None:
        text = self._doc()
        for code in outbox.SIBLING_INBOXES:
            assert re.search(rf"\|\s*`{code}`\s*\|", text), code

    def test_every_path_in_the_code_appears_in_the_document(self) -> None:
        text = self._doc()
        for code, path in outbox.SIBLING_INBOXES.items():
            assert path in text, f"{code} -> {path}"

    def test_the_document_names_no_sibling_the_code_does_not_know(self) -> None:
        """Drift in the other direction is drift too."""
        text = self._doc()
        in_doc = set(re.findall(r"\|\s*`([A-Z]{2,3})`\s*\|", text))
        assert in_doc == set(outbox.SIBLING_INBOXES)

    def test_claude_md_points_at_the_map(self) -> None:
        """A map a cold session cannot find is a map it will re-derive."""
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert "docs/REPLY_PATHS.md" in text


class TestAnOutgoingNoteCarryingAnOperatorIdentifierIsRefused:
    """``OPS-50`` criterion 2. The gate is on what LEAVES, not on what commits.

    WHY THIS IS HERE AND NOT IN A COMMIT HOOK. On 2026-09-07 this project put
    the operator's own email address into a note and delivered it to four
    sibling directories. Every commit-time guard in this tree was silent, and
    silent BY CONSTRUCTION rather than by accident: ``moon_sync_inbox/`` is
    gitignored, so nothing under it is ever staged and no pre-commit hook, no
    tracked-file scan and no ASCII guard ever sees a byte of it. The only place
    an outgoing note passes through is :func:`ops.outbox.deliver`, so that is
    the only place a gate can stand.

    IT RAISES; IT DOES NOT QUIETLY REDACT. A note altered on the way out is a
    note whose author does not know what they sent, and the author is the only
    party who can judge whether the sentence still means what it said. Refusing
    hands the decision back; rewriting takes it away and hides that it was
    taken.

    WHAT THE GATE DOES NOT DO, stated rather than hidden. It checks the
    OPERATOR IDENTIFIER class and not the full game-log rule set. Measured
    2026-09-07 over the 27 notes already in this project's outbox: running
    every file-scan label over them produces 2 findings in 1 note, and both are
    regex SOURCE quoted in prose - a note reporting a git pickaxe sweep quotes
    the patterns it swept with, and the patterns match themselves. A gate that
    refuses a correct note is a gate somebody routes around, which is how a
    guard stops existing. Widening it is a one-line change to
    :data:`lanternlight.redact.OPERATOR_IDENTIFIER_LABELS`.
    """

    def _address(self) -> str:
        # Invented, assembled at runtime, and at a domain that is not reserved
        # for documentation - so the SHAPE half of the guard is what catches it.
        return "someone" + "@" + "a-real-looking-host" + ".com"

    def test_a_note_carrying_an_address_is_refused(self, tmp_path: Path) -> None:
        root, inboxes = _tree(tmp_path)
        with pytest.raises(redact.RedactionError):
            outbox.deliver(
                "2026-09-07-1930-from-LL-with-an-address.md",
                "# to RC\n\nmail " + self._address() + "\n",
                ["RC"],
                root=root,
                inboxes=inboxes,
            )

    def test_the_refusal_happens_before_a_single_byte_is_written(
        self, tmp_path: Path
    ) -> None:
        """Nothing local, nothing remote. The gate is in front of both writes.

        The outbox copy is written FIRST by design (``OPS-43``), so a gate
        placed even one line late would leave the address sitting in this
        tree's own outbox - which is inside the watched channel and therefore
        exactly where the next session would read it back out.
        """
        root, inboxes = _tree(tmp_path)
        name = "2026-09-07-1931-from-LL-nothing-written.md"
        with pytest.raises(redact.RedactionError):
            outbox.deliver(
                name,
                "# to RC\n\nmail " + self._address() + "\n",
                ["RC", "CS"],
                root=root,
                inboxes=inboxes,
            )
        assert not (outbox.default_outbox(root) / name).exists()
        assert not outbox.default_manifest(root).exists()
        assert outbox.load_manifest(root=root) == []
        for code in ("RC", "CS"):
            assert not (Path(inboxes[code]) / name).exists()

    def test_the_note_name_is_checked_as_well_as_its_body(
        self, tmp_path: Path
    ) -> None:
        """A filename leaves the machine too, and it is the half nobody reads.

        Every note this project sends is named after its own subject line, so a
        note ABOUT an address is exactly the note whose name carries one - which
        is the shape the 2026-09-07 correction note came within one edit of.
        """
        root, inboxes = _tree(tmp_path)
        with pytest.raises(redact.RedactionError):
            outbox.deliver(
                "2026-09-07-1932-from-LL-" + self._address() + ".md",
                "# to RC\n\nAn ordinary note.\n",
                ["RC"],
                root=root,
                inboxes=inboxes,
            )

    def test_the_refusal_does_not_quote_the_address(self, tmp_path: Path) -> None:
        """The exception travels - into a traceback, a log, a session summary.

        A guard that prints the identifier at the moment it fires has published
        it, and it has done so in the one place everybody copies verbatim.
        """
        root, inboxes = _tree(tmp_path)
        address = self._address()
        with pytest.raises(redact.RedactionError) as excinfo:
            outbox.deliver(
                "2026-09-07-1933-from-LL-quiet-refusal.md",
                "# to RC\n\nmail " + address + "\n",
                ["RC"],
                root=root,
                inboxes=inboxes,
            )
        message = str(excinfo.value)
        assert address not in message
        assert "a-real-looking-host" not in message

    def test_the_operators_own_derived_identity_is_refused(
        self, tmp_path: Path
    ) -> None:
        """The incident itself, replayed. No literal address in this file.

        The identity is read from git at runtime, which is the whole point of
        criterion 1: the value is redactable because of WHAT IT IS, not because
        of which command printed it.
        """
        identities = redact.operator_git_identities()
        assert identities, "no git identity derived - this test would be inert"
        root, inboxes = _tree(tmp_path)
        with pytest.raises(redact.RedactionError):
            outbox.deliver(
                "2026-09-07-1934-from-LL-git-identity-sweep.md",
                "# to LW\n\ngit log --format said " + identities[0] + "\n",
                ["RC"],
                root=root,
                inboxes=inboxes,
            )

    def test_an_ordinary_note_still_goes_out(self, tmp_path: Path) -> None:
        """The other half of the claim. A gate that refuses everything is an
        outage, not a guard - and this project's whole note channel runs through
        this one function."""
        root, inboxes = _tree(tmp_path)
        record = outbox.deliver(
            "2026-09-07-1935-from-LL-ordinary.md",
            NOTE_TEXT,
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        assert record.delivered == ("RC",)

    def test_a_documentation_address_is_still_deliverable(
        self, tmp_path: Path
    ) -> None:
        """RFC 2606 reserves these so a document can carry an address that
        identifies nobody. This project's own notes discuss addresses; refusing
        the reserved ones would make the incident report unsendable."""
        root, inboxes = _tree(tmp_path)
        record = outbox.deliver(
            "2026-09-07-1936-from-LL-documentation-address.md",
            "# to RC\n\nUse " + "probe" + "@" + "example" + ".invalid" + " here.\n",
            ["RC"],
            root=root,
            inboxes=inboxes,
        )
        assert record.delivered == ("RC",)
