"""Guard the doc-guard selector - ROADMAP ``OPS-31``, criteria 1-3.

WHY THIS EXISTS. A wrap measures the suite, THEN writes the ledger and roadmap
entry recording that measurement, and the entry's own PROSE reddens the tree it
is committed into. Several modules in this suite READ TRACKED ``.md`` FILES and
assert on their content - ``tests/test_source_register.py`` walks every ``.md``
under ``docs/`` and requires each module-ish token it finds to be registered -
so a prose edit is a code change as far as the suite is concerned. The gate
never sees the tree that lands. It has fired three times: ``ac7fd5e``
(``LL-0087``, ``ops.lanes.owner``), ``c9a0f76`` (``LL-0140``, four tokens) and
``LL-0147`` (``lanes.REPO_ROOT``, ``summary.passed``).

WHAT IS GUARDED HERE. :mod:`ops.docguards` derives, AT RUN TIME, which test
modules read tracked ``.md``. The selector must not be a hand-written list: a
list is silently green over every doc and every module added after it was
written, which is the exact failure the ROADMAP item names. So the tests below
build a synthetic git tree, add a doc to it, and require the selector to see
it - a hardcoded list cannot pass that.

WHAT THESE TESTS ARE BLIND TO, stated here because a caveat that lives only in
a chat log is a lie in the artifact:

* :func:`ops.docguards.doc_reading_modules` reads SOURCE TEXT. A module that
  builds a doc path at run time out of pieces - ``REPO_ROOT / "docs" / name`` -
  names no doc in its source and uses no enumerated idiom, so the static pass
  misses it. That is why there is a second, independent derivation: the audit
  hook in ``tests/conftest.py`` records REAL opens, and the pre-commit hook
  refuses when the observed map names a module the selector missed.
* The observed map is written only by a COMPLETE run, and it lives in
  ``ops/runtime/`` which is gitignored. On a fresh clone there is none, so
  :class:`TestTheSelectorCoversWhatWasObserved` falls back to what THIS session
  has observed so far - which is only the modules pytest happened to run before
  this file. The complete cross-check is the pre-commit hook's job.
* The import hop is ONE LEVEL. A test that imports a helper that imports a
  second helper that reads a doc is not reached by the static pass.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _toolguard  # noqa: E402

from ops import docguards  # noqa: E402

PY = sys.executable


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_toolguard.require("git"), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
        check=False,
    )


def _synthetic_tree(root: Path) -> None:
    """A miniature repository with one doc and four test modules.

    Deliberately synthetic. Asserting selection against the REAL tests/ tree
    pins the selector to whatever that tree happens to contain today, and the
    tree churns. What has to stay true is the RULE, so the rule is exercised on
    a tree this test owns.
    """
    (root / "docs").mkdir()
    (root / "docs" / "GUIDE.md").write_text("# guide\n", encoding="ascii")
    (root / "helper_pkg").mkdir()
    (root / "helper_pkg" / "reader.py").write_text(
        'from pathlib import Path\n\n\ndef read():\n    return Path("docs/GUIDE.md").read_text()\n',
        encoding="ascii",
    )
    (root / "helper_pkg" / "quiet.py").write_text("VALUE = 1\n", encoding="ascii")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_direct.py").write_text(
        'from pathlib import Path\n\n\ndef test_it():\n    Path("docs/GUIDE.md").read_text()\n',
        encoding="ascii",
    )
    (tests / "test_idiom.py").write_text(
        "from pathlib import Path\n\n\n"
        "def test_it():\n"
        '    for p in Path(".").rglob("*.md"):\n'
        "        p.read_text()\n",
        encoding="ascii",
    )
    (tests / "test_hop.py").write_text(
        "from helper_pkg import reader\n\n\ndef test_it():\n    reader.read()\n",
        encoding="ascii",
    )
    (tests / "test_quiet.py").write_text(
        "from helper_pkg import quiet\n\n\ndef test_it():\n    assert quiet.VALUE == 1\n",
        encoding="ascii",
    )
    assert _git(root, "init", "-q").returncode == 0
    assert _git(root, "add", "-A").returncode == 0


class TestTheDocSetIsDerivedAtRunTime:
    """A hand-written list is silently green over every doc added after it.

    ``OPS-31`` names that failure explicitly, so it gets a test that a
    hardcoded list cannot pass: the doc is created inside the test.
    """

    def test_a_doc_added_to_a_fresh_index_is_seen(self, tmp_path):
        _synthetic_tree(tmp_path)
        assert "docs/GUIDE.md" in docguards.tracked_docs(tmp_path)

    def test_a_second_doc_added_after_the_first_call_is_also_seen(self, tmp_path):
        _synthetic_tree(tmp_path)
        before = docguards.tracked_docs(tmp_path)
        (tmp_path / "docs" / "LATER.md").write_text("# later\n", encoding="ascii")
        assert _git(tmp_path, "add", "-A").returncode == 0
        after = docguards.tracked_docs(tmp_path)
        assert "docs/LATER.md" not in before, "the fixture already had the doc"
        assert "docs/LATER.md" in after, (
            "a doc added after the first call is invisible, so the doc set is "
            "cached or hardcoded rather than derived at run time"
        )

    def test_a_non_markdown_file_is_not_a_doc(self, tmp_path):
        _synthetic_tree(tmp_path)
        docs = docguards.tracked_docs(tmp_path)
        assert not [d for d in docs if not d.endswith(".md")], docs

    def test_the_real_repository_docs_match_git_right_now(self):
        proc = subprocess.run(
            [_toolguard.require("git"), "ls-files", "-z", "*.md"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert proc.returncode == 0
        listed = {n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n}
        derived = set(docguards.tracked_docs(REPO_ROOT))
        missing = listed - derived
        assert not missing, f"git lists these docs and the selector does not: {sorted(missing)}"


class TestModuleSelection:
    """The three enumerated idioms, each proven on the synthetic tree."""

    def test_a_module_naming_a_doc_path_is_selected(self, tmp_path):
        _synthetic_tree(tmp_path)
        assert "tests/test_direct.py" in docguards.doc_reading_modules(tmp_path)

    def test_a_module_walking_for_markdown_is_selected(self, tmp_path):
        _synthetic_tree(tmp_path)
        assert "tests/test_idiom.py" in docguards.doc_reading_modules(tmp_path)

    def test_a_module_reaching_a_doc_through_one_import_hop_is_selected(self, tmp_path):
        _synthetic_tree(tmp_path)
        assert "tests/test_hop.py" in docguards.doc_reading_modules(tmp_path)

    def test_a_module_that_reads_no_doc_is_not_selected(self, tmp_path):
        """The pin. A selector that returns EVERY module is trivially complete
        and completely useless - it turns the pre-commit hook into a full suite
        run and gets switched off. This is the assertion that makes the three
        above mean something."""
        _synthetic_tree(tmp_path)
        selected = docguards.doc_reading_modules(tmp_path)
        assert "tests/test_quiet.py" not in selected, (
            "a module that names no doc, walks no markdown and imports only a "
            f"quiet helper was selected anyway: {selected}"
        )

    def test_only_pytest_collectable_modules_are_returned(self, tmp_path):
        _synthetic_tree(tmp_path)
        for node in docguards.doc_reading_modules(tmp_path):
            assert Path(node).name.startswith("test_"), node
            assert node.endswith(".py"), node


class TestTheRealRepositorySelection:
    def test_the_three_measured_floor_modules_are_selected(self):
        """``OPS-31`` measured these three at 53 tests in 27.7s and called them
        a FLOOR, not the answer. If the selector cannot even find them it is
        not selecting on the property it claims to."""
        selected = set(docguards.doc_reading_modules(REPO_ROOT))
        for expected in (
            "tests/test_source_register.py",
            "tests/test_ascii_hygiene.py",
            "tests/test_no_pii.py",
        ):
            assert expected in selected, f"{expected} reads tracked .md and was not selected"

    def test_the_selector_is_not_degenerate(self):
        """Not every test module reads a doc. A selector that returns all of
        them has stopped selecting."""
        all_modules = sorted(p.name for p in (REPO_ROOT / "tests").glob("test_*.py"))
        selected = docguards.doc_reading_modules(REPO_ROOT)
        assert len(selected) < len(all_modules), (
            f"the selector returned {len(selected)} of {len(all_modules)} test "
            "modules, which is not a selection"
        )

    def test_every_selected_node_id_exists_on_disk(self):
        for node in docguards.selected_node_ids(REPO_ROOT):
            assert (REPO_ROOT / node).is_file(), node


class TestStagedDocs:
    def test_a_staged_doc_is_reported(self, tmp_path):
        _synthetic_tree(tmp_path)
        assert "docs/GUIDE.md" in docguards.staged_docs(tmp_path)

    def test_a_staged_non_doc_is_not_reported(self, tmp_path):
        _synthetic_tree(tmp_path)
        staged = docguards.staged_docs(tmp_path)
        assert "helper_pkg/reader.py" not in staged, staged

    def test_nothing_staged_reports_nothing(self, tmp_path):
        _synthetic_tree(tmp_path)
        _git(tmp_path, "config", "user.email", "probe@example.invalid")
        _git(tmp_path, "config", "user.name", "probe")
        _git(tmp_path, "config", "commit.gpgsign", "false")
        _git(tmp_path, "-c", "core.hooksPath=", "commit", "-q", "-m", "seed")
        assert docguards.staged_docs(tmp_path) == ()


class TestTheAuditRecorderIsNotDecoration:
    """The independent derivation. ``doc_reading_modules`` reads source text;
    the recorder in ``tests/conftest.py`` watches REAL opens. Two derivations
    of the same set is the only reason a gap in one is visible."""

    def test_the_recorder_is_installed_for_this_session(self, docguard_recorder):
        assert docguard_recorder.installed, (
            "no audit hook is recording doc opens, so the coverage cross-check "
            "below has nothing to compare against"
        )

    def test_a_real_open_of_a_tracked_doc_is_recorded_against_this_module(
        self, docguard_recorder
    ):
        """Non-vacuity proof for the hook itself: open a tracked doc HERE and
        require the recorder to have noticed."""
        _toolguard.require("git")
        (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        seen = docguard_recorder.observed_for("tests/test_docguards.py")
        assert "README.md" in seen, (
            "a real open of README.md inside this test was not recorded, so the "
            f"audit hook is decoration. recorded: {sorted(seen)}"
        )

    def test_an_open_of_an_untracked_markdown_file_is_ignored(
        self, docguard_recorder, tmp_path
    ):
        """The hook must stay cheap and quiet. A scratch .md outside the repo
        is not a tracked doc and must not enter the map."""
        scratch = tmp_path / "scratch.md"
        scratch.write_text("not tracked\n", encoding="ascii")
        scratch.read_text(encoding="ascii")
        seen = docguard_recorder.observed_for("tests/test_docguards.py")
        assert "scratch.md" not in seen
        assert not [s for s in seen if "scratch" in s], sorted(seen)


class TestTheSelectorCoversWhatWasObserved:
    """The coverage guard. If a real open happened in a module the selector did
    not pick, the selector has a hole and the pre-commit subset is blind to it.

    BLIND SPOT, stated in the artifact: the persisted map exists only after a
    complete run, and ``ops/runtime/`` is gitignored, so on a fresh checkout
    only the live half of this runs - and the live half sees only the modules
    pytest ran BEFORE this file. The hook does the complete comparison.
    """

    def test_no_module_observed_so_far_this_session_was_missed(self, docguard_recorder):
        selected = set(docguards.doc_reading_modules(REPO_ROOT))
        observed = set(docguard_recorder.observed_modules())
        gap = sorted(observed - selected - {docguards.SESSION_KEY})
        assert not gap, (
            "these modules really opened a tracked .md and the selector did "
            f"not pick them: {gap}"
        )

    def test_no_module_in_the_persisted_map_was_missed(self):
        _toolguard.require("git")
        observed = docguards.load_observed(REPO_ROOT)
        if observed is None:
            pytest.skip(
                "no persisted observed map - ops/runtime/ is gitignored, so a "
                "fresh checkout has none until a complete run writes one"
            )
        gap = sorted(docguards.coverage_gap(REPO_ROOT))
        assert not gap, f"the persisted map names modules the selector missed: {gap}"


class TestTheHookFile:
    def test_the_hook_has_no_carriage_returns(self):
        """Git for Windows chokes on a CR in a shebang, and Windows
        ``write_text`` turns LF into CRLF without saying so."""
        raw = (REPO_ROOT / ".githooks" / "pre-commit").read_bytes()
        assert b"\r" not in raw, "the pre-commit hook contains a CR"

    def test_the_hook_invokes_the_selector(self):
        text = (REPO_ROOT / ".githooks" / "pre-commit").read_text(encoding="ascii")
        assert "ops.docguards" in text, (
            "the pre-commit hook does not invoke the selector, so criterion 2 "
            "of OPS-31 is unenforced whatever this module asserts"
        )

    def test_the_selector_module_the_hook_needs_exists(self):
        assert (REPO_ROOT / "ops" / "docguards.py").is_file()


def _probe_repo(tmp_path: Path) -> Path:
    """A throwaway repository carrying the real hook and a real selector.

    Throwaway on purpose - a probe commit that slipped through would land in
    real history. Only the pieces the doc guard needs are copied, which is also
    what keeps this fast enough to live in the suite.
    """
    # OPS-83. This helper copies the REAL `.githooks` in and points
    # `core.hooksPath` at it below, so every caller runs a `#!/bin/sh` hook
    # whose body calls grep, head, tr and wc. Without that POSIX userland on
    # PATH git cannot spawn the hook and these cases go red naming nothing.
    # Skip here, naming the missing members. The PRESENT direction is pinned by
    # the seed commit at the end of this function, which runs the real hook.
    _toolguard.require_posix_userland()
    repo = tmp_path / "probe"
    (repo / "ops").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "docs").mkdir()
    shutil.copytree(REPO_ROOT / ".githooks", repo / ".githooks")
    shutil.copy2(REPO_ROOT / "ops" / "docguards.py", repo / "ops" / "docguards.py")
    (repo / "tests" / "test_probe.py").write_text(
        'from pathlib import Path\n\n\ndef test_it():\n    Path("docs/NOTE.md").read_text()\n',
        encoding="ascii",
    )
    (repo / "docs" / "NOTE.md").write_text("# note\n", encoding="ascii")
    (repo / "seed.txt").write_text("seed\n", encoding="ascii")
    assert _git(repo, "init", "-q").returncode == 0
    for key, value in (
        ("user.email", "probe@example.invalid"),
        ("user.name", "hook probe"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", (repo / ".githooks").as_posix()),
    ):
        assert _git(repo, "config", key, value).returncode == 0
    assert _git(repo, "add", "seed.txt", "ops/docguards.py", "tests/test_probe.py").returncode == 0
    seeded = _git(repo, "commit", "-m", "probe: seed")
    assert seeded.returncode == 0, (
        "the hook refused a commit with no staged .md, so every refusal below "
        f"would be meaningless.\n{seeded.stdout}\n{seeded.stderr}"
    )
    return repo


class TestTheHookRefusesFailClosed:
    """``OPS-31`` criterion 2 lives in the hook, not in a test. These run a
    REAL ``git commit`` against a throwaway repository wired to the real hook,
    and check HEAD afterwards. A hook that merely exists is not a hook that
    fires."""

    def test_a_staged_doc_with_no_observed_map_is_refused(self, tmp_path):
        repo = _probe_repo(tmp_path)
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert _git(repo, "add", "docs/NOTE.md").returncode == 0
        result = _git(repo, "commit", "-m", "probe: doc with no map")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode != 0, (
            "an absent observed map failed OPEN - the commit landed with no "
            f"evidence the tree was ever run.\n{result.stdout}\n{result.stderr}"
        )
        assert after == before, f"HEAD moved {before[:8]} -> {after[:8]}"
        assert "observed" in (result.stdout + result.stderr).lower(), (
            "the refusal does not say the observed map is the reason, so the "
            f"operator cannot act on it.\n{result.stdout}\n{result.stderr}"
        )

    def test_a_staged_doc_differing_from_the_worktree_is_refused(self, tmp_path):
        """The run did not reflect what lands. This check must come BEFORE the
        observed-map check, so it is the reason quoted even with no map."""
        repo = _probe_repo(tmp_path)
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        (repo / "docs" / "NOTE.md").write_text("# staged\n", encoding="ascii")
        assert _git(repo, "add", "docs/NOTE.md").returncode == 0
        (repo / "docs" / "NOTE.md").write_text("# worktree, different\n", encoding="ascii")
        result = _git(repo, "commit", "-m", "probe: staged differs")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode != 0, (
            f"a staged doc that differs from the worktree landed.\n{result.stdout}\n{result.stderr}"
        )
        assert after == before
        blob = (result.stdout + result.stderr).lower()
        assert "working tree" in blob or "worktree" in blob, (
            f"the refusal does not name the reason.\n{result.stdout}\n{result.stderr}"
        )

    def test_a_commit_with_no_staged_doc_is_untouched_by_the_doc_guard(self, tmp_path):
        """The pin. A doc guard that refuses everything is not a guard, and
        the absent-map refusal above would prove nothing without this."""
        repo = _probe_repo(tmp_path)
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        (repo / "other.txt").write_text("no docs here\n", encoding="ascii")
        assert _git(repo, "add", "other.txt").returncode == 0
        result = _git(repo, "commit", "-m", "probe: no doc staged")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode == 0, (
            f"the doc guard refused a commit with no staged .md.\n{result.stdout}\n{result.stderr}"
        )
        assert after != before

    def test_a_repository_without_the_selector_is_skipped_not_refused(self, tmp_path):
        """The hook is copied verbatim into throwaway repositories by
        ``tests/test_no_pii.py`` and ``tests/test_ascii_hygiene.py``, and the
        first of those commits a README.md. A doc guard that fired there would
        redden this suite for a reason that has nothing to do with the tree
        being committed. Absence of ``ops/docguards.py`` means there is nothing
        to select and nothing to check - it is not Lanternlight."""
        repo = _probe_repo(tmp_path)
        (repo / "ops" / "docguards.py").unlink()
        assert _git(repo, "rm", "-q", "--cached", "ops/docguards.py").returncode == 0
        assert _git(repo, "commit", "-q", "-m", "probe: drop selector").returncode == 0
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert _git(repo, "add", "docs/NOTE.md").returncode == 0
        result = _git(repo, "commit", "-m", "probe: doc in a foreign repo")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode == 0, (
            "the doc guard fired in a repository that does not carry the "
            f"selector.\n{result.stdout}\n{result.stderr}"
        )
        assert after != before


def _seed_observed_map(repo: Path) -> None:
    """Give the probe repository a map the hook will accept.

    Without this the hook stops at the observed-map check and never reaches the
    subset run, so the two tests below - the only ones that exercise the part
    of the hook that actually catches the defect - would prove nothing.
    """
    docguards.write_observed(
        {
            "complete": True,
            "exitstatus": 0,
            "args": ["tests"],
            "root": str(repo.resolve()),
            "modules": {"tests/test_probe.py": ["docs/NOTE.md"]},
            "modules_run": ["tests/test_probe.py"],
            "test_module_digests": docguards.test_module_digests(repo),
        },
        repo,
    )


class TestTheHookRunsTheSubsetAgainstTheStagedProse:
    """``OPS-31`` criterion 2 and criterion 3, end to end and mechanical.

    The probe repository carries a test that asserts on a document's CONTENT,
    which is the shape of ``tests/test_source_register.py`` and the shape that
    reddened ``ac7fd5e``, ``c9a0f76`` and ``LL-0147``. Staging prose that
    violates it must refuse the commit; fixing the prose must let it through.
    Red and green, both through a real ``git commit``, both checked at HEAD.
    """

    def _repo_with_a_content_assertion(self, tmp_path: Path) -> Path:
        repo = _probe_repo(tmp_path)
        (repo / "tests" / "test_probe.py").write_text(
            "from pathlib import Path\n\n\n"
            "def test_the_note_is_registered():\n"
            '    text = Path("docs/NOTE.md").read_text(encoding="ascii")\n'
            '    assert "REGISTERED" in text, "the note cites an unregistered token"\n',
            encoding="ascii",
        )
        assert _git(repo, "add", "tests/test_probe.py").returncode == 0
        assert _git(repo, "commit", "-q", "-m", "probe: content assertion").returncode == 0
        _seed_observed_map(repo)
        return repo

    def test_prose_that_reddens_the_subset_is_refused(self, tmp_path):
        repo = self._repo_with_a_content_assertion(tmp_path)
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        (repo / "docs" / "NOTE.md").write_text(
            "# note\n\nan entry citing a token nobody wrote down\n", encoding="ascii"
        )
        assert _git(repo, "add", "docs/NOTE.md").returncode == 0
        result = _git(repo, "commit", "-m", "probe: prose that reddens the tree")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode != 0, (
            "prose that fails a doc-reading test LANDED, which is the exact "
            f"defect OPS-31 exists for.\n{result.stdout}\n{result.stderr}"
        )
        assert after == before, f"HEAD moved {before[:8]} -> {after[:8]}"
        assert "test_probe" in (result.stdout + result.stderr), (
            "the refusal does not name the test that failed, so the operator "
            f"cannot act on it.\n{result.stdout}\n{result.stderr}"
        )

    def test_the_same_commit_lands_once_the_prose_is_fixed(self, tmp_path):
        """The green half. Without it the test above is satisfied by a hook
        that refuses every commit carrying a document."""
        repo = self._repo_with_a_content_assertion(tmp_path)
        before = _git(repo, "rev-parse", "HEAD").stdout.strip()
        (repo / "docs" / "NOTE.md").write_text(
            "# note\n\nan entry citing a REGISTERED token\n", encoding="ascii"
        )
        assert _git(repo, "add", "docs/NOTE.md").returncode == 0
        result = _git(repo, "commit", "-m", "probe: prose that is registered")
        after = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert result.returncode == 0, (
            f"clean prose was refused.\n{result.stdout}\n{result.stderr}"
        )
        assert after != before


class TestTheObservedMapContract:
    def test_an_absent_map_reads_as_none_not_as_an_empty_success(self, tmp_path):
        assert docguards.load_observed(tmp_path) is None

    def test_a_map_is_written_atomically_through_a_temporary(self, tmp_path):
        payload = {"modules": {"tests/test_x.py": ["README.md"]}, "complete": True}
        target = docguards.write_observed(payload, tmp_path)
        assert target.is_file()
        assert not list(target.parent.glob("*.tmp")), "a temporary survived the write"
        assert docguards.load_observed(tmp_path)["modules"] == payload["modules"]

    def test_a_map_naming_an_unselected_module_is_reported_as_a_gap(self, tmp_path):
        _synthetic_tree(tmp_path)
        docguards.write_observed(
            {
                "modules": {"tests/test_quiet.py": ["docs/GUIDE.md"]},
                "complete": True,
                "root": str(tmp_path),
            },
            tmp_path,
        )
        assert "tests/test_quiet.py" in docguards.coverage_gap(tmp_path), (
            "a module that really opened a doc and is not selected was not "
            "reported, so the coverage guard is decoration"
        )

    def test_a_map_naming_only_selected_modules_reports_no_gap(self, tmp_path):
        _synthetic_tree(tmp_path)
        docguards.write_observed(
            {
                "modules": {"tests/test_direct.py": ["docs/GUIDE.md"]},
                "complete": True,
                "root": str(tmp_path),
            },
            tmp_path,
        )
        assert docguards.coverage_gap(tmp_path) == ()


class TestThePlantedDefect:
    """``OPS-31`` criterion 3 - plant the exact defect and watch it go red.

    The defect is a ledger entry whose PROSE cites a dotted token that is not
    in the source register, which is what ``ac7fd5e``, ``c9a0f76`` and
    ``LL-0147`` each did. The plant happens in a temporary docs tree, never in
    ``docs/LEDGER.md``: the real ledger is append-only and this test must not
    write to it.
    """

    #: What the host-shaped pattern REPORTS for the planted citation. It
    #: truncates at the first label carrying an underscore, so a ledger entry
    #: naming `ops.docguards.probeonly_node_ids` is reported as this - the same
    #: truncation `LL-0141` and `LL-0147` each had to register.
    #:
    #: DELIBERATELY A NAME THAT DOES NOT EXIST. The first draft planted
    #: `ops.docguards.selected`, a real attribute - and when the non-vacuity
    #: proof registered that token in `KNOWN_NON_HOSTS`, as the proof is
    #: supposed to, these two tests went red. A test that asserts a token is
    #: UNREGISTERED is asserting against global state anyone may legitimately
    #: change, so it has to own a token nobody would ever register, and say so
    #: out loud with the anchor below.
    TOKEN = "ops.docguards.probeonly"

    def _plant(self, docs: Path) -> None:
        (docs / "LEDGER.md").write_text(
            "# probe ledger\n\n"
            "### LL-9999 - 2026-09-06 - a planted entry that cites a token\n\n"
            "**Evidence:**\n"
            "- `ops.docguards.probeonly_node_ids` returns the modules to run\n",
            encoding="ascii",
        )

    def test_the_planted_token_is_not_already_registered(self):
        """The anchor. Everything below asserts that an UNREGISTERED token is
        reported, which is vacuous if the token was quietly registered."""
        import test_source_register as guard

        assert self.TOKEN not in guard.KNOWN_NON_HOSTS, (
            f"{self.TOKEN} has been added to KNOWN_NON_HOSTS, so the plant "
            "below no longer plants anything - pick a token nobody registers"
        )

    def test_the_planted_token_is_reported_before_it_is_registered(
        self, tmp_path, monkeypatch
    ):
        import test_source_register as guard

        docs = tmp_path / "docs"
        docs.mkdir()
        self._plant(docs)
        # The guard reports paths relative to its own REPO_ROOT. Point it at
        # the temporary tree so the plant never has to live in docs/LEDGER.md,
        # which is append-only and must not be written by a test.
        monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
        found = guard.cited_hosts(docs)
        assert self.TOKEN in found, (
            "the content guard did not even SEE the planted token, so a red "
            f"result from it would prove nothing. saw: {sorted(found)}"
        )
        unregistered = guard.external_sources(docs)
        assert self.TOKEN in unregistered, (
            "the planted token is not reported as an unregistered source, so "
            "the defect this whole item exists for is invisible"
        )

    def test_registering_the_token_clears_it(self, tmp_path, monkeypatch):
        import test_source_register as guard

        docs = tmp_path / "docs"
        docs.mkdir()
        self._plant(docs)
        monkeypatch.setattr(guard, "REPO_ROOT", tmp_path)
        assert self.TOKEN in guard.external_sources(docs), "anchor: not red first"
        monkeypatch.setattr(
            guard, "KNOWN_NON_HOSTS", guard.KNOWN_NON_HOSTS | {self.TOKEN}
        )
        assert self.TOKEN not in guard.external_sources(docs), (
            "registering the token did not clear it, so red and green here are "
            "not controlled by the register"
        )

    def test_the_guard_that_catches_this_defect_is_in_the_selected_subset(self):
        """The plant above proves the CONTENT guard catches it. This proves the
        pre-commit subset actually runs that guard - without it the whole chain
        is a guard nobody invokes."""
        assert "tests/test_source_register.py" in docguards.selected_node_ids(REPO_ROOT)


def test_the_selector_runs_from_the_command_line():
    """The hook is ``/bin/sh``. It reaches the selector through ``-m``."""
    proc = subprocess.run(
        [PY, "-m", "ops.docguards", "select"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "ascii"},
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    assert "tests/test_source_register.py" in lines, proc.stdout


class TestObservedStatusIsItselfGuarded:
    """`observed_status` decides whether the pre-commit hook trusts the map.

    It had ZERO test references tree-wide when this class was written, which is
    the same species of defect as the never-called `check_per_file_counts` that
    `OPS-31` closed in `ops/merge_gate.py` - a function whose behaviour is
    correct today and which nothing would notice breaking tomorrow. Found by
    the cycle-51 refutation pass, which deleted every staleness branch and
    watched `tests/test_docguards.py` stay green at 38 passed.

    Each test below drives ONE refusal reason, so deleting that branch reddens
    exactly one test rather than the whole class.
    """

    @staticmethod
    def _write(_root_dir, **overrides):
        """Write an otherwise-usable observed map, with fields overridden."""
        payload = {
            "complete": True,
            "exitstatus": 0,
            "root": str(_root_dir.resolve()),
            "modules": {},
            "test_module_digests": docguards.test_module_digests(_root_dir),
        }
        payload.update(overrides)
        path = _root_dir / "ops" / "runtime" / docguards.OBSERVED_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_an_absent_map_is_refused_and_says_how_to_make_one(self, tmp_path):
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("no observed map" in r for r in reasons), reasons
        assert any("python -m pytest" in r for r in reasons), reasons

    def test_a_usable_map_is_ACCEPTED(self, tmp_path):
        """Positive control - without it every test below could pass vacuously."""
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        self._write(tmp_path)
        usable, reasons = docguards.observed_status(tmp_path)
        assert usable, reasons

    def test_a_map_from_a_PARTIAL_run_is_refused(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        self._write(tmp_path, complete=False)
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("partial run" in r for r in reasons), reasons

    def test_a_map_from_a_RED_run_is_refused(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        self._write(tmp_path, exitstatus=1)
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("not green" in r for r in reasons), reasons

    def test_a_map_from_a_FOREIGN_checkout_is_refused(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        self._write(tmp_path, root=r"C:\somewhere\else")
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("written from" in r for r in reasons), reasons

    def test_a_map_with_NO_DIGESTS_is_refused(self, tmp_path):
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        self._write(tmp_path, test_module_digests="not-a-dict")
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("no test module digests" in r for r in reasons), reasons

    def test_a_test_module_EDITED_since_the_run_is_refused(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        module = tests_dir / "test_probe.py"
        module.write_text("# before\n", encoding="utf-8")
        self._write(tmp_path)
        module.write_text("# after - a different digest\n", encoding="utf-8")
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("edited since the run" in r for r in reasons), reasons

    def test_a_test_module_ADDED_since_the_run_is_refused(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        self._write(tmp_path)
        (tests_dir / "test_new.py").write_text("# new\n", encoding="utf-8")
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("added since the run" in r for r in reasons), reasons

    def test_a_test_module_REMOVED_since_the_run_is_refused(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        module = tests_dir / "test_gone.py"
        module.write_text("# here\n", encoding="utf-8")
        self._write(tmp_path)
        module.unlink()
        usable, reasons = docguards.observed_status(tmp_path)
        assert not usable
        assert any("removed since the run" in r for r in reasons), reasons
