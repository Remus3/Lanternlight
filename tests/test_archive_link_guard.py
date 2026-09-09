"""Tests for the roadmap-to-archive link guard - ROADMAP OPS-57 criterion 6.

WHY THIS EXISTS. ``ROADMAP.md`` is about to be split: its CLOSED and REFUTED
sections move verbatim into an archive document and the roadmap keeps a
one-line stub per archived item that links into that archive. Criterion 6 of
OPS-57 says a test must prove the entry point actually RESOLVES - "a file that
exists and is unreferenced is the invisible-work failure", and an archive
nobody is told about is that failure wearing a tidy filename. Asserting only
that the archive file exists would be precisely the vacuous guard this
repository keeps writing down.

THE CONTROLS, AND WHY EACH ONE IS HERE. Three of the classes below exist as a
matched set and none of them is redundant:

- :class:`TestPositiveControlEveryArchivedItemIsReachable` is the control that
  proves the guard can say GREEN at all. Without it, a reader that silently
  fell back to something permissive - an anchor regex that matched nothing, a
  heading scan that returned an empty list, an exception swallowed into "no
  findings" - would report green on the exact tree that motivated this item,
  and every other test here would still pass. A guard that only ever says
  "fine" is decoration.
- :class:`TestNegativeControlRemovedStubIsUnreachable` removes ONE stub from
  that same green pair and requires red, with the specific unreachable item
  NAMED in the finding. "Something is wrong" is not actionable by a cold
  session; the heading is.
- :class:`TestNegativeControlWrongAnchorIsDangling` keeps the stub but breaks
  its anchor by a single character. This is the failure that reads as coverage:
  the roadmap looks like it links to the archived item, a human skimming the
  stub list sees full coverage, and the link lands nowhere. It must be RED, and
  red as a DANGLING link rather than quietly counted as a stub that satisfies
  reachability.

THE DID-NOT-RUN ANSWER IS A THIRD ANSWER. Before the split happens the archive
file does not exist, and the guard must say so explicitly rather than return an
empty finding list that reads as a pass.
:class:`TestArchiveMissingIsDidNotRunNotAPass` pins that ``ran`` is false and
that ``format()`` says so out loud. Its sibling
:class:`TestArchiveMissingWhileRoadmapLinksToItIsAFailure` pins the case that
keeps did-not-run from becoming its own escape hatch: once the roadmap DOES
carry stub links, a missing archive is a dangling entry point and a hard
failure, not a shrug.

THE ANCHOR RULE IS TESTED AGAINST REAL HEADINGS. The fixture headings used
below are asserted at test time to be verbatim ``## `` headings somewhere in
the ROADMAP PAIR - ``ROADMAP.md`` together with ``docs/ROADMAP_ARCHIVE.md`` -
so this file cannot drift into testing anchor derivation against tidy invented
strings while the real document is full of periods, backticks, parentheses,
commas and hyphen runs. Expected anchors are hardcoded here rather
than computed with :func:`tools.archive_link_guard.anchor_for` - deriving the
expectation from the implementation under test would assert only that a
function equals itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import archive_link_guard  # noqa: E402

# Two headings copied verbatim out of this repository's roadmap. Both are
# asserted to still be present in the ROADMAP PAIR by
# TestAnchorRuleAgainstRealHeadings, so a rename surfaces as a test failure
# here rather than as a silently invented fixture. Both were live ROADMAP.md
# headings when they were copied and both are now in the archive, which is
# exactly why the subject of that control is the pair and not one file.
REAL_HEADING_PUNCTUATION = (
    "OPS-49. `CLAUDE.md` cited a git index mode as though it were a claim "
    "about execution - CLOSED 2026-09-07"
)
REAL_ANCHOR_PUNCTUATION = (
    "ops-49-claudemd-cited-a-git-index-mode-as-though-it-were-a-claim-"
    "about-execution---closed-2026-09-07"
)

REAL_HEADING_PARENS = (
    "OPS-17. `_dead_pid()` reopens the pid-reuse hole its own docstring "
    "warns about - CLOSED 2026-09-04"
)
REAL_ANCHOR_PARENS = (
    "ops-17-deadpid-reopens-the-pid-reuse-hole-its-own-docstring-"
    "warns-about---closed-2026-09-04"
)

# A second real-shaped archived item, used to build fixture pairs with more
# than one entry so "collect every problem" can be exercised.
SECOND_HEADING = "OPS-53. The watcher status reporter says the wrong tense - CLOSED 2026-09-08"
SECOND_ANCHOR = "ops-53-the-watcher-status-reporter-says-the-wrong-tense---closed-2026-09-08"

ARCHIVE_REL = "docs/ROADMAP_ARCHIVE.md"

#: The ROADMAP PAIR: the two documents that between them hold every roadmap
#: item, open or archived. Before OPS-57's split ran, that was ROADMAP.md
#: alone; the split moved the CLOSED and REFUTED sections into the archive
#: without changing their heading text, so the pair is the subject that was
#: conserved across the split and is the honest subject for a control whose
#: property is "this heading is real text from this repository".
ROADMAP_PAIR = ("ROADMAP.md", ARCHIVE_REL)


def _documents_containing(heading: str) -> list[str]:
    """Return which documents of :data:`ROADMAP_PAIR` carry ``heading``.

    Membership is decided with the guard's own
    :func:`tools.archive_link_guard.iter_headings`, so a fixture only counts
    when it is a real top-level ``## `` heading rather than a substring of some
    body paragraph or a line inside a fenced code block.

    A file of the pair that is not on disk contributes nothing rather than
    raising: the archive does not exist before the split, and the caller's
    assertion still fails - loudly and with both paths named - if the heading
    is then found nowhere.
    """
    found: list[str] = []
    for rel_path in ROADMAP_PAIR:
        path = REPO_ROOT / rel_path
        if not path.is_file():
            continue
        if heading in archive_link_guard.iter_headings(path.read_text(encoding="utf-8")):
            found.append(rel_path)
    return found


def _archive(*headings: str) -> str:
    """Build an archive document carrying one ``## `` section per heading."""
    parts = ["# Lanternlight roadmap archive", ""]
    for heading in headings:
        parts.extend([f"## {heading}", "", "Body text for this archived item.", ""])
    return "\n".join(parts)


