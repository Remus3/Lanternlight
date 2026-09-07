"""The inbox keys are CONTENT digests, and this file is what proves it.

WHY THIS FILE EXISTS
--------------------
A mutation run against ``ops/inbox_watch.py`` on 2026-09-07, before this file
existed, replaced the note key's content digest with the file's ``st_size`` and
then with its ``st_mtime_ns``. Both mutants SURVIVED the whole inbox suite.

The reason is the shape of the existing edit test: it replaces the note's text
with a longer sentence, moments after writing the first one. A size-keyed
watcher sees a different size, a mtime-keyed watcher sees a different mtime, and
both report the edit for the wrong reason. The test could not fail, so it was
proving that SOMETHING about the file changed, not that the CONTENT is what the
key is taken over. That distinction is the whole point of the key: a stat-keyed
watcher misses an edit that preserves length, and it misses a restored file
whose timestamp was rewritten by a copy.

HOW THE ARM IS BUILT, AND WHY EACH STEP IS LOAD-BEARING
-------------------------------------------------------
1. **The mtime is forced to a fixed past value BEFORE the acknowledgement**, so
   the value the watcher would key on is known rather than "whatever the clock
   said".
2. **The edit is IN PLACE and at constant byte length.** Equal length is what
   disarms an ``st_size`` key.
3. **The mtime is asserted to have MOVED before it is restored.** Without that
   assertion the restore could be papering over a write that never happened,
   and a mutation that fails to apply looks exactly like a passing test.
4. **The mtime is then restored and re-asserted**, together with the size, so
   the only thing that differs between the two looks is the bytes.
5. **Bytes are written, never text.** ``write_text`` on Windows turns LF into
   CRLF, so a "same length" fixture silently is not one.
"""

from __future__ import annotations

import os
from pathlib import Path

from ops import inbox_watch

#: A fixed past timestamp, in nanoseconds. Any value works as long as it is not
#: the clock: the point is that both looks see the SAME mtime.
FROZEN_NS = 1_600_000_000_000_000_000


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    inbox = tmp_path / "moon_sync_inbox"
    inbox.mkdir()
    return inbox, tmp_path / "runtime" / "inbox_seen.json"


