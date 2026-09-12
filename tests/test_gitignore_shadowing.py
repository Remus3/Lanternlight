"""Does any ignore rule here already shadow a TRACKED file?

ROADMAP ``OPS-75``. An unanchored ignore pattern can match a path that is
ALREADY tracked. Git keeps honouring the tracked entry, so nothing breaks and
nothing warns - but an untracked SIBLING added next to it in the same directory
is silently refused by ``git add``, and the refusal looks like the file simply
not mattering. This repository has two live reasons to care: ``moon_sync_inbox/``
is gitignored and is exactly where a mistaken addition would be invisible, and
``ops/runtime/`` is gitignored while sitting inside a package directory that is
not.

THE INSTRUMENT, and the flag that makes it answer the right question.
``git check-ignore`` normally consults the index, so it says NOTHING about a
tracked path - which is precisely the population this item asks about.
``--no-index`` is what removes that short-circuit. The whole measurement is one
pipe::

    git ls-files -z | git check-ignore --no-index -v -z --stdin

``-v`` makes each record four NUL-separated fields: source file, line number,
pattern, pathname.

SCOPE IS EVERY EXCLUDE SOURCE GIT HONOURS, NOT THE FILE NAMED ``.gitignore``.
Asking ``git`` rather than parsing a file by hand is the right instrument, and
the price of it is that the answer is wider than this module's name suggests.
Findings have been produced here from ``.git/info/exclude`` and from a global
``core.excludesFile`` as well as from a tracked ``.gitignore``, all three
observed rather than reasoned about. Any nested ``.gitignore`` in a
subdirectory counts too.

THE ANSWER IS THEREFORE MACHINE-CONFIG DEPENDENT, and that is stated here
rather than discovered by whoever hits it. ``.git/info/exclude`` is per-clone
and untracked; a global excludes file is per-machine and lives outside the
repository entirely. A contributor carrying ``*.log`` in their global excludes
can see this module go red on a tree that is green for everyone else. What
makes that survivable instead of baffling is that every finding names the
SOURCE FILE and LINE NUMBER it came from - see :func:`format_findings` - so a
red that originates outside the repository says so in its own message, with an
absolute path for the global case.

A PATTERN BEGINNING WITH ``!`` IS A NEGATION and means the path is NOT ignored.
Counting one of those as a defect is the over-reporting failure this repository
has been burned by before - ``OPS-79``: a positive specimen proves an instrument
can SEE and proves nothing about whether it INVENTS. So there are two specimens
below and not one, and the negative specimen reproduces this repository's own
carve-out shape.

THE SIBLING QUESTION QUALIFIES A MATCH - IT IS NOT A FREE-STANDING HUNT.
Criterion 1 asks for a tracked path "matched by a pattern that would ALSO
ignore an untracked sibling in the same directory", so the sibling is asked
about ONLY for tracked paths some pattern already matched. Asking it of every
tracked path instead turns the probe token into the subject of the answer: with
``*_*.txt`` in the ignore file and ``notes.txt`` tracked, ``notes.txt`` is
matched by nothing and is not a finding, yet the synthesized
``notes_<probe>.txt`` IS net-ignored purely because the construction injects an
underscore. A real new neighbour called ``notes2.txt`` would be added without a
murmur. Reporting that is INVENTING a finding, which is the ``OPS-79`` failure
one level over from the negation split, and it is pinned as a
NOT-reported case by :class:`TestTheProbeTokenDoesNotInventFindings`.

WHAT THE QUALIFIED QUESTION IS FOR, and it is worth more than the broad one: a
tracked path saved ONLY by a NEGATION that is NARROWER than the pattern
ignoring it. ``*.log`` plus ``!keep.log`` leaves ``keep.log`` tracked, clean and
completely unremarkable, while every neighbour beside it is silently refused and
nothing warns. That specimen is :class:`TestANarrowNegationSpecimen`. This
repository's own carve-out is the wide shape - ``*.gvas.b64`` with
``!tests/fixtures/**/*.gvas.b64`` covers the siblings as well as the tracked
files - and it stays clean, which is what the negative specimen pins.

NO PROBE TOKEN IS NEUTRAL AGAINST EVERY CONCEIVABLE PATTERN, and no narrowing
makes it so. The token is alphanumeric to avoid glob metacharacters and the
separator is an underscore; a pattern written to match either of those, against
a tracked path that some other pattern already matched, would still be
answering partly about the probe. Qualifying the question removes the whole
class of false positives against UNMATCHED paths, which is where the observed
one lived. It does not remove the class outright, and the honest limit in the
other direction is that a pattern shaped like ``notes_*.txt`` against an
unmatched tracked ``notes.txt`` is now out of scope - that is criterion 1's
wording, deliberately, rather than an oversight.

CRITERION 2 - NOTHING IS STORED. The tracked listing and the pattern set are
both asked of ``git`` at run time. No count and no filename is written into this
file, for the reason ``tests/test_source_register.py`` already gives about
itself: a committed list of filenames goes stale on the first rename and then
reads as a confident lie.

CRITERION 3 - NOISIER, NOT QUIETER, AND THE TWO HALVES ARE DIFFERENT.

* ``git`` ABSENT is a SKIP, through :func:`_toolguard.require`. That is the
  noisier answer in this suite and not a contradiction of ``OPS-78``/``OPS-83``:
  ``tests/_toolguard.py`` announces every such skip by name in an end-of-run
  banner, so a reader who sees green also sees the line saying these tests did
  not run. The quiet failure would be a silent PASS on a machine with no git.
* ``git`` PRESENT but the tracked listing EMPTY, or the command failing, is a
  LOUD FAILURE. That is the real trap: an empty listing makes the whole check
  vacuously green, and a green vacuous check is worse than no check. It is
  raised as :class:`GitListingUnusable` and tested in both directions against
  real throwaway repositories rather than a mock.

CRITERION 6 - THE LIVE NUMBER IS SURFACED. Every real-repository arm carries
the measured counts in its assertion message, and
:meth:`TestTheRealRepository.test_the_live_counts_are_reported` prints them. Run
``python -m pytest tests/test_gitignore_shadowing.py -s`` to read them on a
green run. No specific number is asserted anywhere: the count is a measurement,
and a measurement pinned to a constant is the staleness criterion 2 forbids one
level down.

Every git repository built here is a throwaway under ``tmp_path``. Nothing in
this module writes to this repository's index, and no probe file is ever planted
in this tree - ``git check-ignore`` takes arbitrary path STRINGS and needs no
file on disk, which is what lets the sibling question be asked without touching
anything.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _toolguard  # noqa: E402

#: git exports these to a hook, and a hook that ran this suite would otherwise
#: hand them to every ``git`` below - which would then operate on the repository
#: being committed instead of the throwaway one under ``tmp_path``. Copied in
#: shape from ``tests/test_precommit_gate_lint.py``, which learned it first, and
#: from ``.githooks/pre-commit`` section 3d, where four tests failed inside a
#: hook for exactly this reason. Measured, not assumed: with ``GIT_DIR`` set to
#: this repository, ``git ls-files -z`` run inside a fresh throwaway returns the
#: OUTER repository's listing, so every arm below would silently audit the wrong
#: tree while reporting a clean bill of health. Pinned by
#: :class:`TestTheHookEnvironmentCannotLeakIn` rather than asserted by comment.
GIT_HOOK_ENV = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_PARAMETERS",
    "GIT_AUTHOR_DATE",
    "GIT_EDITOR",
)

#: Inserted into a synthesized sibling name. Alphanumeric on purpose: a probe
#: token carrying a glob metacharacter would change which patterns can match it
#: and would make the answer a statement about the token.
SIBLING_PROBE = "ops75siblingprobe"


class GitListingUnusable(RuntimeError):
    """Raised when ``git`` is present but its answer cannot be trusted.

    An EMPTY tracked listing, or a non-zero exit from the listing command, makes
    every downstream check vacuously green. Criterion 3: the check gets noisier
    when its input is missing, never quieter. This is deliberately NOT a skip -
    a skip here would be indistinguishable from a clean bill of health on the
    one machine where the instrument is broken.
    """


class IgnoreRecord(NamedTuple):
    """One ``git check-ignore -v`` record: which pattern matched which path."""

    #: The file the pattern was read from, e.g. ``.gitignore``.
    source: str
    #: Line number within that file, as text - it is only ever reported.
    line: str
    #: The pattern itself. A leading ``!`` means NEGATED, i.e. NOT ignored.
    pattern: str
    #: The path that was asked about.
    path: str

    @property
    def negated(self) -> bool:
        """Whether this record UN-ignores the path rather than ignoring it."""
        return self.pattern.startswith("!")


class ShadowAudit(NamedTuple):
    """The whole measurement for one population of paths."""

    #: Every path that was asked about.
    asked: tuple[str, ...]
    #: Every path some pattern matched, negated or not.
    matched: tuple[IgnoreRecord, ...]
    #: The subset whose pattern begins with ``!``. NOT findings.
    negated: tuple[IgnoreRecord, ...]
    #: The findings: matched by a pattern that really does ignore.
    net_ignored: tuple[IgnoreRecord, ...]

    def counts(self) -> str:
        """The measured counts as one readable line. Never a stored constant."""
        return (
            f"asked={len(self.asked)} matched={len(self.matched)} "
            f"negated={len(self.negated)} net_ignored={len(self.net_ignored)}"
        )


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    for name in GIT_HOOK_ENV:
        env.pop(name, None)
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run ``git`` in ``repo``, in BYTES mode.

    Bytes rather than text because every command here uses ``-z``: the records
    are NUL-separated and a text-mode newline translation has no business near
    them.
    """
    return subprocess.run(
        [_toolguard.require("git"), *args],
        cwd=repo,
        capture_output=True,
        timeout=300,
        env=_clean_env(),
        check=False,
    )


