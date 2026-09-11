"""Tests for the step that APPLIES an OPS-57 continuity-document split.

ROADMAP ``OPS-80``. ``tools/doc_archive.py`` plans a split and deliberately
writes nothing: it is a library of pure text-to-text functions, and its own
docstring defends that separation because this repository has been bitten by
tools that did more than their name promised. The defect ``OPS-80`` records is
not that separation - it is that ``CLAUDE.md`` told a cold session under a
fired size budget to re-run ``tools/doc_archive.py``, a command that prints a
report and changes nothing. ``scripts/apply_doc_split.py`` is the missing half:
a thin applier that calls the planner, re-derives the conservation properties
against the SOURCE text, and only then writes.

WHY THE APPLIER RE-DERIVES RATHER THAN TRUSTS. The planning functions already
raise :class:`tools.doc_archive.ConservationError` on a lossy plan. Re-checking
inside the applier is not redundancy for its own sake: a guard that reads its
expectation out of the thing it grades cannot fail, so the applier reassembles
the ORIGINAL document from the plan's own sections - sorted back into their
source order, by the character offsets the planner reported - and demands exact
full-text equality. That check would survive the planner's internal asserts
being deleted outright, which is the only version of the check worth having.

WHAT IS AND IS NOT CONSERVED, STATED EXACTLY. For the ledger the property is
total: ``live + archived_tail == original``, byte for byte, because the ledger
cut is a contiguous tail. For the roadmap one section is deliberately NOT
conserved - the generated ``## Archive index``. It is regenerated on every run
so that one index covers old and new archived items, so the roadmap property is
stated against the source with its previous index section removed, and the
index's own correctness is proved separately by ``tools/archive_link_guard.py``
in both directions. Writing the weaker property down here rather than quietly
relaxing the strong one is the point: a conservation claim that silently
excludes an unnamed section is worth nothing.

THE VACUOUS-GUARD TRAP THIS FILE IS BUILT AGAINST. A refusal test that feeds
the applier a plan it would reject for some OTHER reason passes while the
conservation check is dead code. So every refusal test below mutates a
FAITHFUL plan by exactly one character or one section, asserts the unmutated
plan verifies first, and asserts the mutation actually changed the text it
aimed at before believing the refusal.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import apply_doc_split  # noqa: E402
from tools import doc_archive  # noqa: E402

ROADMAP_PATH = REPO_ROOT / "ROADMAP.md"
LEDGER_PATH = REPO_ROOT / "docs/LEDGER.md"
ROADMAP_ARCHIVE_PATH = REPO_ROOT / doc_archive.DEFAULT_ROADMAP_ARCHIVE
LEDGER_ARCHIVE_PATH = REPO_ROOT / doc_archive.DEFAULT_LEDGER_ARCHIVE

#: Independent section scanners. Deliberately NOT ``doc_archive.split_sections``:
#: a test that reassembles a document with the same function the applier used
#: to take it apart cannot detect an error in that function.
_H2 = re.compile(r"^## ", re.MULTILINE)
_ENTRY = re.compile(r"^### LL-", re.MULTILINE)

#: The live roadmap's generated index heading, as text a slice starts with.
_INDEX_PREFIX = doc_archive.INDEX_HEADING


def _slice_on(pattern: re.Pattern[str], text: str) -> tuple[str, list[str]]:
    """Return the run-in before the first match and each match's own slice."""
    starts = [m.start() for m in pattern.finditer(text)]
    if not starts:
        return text, []
    bounds = [*starts, len(text)]
    return text[: starts[0]], [text[starts[i] : bounds[i + 1]] for i in range(len(starts))]


def _archive_body(pattern: re.Pattern[str], text: str) -> str:
    """Return an archive document's text from its first section onward."""
    _, chunks = _slice_on(pattern, text)
    return "".join(chunks)


def _repo_copy(tmp_path: Path) -> Path:
    """Copy the four real continuity documents into a throwaway repo root."""
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    shutil.copyfile(ROADMAP_PATH, root / "ROADMAP.md")
    shutil.copyfile(LEDGER_PATH, root / "docs/LEDGER.md")
    if ROADMAP_ARCHIVE_PATH.exists():
        shutil.copyfile(ROADMAP_ARCHIVE_PATH, root / doc_archive.DEFAULT_ROADMAP_ARCHIVE)
    if LEDGER_ARCHIVE_PATH.exists():
        shutil.copyfile(LEDGER_ARCHIVE_PATH, root / doc_archive.DEFAULT_LEDGER_ARCHIVE)
    return root


def _read(path: Path) -> str:
    """Return a document's text, decoded the one way this repository writes it."""
    return path.read_text(encoding="utf-8")