def _write_bytes(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _freeze(path: Path) -> None:
    os.utime(path, ns=(FROZEN_NS, FROZEN_NS))
    assert path.stat().st_mtime_ns == FROZEN_NS, "the mtime could not be pinned"


def _edit_in_place_leaving_stat_identical(path: Path, replacement: bytes) -> None:
    """Rewrite ``path`` with different bytes of the SAME length and stat.

    Returns nothing; it raises instead, because every check here is an ARMING
    check. A silent failure of any one of them would leave a test that passes
    for a reason it does not name.
    """
    before = path.read_bytes()
    assert len(replacement) == len(before), (
        f"the arm needs a constant-length edit: {len(before)} -> {len(replacement)}"
    )
    assert replacement != before, "the arm needs the bytes to actually differ"
    frozen = path.stat().st_mtime_ns
    assert frozen == FROZEN_NS, "the mtime was not pinned before the edit"

    path.write_bytes(replacement)

    assert path.stat().st_mtime_ns != frozen, (
        "the write did not move the mtime, so restoring it proves nothing and "
        "an mtime-keyed watcher would be exonerated by accident"
    )
    _freeze(path)
    assert path.stat().st_size == len(before), "the size moved after all"
    assert path.read_bytes() == replacement, "the edit did not stick"


def _new_names(result) -> set[str]:
    out: set[str] = set()
    for group in result.groups:
        if group.is_new:
            out.update(group.names)
    return out


class TestTheNoteKeyIsTakenOverContent:
    def test_a_same_length_same_mtime_edit_still_resurfaces_the_note(
        self, tmp_path: Path
    ) -> None:
        inbox, state = _tree(tmp_path)
        note = _write_bytes(inbox / "note.md", b"# From RC - hi\n\nsent to LL. AAAA\n")
        _freeze(note)

        inbox_watch.acknowledge_inbox(inbox=inbox, state=state)
        _edit_in_place_leaving_stat_identical(note, b"# From RC - hi\n\nsent to LL. BBBB\n")
        after = inbox_watch.scan(inbox=inbox, state=state)

        assert _new_names(after) == {"note.md"}, (
            "the note's size and mtime are byte-for-byte what they were at the "
            "acknowledgement, so a stat-keyed watcher calls this already seen - "
            "and on this channel an edit is usually the correction"
        )

    def test_an_unedited_note_with_a_moved_mtime_does_not_resurface(
        self, tmp_path: Path
    ) -> None:
        """The other direction, so the test above is not bought by noise.

        Touching a file - which a copy, a sync or an editor does routinely -
        must not be reported as mail. An mtime-keyed watcher fails this one.
        """
        inbox, state = _tree(tmp_path)
        note = _write_bytes(inbox / "note.md", b"# From RC - hi\n\nsent to LL.\n")
        _freeze(note)
        inbox_watch.acknowledge_inbox(inbox=inbox, state=state)

        os.utime(note, ns=(FROZEN_NS + 10**9, FROZEN_NS + 10**9))
        after = inbox_watch.scan(inbox=inbox, state=state)

        assert _new_names(after) == set()

    def test_two_notes_swapping_their_contents_resurface(self, tmp_path: Path) -> None:
        """Sizes unchanged, both mtimes restored: only the bytes moved."""
        inbox, state = _tree(tmp_path)
        first = _write_bytes(inbox / "a.md", b"# From RC\n\nsent to LL. AAAA\n")
        second = _write_bytes(inbox / "b.md", b"# From RC\n\nsent to LL. BBBB\n")
        _freeze(first)
        _freeze(second)
        inbox_watch.acknowledge_inbox(inbox=inbox, state=state)

        _edit_in_place_leaving_stat_identical(first, b"# From RC\n\nsent to LL. BBBB\n")
        _edit_in_place_leaving_stat_identical(second, b"# From RC\n\nsent to LL. AAAA\n")
        after = inbox_watch.scan(inbox=inbox, state=state)

        assert _new_names(after) == {"a.md", "b.md"}


class TestTheDropManifestKeyIsTakenOverContent:
    def test_a_same_length_same_mtime_edit_inside_a_drop_resurfaces_it(
        self, tmp_path: Path
    ) -> None:
        inbox, state = _tree(tmp_path)
        drop = inbox / "from-XX-verbatim"
        inside = _write_bytes(drop / "tools" / "guard.py", b"VALUE = 1111\n")
        _freeze(inside)
        _freeze(drop)

        inbox_watch.acknowledge_inbox(inbox=inbox, state=state)
        _edit_in_place_leaving_stat_identical(inside, b"VALUE = 2222\n")
        # The drop's OWN directory mtime is pinned as well. A directory's mtime
        # does not move when a file inside it is rewritten, so leaving it alone
        # would exonerate a directory-mtime key by accident rather than on the
        # evidence.
        _freeze(drop)
        after = inbox_watch.scan(inbox=inbox, state=state)

        changed = [d.name for d in after.drops if d.is_new]
        assert changed == ["from-XX-verbatim"], (
            "the drop's byte total and its directory mtime are unchanged, so a "
            "stat-keyed manifest calls a corrected file already seen"
        )

    def test_an_untouched_drop_with_a_moved_directory_mtime_does_not_resurface(
        self, tmp_path: Path
    ) -> None:
        inbox, state = _tree(tmp_path)
        drop = inbox / "from-XX-verbatim"
        inside = _write_bytes(drop / "tools" / "guard.py", b"VALUE = 1111\n")
        _freeze(inside)
        _freeze(drop)
        inbox_watch.acknowledge_inbox(inbox=inbox, state=state)

        moved = FROZEN_NS + 10**9
        os.utime(drop, ns=(moved, moved))
        os.utime(inside, ns=(moved, moved))
        after = inbox_watch.scan(inbox=inbox, state=state)

        assert [d.name for d in after.drops if d.is_new] == []
