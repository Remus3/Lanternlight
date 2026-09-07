"""Tracked git hooks must be recorded EXECUTABLE in the index.

No ROADMAP id is cited here on purpose: at the time this module was written
the highest tracked item was ``OPS-31`` and nothing had been opened for this
defect, so quoting a number would have invented a cross-reference the next
cold session could not resolve. The merger that lands this owns that record.

Every file under ``.githooks/`` is a tier-0 gate: the ``pre-commit`` hook is
the second fence keeping operator PII out of a PUBLIC repository, and
``commit-msg`` is what keeps a banned glyph out of a commit message. Both are
wired by ``scripts/install_hooks.py`` setting ``core.hooksPath``.

THE DEFECT THIS GUARDS. Git refuses to run a hook that is not executable on
POSIX and reports NOTHING when it declines - no warning, no non-zero exit, no
log line. A gate that has silently stopped firing is indistinguishable from a
gate that fires and finds nothing wrong. Both tracked hooks in this repository
were measured at index mode ``100644`` on 2026-09-06.

THE HOLE IS NARROWER THAN IT LOOKS, and the narrow version is the true one:

* A clone that never runs the bootstrap is NOT affected. ``core.hooksPath`` is
  unset there, so ``.githooks/`` is never consulted and the mode is irrelevant.
* A bootstrapped clone is REPAIRED. ``install_hooks.make_executable`` chmods
  ``+x`` on POSIX before wiring the path.
* The residual is LATER-ARRIVING. A bootstrapped POSIX clone that then runs
  ``git pull`` / ``checkout`` / ``merge`` / ``reset --hard`` over a REWRITTEN
  hook file gets that file materialised at the INDEX mode, destroying the
  execute bit the bootstrap set, while ``core.hooksPath`` stays set. The gate
  then stops firing, silently.

That third bullet is git's DOCUMENTED behaviour and has NOT been reproduced.
There is no POSIX host on this machine to reproduce it on, so the load-bearing
step of the failure chain is read, not measured. Anyone who does reproduce it -
or finds it behaves otherwise - should correct this paragraph.

WHY A LOCAL GREEN TELLS YOU NOTHING - state this before believing any run of
this module. Git for Windows sets ``core.filemode=false`` and runs hooks
through ``sh`` without consulting the execute bit, so a hook at ``100644``
fires here exactly as one at ``100755`` does. This project's CI is
``runs-on: windows-latest`` and has no POSIX job, so **the behaviour this
module protects cannot be exercised on the operator's machine or on any runner
this repository currently uses.** What runs everywhere is the cheap proxy:
the recorded index mode, which is a property of the tree rather than of the
platform reading it.

WHAT IS DELIBERATELY NOT ASSERTED HERE. That a hook FIRES. Presence, wiring
and mode are three different facts and this module speaks only to the third.
The end-to-end arm - stage a banned glyph, attempt a real commit, assert HEAD
is unchanged - lives in ``tests/test_ascii_hygiene.py`` and
``tests/test_no_pii.py``. Nothing in this repository has ever measured a hook
firing on a POSIX host at either mode, and the mode flip does not change that.

THE OTHER HALF, WHICH IS WHY THIS FILE EXISTS AT ALL.
``install_hooks.make_executable`` - the one function standing between this
public repository and a silently dead gate - was graded by NOTHING before this
module. Measured 2026-09-06: there was no ``tests/test_install_hooks.py``, and
a case-insensitive search of ``tests/`` for ``install_hooks``,
``make_executable`` and ``100755`` returned zero hits. Its POSIX branch is
unreachable on Windows, so the coverage below is honest about its own limits
rather than broad and unfalsifiable - see :class:`TestMakeExecutable`.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import install_hooks  # noqa: E402

#: The directory ``core.hooksPath`` points at. Not imported from the installer
#: on purpose: this guard must keep working if that constant is renamed, and a
#: guard that reads its expectation out of the thing it grades cannot fail.
HOOKS_DIRNAME = ".githooks"

EXECUTABLE_MODE = "100755"

#: The floor. Fewer tracked hooks than this is a FAILURE, never a pass.
#:
#: Measured 2026-09-06: ``git ls-files .githooks/`` lists exactly two paths,
#: ``.githooks/commit-msg`` and ``.githooks/pre-commit``.
#:
#: WHY A COUNT AND NOT A HAND-MAINTAINED LIST OF NAMES. A name list has to be
#: edited every time a hook is added, and the edit that does not happen is
#: invisible: the new hook is simply not in the list, so it is never checked,
#: and the suite stays green while the coverage shrinks. That is the same
#: failure this floor exists to catch, moved one level up. A count cannot
#: exempt a file - a new hook is checked the moment it is tracked, because the
#: pathspec finds it - and it still refuses a listing that has collapsed. It
#: buys strictly less than a name list would in exchange for not rotting.
#:
#: The floor is the reason a stale or mistyped pathspec cannot report green:
#: an empty result is what a broken query looks like, and CLAUDE.md's "an empty
#: grep is a claim about your pattern" is exactly this lesson. Raise the number
#: when a third hook lands; never lower it to make a run go green.
MIN_TRACKED_HOOKS = 2


class IndexEntry(NamedTuple):
    """One record of ``git ls-files -s``: the index's view of a path."""

    mode: str
    blob: str
    stage: str
    path: str


