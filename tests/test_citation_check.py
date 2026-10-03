"""Citations in the continuity documents must resolve - ``OPS-113`` citation half.

The four acceptance points this module pins, quoted by number from the item:

(1) SHA CITES are extracted from ``ROADMAP.md``, ``docs/LEDGER.md`` and both
    archives - a 7-to-40 character lowercase hex token holding at least one
    letter ``a-f`` AND at least one digit - and every one that does not resolve
    as a commit is reported. The exact extraction rule, including what is
    deliberately NOT a cite, is in ``tools/citation_check.py``'s docstring.
(2) Unresolvable shas are named in a TRACKED allowlist with a reason, the
    allowlist may only SHRINK, and an unresolvable sha not in it is red. The
    shrink rule is enforced against :data:`PINNED_ALLOWLIST_KEYS` below, not
    against git history - see that constant's comment.
(3) ``path:line`` cites whose path exists are range-checked; a line past end of
    file is red. Whether an in-range line still says what the cite meant is NOT
    decided here, and a green run does not mean every cite is correct.
(4) The checker runs in the suite (this file) and in ``python -m ops.preflight``.

Logic tests use synthetic text and either an injected resolver or a throwaway
git repository under ``tmp_path``. One real-tree test proves the four live
documents are clean modulo the allowlist, and one plants a dead sha into a COPY
of a real document to prove that test can go red.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import _toolguard
import pytest

from ops import preflight
from tools import citation_check as cc

REPO_ROOT = Path(__file__).resolve().parents[1]


# THE ALLOWLIST MAY ONLY SHRINK - enforced here, with no history assumption.
#
# Every key in tools/citation_allowlist.txt must be in this set. Removing a key
# from the allowlist (and, optionally, from here) is always fine. EDITING THIS
# SET TO ADMIT A NEW ENTRY IS THE FORBIDDEN MOVE unless a docs/LEDGER.md entry
# in the same change records which cite it covers and why the extraction rule
# in tools/citation_check.py could not be fixed instead. The set lives in a
# test, not beside the allowlist, so growth is a visible diff to a guard that a
# reviewer reads, rather than one more row in a data file.
#
# This replaced a comparison with `git show HEAD:` (refuted 2026-10-03): it
# skipped while the allowlist was untracked or only staged, and once committed
# it compared the file with itself, so a new dead sha added to the allowlist
# together with a cite of it went green. A fresh clone has neither problem
# with a pinned set, and neither does a shallow one.
#
# Pinned 2026-10-03, OPS-113. The four pure-digit keys (4718293, 5899729,
# 6074631, 7661391) arrived with the pure-digit commit-context rule in the same
# change; they were dead cites the letter+digit rule could not see.
PINNED_ALLOWLIST_KEYS: frozenset[str] = frozenset(
    {
        "060d48d",
        "0996f1b6",
        "0d919c0",
        "0f7bf67",
        "104c316",
        "21f1c94",
        "290cbf80",
        "2c0b7a5",
        "2e56714",
        "308d69c",
        "311cef8",
        "38fda61",
        "3b5c3fb",
        "434818c",
        "43693b3",
        "4718293",
        "4ccff35",
        "52ac836",
        "548e5b6",
        "5725c03",
        "5899729",
        "5bc3347",
        "5f545b7",
        "6074631",
        "60cf878",
        "66bad3f",
        "6ad1531e2",
        "6de0420",
        "6e3c1c752",
        "73423fa",
        "7661391",
        "7fcf640",
        "814b1ea",
        "81d3237",
        "899f6eb9",
        "8bb1178",
        "8c5eaee",
        "950915d",
        "9879c60",
        "98d2cac",
        "a3a8d9d",
        "a51c608",
        "a9317e03733da7f54b5da0eaa8edcb2697495cf5",
        "ac7fd5e",
        "ad0aa0b",
        "ad2209a",
        "af70a73",
        "af7fc49",
        "b153d41",
        "b4d4888",
        "b98cf91",
        "bc2aad7",
        "bfda016",
        "c9a0f76",
        "cc47938",
        "ce5ccc7",
        "cf3327b",
        "d029669",
        "d35eac2",
        "d638be2",
        "d7b96ce",
        "d8220fe4a54dd208",
        "da35f8b1",
        "e23f9fd",
        "e2fe3e2",
        "e806747",
        "ec3946d",
        "edf5698",
        "f04d394",
        "f9bf1d9",
        "fe877d3",
        "ff0bee2",
    }
)


def _unpinned(keys) -> list[str]:
    return sorted(set(keys) - PINNED_ALLOWLIST_KEYS)


def _never(tokens):
    return set()


def _always(tokens):
    return set(tokens)


# ---------------------------------------------------------------- extraction


class TestShaExtraction:
    def _toks(self, text: str) -> list[str]:
        return [t for _, t in cc.extract_shas(text)]

    def test_letter_and_digit_are_both_required(self) -> None:
        # Pure-digit runs in ROADMAP.md are game ids and buildids, measured.
        assert self._toks("id `6130017` and `abcdefa` and `abc1234`") == ["abc1234"]

    def test_length_bounds_are_seven_to_forty(self) -> None:
        six = "abc123"
        seven = "abc1234"
        forty = "a" * 39 + "1"
        forty_one = "a" * 40 + "1"
        sixty_four = ("0f6e03b4" * 8)
        text = f"{six} {seven} {forty} {forty_one} {sixty_four}"
        assert self._toks(text) == [seven, forty]

    def test_unbackticked_cites_are_extracted(self) -> None:
        text = "HEAD e2ffe31 and commit 0bff3f8, and at `dfe7c63`."
        assert self._toks(text) == ["e2ffe31", "0bff3f8", "dfe7c63"]

    def test_a_range_contributes_both_ends(self) -> None:
        assert self._toks("git diff 21f1c94..fe877d3 -- x") == ["21f1c94", "fe877d3"]

    def test_hex_run_inside_a_longer_word_is_not_a_cite(self) -> None:
        text = "xabc1234 abc1234z abc_1234ab LL-FYI-fc22e86eebe9-LL 0xdeadbee1"
        assert self._toks(text) == []

    def test_uppercase_hex_is_not_a_cite(self) -> None:
        assert self._toks("ABC1234 Abc1234") == []

    def test_cross_repository_reference_is_not_a_cite(self) -> None:
        # GitHub's own cross-repo syntax, Owner/Repo@sha. The documented way to
        # cite a SIBLING's commit without it being read as ours.
        assert self._toks("Remus3/Amberstone@6ad1531e2 landed") == []

    def test_truncated_digest_marked_with_an_ellipsis_is_not_a_cite(self) -> None:
        assert self._toks("sha `296547c5...` and d642ee54...601455") == []

    def test_digest_word_immediately_before_excludes(self) -> None:
        text = (
            "sha256 1c44235c, digest `abd350bf`, git blob d81fb50, "
            "tree object 802027e, bytes `61895d00`, prefix 9648bec2ef"
        )
        assert self._toks(text) == []

    def test_digest_word_further_back_does_not_exclude(self) -> None:
        # Only the IMMEDIATELY preceding word counts, so a byte count earlier in
        # a sentence cannot hide a real commit cite.
        assert self._toks("150,904 bytes at commit abc1234") == ["abc1234"]

    # Pure-digit tokens: only in COMMIT CONTEXT. A bare 7-digit run is far more
    # often a game item id (3030403) or a Steam buildid (24813185).

    def test_pure_digit_without_commit_context_is_not_a_cite(self) -> None:
        text = "weapon `3030403`, buildid 24813185, int32 6130017 at 22:53:30"
        assert self._toks(text) == []

    def test_pure_digit_after_a_commit_word_is_a_cite(self) -> None:
        assert self._toks("before commit `5899729` and is stale") == ["5899729"]
        assert self._toks("- commit 6074631 adds 835 lines") == ["6074631"]
        assert self._toks("the COMMITTED tree at 6074631 verified") == ["6074631"]
        assert self._toks("from a worktree at 7661391^, got") == ["7661391"]
        assert self._toks("sha 1234567 and HEAD 7654321") == ["1234567", "7654321"]

    def test_a_commit_word_more_than_three_words_back_does_not_count(self) -> None:
        assert self._toks("commit was made long before 1234567") == []

    def test_pure_digit_beside_a_letter_sha_in_a_list_is_a_cite(self) -> None:
        assert self._toks("produced 9380317, f12a1b9, 7971473 and 06d113c") == [
            "9380317", "f12a1b9", "7971473", "06d113c"
        ]
        assert self._toks("with `HEAD` moving `434818c -> 4718293`.") == [
            "434818c", "4718293"
        ]
        assert self._toks("(8442072 to 1978cfc) is") == ["8442072", "1978cfc"]
        assert self._toks("git diff 1234567..abc1234") == ["1234567", "abc1234"]

    def test_a_digest_neighbour_does_not_pull_a_pure_digit_in(self) -> None:
        # `61895d00` is excluded as a digest, so it is not a sha to sit beside.
        assert self._toks("int32 `6130017`, bytes `61895d00`") == []

    def test_a_neighbour_across_other_words_does_not_count(self) -> None:
        assert self._toks("item 3030403 dropped at abc1234") == ["abc1234"]

    def test_line_numbers_are_one_based(self) -> None:
        assert cc.extract_shas("one\ntwo abc1234\n") == [(2, "abc1234")]


class TestLineCiteExtraction:
    def test_plain_and_backticked_and_linked(self) -> None:
        text = "see tools/x.py:12, `ops/y.py:3` and [z](docs/Z.md:40)"
        assert cc.extract_line_cites(text) == [
            (1, "tools/x.py", 12),
            (1, "ops/y.py", 3),
            (1, "docs/Z.md", 40),
        ]

    def test_github_anchor_form(self) -> None:
        assert cc.extract_line_cites("a/b.py#L77") == [(1, "a/b.py", 77)]

    def test_a_range_is_checked_at_its_far_end(self) -> None:
        assert cc.extract_line_cites("watch.py:1038-1039") == [(1, "watch.py", 1039)]

    def test_line_and_column_takes_the_line(self) -> None:
        assert cc.extract_line_cites("docs/E.md:97:29") == [(1, "docs/E.md", 97)]

    def test_a_dotted_name_with_no_line_is_not_a_cite(self) -> None:
        assert cc.extract_line_cites("tools/x.py and ROADMAP.md: done") == []

    def test_a_leading_dot_directory_is_kept(self) -> None:
        assert cc.extract_line_cites(".claude/commands/loop.md:48") == [
            (1, ".claude/commands/loop.md", 48)
        ]


# ---------------------------------------------------------------- allowlist


class TestAllowlistParsing:
    def test_a_well_formed_entry_parses(self) -> None:
        entries = cc.parse_allowlist(
            "# comment\n\nabc1234 pre-rewrite cited in LL-0100, rewritten away\n"
        )
        assert entries == {
            "abc1234": cc.AllowEntry("abc1234", "pre-rewrite", "cited in LL-0100, rewritten away")
        }

    def test_an_entry_without_a_why_is_refused(self) -> None:
        with pytest.raises(ValueError, match="why"):
            cc.parse_allowlist("abc1234 pre-rewrite\n")

    def test_an_unknown_reason_is_refused(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            cc.parse_allowlist("abc1234 because it is old\n")

    def test_a_duplicate_is_refused(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            cc.parse_allowlist("abc1234 pre-rewrite a\nabc1234 not-a-commit b\n")

    def test_out_of_range_entries_key_on_path_and_line(self) -> None:
        entries = cc.parse_allowlist("tools/x.py:900 out-of-range quoted historically\n")
        assert entries["tools/x.py:900"].reason == "out-of-range"

    def test_a_sha_with_a_line_reason_is_refused(self) -> None:
        with pytest.raises(ValueError, match="reason"):
            cc.parse_allowlist("abc1234 out-of-range nonsense\n")


# ---------------------------------------------------------------- the check


def _tree(tmp_path: Path) -> Path:
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "x.py").write_bytes(b"a\nb\nc\n")
    return tmp_path


class TestCheck:
    def test_an_unresolvable_sha_not_allowlisted_is_red(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "at commit abc1234\n"}, {}, _never, _tree(tmp_path))
        assert not report.ok
        assert [(c.doc, c.line, c.token) for c in report.dead_shas] == [
            ("ROADMAP.md", 1, "abc1234")
        ]

    def test_a_resolvable_sha_is_green(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "at commit abc1234\n"}, {}, _always, _tree(tmp_path))
        assert report.ok, report.format()

    def test_an_allowlisted_dead_sha_is_named_not_hidden(self, tmp_path: Path) -> None:
        allow = cc.parse_allowlist("abc1234 pre-rewrite old\n")
        report = cc.check({"ROADMAP.md": "at abc1234\n"}, allow, _never, _tree(tmp_path))
        assert report.ok, report.format()
        assert [c.token for c in report.allowlisted] == ["abc1234"]
        assert "abc1234" in report.format()

    def test_an_allowlist_entry_that_now_resolves_is_red(self, tmp_path: Path) -> None:
        allow = cc.parse_allowlist("abc1234 pre-rewrite old\n")
        report = cc.check({"ROADMAP.md": "at abc1234\n"}, allow, _always, _tree(tmp_path))
        assert not report.ok
        assert report.stale_resolvable == ["abc1234"]

    def test_an_allowlist_entry_nobody_cites_is_red(self, tmp_path: Path) -> None:
        allow = cc.parse_allowlist("abc1234 pre-rewrite old\n")
        report = cc.check({"ROADMAP.md": "nothing\n"}, allow, _never, _tree(tmp_path))
        assert not report.ok
        assert report.stale_unused == ["abc1234"]

    def test_a_line_past_end_of_file_is_red(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "see tools/x.py:4\n"}, {}, _never, _tree(tmp_path))
        assert not report.ok
        assert [(c.path, c.cited_line, c.file_lines) for c in report.out_of_range] == [
            ("tools/x.py", 4, 3)
        ]

    def test_the_last_line_is_in_range(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "see tools/x.py:3\n"}, {}, _never, _tree(tmp_path))
        assert report.ok, report.format()

    def test_a_path_that_does_not_exist_is_skipped_and_counted(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "see m.py:999\n"}, {}, _never, _tree(tmp_path))
        assert report.ok
        assert report.line_cites_skipped == 1

    def test_an_allowlisted_out_of_range_cite_is_green_and_unused_is_red(
        self, tmp_path: Path
    ) -> None:
        allow = cc.parse_allowlist("tools/x.py:4 out-of-range historic\n")
        hit = cc.check({"ROADMAP.md": "tools/x.py:4\n"}, allow, _never, _tree(tmp_path))
        assert hit.ok, hit.format()
        miss = cc.check({"ROADMAP.md": "nothing\n"}, allow, _never, _tree(tmp_path))
        assert miss.stale_unused == ["tools/x.py:4"]

    def test_line_zero_is_out_of_range(self, tmp_path: Path) -> None:
        report = cc.check({"ROADMAP.md": "tools/x.py:0\n"}, {}, _never, _tree(tmp_path))
        assert not report.ok


# ---------------------------------------------------------------- git resolver


class TestGitResolver:
    def test_resolves_commits_only(self, tmp_path: Path) -> None:
        git = _toolguard.require("git")

        def run(*args: str) -> str:
            return subprocess.run(
                [git, *args], cwd=tmp_path, capture_output=True, text=True, check=True
            ).stdout.strip()

        run("init", "-q")
        (tmp_path / "f.txt").write_text("x")
        run("add", "f.txt")
        run("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "m")
        commit = run("rev-parse", "HEAD")
        blob = run("rev-parse", "HEAD:f.txt")
        bogus = "abc1234"
        assert not commit.startswith(bogus)
        resolved = cc.git_resolver(tmp_path)([commit, commit[:7], blob, bogus])
        assert resolved == {commit, commit[:7]}

    def test_an_empty_query_does_not_call_git(self, tmp_path: Path) -> None:
        assert cc.git_resolver(tmp_path / "nowhere")([]) == set()


# ---------------------------------------------------------------- real tree


def _real_texts() -> dict[str, str]:
    return {d: (REPO_ROOT / d).read_text(encoding="utf-8") for d in cc.DOCS}


class TestRealTree:
    def test_the_four_documents_are_clean_modulo_the_allowlist(self) -> None:
        _toolguard.require("git")
        report = cc.check_repo(REPO_ROOT)
        assert report.ok, report.format()
        # Non-vacuity of the extractor on the real corpus: the archives are
        # known to carry dozens of pre-rewrite cites, so a run that extracted
        # nothing has broken the extractor, not cleaned the documents.
        assert report.sha_cites >= 100, report.format()
        assert len(report.allowlisted) >= 29, report.format()

    def test_a_planted_dead_sha_in_a_copy_of_a_real_document_is_red(self) -> None:
        _toolguard.require("git")
        resolver = cc.git_resolver(REPO_ROOT)
        planted = "abc1234"
        assert resolver([planted]) == set(), "the planted sha must not resolve"
        texts = _real_texts()
        texts["ROADMAP.md"] += f"\nFixed at commit {planted}.\n"
        allow = cc.load_allowlist(REPO_ROOT / cc.ALLOWLIST)
        report = cc.check(texts, allow, resolver, REPO_ROOT)
        assert not report.ok
        assert [c.token for c in report.dead_shas] == [planted]

    def test_the_pre_rewrite_pure_digit_cites_are_extracted(self) -> None:
        # The refuted gap: three dead pre-rewrite cites that the letter+digit
        # rule could not see. They must be extracted, and then be allowlisted.
        text = (REPO_ROOT / "docs" / "LEDGER_ARCHIVE.md").read_text(encoding="utf-8")
        found = {t for _, t in cc.extract_shas(text)}
        assert {"6074631", "5899729", "7661391"} <= found

    def test_the_allowlist_only_shrinks(self) -> None:
        # Against the pinned set above - no git, no history, works on a fresh
        # clone. Adding a row is how a NEW dead cite would be muted, which
        # acceptance point (2) forbids.
        current = cc.load_allowlist(REPO_ROOT / cc.ALLOWLIST)
        assert _unpinned(current) == []

    def test_a_grown_allowlist_is_refused_by_the_pin(self) -> None:
        # The refuter's exact attack, replayed on a COPY: add a dead sha to the
        # allowlist AND cite it. check() alone is green - that is the hole -
        # and the pin is what turns it red.
        _toolguard.require("git")
        resolver = cc.git_resolver(REPO_ROOT)
        smuggled = "def5a78"
        assert resolver([smuggled]) == set(), "the smuggled sha must not resolve"
        live = (REPO_ROOT / cc.ALLOWLIST).read_text(encoding="utf-8")
        allow = cc.parse_allowlist(live + f"{smuggled} pre-rewrite smuggled in\n")
        texts = _real_texts()
        texts["ROADMAP.md"] += f"\nFixed at commit {smuggled}.\n"
        report = cc.check(texts, allow, resolver, REPO_ROOT)
        assert report.ok, report.format()
        assert _unpinned(allow) == [smuggled]

    def test_every_pre_rewrite_entry_is_in_the_commit_map_when_present(self) -> None:
        cmap = REPO_ROOT / ".git" / "filter-repo" / "commit-map"
        if not cmap.is_file():
            pytest.skip("no commit-map in this clone - a fresh clone never has one")
        old = [ln.split()[0] for ln in cmap.read_text().splitlines()[1:] if ln.strip()]
        allow = cc.load_allowlist(REPO_ROOT / cc.ALLOWLIST)
        unmatched = [
            k for k, e in allow.items()
            if e.reason == "pre-rewrite" and not any(o.startswith(k) for o in old)
        ]
        assert unmatched == []

    def test_every_allowlist_entry_says_why(self) -> None:
        allow = cc.load_allowlist(REPO_ROOT / cc.ALLOWLIST)
        assert allow
        assert all(len(e.why.split()) >= 2 for e in allow.values())


# ---------------------------------------------------------------- CLI and wiring


class TestCli:
    def test_main_is_green_on_the_real_tree(self, capsys: pytest.CaptureFixture[str]) -> None:
        _toolguard.require("git")
        assert cc.main([]) == 0
        assert "CITATIONS OK" in capsys.readouterr().out

    def test_main_refuses_an_argument(self) -> None:
        assert cc.main(["--root", "elsewhere"]) == 2


class TestPreflightWiring:
    def test_this_module_runs_in_the_preflight(self) -> None:
        assert "tests/test_citation_check.py" in preflight.MODULES