def _stub(heading: str, anchor: str) -> str:
    """Build one roadmap stub line linking into the archive by ``anchor``."""
    return f"- [{heading}]({ARCHIVE_REL}#{anchor})"


def _roadmap(*stubs: str) -> str:
    """Build a roadmap carrying an archived-items stub list."""
    parts = [
        "# Lanternlight ROADMAP",
        "",
        "## OPS-99. Something still open",
        "",
        "Open work stays here in full.",
        "",
        "## Archived items",
        "",
        f"Closed and refuted items moved verbatim into [{ARCHIVE_REL}]({ARCHIVE_REL}).",
        "",
    ]
    parts.extend(stubs)
    parts.append("")
    return "\n".join(parts)


class TestAnchorRuleAgainstRealHeadings:
    """The anchor rule is exercised on headings that really exist today.

    A rule verified only against invented headings is a rule verified against
    the easy case. The real document's headings carry periods, backticks,
    parentheses, commas and runs of hyphens, and every one of those changes the
    derived anchor.
    """

    def test_fixture_headings_are_real_text_from_the_roadmap_pair(self) -> None:
        """Each fixture heading is a verbatim ``## `` heading in the PAIR.

        This is what makes the two anchor tests below claims about the real
        documents rather than about a convenient string.

        WHY THE PAIR AND NOT ONE FILE. The property worth preserving is "these
        fixture headings are REAL text from this repository, not invented".
        Both fixtures were live ``ROADMAP.md`` headings when they were copied
        in, and OPS-57's split then moved them verbatim into
        ``docs/ROADMAP_ARCHIVE.md`` because they are CLOSED. Pinning either
        single file makes the control a claim about WHICH SIDE an item sits on,
        which is a fact the splitter is designed to change - and the splitter
        is documented as the response to a size budget firing, so it will run
        again and move more headings. A control that must be hand-edited every
        time the split runs is a control that eventually gets edited carelessly
        to go green. The pair is what the pre-split roadmap was, and it is
        conserved by the split.

        WHAT THE PAIR COSTS, stated rather than hedged out loud: this control
        can no longer notice an item being moved between the two documents, so
        a heading wrongly moved to the archive while still open - or dragged
        back out of it - passes here. That is deliberate, and it is not
        unguarded: reachability BETWEEN the two documents is the whole subject
        of ``check_texts`` and of ``TestLiveRepoEntryPoint`` below. The one
        thing this control must still be able to say is ABSENT, which
        :meth:`test_a_heading_in_neither_document_is_reported_absent` pins.
        """
        for heading in (REAL_HEADING_PUNCTUATION, REAL_HEADING_PARENS):
            documents = _documents_containing(heading)
            assert documents, (
                f"fixture heading is in neither document of the roadmap pair "
                f"{ROADMAP_PAIR}, so it is no longer real text from this "
                f"repository: {heading!r}"
            )

    def test_a_heading_in_neither_document_is_reported_absent(self) -> None:
        """The membership check above must be ABLE to say no.

        A lookup that silently returned every heading - a scanner that matched
        too loosely, a read that fell back to an empty list and an assertion
        written the other way round - would make the control above green
        forever and let an invented fixture in. This pins the negative
        permanently, so nobody has to remember to re-run it by hand after the
        next split.
        """
        never_written = (
            "OPS-000. This heading is not in ROADMAP.md or the archive - "
            "NOT AN ITEM 1970-01-01"
        )
        assert _documents_containing(never_written) == []

    def test_periods_commas_and_backticks_are_dropped(self) -> None:
        """Lowercase, spaces to hyphens, then drop non-alphanumeric-or-hyphen."""
        assert (
            archive_link_guard.anchor_for(REAL_HEADING_PUNCTUATION)
            == REAL_ANCHOR_PUNCTUATION
        )

    def test_parentheses_and_underscores_are_dropped(self) -> None:
        """``_dead_pid()`` collapses to ``deadpid``.

        The underscore drop is a deliberate, documented divergence from
        GitHub's own slugger, which keeps underscores. It is pinned here so the
        divergence is a decision on the record rather than an accident nobody
        measured - see the module docstring of ``tools/archive_link_guard.py``.
        """
        assert archive_link_guard.anchor_for(REAL_HEADING_PARENS) == REAL_ANCHOR_PARENS

    def test_hyphen_runs_are_preserved_not_collapsed(self) -> None:
        """`` - `` becomes ``---``; collapsing it would break every real link."""
        assert "---closed-" in REAL_ANCHOR_PUNCTUATION
        assert archive_link_guard.anchor_for("A - B") == "a---b"