def parse_ls_files_stage(payload: str) -> list[IndexEntry]:
    """Parse ``git ls-files -s -z`` output into entries.

    Format, measured rather than assumed: ``<mode> <blob> <stage>\\t<path>``
    with records separated by NUL. ``-z`` is used so a path containing a
    space, a quote or a non-ASCII byte arrives verbatim instead of being
    C-quoted by git.

    An unparsable record RAISES. A parser that skipped what it could not read
    would drop straight into the floor's blind spot - a listing silently
    shrinking to nothing is precisely how this guard would turn into
    decoration.
    """
    entries: list[IndexEntry] = []
    for record in payload.split("\0"):
        if not record:
            continue
        meta, tab, path = record.partition("\t")
        fields = meta.split()
        if not tab or not path or len(fields) != 3:
            raise ValueError(f"unparsable 'git ls-files -s' record: {record!r}")
        entries.append(IndexEntry(fields[0], fields[1], fields[2], path))
    return entries


def tracked_index_entries(
    pathspec: str = HOOKS_DIRNAME, root: Path = REPO_ROOT
) -> list[IndexEntry] | None:
    """Index entries under ``pathspec``, or ``None`` when git cannot answer.

    ``None`` and ``[]`` are different facts and conflating them is the whole
    defect this module guards against. ``None`` means the QUESTION failed -
    git is missing, or ``root`` is not a work tree, as in a source tarball;
    callers skip. ``[]`` means git answered and the answer was "nothing
    tracked there", which is a FAILURE - see :func:`floor_problem`.

    Follows ``tests/_tracked.py``: git is asked rather than the filesystem,
    because the execute bit recorded in the index is the only one a fresh
    clone materialises, and it is a fact no ``os.stat`` on Windows can report.
    """
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-s", "-z", "--", pathspec],
            cwd=root,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return parse_ls_files_stage(proc.stdout.decode("utf-8", "replace"))


def floor_problem(
    entries: list[IndexEntry], minimum: int = MIN_TRACKED_HOOKS
) -> str | None:
    """Describe a listing that has shrunk below the floor, else ``None``."""
    if len(entries) >= minimum:
        return None
    found = ", ".join(entry.path for entry in entries) or "(nothing)"
    return (
        f"expected at least {minimum} tracked file(s) under {HOOKS_DIRNAME}/, "
        f"found {len(entries)}: {found}. Either a hook was deleted or the "
        f"pathspec no longer matches - an empty listing reporting green is the "
        f"exact failure this floor exists to prevent."
    )


def mode_problems(entries: list[IndexEntry]) -> list[str]:
    """One line per entry whose index mode is not ``100755``."""
    return [
        f"  {entry.path}: index mode {entry.mode} (expected {EXECUTABLE_MODE})"
        for entry in entries
        if entry.mode != EXECUTABLE_MODE
    ]


def repair_command(entries: list[IndexEntry]) -> str:
    """The exact command that fixes the offending entries, content untouched."""
    offenders = [e.path for e in entries if e.mode != EXECUTABLE_MODE]
    return "git update-index --chmod=+x " + " ".join(offenders)