class TestWriteAtomic:
    """``write_atomic`` must never leave a reader half a document."""

    def test_it_puts_the_text_at_the_target(self, tmp_path: Path) -> None:
        target = tmp_path / "doc.md"
        apply_doc_split.write_atomic(target, "one\ntwo\n")
        assert _read(target) == "one\ntwo\n"

    def test_a_failed_publish_leaves_the_old_content_intact(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write that dies mid-flight must not truncate what was there.

        This is the assertion that fails the moment ``write_atomic`` becomes a
        plain ``target.write_text(...)``: a direct write truncates the target
        before it can fail, so the old content is already gone.
        """
        target = tmp_path / "doc.md"
        target.write_text("ORIGINAL\n", encoding="utf-8")

        def explode(self: Path, other: object) -> None:
            raise OSError("publish refused")

        monkeypatch.setattr(Path, "replace", explode)
        with pytest.raises(OSError):
            apply_doc_split.write_atomic(target, "REPLACEMENT\n")
        assert _read(target) == "ORIGINAL\n"

    def test_it_leaves_no_temporary_file_behind_on_success(self, tmp_path: Path) -> None:
        target = tmp_path / "doc.md"
        apply_doc_split.write_atomic(target, "body\n")
        assert [p.name for p in tmp_path.iterdir()] == ["doc.md"]

    def test_it_writes_line_feeds_and_not_carriage_returns(self, tmp_path: Path) -> None:
        """Python's text mode would turn every LF into CRLF on this platform.

        Read back as BYTES on purpose. ``read_text`` translates line endings on
        the way in and hides exactly the damage this asserts against - which is
        the repository's own recorded trap about byte counts that lie.
        """
        target = tmp_path / "doc.md"
        apply_doc_split.write_atomic(target, "alpha\nbeta\n")
        assert target.read_bytes() == b"alpha\nbeta\n"


class TestRoadmapVerification:
    """The roadmap conservation check, exercised on the real document."""

    def _plan(self) -> tuple[str, str, doc_archive.RoadmapPlan]:
        source = _read(ROADMAP_PATH)
        prior = _read(ROADMAP_ARCHIVE_PATH) if ROADMAP_ARCHIVE_PATH.exists() else ""
        plan = doc_archive.plan_roadmap_split(
            source, doc_archive.DEFAULT_ROADMAP_ARCHIVE, existing_archive=prior
        )
        return source, prior, plan

    def test_a_faithful_plan_verifies(self) -> None:
        source, prior, plan = self._plan()
        apply_doc_split.verify_roadmap(source, prior, plan)

    def test_it_refuses_an_archive_that_dropped_one_character(self) -> None:
        source, prior, plan = self._plan()
        apply_doc_split.verify_roadmap(source, prior, plan)
        damaged = plan.archive_text[:-1]
        assert damaged != plan.archive_text, "the mutation did not change the archive"
        lossy = doc_archive.RoadmapPlan(
            roadmap_text=plan.roadmap_text,
            archive_text=damaged,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_roadmap(source, prior, lossy)

    def test_it_refuses_a_live_document_whose_kept_text_was_reflowed(self) -> None:
        source, prior, plan = self._plan()
        anchor = plan.kept[-1].text
        assert anchor in plan.roadmap_text, "the anchor text is not in the live document"
        reflowed = plan.roadmap_text.replace(anchor, anchor.replace("\n", " ", 1), 1)
        assert reflowed != plan.roadmap_text, "the reflow mutation did not apply"
        lossy = doc_archive.RoadmapPlan(
            roadmap_text=reflowed,
            archive_text=plan.archive_text,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_roadmap(source, prior, lossy)

    def test_it_refuses_when_the_archive_forgets_what_it_already_held(self) -> None:
        source, prior, plan = self._plan()
        if not prior:
            pytest.skip("no archive exists yet, so nothing can be forgotten")
        lossy = doc_archive.RoadmapPlan(
            roadmap_text=plan.roadmap_text,
            archive_text=plan.archive_header,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_roadmap(source, prior, lossy)


class TestLedgerVerification:
    """The ledger conservation check. Here the property is total equality."""

    def _plan(
        self, keep: int = doc_archive.DEFAULT_LEDGER_KEEP
    ) -> tuple[str, str, doc_archive.LedgerPlan]:
        source = _read(LEDGER_PATH)
        prior = _read(LEDGER_ARCHIVE_PATH) if LEDGER_ARCHIVE_PATH.exists() else ""
        plan = doc_archive.plan_ledger_split(source, keep, existing_archive=prior)
        return source, prior, plan

    def test_a_faithful_plan_verifies(self) -> None:
        source, prior, plan = self._plan()
        apply_doc_split.verify_ledger(source, prior, plan)

    def test_it_refuses_an_entry_edited_by_one_character(self) -> None:
        source, prior, plan = self._plan(keep=1)
        apply_doc_split.verify_ledger(source, prior, plan)
        victim = plan.archived[0].text
        assert victim in plan.archive_text, "the anchor entry is not in the archive"
        edited = plan.archive_text.replace(victim, victim.replace("-", "_", 1), 1)
        assert edited != plan.archive_text, "the one-character edit did not apply"
        lossy = doc_archive.LedgerPlan(
            ledger_text=plan.ledger_text,
            archive_text=edited,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_ledger(source, prior, lossy)

    def test_it_refuses_a_modified_head_through_the_marker(self) -> None:
        source, prior, plan = self._plan(keep=1)
        assert doc_archive.LEDGER_MARKER in source, "the real ledger carries no marker"
        damaged = plan.ledger_text.replace("# Lanternlight", "# Lanternlight ", 1)
        assert damaged != plan.ledger_text, "the head mutation did not apply"
        lossy = doc_archive.LedgerPlan(
            ledger_text=damaged,
            archive_text=plan.archive_text,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_ledger(source, prior, lossy)

    def test_it_refuses_when_the_live_document_keeps_an_archived_entry_too(self) -> None:
        """Duplication is a conservation failure in the other direction."""
        source, prior, plan = self._plan(keep=1)
        duplicated = plan.ledger_text + plan.archived[0].text
        assert duplicated != plan.ledger_text, "the duplication mutation did not apply"
        lossy = doc_archive.LedgerPlan(
            ledger_text=duplicated,
            archive_text=plan.archive_text,
            archive_header=plan.archive_header,
            kept=plan.kept,
            archived=plan.archived,
        )
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.verify_ledger(source, prior, lossy)


class TestApplyOnCopiesOfTheRealDocuments:
    """End to end, against copies, so the real tree is never the subject."""

    def test_the_roadmap_pair_reconstructs_the_original(self, tmp_path: Path) -> None:
        root = _repo_copy(tmp_path)
        before = _read(root / "ROADMAP.md")
        prior_body = _archive_body(_H2, _read(root / doc_archive.DEFAULT_ROADMAP_ARCHIVE))

        apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)

        live = _read(root / "ROADMAP.md")
        archive_body = _archive_body(_H2, _read(root / doc_archive.DEFAULT_ROADMAP_ARCHIVE))
        assert archive_body.startswith(prior_body), "the archive forgot what it held"
        moved = archive_body[len(prior_body) :]

        preamble, before_sections = _slice_on(_H2, before)
        before_items = [s for s in before_sections if not s.startswith(_INDEX_PREFIX)]
        live_preamble, live_sections = _slice_on(_H2, live)
        live_kept = live_preamble + "".join(
            s for s in live_sections if not s.startswith(_INDEX_PREFIX)
        )
        _, moved_sections = _slice_on(_H2, moved)
        for section in moved_sections:
            assert section in before, "an archived section was altered on the way out"

        remaining = list(moved_sections)
        expected_items = []
        for section in before_items:
            if section in remaining:
                remaining.remove(section)
            else:
                expected_items.append(section)
        assert remaining == [], "an archived section did not come from the source"
        expected_live = preamble + "".join(expected_items)

        # Equality over the FULL text, with one named exception: the planner
        # separates the regenerated index from the last kept section with an
        # extra blank line, so the live document's trailing newline RUN grows
        # by one per run. That is additive whitespace, never lost content, and
        # it is pinned rather than tolerated - the second assertion says the
        # difference can be newlines and nothing else. Filed as ROADMAP OPS-81.
        assert live_kept.rstrip("\n") == expected_live.rstrip("\n")
        assert set(live_kept[len(live_kept.rstrip("\n")) :]) <= {"\n"}
        assert len(live_kept) - len(expected_live) <= 1

    def test_the_ledger_pair_reproduces_the_original_byte_for_byte(
        self, tmp_path: Path
    ) -> None:
        root = _repo_copy(tmp_path)
        before = _read(root / "docs/LEDGER.md")
        prior_body = _archive_body(_ENTRY, _read(root / doc_archive.DEFAULT_LEDGER_ARCHIVE))

        apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)

        live = _read(root / "docs/LEDGER.md")
        archive_body = _archive_body(_ENTRY, _read(root / doc_archive.DEFAULT_LEDGER_ARCHIVE))
        assert archive_body.endswith(prior_body), "the archive forgot what it held"
        moved = archive_body[: len(archive_body) - len(prior_body)]
        assert live + moved == before

    def test_the_ledger_head_through_the_marker_is_untouched(self, tmp_path: Path) -> None:
        root = _repo_copy(tmp_path)
        before = _read(root / "docs/LEDGER.md")
        cut = before.find(doc_archive.LEDGER_MARKER) + len(doc_archive.LEDGER_MARKER)
        apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)
        assert _read(root / "docs/LEDGER.md")[:cut] == before[:cut]

    def test_applying_twice_moves_nothing_new(self, tmp_path: Path) -> None:
        """A second run must be a no-op in content, not merely non-destructive.

        Three of the four documents come back byte-identical. ``ROADMAP.md``
        does not, and the difference is pinned exactly rather than waved at:
        the planner inserts a blank line between the last kept section and the
        regenerated index, so the newline RUN at that one junction grows by one
        per run and nothing else changes. Filed as ROADMAP ``OPS-81``.
        """
        root = _repo_copy(tmp_path)
        apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)
        once = {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS}
        apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)
        twice = {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS}

        for path in apply_doc_split.WRITTEN_PATHS:
            if path == "ROADMAP.md":
                continue
            assert twice[path] == once[path], f"a second run changed {path}"

        head_once, _, tail_once = once["ROADMAP.md"].partition(_INDEX_PREFIX)
        head_twice, _, tail_twice = twice["ROADMAP.md"].partition(_INDEX_PREFIX)
        assert tail_twice == tail_once, "the regenerated index differed between runs"
        assert head_twice.rstrip("\n") == head_once.rstrip("\n")
        assert len(head_twice) - len(head_once) == 1

    def test_a_lossy_plan_writes_nothing_at_all(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _repo_copy(tmp_path)
        before = {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS}
        real = doc_archive.plan_roadmap_split

        def lossy(
            text: str, archive_path: str, existing_archive: str = ""
        ) -> doc_archive.RoadmapPlan:
            plan = real(text, archive_path, existing_archive=existing_archive)
            return doc_archive.RoadmapPlan(
                roadmap_text=plan.roadmap_text,
                archive_text=plan.archive_text[:-1],
                archive_header=plan.archive_header,
                kept=plan.kept,
                archived=plan.archived,
            )

        monkeypatch.setattr(doc_archive, "plan_roadmap_split", lossy)
        with pytest.raises(apply_doc_split.ApplyRefused):
            apply_doc_split.apply_split(root, keep_entries=doc_archive.DEFAULT_LEDGER_KEEP)
        assert {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS} == before


class TestCommandLine:
    """The CLI must not write unless it was asked to, in so many words."""

    def test_a_bare_run_reports_and_writes_nothing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = _repo_copy(tmp_path)
        before = {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS}
        code = apply_doc_split.main(["--repo-root", str(root)])
        assert code == 0
        assert {p: _read(root / p) for p in apply_doc_split.WRITTEN_PATHS} == before
        assert "nothing was written" in capsys.readouterr().out

    def test_the_apply_flag_writes(self, tmp_path: Path) -> None:
        """``--keep 1`` so the assertion is about the flag, not about the state.

        With the default keep count this test passes only while the live ledger
        holds more entries than the split leaves behind - which stops being
        true the moment a split is actually applied, and it was measured
        failing for exactly that reason. Asking for one kept entry guarantees
        something moves whatever state the real documents are in.
        """
        root = _repo_copy(tmp_path)
        before = _read(root / "docs/LEDGER.md")
        code = apply_doc_split.main(["--repo-root", str(root), "--keep", "1", "--apply"])
        assert code == 0
        assert _read(root / "docs/LEDGER.md") != before

    def test_an_unknown_flag_is_a_usage_error(self, tmp_path: Path) -> None:
        root = _repo_copy(tmp_path)
        with pytest.raises(SystemExit):
            apply_doc_split.main(["--repo-root", str(root), "--not-a-flag"])


class TestClaudeMdNamesTheApplyingStep:
    """OPS-80 criterion 4. The instruction must name the step that applies.

    Searched on a whitespace-collapsed copy on purpose: prose in this
    repository is hard-wrapped near 80 columns, so a line-oriented pattern is a
    claim about the file's line breaks rather than about its content.

    The blockquote markers come off BEFORE the collapse, and that is not
    cosmetic. The instruction being checked lives inside a ``>`` block, so a
    naive collapse turns "do not raise the\\n> number" into "do not raise the >
    number" and the sentence is unfindable - a false clean bill produced by the
    reader rather than by the file, which is this repository's recorded trap
    about a grep being a claim about your pattern.
    """

    def _collapsed(self) -> str:
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        stripped = [line.lstrip().lstrip(">").strip() for line in text.splitlines()]
        return " ".join(" ".join(stripped).split())

    def test_it_names_the_applier(self) -> None:
        assert "scripts/apply_doc_split.py" in self._collapsed()

    def test_it_still_forbids_raising_the_number(self) -> None:
        assert "do not raise the number" in self._collapsed()

    def test_it_does_not_send_a_cold_session_to_a_tool_that_writes_nothing(self) -> None:
        """The stale sentence named only the planner. Its exact shape is gone."""
        collapsed = self._collapsed()
        assert "RE-RUN `tools/doc_archive.py`; do not raise the number" not in collapsed