class TestPositiveControlEveryArchivedItemIsReachable:
    """GREEN control: a correct roadmap+archive pair reports no findings.

    Without this control the whole file could pass while the guard was
    incapable of saying anything but "fine" - an anchor regex that matched
    nothing, or a heading scan returning an empty list, would report green on
    the exact tree that motivated OPS-57. Every negative control below is only
    meaningful because this one exists.
    """

    def test_correct_pair_is_green(self) -> None:
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(
                _stub(REAL_HEADING_PUNCTUATION, REAL_ANCHOR_PUNCTUATION),
                _stub(SECOND_HEADING, SECOND_ANCHOR),
            ),
            archive_text=_archive(REAL_HEADING_PUNCTUATION, SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ran is True
        assert report.ok is True
        assert report.findings == ()

    def test_green_report_counts_what_it_actually_checked(self) -> None:
        """A green verdict states the sizes it saw, so "0 of 0" is visible."""
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(
                _stub(REAL_HEADING_PUNCTUATION, REAL_ANCHOR_PUNCTUATION),
                _stub(SECOND_HEADING, SECOND_ANCHOR),
            ),
            archive_text=_archive(REAL_HEADING_PUNCTUATION, SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        assert len(report.archive_headings) == 2
        assert len(report.stub_anchors) == 2
        assert "OK" in report.format()


class TestNegativeControlRemovedStubIsUnreachable:
    """RED control: an archived item with no stub is the exact failure."""

    def test_missing_stub_is_red(self) -> None:
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(REAL_HEADING_PUNCTUATION, REAL_ANCHOR_PUNCTUATION)),
            archive_text=_archive(REAL_HEADING_PUNCTUATION, SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ran is True
        assert report.ok is False

    def test_finding_names_the_specific_unreachable_item(self) -> None:
        """The heading itself is in the detail - "something is wrong" is not
        actionable by a cold session, and the guard exists for cold sessions."""
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(REAL_HEADING_PUNCTUATION, REAL_ANCHOR_PUNCTUATION)),
            archive_text=_archive(REAL_HEADING_PUNCTUATION, SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        kinds = [f.kind for f in report.findings]
        assert kinds == ["unreachable"]
        assert report.findings[0].heading == SECOND_HEADING
        assert SECOND_HEADING in report.findings[0].detail
        assert SECOND_HEADING in report.format()
        # The item that DOES have a stub is not dragged in with it.
        assert REAL_HEADING_PUNCTUATION not in report.findings[0].detail

    def test_every_unreachable_item_is_collected_not_just_the_first(self) -> None:
        """A scan that stopped at the first problem would hide the rest."""
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(),
            archive_text=_archive(REAL_HEADING_PUNCTUATION, SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        assert [f.kind for f in report.findings] == ["unreachable", "unreachable"]
        assert {f.heading for f in report.findings} == {
            REAL_HEADING_PUNCTUATION,
            SECOND_HEADING,
        }


class TestNegativeControlWrongAnchorIsDangling:
    """RED control: a stub whose anchor resolves to nothing reads as coverage.

    This is the subtler of the two failures. The stub line is present, a human
    skimming the archived-items list sees full coverage, and the link lands
    nowhere. It must be red - and red in BOTH directions: the dangling anchor
    is reported, and the archived item is still counted as unreachable rather
    than credited to a link that does not resolve.
    """

    def test_single_character_typo_is_red(self) -> None:
        typo = REAL_ANCHOR_PUNCTUATION.replace("ops-49", "ops-94")
        assert typo != REAL_ANCHOR_PUNCTUATION
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(REAL_HEADING_PUNCTUATION, typo)),
            archive_text=_archive(REAL_HEADING_PUNCTUATION),
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ok is False
        kinds = sorted(f.kind for f in report.findings)
        assert kinds == ["dangling", "unreachable"]
        dangling = next(f for f in report.findings if f.kind == "dangling")
        assert dangling.anchor == typo
        assert typo in report.format()

    def test_anchor_derived_by_a_different_rule_is_red(self) -> None:
        """An anchor built by a plausible-but-different rule must not pass.

        Here the writer collapsed the `` - `` hyphen run to a single hyphen,
        which is what several other slug conventions do. It is wrong for this
        document and the guard must say so rather than fuzzy-match its way to
        green.
        """
        other_rule = REAL_ANCHOR_PUNCTUATION.replace("---closed-", "-closed-")
        assert other_rule != REAL_ANCHOR_PUNCTUATION
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(REAL_HEADING_PUNCTUATION, other_rule)),
            archive_text=_archive(REAL_HEADING_PUNCTUATION),
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ok is False
        assert any(f.kind == "dangling" and f.anchor == other_rule for f in report.findings)


class TestArchiveMissingIsDidNotRunNotAPass:
    """Before the split, the guard must say DID NOT RUN, never OK."""

    def test_missing_archive_reports_did_not_run(self) -> None:
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(),
            archive_text=None,
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ran is False
        assert report.ok is False
        assert "DID NOT RUN" in report.format()
        assert "OK" not in report.format()

    def test_did_not_run_is_distinguishable_from_a_clean_pass(self) -> None:
        """The two answers differ on ``ran``, not only on prose.

        A caller that only looked at ``findings`` would read both as "nothing
        wrong", which is the conflation this test exists to prevent.
        """
        not_run = archive_link_guard.check_texts(
            roadmap_text=_roadmap(),
            archive_text=None,
            archive_rel_path=ARCHIVE_REL,
        )
        clean = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(SECOND_HEADING, SECOND_ANCHOR)),
            archive_text=_archive(SECOND_HEADING),
            archive_rel_path=ARCHIVE_REL,
        )
        assert not_run.findings == ()
        assert clean.findings == ()
        assert (not_run.ran, not_run.ok) != (clean.ran, clean.ok)