def _entries_or_skip(
    pathspec: str = HOOKS_DIRNAME, root: Path = REPO_ROOT
) -> list[IndexEntry]:
    entries = tracked_index_entries(pathspec, root)
    if entries is None:
        pytest.skip(
            f"git could not list the index under {root}; this guard reads a "
            f"git-only fact and has nothing to fall back on"
        )
    return entries


class TestTrackedHookFileModes:
    """The index must record every tracked hook as executable."""

    def test_git_lists_at_least_the_hooks_we_know_about(self) -> None:
        """A listing that finds nothing must FAIL, not pass quietly."""
        entries = _entries_or_skip()
        problem = floor_problem(entries)
        assert problem is None, problem

    def test_every_tracked_hook_is_executable_in_the_index(self) -> None:
        """Names each offender with its mode and prints the repair command."""
        entries = _entries_or_skip()

        # The floor is re-checked here rather than left to the test above.
        # This assertion is a for-comprehension over `entries`, and an empty
        # `entries` would satisfy it vacuously - a guard that passes hardest
        # when it is most broken.
        floor = floor_problem(entries)
        assert floor is None, floor

        problems = mode_problems(entries)
        assert not problems, (
            f"{len(problems)} tracked hook(s) are not {EXECUTABLE_MODE}:\n"
            + "\n".join(problems)
            + "\n\nGit refuses to run a non-executable hook on POSIX and says "
            "nothing when it declines, so this gate can stop firing silently "
            "on a third-party clone. Repair - content bytes unchanged, only "
            "the index mode:\n\n    "
            + repair_command(entries)
            + "\n\nThen commit the mode change."
        )


class TestTheFloorIsNotVacuous:
    """An empty or shrunken listing must be a failure in its own right."""

    def test_an_empty_listing_is_a_problem(self) -> None:
        assert floor_problem([]) is not None

    def test_a_shrunken_listing_is_a_problem(self) -> None:
        lone = [IndexEntry(EXECUTABLE_MODE, "0" * 40, "0", ".githooks/pre-commit")]
        problem = floor_problem(lone)
        assert problem is not None
        assert ".githooks/pre-commit" in problem

    def test_a_pathspec_matching_nothing_reaches_the_floor_not_a_skip(self) -> None:
        """The real collector, pointed at a directory with no tracked hooks.

        Measured: ``git ls-files`` exits 0 with empty output for a pathspec
        that matches nothing, so this arrives as ``[]`` rather than ``None``
        and must therefore FAIL the floor rather than skip past it.
        """
        entries = tracked_index_entries(".githooks-no-such-directory")
        if entries is None:
            pytest.skip("git could not answer at all; nothing to prove here")
        assert entries == []
        assert floor_problem(entries) is not None

    def test_a_git_tree_with_no_hooks_at_all_fails_the_floor(
        self, tmp_path: Path
    ) -> None:
        """End to end through the real subprocess, on a throwaway repository."""
        _git_init(tmp_path)
        entries = tracked_index_entries(HOOKS_DIRNAME, tmp_path)
        if entries is None:
            pytest.skip("git could not answer at all; nothing to prove here")
        assert entries == []
        assert floor_problem(entries) is not None