def tracked_paths(repo: Path) -> tuple[str, ...]:
    """Every tracked path in ``repo``, asked of ``git`` right now.

    Raises :class:`GitListingUnusable` when the command fails or the listing is
    empty. See the module docstring on why that is a failure and not a skip.
    """
    proc = _git(repo, "ls-files", "-z")
    if proc.returncode != 0:
        raise GitListingUnusable(
            f"git ls-files failed in {repo} with exit {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    names = tuple(n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n)
    if not names:
        raise GitListingUnusable(
            f"git ls-files returned NOTHING in {repo}. Every check built on this "
            "listing would be vacuously green, so this is a failure and not a pass."
        )
    return names


def parse_check_ignore_fields(fields: list[str]) -> tuple[IgnoreRecord, ...]:
    """Group NUL-split ``check-ignore -v -z`` fields into four-field records.

    A SEPARATE FUNCTION so the shape check below can be reached. Left inline it
    was unreachable with today's git and a mutation that deleted it survived the
    whole campaign - a branch no test can reach is decoration, whatever it says.
    """
    fields = list(fields)
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) % 4 != 0:
        raise GitListingUnusable(
            f"git check-ignore -v -z emitted {len(fields)} fields, which is not a "
            "whole number of four-field records. The output shape changed, so every "
            "record parsed out of it is suspect."
        )
    return tuple(IgnoreRecord(*fields[index : index + 4]) for index in range(0, len(fields), 4))