class TestArchiveMissingWhileRoadmapLinksToItIsAFailure:
    """DID-NOT-RUN must not become an escape hatch once stubs exist."""

    def test_stub_without_an_archive_file_is_red(self) -> None:
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(SECOND_HEADING, SECOND_ANCHOR)),
            archive_text=None,
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ran is True
        assert report.ok is False
        assert [f.kind for f in report.findings] == ["archive_missing"]
        assert ARCHIVE_REL in report.findings[0].detail


class TestDuplicateArchiveAnchorsAreAmbiguous:
    """Two archive headings that slug to one anchor make reachability a lie.

    One stub would appear to satisfy both, so the second item is unreachable
    while every count says otherwise.
    """

    def test_duplicate_anchor_is_red(self) -> None:
        # These two headings differ only in punctuation the anchor rule drops.
        a = "OPS-70. A thing, done - CLOSED 2026-09-08"
        b = "OPS-70. A thing done - CLOSED 2026-09-08"
        anchor = "ops-70-a-thing-done---closed-2026-09-08"
        report = archive_link_guard.check_texts(
            roadmap_text=_roadmap(_stub(a, anchor)),
            archive_text=_archive(a, b),
            archive_rel_path=ARCHIVE_REL,
        )
        assert report.ok is False
        assert any(f.kind == "ambiguous" for f in report.findings)