class TestTheModeCheckCanDistinguish:
    """Showing it can go red is half a guard; it must also go green."""

    def test_a_listing_already_at_100755_reports_no_problems(self) -> None:
        """The real parser, on real ``git ls-files -s -z`` bytes.

        The payload is a verbatim capture of the format, so this exercises the
        parser rather than a convenient reimagining of it.
        """
        payload = (
            "100755 039e4d0069c5c26909f86c505b9de66182e6d1f3 0\t"
            ".githooks/commit-msg\0"
            "100755 039e4d0069c5c26909f86c505b9de66182e6d1f3 0\t"
            ".githooks/pre-commit\0"
        )
        entries = parse_ls_files_stage(payload)
        assert [e.path for e in entries] == [
            ".githooks/commit-msg",
            ".githooks/pre-commit",
        ]
        assert floor_problem(entries) is None
        assert mode_problems(entries) == []

    def test_a_real_repository_at_100755_passes_end_to_end(
        self, tmp_path: Path
    ) -> None:
        """Construct the passing case for real, then run the whole pipeline.

        ``git update-index --chmod=+x`` sets the index mode regardless of
        ``core.filemode``, which is what makes the passing case constructible
        on Windows at all. Measured 2026-09-06 on this machine.

        Contained to ``tmp_path`` on purpose - nothing here touches the
        repository under test.
        """
        _git_init(tmp_path)
        hooks = tmp_path / HOOKS_DIRNAME
        hooks.mkdir()
        names = ("commit-msg", "pre-commit")
        for name in names:
            (hooks / name).write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        _git(tmp_path, "add", "-A")

        before = tracked_index_entries(HOOKS_DIRNAME, tmp_path)
        if before is None:
            pytest.skip("git could not answer at all; nothing to prove here")
        # Assert the setup landed BEFORE trusting anything built on it. A
        # staging step that silently added nothing looks exactly like a clean
        # bill of health once the floor is removed from the picture.
        assert sorted(e.path for e in before) == [
            f"{HOOKS_DIRNAME}/commit-msg",
            f"{HOOKS_DIRNAME}/pre-commit",
        ]
        assert mode_problems(before), (
            "a freshly added hook was expected at a non-executable index mode "
            "on this platform; the fixture proves nothing if it starts green"
        )

        _git(tmp_path, "update-index", "--chmod=+x", *(f"{HOOKS_DIRNAME}/{n}" for n in names))

        after = tracked_index_entries(HOOKS_DIRNAME, tmp_path)
        assert after is not None
        assert floor_problem(after) is None
        assert mode_problems(after) == [], (
            "the mode check reported a problem on a repository whose hooks are "
            "genuinely 100755, so it cannot distinguish and its red is worthless"
        )

    def test_an_unparsable_record_raises_rather_than_being_dropped(self) -> None:
        with pytest.raises(ValueError, match="unparsable"):
            parse_ls_files_stage("100755 deadbeef 0 no-tab-here\0")

    def test_a_short_record_raises_rather_than_being_dropped(self) -> None:
        with pytest.raises(ValueError, match="unparsable"):
            parse_ls_files_stage("100755 0\t.githooks/pre-commit\0")


class _StubStat:
    def __init__(self, st_mode: int) -> None:
        self.st_mode = st_mode


class _StubPath:
    """Only what ``make_executable`` actually touches: ``stat`` and ``chmod``.

    A recording stub, not a raising spy. A spy that raises to prove it was
    called is vacuous under fail-soft code - ``AssertionError`` is an
    ``Exception``, and code that swallows exceptions swallows the proof with
    them. ``make_executable`` currently narrows to ``OSError``, so a raise
    would propagate today, but recording the calls and asserting on them
    afterwards cannot be swallowed by any future widening of that handler.

    ``stat_calls`` is asserted explicitly for the same reason: if a call is
    ever swallowed, the count is where it shows up.
    """

    def __init__(self, modes: list[int], chmod_error: OSError | None = None) -> None:
        self._modes = list(modes)
        self._chmod_error = chmod_error
        self.chmod_calls: list[int] = []
        self.stat_calls = 0

    def stat(self) -> _StubStat:
        self.stat_calls += 1
        if not self._modes:
            raise AssertionError(
                "make_executable called stat() more often than the stub was primed for"
            )
        return _StubStat(self._modes.pop(0))

    def chmod(self, mode: int) -> None:
        self.chmod_calls.append(mode)
        if self._chmod_error is not None:
            raise self._chmod_error