def check_ignore_records(repo: Path, paths: tuple[str, ...]) -> tuple[IgnoreRecord, ...]:
    """Ask ``git check-ignore --no-index -v`` about ``paths``.

    ``--no-index`` is the load-bearing flag: without it git short-circuits on
    anything already in the index and reports nothing about a tracked path,
    which is the entire population this module exists to interrogate.

    Exit status 1 means "none of them are ignored" and is a normal answer, not
    an error; only something else is a failure.
    """
    if not paths:
        raise GitListingUnusable(
            "check_ignore_records was asked about NO paths. An empty question "
            "has an empty answer that looks exactly like a clean bill of health."
        )
    payload = ("\0".join(paths) + "\0").encode("utf-8")
    proc = subprocess.run(
        [_toolguard.require("git"), "check-ignore", "--no-index", "-v", "-z", "--stdin"],
        cwd=repo,
        input=payload,
        capture_output=True,
        timeout=300,
        env=_clean_env(),
        check=False,
    )
    if proc.returncode not in (0, 1):
        raise GitListingUnusable(
            f"git check-ignore failed in {repo} with exit {proc.returncode}: "
            f"{proc.stderr.decode('utf-8', 'replace').strip()}"
        )
    return parse_check_ignore_fields(proc.stdout.decode("utf-8", "replace").split("\0"))


def audit(repo: Path, paths: tuple[str, ...]) -> ShadowAudit:
    """Split the ``check-ignore`` answer into negations and real findings."""
    matched = check_ignore_records(repo, paths)
    negated = tuple(record for record in matched if record.negated)
    net = tuple(record for record in matched if not record.negated)
    return ShadowAudit(asked=paths, matched=matched, negated=negated, net_ignored=net)


def sibling_of(path: str, probe: str = SIBLING_PROBE) -> str:
    """A synthesized UNTRACKED sibling of ``path`` in the same directory.

    STEM + PROBE + EVERY SUFFIX, e.g. ``camp_data.gvas.b64`` becomes
    ``camp_data_<probe>.gvas.b64``. That construction is chosen because it
    preserves BOTH a prefix glob (``API-Key-*.txt`` still matches) and a suffix
    glob (``*.gvas.b64`` still matches), so a pattern of either family that
    would swallow a real new file is still seen.

    IT CANNOT PRESERVE AN EXACT-FULL-NAME PATTERN such as ``secrets.json``, and
    that is correct rather than a hole: an exact-name pattern cannot shadow a
    SIBLING by definition - it shadows exactly one name, which is the tracked
    path itself, and that is what the primary arm already covers. Pinned by
    :class:`TestAnExactNameSpecimen`.

    A leading dot is kept as part of the stem, so ``.gitignore`` becomes
    ``.gitignore_<probe>`` rather than ``_<probe>.gitignore``, which would have
    thrown the name away entirely.
    """
    directory, _, base = path.rpartition("/")
    lead = "." if base.startswith(".") else ""
    rest = base[1:] if lead else base
    stem, dot, suffixes = rest.partition(".")
    name = f"{lead}{stem}_{probe}{dot}{suffixes}"
    return f"{directory}/{name}" if directory else name