class TestHeadingScanIgnoresFencedCode:
    """A ``## `` line inside a fence is a shell comment, not a heading.

    ROADMAP.md and the archive both carry fenced blocks full of commands, and
    counting one of those as an archived item would produce a permanent, unfixable
    unreachable finding that trains readers to ignore the guard.
    """

    def test_fenced_hashes_are_not_headings(self) -> None:
        text = "\n".join(
            [
                "# Doc",
                "",
                "```sh",
                "## not a heading",
                "```",
                "",
                f"## {SECOND_HEADING}",
            ]
        )
        assert archive_link_guard.iter_headings(text) == [SECOND_HEADING]

    def test_deeper_headings_are_not_archived_items(self) -> None:
        """Only ``## `` is an archived item; ``### Acceptance`` is a sub-part."""
        text = f"## {SECOND_HEADING}\n\n### Acceptance\n\ntext\n"
        assert archive_link_guard.iter_headings(text) == [SECOND_HEADING]


class TestStubLinkScan:
    """Only links that point INTO the archive with a fragment are stubs."""

    def test_links_to_other_documents_are_ignored(self) -> None:
        text = "See [the ledger](docs/LEDGER.md#ll-0170) and [adr](docs/adr/README.md)."
        assert archive_link_guard.stub_anchors(text, ARCHIVE_REL) == []

    def test_fragmentless_archive_link_is_not_a_stub(self) -> None:
        """A link to the archive as a whole is a pointer, not an entry point."""
        text = f"Closed items live in [the archive]({ARCHIVE_REL})."
        assert archive_link_guard.stub_anchors(text, ARCHIVE_REL) == []

    def test_leading_dot_slash_still_matches(self) -> None:
        text = f"[x](./{ARCHIVE_REL}#{SECOND_ANCHOR})"
        assert archive_link_guard.stub_anchors(text, ARCHIVE_REL) == [SECOND_ANCHOR]