class TestMakeExecutable:
    """Coverage for ``scripts/install_hooks.py``, which had none.

    WHAT THESE TESTS ESTABLISH: that the function asks for exactly the three
    execute bits, that it reports changed versus unchanged correctly, and that
    it swallows a filesystem refusal instead of aborting the bootstrap.

    WHAT THEY DO NOT ESTABLISH, AND CANNOT ON THIS PLATFORM. That a chmod
    PERSISTS. Windows has no POSIX execute bit; ``os.chmod`` there honours
    only the read-only flag, so the function's own re-stat sees the bits gone
    and correctly reports "unchanged". The single line that matters on a POSIX
    clone - the bits surviving the chmod, and git then recording ``100755`` -
    is therefore not exercised here, and this project's CI is
    ``runs-on: windows-latest``, so it is not exercised there either.
    :meth:`test_the_bits_actually_persist_on_posix` is wired for the day a
    POSIX host runs this suite; today it SKIPS everywhere, which is a visible
    hole rather than a green tick over an untested branch.

    That gap is exactly why ``TestTrackedHookFileModes`` above checks the
    RECORDED index mode instead: it is the same defect observed through a
    property of the tree, which every platform can read.
    """

    def test_it_asks_for_user_group_and_other_execute(self) -> None:
        """Pins the computed bits. Dropping any one of the three fails here."""
        stub = _StubPath([0o100644, 0o100755])
        result = install_hooks.make_executable(stub)  # type: ignore[arg-type]
        assert stub.chmod_calls == [0o100755]
        assert result is True
        assert stub.stat_calls == 2

    def test_an_already_executable_file_is_left_alone(self) -> None:
        """Idempotence: no chmod at all, and no claim of a change."""
        stub = _StubPath([0o100755])
        result = install_hooks.make_executable(stub)  # type: ignore[arg-type]
        assert stub.chmod_calls == []
        assert result is False
        assert stub.stat_calls == 1

    def test_bits_that_do_not_survive_are_reported_as_unchanged(self) -> None:
        """The Windows shape: chmod accepted, nothing persisted.

        The re-stat is load bearing. Without it the installer would print
        "(execute bit added)" on every run on Windows and read as broken.
        """
        stub = _StubPath([0o100644, 0o100644])
        result = install_hooks.make_executable(stub)  # type: ignore[arg-type]
        assert stub.chmod_calls == [0o100755]
        assert result is False
        assert stub.stat_calls == 2

    def test_a_refused_chmod_does_not_abort_the_bootstrap(self) -> None:
        stub = _StubPath([0o100644], chmod_error=PermissionError("denied"))
        result = install_hooks.make_executable(stub)  # type: ignore[arg-type]
        assert stub.chmod_calls == [0o100755]
        assert result is False
        assert stub.stat_calls == 1

    def test_a_missing_path_is_false_not_an_exception(self, tmp_path: Path) -> None:
        """Real filesystem, no stub: the installer must not die on a gap."""
        missing = tmp_path / "no-such-hook"
        assert not missing.exists()
        assert install_hooks.make_executable(missing) is False

    def test_it_is_idempotent_against_a_real_file(self, tmp_path: Path) -> None:
        """Platform-independent invariant, asserted on a real file.

        The FIRST call differs by platform - True on POSIX where the bits
        stick, False on Windows where they do not - so it is deliberately not
        asserted. The second call must report no change on either, and that is
        the property the installer's console output depends on.
        """
        target = tmp_path / "hook"
        target.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        first = install_hooks.make_executable(target)
        assert first in (True, False)
        assert install_hooks.make_executable(target) is False

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows has no POSIX execute bit; chmod cannot persist one",
    )
    def test_the_bits_actually_persist_on_posix(self, tmp_path: Path) -> None:
        """The load-bearing outcome, on the only platform that can show it.

        This is the assertion the operator's machine and this project's
        windows-latest CI can never run. It is here so a POSIX clone, or a
        future runner, grades the branch instead of nobody grading it.
        """
        target = tmp_path / "hook"
        target.write_text("#!/bin/sh\nexit 0\n", encoding="ascii")
        target.chmod(0o644)

        assert install_hooks.make_executable(target) is True

        mode = target.stat().st_mode
        assert mode & stat.S_IXUSR
        assert mode & stat.S_IXGRP
        assert mode & stat.S_IXOTH


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run git inside a throwaway tree, failing loudly if it does not work."""
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr.strip()}"
    return proc


def _git_init(root: Path) -> None:
    """Initialise an isolated repository, or skip if git is not runnable."""
    try:
        subprocess.run(
            ["git", "init", "-q", "."],
            cwd=root,
            capture_output=True,
            timeout=60,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        pytest.skip("git is not runnable here, so no temporary repository is possible")
    assert (root / ".git").is_dir(), "git init reported success but made no .git"