def qualifying_siblings(repo: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    """Siblings of only those ``paths`` some pattern ALREADY MATCHED.

    Criterion 1's sibling clause qualifies a match; it does not stand on its
    own. Narrowing the population here rather than filtering findings later is
    deliberate - an unmatched tracked path never reaches ``check-ignore`` as a
    synthesized name at all, so the probe token cannot manufacture an answer
    about it. See the module docstring for the ``*_*.txt`` case this removes and
    the ``!keep.log`` case it exists to catch.

    An EMPTY result means no pattern touches any tracked path, so no pattern can
    qualify. That is a real clean bill rather than a vacuous one: it is derived
    from a primary audit that ran, and the primary arm asserts on the same
    audit. The count is surfaced by
    :meth:`TestTheRealRepository.test_the_live_counts_are_reported`, so a
    ``matched=0`` tree is visible rather than merely quiet.
    """
    primary = audit(repo, paths)
    matched = tuple(dict.fromkeys(record.path for record in primary.matched))
    return tuple(sibling_of(path) for path in matched)


def format_findings(title: str, result: ShadowAudit) -> str:
    """An actionable failure message: path, pattern, source file and line.

    Actionable WITHOUT a second investigation is the whole requirement. A
    message saying only "3 findings" sends the reader back to the command line
    to re-derive what this run already knew.
    """
    lines = [f"{title} [{result.counts()}]"]
    for record in result.net_ignored:
        lines.append(
            f"  {record.path}  is ignored by  {record.source}:{record.line}  "
            f"pattern {record.pattern!r}"
        )
    return "\n".join(lines)


def assert_no_shadowing(repo: Path, paths: tuple[str, ...], title: str) -> ShadowAudit:
    """THE CHECK. Fail if any of ``paths`` is net-ignored, and return the audit.

    Returning the audit is deliberate: a caller that wants the numbers gets them
    from the same call that did the checking, so the reported count and the
    checked count cannot drift apart.
    """
    result = audit(repo, paths)
    assert not result.net_ignored, format_findings(title, result)
    return result


class TestTheRealRepository:
    """The primary check, against this tree, measured at run time."""

    def test_no_tracked_path_is_net_ignored(self):
        """OPS-75 criterion 1. No tracked path may be shadowed by a pattern."""
        paths = tracked_paths(REPO_ROOT)
        assert_no_shadowing(REPO_ROOT, paths, "TRACKED PATHS SHADOWED BY AN IGNORE RULE")

    def test_no_qualifying_sibling_is_net_ignored(self):
        """OPS-75 criterion 1, the sibling half, asked as a QUALIFIER.

        The question the item actually asks is not only whether the tracked path
        is ignored, but whether the pattern matching it would ALSO swallow an
        untracked neighbour - the silent ``git add`` refusal. ``check-ignore``
        answers about path STRINGS, so the neighbour is synthesized and nothing
        is written to disk.

        Only tracked paths that a pattern ALREADY MATCHED are asked about. A
        tracked path no pattern touches has no pattern to qualify, and asking
        anyway makes the probe token the subject of the answer - see the module
        docstring.
        """
        paths = tracked_paths(REPO_ROOT)
        siblings = qualifying_siblings(REPO_ROOT, paths)
        assert len(siblings) <= len(paths)
        if not siblings:
            matched = audit(REPO_ROOT, paths).matched
            assert matched == (), (
                "qualifying_siblings returned nothing while patterns DID match "
                f"{len(matched)} tracked path(s) - the narrowing dropped the question"
            )
            return
        assert_no_shadowing(REPO_ROOT, siblings, "SIBLINGS SHADOWED BY AN IGNORE RULE")

    def test_the_live_counts_are_reported(self, capsys):
        """OPS-75 criterion 6. Surface the number so the ledger can record it.

        No number is asserted. What IS asserted is that the three populations
        partition cleanly, which is the property that would break if the
        negation split ever went wrong.
        """
        paths = tracked_paths(REPO_ROOT)
        tracked_result = audit(REPO_ROOT, paths)
        siblings = qualifying_siblings(REPO_ROOT, paths)
        results = [tracked_result]
        if siblings:
            results.append(audit(REPO_ROOT, siblings))
        with capsys.disabled():
            print(f"\nOPS-75 tracked:  {tracked_result.counts()}")
            print(f"OPS-75 qualifying siblings asked: {len(siblings)}")
            for extra in results[1:]:
                print(f"OPS-75 siblings: {extra.counts()}")
        for result in results:
            assert len(result.matched) == len(result.negated) + len(result.net_ignored), (
                f"the negation split lost or duplicated a record: {result.counts()}"
            )

    def test_the_listing_is_asked_of_git_at_run_time(self, tmp_path):
        """OPS-75 criterion 2, pinned by BEHAVIOUR rather than by prose.

        A listing stored in this file could not grow when the repository does,
        so the proof that nothing is stored is that a file added between two
        calls is absent from the first answer and present in the second.

        Deliberately NOT written as a scan of this module's own source for
        filename literals. Docstrings here legitimately cite tracked paths -
        ``tests/_toolguard.py``, ``docs/OPERATIONS.md`` - and a guard that
        called a citation a stored listing would be crying wolf about prose.
        """
        repo = _throwaway_repo(tmp_path / "listing", "*.log\n")
        _add(repo, "one.txt")
        before = tracked_paths(repo)
        _add(repo, "two.txt")
        after = tracked_paths(repo)
        assert "one.txt" in before
        assert "two.txt" not in before
        assert "two.txt" in after


def _throwaway_repo(root: Path, ignore_text: str) -> Path:
    """A throwaway repository carrying ``ignore_text`` as its ``.gitignore``.

    NO HOOKS ARE WIRED. This item needs no hook, and wiring one would give every
    test here a POSIX-userland dependency it does not have. ``core.hooksPath``
    is pointed at a directory that does not exist so an inherited setting from
    the environment cannot quietly attach one.
    """
    root.mkdir(parents=True, exist_ok=True)
    assert _git(root, "init", "-q").returncode == 0, "git init failed"
    for key, value in (
        ("user.email", "probe@example.invalid"),
        ("user.name", "probe"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", (root / ".nohooks").as_posix()),
    ):
        assert _git(root, "config", key, value).returncode == 0, key
    (root / ".gitignore").write_text(ignore_text, encoding="ascii", newline="\n")
    assert _git(root, "add", "--", ".gitignore").returncode == 0
    return root


def _sealed_non_repo(path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory that is NOT a git repository, and cannot accidentally be one.

    ``git`` searches parent directories for a ``.git``, so a bare ``tmp_path``
    subdirectory is only reliably outside a repository on a machine whose temp
    tree happens not to sit under one. ``GIT_CEILING_DIRECTORIES`` stops that
    upward walk, which turns "probably not a repository here" into a fact.

    On THIS machine the temp tree is not under a repository, so the ceiling
    changes no result for the callers above and a mutation removing it once
    survived a whole campaign on that basis. It is no longer recorded as
    unpinned: :class:`TestTheCeilingReallyStopsTheUpwardWalk` builds the machine
    this is armour for - a throwaway repository with a probe directory nested
    two levels inside it - and reddens when the ceiling goes. Documenting a
    load-bearing line as untested is a worse answer than building the specimen
    that tests it.
    """
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(path.parent))
    return path


def _add(repo: Path, relpath: str, *, force: bool = False) -> None:
    """Create ``relpath`` under ``repo`` and stage it, forcing past an ignore."""
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("probe\n", encoding="ascii", newline="\n")
    args = ["add", "-f", "--", relpath] if force else ["add", "--", relpath]
    assert _git(repo, *args).returncode == 0, relpath


class TestThePositiveSpecimen:
    """A repository where a tracked file REALLY IS shadowed. The check must fail.

    Without this the whole module could be blind and still green, which is the
    only failure mode a clean tree cannot distinguish from a working check.
    """

    def test_a_shadowed_tracked_file_is_found(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "positive", "*.log\n")
        _add(repo, "logs/app.log", force=True)
        paths = tracked_paths(repo)
        assert "logs/app.log" in paths
        with pytest.raises(AssertionError) as excinfo:
            assert_no_shadowing(repo, paths, "POSITIVE SPECIMEN")
        message = str(excinfo.value)
        assert "logs/app.log" in message
        assert "'*.log'" in message
        assert ".gitignore:1" in message

    def test_the_shadowed_file_also_shadows_its_sibling(self, tmp_path):
        """The sibling half of the same specimen - the silent ``git add`` refusal."""
        repo = _throwaway_repo(tmp_path / "positive_sibling", "*.log\n")
        _add(repo, "logs/app.log", force=True)
        siblings = qualifying_siblings(repo, tracked_paths(repo))
        assert f"logs/app_{SIBLING_PROBE}.log" in siblings
        with pytest.raises(AssertionError) as excinfo:
            assert_no_shadowing(repo, siblings, "POSITIVE SIBLING SPECIMEN")
        assert f"logs/app_{SIBLING_PROBE}.log" in str(excinfo.value)

    def test_a_prefix_glob_survives_the_sibling_construction(self, tmp_path):
        """``API-Key-*.txt`` is the other glob family, and it must be seen too."""
        repo = _throwaway_repo(tmp_path / "prefix", "API-Key-*.txt\n")
        _add(repo, "secrets/API-Key-live.txt", force=True)
        siblings = qualifying_siblings(repo, tracked_paths(repo))
        with pytest.raises(AssertionError) as excinfo:
            assert_no_shadowing(repo, siblings, "PREFIX GLOB SPECIMEN")
        assert "API-Key-live_" in str(excinfo.value)


class TestTheNegativeSpecimen:
    """The carve-out shape: ignored, then UN-ignored by a later ``!`` pattern.

    An over-reporting check that called every match a finding would fail here,
    which is the ``OPS-79`` point: a positive specimen proves the instrument can
    SEE and says nothing about whether it INVENTS.
    """

    IGNORE_TEXT = "*.gvas.b64\n!fixtures/**/*.gvas.b64\n"

    def test_a_negated_tracked_file_is_not_a_finding(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "negative", self.IGNORE_TEXT)
        _add(repo, "fixtures/deck.gvas.b64")
        result = assert_no_shadowing(repo, tracked_paths(repo), "NEGATIVE SPECIMEN")
        assert result.net_ignored == ()

    def test_the_instrument_really_saw_it_and_classified_it_as_negated(self, tmp_path):
        """Pin the PRESENT direction.

        A clean pass with zero matches would be a different fact entirely - it
        would mean the check never reached the file at all.
        """
        repo = _throwaway_repo(tmp_path / "negative_seen", self.IGNORE_TEXT)
        _add(repo, "fixtures/deck.gvas.b64")
        result = audit(repo, tracked_paths(repo))
        assert [record.path for record in result.negated] == ["fixtures/deck.gvas.b64"]
        assert result.negated[0].pattern == "!fixtures/**/*.gvas.b64"

    def test_a_negated_sibling_is_not_a_finding_either(self, tmp_path):
        """The WIDE carve-out, which is this repository's own shape.

        ``!fixtures/**/*.gvas.b64`` covers the siblings as well as the tracked
        file, so the qualified question reaches the sibling and still answers
        clean. Contrast :class:`TestANarrowNegationSpecimen`, where the negation
        covers only the tracked name.
        """
        repo = _throwaway_repo(tmp_path / "negative_sibling", self.IGNORE_TEXT)
        _add(repo, "fixtures/deck.gvas.b64")
        siblings = qualifying_siblings(repo, tracked_paths(repo))
        assert siblings == (f"fixtures/deck_{SIBLING_PROBE}.gvas.b64",)
        result = assert_no_shadowing(repo, siblings, "NEGATIVE SIBLING SPECIMEN")
        assert result.net_ignored == ()
        assert [record.path for record in result.negated] == [
            f"fixtures/deck_{SIBLING_PROBE}.gvas.b64"
        ]


class TestAnExactNameSpecimen:
    """The stated limit of the sibling construction, pinned rather than implied.

    An exact-full-name pattern cannot shadow a sibling, so the sibling arm is
    SILENT about it by design and the primary arm is the one that catches it.
    Written as a test because a limit that lives only in a docstring is a limit
    nobody re-checks.
    """

    def test_the_primary_arm_catches_it(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "exact", "secrets.json\n")
        _add(repo, "secrets.json", force=True)
        with pytest.raises(AssertionError) as excinfo:
            assert_no_shadowing(repo, tracked_paths(repo), "EXACT NAME SPECIMEN")
        assert "secrets.json" in str(excinfo.value)

    def test_the_sibling_arm_is_silent_about_it_and_that_is_correct(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "exact_sibling", "secrets.json\n")
        _add(repo, "secrets.json", force=True)
        siblings = qualifying_siblings(repo, tracked_paths(repo))
        assert f"secrets_{SIBLING_PROBE}.json" in siblings
        result = assert_no_shadowing(repo, siblings, "EXACT NAME SIBLING SPECIMEN")
        assert result.net_ignored == ()


class TestANarrowNegationSpecimen:
    """The case the QUALIFIED sibling question exists to catch.

    ``*.log`` ignores everything; ``!keep.log`` un-ignores exactly one name. The
    tracked ``keep.log`` is therefore matched, negated, and completely
    unremarkable - the primary arm is correctly silent about it. Every neighbour
    beside it is still swallowed by ``*.log``, so a new ``keep2.log`` is refused
    by ``git add`` with no message. Nothing in the tree says so. This is the
    shadow the item is named after, and the broad sibling sweep buried it among
    probe-token artefacts.
    """

    IGNORE_TEXT = "*.log\n!keep.log\n"

    def test_the_primary_arm_is_correctly_silent(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "narrow_primary", self.IGNORE_TEXT)
        _add(repo, "keep.log")
        result = assert_no_shadowing(repo, tracked_paths(repo), "NARROW NEGATION PRIMARY")
        assert result.net_ignored == ()
        assert [record.path for record in result.negated] == ["keep.log"]

    def test_the_qualified_sibling_arm_catches_it(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "narrow_sibling", self.IGNORE_TEXT)
        _add(repo, "keep.log")
        siblings = qualifying_siblings(repo, tracked_paths(repo))
        assert siblings == (f"keep_{SIBLING_PROBE}.log",)
        with pytest.raises(AssertionError) as excinfo:
            assert_no_shadowing(repo, siblings, "NARROW NEGATION SIBLING")
        message = str(excinfo.value)
        assert f"keep_{SIBLING_PROBE}.log" in message
        assert "'*.log'" in message


class TestTheProbeTokenDoesNotInventFindings:
    """``OPS-79`` one level over: can the instrument INVENT, not just SEE?

    ``*_*.txt`` matches any name containing an underscore. Tracked ``notes.txt``
    contains none, so no pattern touches it and it is not a finding. The
    synthesized ``notes_<probe>.txt`` DOES contain one, purely because
    :func:`sibling_of` injects a separator - and a real neighbour called
    ``notes2.txt`` would be added without complaint. Reporting that would be a
    finding where there is none.

    The fix is the narrowing, not the token: an unmatched tracked path is never
    asked about as a sibling, so nothing about ``notes.txt`` reaches
    ``check-ignore`` in synthesized form at all.
    """

    IGNORE_TEXT = "*_*.txt\n"

    def test_the_unmatched_tracked_path_is_not_a_finding(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "invent_primary", self.IGNORE_TEXT)
        _add(repo, "notes.txt")
        result = assert_no_shadowing(repo, tracked_paths(repo), "INVENTION PRIMARY")
        assert result.matched == (), (
            "the specimen is wrong if any pattern matches the tracked path: "
            f"{result.counts()}"
        )

    def test_no_sibling_is_asked_about_and_so_none_is_reported(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "invent_sibling", self.IGNORE_TEXT)
        _add(repo, "notes.txt")
        assert qualifying_siblings(repo, tracked_paths(repo)) == ()

    def test_the_broad_question_really_would_have_invented_one(self, tmp_path):
        """The control, without which the arm above proves nothing.

        If the unqualified sweep were ALSO clean here, the narrowing would be
        removing a hazard that does not exist and this specimen would be
        decoration. It is not: asked about every tracked path, the probe token
        manufactures a net-ignored name out of a file nothing ignores.
        """
        repo = _throwaway_repo(tmp_path / "invent_control", self.IGNORE_TEXT)
        _add(repo, "notes.txt")
        broad = tuple(sibling_of(path) for path in tracked_paths(repo))
        result = audit(repo, broad)
        assert [record.path for record in result.net_ignored] == [
            f"notes_{SIBLING_PROBE}.txt"
        ]


class TestABrokenInstrumentFailsLoudly:
    """OPS-75 criterion 3, the half that is a FAILURE and not a skip.

    ``git`` being absent skips, announced by the ``tests/_toolguard.py`` banner.
    ``git`` being PRESENT and answering nothing is a different fact: it makes
    every arm above vacuously green, so it is raised.
    """

    def test_a_failing_listing_raises_rather_than_returning_empty(self, tmp_path, monkeypatch):
        not_a_repo = _sealed_non_repo(tmp_path / "not_a_repo", monkeypatch)
        with pytest.raises(GitListingUnusable) as excinfo:
            tracked_paths(not_a_repo)
        assert "git ls-files failed" in str(excinfo.value)

    def test_a_failing_check_ignore_raises_rather_than_reporting_nothing(
        self, tmp_path, monkeypatch
    ):
        """The hole a mutation found, and the reason the campaign was run.

        Removing the return-code guard from :func:`check_ignore_records` left
        every test in this module green: a failed ``git check-ignore`` writes
        nothing to stdout, an empty stdout parses into zero records, and zero
        records reads exactly like a clean bill of health. Same defect as the
        empty listing above, one command further along.
        """
        not_a_repo = _sealed_non_repo(tmp_path / "no_repo_for_check_ignore", monkeypatch)
        with pytest.raises(GitListingUnusable) as excinfo:
            check_ignore_records(not_a_repo, ("a.txt",))
        assert "git check-ignore failed" in str(excinfo.value)

    def test_an_empty_listing_raises_rather_than_passing_vacuously(self, tmp_path):
        """A real repository with a real ``.git`` and NOTHING tracked in it."""
        repo = tmp_path / "empty_repo"
        repo.mkdir()
        assert _git(repo, "init", "-q").returncode == 0
        assert _git(repo, "ls-files", "-z").returncode == 0, "git itself is fine here"
        with pytest.raises(GitListingUnusable) as excinfo:
            tracked_paths(repo)
        assert "returned NOTHING" in str(excinfo.value)

    def test_an_empty_question_raises_rather_than_answering_clean(self, tmp_path):
        repo = _throwaway_repo(tmp_path / "empty_question", "*.log\n")
        with pytest.raises(GitListingUnusable) as excinfo:
            check_ignore_records(repo, ())
        assert "NO paths" in str(excinfo.value)

    def test_a_ragged_record_stream_raises_rather_than_parsing_on(self):
        """A changed output shape must not be silently regrouped into records."""
        with pytest.raises(GitListingUnusable) as excinfo:
            parse_check_ignore_fields([".gitignore", "1", "*.log", ""])
        assert "not a whole number" in str(excinfo.value)

    def test_a_well_formed_record_stream_still_parses(self):
        """The present direction, so the arm above is not a bare negative."""
        records = parse_check_ignore_fields(
            [".gitignore", "1", "*.log", "a.log", ".gitignore", "2", "!b.log", "b.log", ""]
        )
        assert [record.path for record in records] == ["a.log", "b.log"]
        assert [record.negated for record in records] == [False, True]

    def test_the_guard_uses_the_resolved_path_git_was_found_at(self):
        """Bidirectional guard discipline, ``docs/OPERATIONS.md``.

        :func:`_toolguard.require` returns a PATH and every invocation in this
        module uses it, so what this module has is not a guard that skips when
        git is missing and does nothing when it is there.
        """
        resolved = _toolguard.require("git")
        assert Path(resolved).exists()
        proc = _git(REPO_ROOT, "rev-parse", "--is-inside-work-tree")
        assert proc.stdout.decode("ascii", "replace").strip() == "true"


class TestTheCeilingReallyStopsTheUpwardWalk:
    """``GIT_CEILING_DIRECTORIES`` in :func:`_sealed_non_repo`, pinned at last.

    Every other arm that wants a NON-repository gets one for free here, because
    this machine's temp tree is not inside a repository. That is luck, not a
    property of the code, and it is exactly why removing the ceiling used to
    survive the campaign. So the specimen builds the unlucky machine instead of
    waiting for one: a real throwaway repository with the probe directory nested
    two levels down inside it. Without the ceiling ``git`` walks up and finds
    that repository, and the arms that expect a loud failure would quietly
    audit somebody else's tree.
    """

    def test_a_probe_inside_a_repository_is_still_sealed(self, tmp_path, monkeypatch):
        outer = _throwaway_repo(tmp_path / "ceiling_nest", "*.log\n")
        probe = outer / "mid" / "probe"
        assert _sealed_non_repo(probe, monkeypatch) == probe
        with pytest.raises(GitListingUnusable) as excinfo:
            tracked_paths(probe)
        assert "git ls-files failed" in str(excinfo.value)

    def test_without_the_ceiling_the_walk_reaches_the_repository(self, tmp_path):
        """The control. If this behaved the same, the arm above would prove nothing.

        No ``monkeypatch`` and therefore no ceiling: the same nested probe
        directory resolves INTO the enclosing repository. ``git`` exits 0 and
        reports being inside a work tree, and the only reason the listing is
        empty is that ``ls-files`` is scoped to ``cwd`` - which is a different
        fact, and a different failure message, from "there is no repository
        here". Sealed says ``git ls-files failed``; unsealed says
        ``returned NOTHING``. Measured, and the distinction is the whole point:
        an unsealed probe that happened to sit at a repository ROOT would answer
        about that repository and raise nothing at all.
        """
        outer = _throwaway_repo(tmp_path / "ceiling_control", "*.log\n")
        probe = outer / "mid" / "probe"
        probe.mkdir(parents=True, exist_ok=True)
        assert "GIT_CEILING_DIRECTORIES" not in os.environ
        inside = _git(probe, "rev-parse", "--is-inside-work-tree")
        assert inside.returncode == 0
        assert inside.stdout.decode("ascii", "replace").strip() == "true"
        assert tracked_paths(outer) == (".gitignore",)
        with pytest.raises(GitListingUnusable) as excinfo:
            tracked_paths(probe)
        assert "returned NOTHING" in str(excinfo.value)


#: The members of :data:`GIT_HOOK_ENV` measured to REDIRECT a ``git`` command at
#: a different repository than its ``cwd``. The rest of that tuple is popped for
#: tidiness and because a hook exports them together; these three are the ones
#: that turn a throwaway audit into an audit of the real tree, so these are the
#: ones an arm below actually leaks on purpose.
GIT_HOOK_ENV_REDIRECTORS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")

#: A suffix chosen to be absent from every ignore source on this machine, so a
#: record carrying it can only have come from the throwaway's own ``.gitignore``.
LEAK_PROBE_SUFFIX = ".ops75leakprobe"


def _leak_the_hook_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Export this repository's hook variables, as a real pre-commit hook does.

    Set AFTER the throwaway repository is built, because ``_throwaway_repo``
    itself shells out to ``git`` and would otherwise be redirected while it was
    still creating the specimen.
    """
    monkeypatch.setenv("GIT_DIR", str(REPO_ROOT / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(REPO_ROOT))
    monkeypatch.setenv("GIT_INDEX_FILE", str(REPO_ROOT / ".git" / "index"))
    for name in GIT_HOOK_ENV_REDIRECTORS:
        assert name in GIT_HOOK_ENV, f"{name} is leaked here but not scrubbed by _clean_env"
        assert os.environ.get(name), f"{name} did not actually reach the environment"


class TestTheHookEnvironmentCannotLeakIn:
    """``_clean_env`` is load-bearing, so it is watched rather than asserted.

    ``.githooks/pre-commit`` section 3d records four tests failing inside a hook
    because git's exported hook environment reached throwaway repositories. The
    same shape here is worse than a failure: ``GIT_DIR`` pointing at this tree
    makes ``git ls-files`` inside a fresh throwaway answer about THIS repository,
    so every specimen below would quietly audit the wrong tree and report a
    clean bill of health about a population nobody asked for.

    Both commands this module runs are covered, because scrubbing one and not
    the other would be exactly as invisible.
    """

    def test_the_listing_is_about_the_throwaway_and_not_this_repository(
        self, tmp_path, monkeypatch
    ):
        repo = _throwaway_repo(tmp_path / "leak_listing", "*.log\n")
        _add(repo, "one.txt")
        outer = set(tracked_paths(REPO_ROOT))
        expected = {".gitignore", "one.txt"}
        distinctive = outer - expected
        assert distinctive, (
            "this repository must track something the throwaway does not, or a "
            "leak would be indistinguishable from a correct answer"
        )
        _leak_the_hook_environment(monkeypatch)
        answer = set(tracked_paths(repo))
        assert answer == expected, (
            "the hook environment redirected the listing: it answered about "
            f"{len(answer)} path(s) instead of the throwaway's {len(expected)}"
        )
        assert not answer & distinctive

    def test_check_ignore_reads_the_throwaway_rules_and_not_this_repository(
        self, tmp_path, monkeypatch
    ):
        repo = _throwaway_repo(tmp_path / "leak_check_ignore", f"*{LEAK_PROBE_SUFFIX}\n")
        probe_path = f"a{LEAK_PROBE_SUFFIX}"
        _leak_the_hook_environment(monkeypatch)
        records = check_ignore_records(repo, (probe_path,))
        assert [record.path for record in records] == [probe_path], (
            "the hook environment redirected check-ignore: the throwaway's own "
            f"rule for {probe_path!r} was not the one consulted"
        )
        assert records[0].pattern == f"*{LEAK_PROBE_SUFFIX}"