class TestLiveRepoEntryPoint:
    """``main()`` behaves sanely against the real tree, split or not."""

    def test_check_repo_returns_a_report_either_way(self) -> None:
        report = archive_link_guard.check_repo()
        assert isinstance(report, archive_link_guard.Report)
        # Whatever the state of the tree, the report must be self-describing:
        # a not-ran report says so, and a ran report never claims OK while
        # carrying findings.
        if report.ran:
            assert report.ok is (report.findings == ())
        else:
            assert "DID NOT RUN" in report.format()

    def test_main_exit_code_matches_the_verdict(self) -> None:
        # An EXPLICIT empty argument list, not main(). Since OPS-64 the guard
        # reads sys.argv when argv is None, and under a test runner sys.argv is
        # the runner's own - which is now refused rather than ignored, and would
        # make this test measure argument handling instead of the verdict. The
        # None-means-sys.argv contract has its own test in
        # TestArgvIsRefusedOrReal, with sys.argv patched so the argv under test
        # is a known one.
        report = archive_link_guard.check_repo()
        expected = 0 if (not report.ran or report.ok) else 1
        assert archive_link_guard.main([]) == expected


class TestArgvIsRefusedOrReal:
    """ROADMAP ``OPS-64``: an argument must change the check or be refused.

    WHY THIS CLASS EXISTS. Until OPS-64 was closed, ``main()`` took no
    parameters and read ``sys.argv`` not at all, so a caller who passed a flag
    naming a scratch file got a verdict about the REAL documents and no
    indication that the flag had gone nowhere. The wrap's own refutation pass
    hit exactly that: it tried to break the guard by pointing it at scratch
    files, and the guard printed an identical green line. A true answer to a
    question nobody asked is worse than an error, because an error is visible.

    THE TWO HALVES ARE TESTED SEPARATELY BECAUSE EITHER CAN REGRESS ALONE.
    An unknown argument must be REFUSED with a non-zero exit and a message
    naming it, and the options that ARE understood must be REAL - passing them
    must change which documents are read. The second half is the one an exit
    code cannot prove, so every test of it asserts something that could only
    have come from the scratch pair: the scratch pair carries two archived
    headings where the live archive carries dozens, and the scratch heading
    text appears nowhere in this repository's real documents.
    """

    #: An argument no version of this guard has ever understood. Spelled to be
    #: unmistakable in an assertion failure, and deliberately not a near-miss
    #: of a real option - the near-miss case has its own test below.
    BOGUS = "--pretend-this-does-something"

    def _scratch_pair(
        self,
        tmp_path: Path,
        roadmap_rel: str,
        archive_rel: str,
        stub_anchors: tuple[str, ...],
        headings: tuple[str, ...],
    ) -> None:
        """Write a roadmap and an archive under ``tmp_path``.

        ``stub_anchors`` are written as stub links to ``archive_rel`` and
        ``headings`` become the archive's ``## `` sections. They are passed
        separately rather than derived from each other so a caller can build a
        pair that is deliberately INCONSISTENT - a heading with no stub, say -
        which is what the negative case here needs.
        """
        roadmap_path = tmp_path / roadmap_rel
        archive_path = tmp_path / archive_rel
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        stubs = "\n".join(
            f"- [archived item]({archive_rel}#{anchor})" for anchor in stub_anchors
        )
        roadmap_path.write_text(
            "# Scratch roadmap\n\n## Archived items\n\n" + stubs + "\n",
            encoding="utf-8",
        )
        sections = "\n".join(f"## {heading}\n\nBody.\n" for heading in headings)
        archive_path.write_text("# Scratch archive\n\n" + sections, encoding="utf-8")

    def test_unknown_flag_is_refused_rather_than_ignored(self) -> None:
        """Criterion 1: a made-up flag exits non-zero, and not with 1.

        2 rather than 1 on purpose: 1 means the check ran and found a real
        reachability defect in the documents, and a usage error is not that. A
        caller that cannot tell the two apart learns nothing from either.
        """
        assert archive_link_guard.main([self.BOGUS]) == 2

    def test_refusal_names_the_argument(self, capsys) -> None:
        """Criterion 1: the message says WHICH argument was refused.

        "bad usage" sends the reader back to the source; the offending token
        sends them to their own command line.
        """
        assert archive_link_guard.main([self.BOGUS]) == 2
        assert self.BOGUS in capsys.readouterr().err

    def test_a_positional_argument_is_refused_too(self) -> None:
        """A bare path is the most likely wrong invocation, so it must fail.

        ``python tools/archive_link_guard.py ROADMAP.md`` looks like it scopes
        the check to one document. This guard takes no positional argument, so
        that invocation must be an error rather than a whole-tree verdict
        wearing the appearance of a scoped one.
        """
        assert archive_link_guard.main(["ROADMAP.md"]) == 2

    def test_an_abbreviated_option_is_refused(self) -> None:
        """Prefix abbreviation is switched OFF, so a truncated flag fails.

        ``argparse`` accepts any unambiguous prefix by default, which means
        ``--arch`` would silently become ``--archive``. That is a second way for
        a caller to get a verdict about something other than what they typed, so
        :func:`tools.archive_link_guard.build_parser` disables it and this test
        pins the decision. The token is deliberately a prefix of a REAL option -
        the plain unknown-flag case above would pass even with abbreviation on.
        """
        assert archive_link_guard.main(["--arch"]) == 2

    def test_help_is_not_a_refusal(self) -> None:
        """``--help`` is understood, so it exits 0 rather than 2.

        Folding help into the usage-error path would make the one invocation
        that asks what the options ARE report failure.
        """
        assert archive_link_guard.main(["--help"]) == 0

    def test_empty_argv_runs_the_live_check(self) -> None:
        """No arguments still means the real tree, exactly as before OPS-64."""
        report = archive_link_guard.check_repo()
        expected = 0 if (not report.ran or report.ok) else 1
        assert archive_link_guard.main([]) == expected

    def test_none_argv_reads_the_process_arguments(self, monkeypatch) -> None:
        """``main(None)`` means "read ``sys.argv``", proved by patching it.

        This is the property that makes the command line work at all, and it is
        invisible in-process because a test runner's own ``sys.argv`` is not the
        guard's. Both directions are pinned: a patched argv carrying a bogus
        flag must be REFUSED, and a patched argv carrying nothing must run the
        live check. Without the second half an implementation that always
        returned 2 would pass the first.
        """
        monkeypatch.setattr(sys, "argv", ["archive_link_guard.py", self.BOGUS])
        assert archive_link_guard.main() == 2

        report = archive_link_guard.check_repo()
        expected = 0 if (not report.ran or report.ok) else 1
        monkeypatch.setattr(sys, "argv", ["archive_link_guard.py"])
        assert archive_link_guard.main() == expected

    def test_repo_root_option_reads_the_scratch_tree(self, tmp_path, capsys) -> None:
        """Criterion 2: ``--repo-root`` changes which tree is read.

        The scratch pair is consistent, so the verdict is green - and the counts
        in the report are the SCRATCH pair's two headings. The live archive
        carries dozens, so a report of "2 archived heading(s)" could not have
        been produced by reading the real documents. That count, not the exit
        code, is what makes this test able to fail.
        """
        self._scratch_pair(
            tmp_path,
            "ROADMAP.md",
            ARCHIVE_REL,
            stub_anchors=("scratch-one", "scratch-two"),
            headings=("scratch one", "scratch two"),
        )
        code = archive_link_guard.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out
        assert code == 0, out
        assert "OK (2 archived heading(s), 2 stub link(s))" in out

    def test_roadmap_and_archive_options_read_those_documents(
        self, tmp_path, capsys
    ) -> None:
        """Criterion 2: ``--roadmap`` and ``--archive`` change which FILES are read.

        Named differently from the defaults on purpose. If either option were
        accepted and ignored, the guard would look for ``ROADMAP.md`` and
        ``docs/ROADMAP_ARCHIVE.md`` under the scratch root, find neither, and
        report DID NOT RUN - so this test fails loudly instead of passing on a
        coincidence.
        """
        self._scratch_pair(
            tmp_path,
            "scratch_roadmap.md",
            "scratch_archive.md",
            stub_anchors=("scratch-one", "scratch-two"),
            headings=("scratch one", "scratch two"),
        )
        code = archive_link_guard.main(
            [
                "--repo-root",
                str(tmp_path),
                "--roadmap",
                "scratch_roadmap.md",
                "--archive",
                "scratch_archive.md",
            ]
        )
        out = capsys.readouterr().out
        assert code == 0, out
        assert "OK (2 archived heading(s), 2 stub link(s))" in out

    def test_a_broken_scratch_pair_is_red_and_names_the_scratch_item(
        self, tmp_path, capsys
    ) -> None:
        """Criterion 2, the half an exit code cannot prove.

        The scratch archive holds a heading with no stub, so the verdict must be
        RED and the finding must NAME that heading. The heading text exists
        nowhere in this repository's real documents, so its presence in the
        output is positive evidence about which archive was read - which an exit
        code of 1 alone would not be, since the live tree could be red too.
        """
        self._scratch_pair(
            tmp_path,
            "ROADMAP.md",
            ARCHIVE_REL,
            stub_anchors=("scratch-one",),
            headings=("scratch one", "scratch two only in the scratch archive"),
        )
        code = archive_link_guard.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out
        assert code == 1, out
        assert "scratch two only in the scratch archive" in out

    def test_a_missing_scratch_archive_is_did_not_run(self, tmp_path, capsys) -> None:
        """The archive option is read for EXISTENCE as well as for content.

        A roadmap with no stub links and no archive on disk is the pre-split
        state, which is DID NOT RUN rather than a pass. Pointing the options at
        a scratch tree in that state must reproduce it - if ``--repo-root`` were
        ignored the live tree would answer OK instead.
        """
        (tmp_path / "ROADMAP.md").write_text(
            "# Scratch roadmap\n\nNo stub links at all.\n", encoding="utf-8"
        )
        assert archive_link_guard.main(["--repo-root", str(tmp_path)]) == 0
        assert "DID NOT RUN" in capsys.readouterr().out

    def test_a_finding_names_the_roadmap_that_was_actually_read(
        self, tmp_path, capsys
    ) -> None:
        """A finding must call the roadmap by the name that was read.

        The findings used to interpolate the module-level default
        ``ROADMAP.md`` even when another document had been read, which is the
        OPS-64 defect moved down one level: the verdict is true, and the
        sentence a reader acts on points at the wrong file. Proved by reading a
        scratch roadmap under a different name and requiring that name, and only
        that name, in the finding text.
        """
        self._scratch_pair(
            tmp_path,
            "scratch_roadmap.md",
            "scratch_archive.md",
            stub_anchors=(),
            headings=("scratch one",),
        )
        code = archive_link_guard.main(
            [
                "--repo-root",
                str(tmp_path),
                "--roadmap",
                "scratch_roadmap.md",
                "--archive",
                "scratch_archive.md",
            ]
        )
        out = capsys.readouterr().out
        assert code == 1, out
        assert "no stub in scratch_roadmap.md" in out
        assert "no stub in ROADMAP.md" not in out

    def test_the_verdict_says_which_documents_it_read(self, tmp_path, capsys) -> None:
        """A verdict must carry its own scope, so it cannot answer for elsewhere.

        This is the OPS-64 defect stated positively. The refutation pass was
        misled by a green line that named nothing, so every run now prints the
        root, the roadmap and the archive it actually read. Asserted against a
        scratch tree, whose path cannot appear unless the flag was honoured.
        """
        self._scratch_pair(
            tmp_path,
            "ROADMAP.md",
            ARCHIVE_REL,
            stub_anchors=("scratch-one",),
            headings=("scratch one",),
        )
        archive_link_guard.main(["--repo-root", str(tmp_path)])
        out = capsys.readouterr().out
        assert str(tmp_path) in out
        assert "ROADMAP.md" in out
        assert ARCHIVE_REL in out
