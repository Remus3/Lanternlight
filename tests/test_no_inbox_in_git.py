"""Nothing under ``moon_sync_inbox/`` is ever added to git.

``ROADMAP.md`` ``OPS-35`` acceptance criterion 1. The cross-project mail
directory holds notes and whole source drops written by OTHER projects on this
machine. Those files carry no license statement, this repository is PUBLIC and
Apache-2.0, and a maintainer who credits prior authors cannot unilaterally
relicense the result - so a single one of them reaching a commit is a licensing
failure that is very hard to undo once pushed. Our own outgoing notes under
``moon_sync_inbox/_outbox/`` are equally not for git.

WHY THIS EXISTS WHEN ``.gitignore`` ALREADY IGNORES THE DIRECTORY. An ignore
rule is a default, not a guarantee. ``git add -f`` overrides it without a
warning, a future edit to ``.gitignore`` can drop the line while the tree looks
untouched, and a path can reach inside the directory through a symlink whose own
path is nowhere near it. So the load-bearing check here asserts the PROPERTY -
no tracked path resolves inside that directory - by asking git what is actually
in the index. The ignore rule is checked too, but as a SEPARATE test with its
own name, so that losing the ignore line and gaining a tracked file are two
distinguishable failures rather than one.

The checking functions take a repository root as an argument rather than reading
this one. That is what lets the suite watch the guard go RED against a throwaway
repository built in ``tmp_path`` - see
:func:`test_a_staged_inbox_file_is_reported`. Staging a sibling's unlicensed
source into THIS repository's index, even for a second, is exactly the accident
the guard exists to prevent, so the red state is reached somewhere else on
purpose.

This module deliberately does NOT reuse ``tests/_tracked.py``. That walker falls
back to a filesystem walk when git is unavailable, which is the right call for a
content-hygiene sweep and the wrong one here: "tracked" is the entire question,
and a filesystem walk would answer a different one while looking like a pass.

WHAT THIS GUARD DOES CHECK, one clause per mechanism:

* Every entry in the index whose repo-relative path lies inside
  ``moon_sync_inbox/`` - which includes ``moon_sync_inbox/_outbox/`` and any
  depth of nesting below either.
* Every entry whose path, once fully resolved on disk, lands inside the
  resolved inbox directory. This is the check that catches a tracked symlink
  sitting elsewhere in the tree and pointing in, and a path that reaches in via
  ``..`` - which git itself will not store, but the check costs nothing and does
  not depend on that belief staying true.
* Every entry recorded in the index with mode ``120000`` (a symlink), by reading
  the LINK TARGET out of the index blob and resolving it against the link's own
  directory. This one exists because Windows checkouts without symlink support
  materialise such an entry as an ordinary text file containing the target, so
  ``Path.is_symlink`` is False and the resolution check above sees nothing. The
  index is also the correct axis for the question "was this added to git".

WHAT IT IS BLIND TO, written down here because a caveat that lives only in
conversation is a lie in the artifact:

* **It reads the INDEX of ONE repository state - the current one.** It says
  nothing about history: a file committed last week and deleted since is gone
  from the index and still in the objects a clone would fetch. It says nothing
  about other branches, about stashes, or about a second worktree.
* **It cannot see an untracked file.** That is correct for this criterion (an
  untracked file has not been added to git) but it means a green result here is
  not a statement about what is sitting in the working tree.
* **Directory junctions and other NTFS reparse points that are not symlinks
  have not been measured.** ``Path.resolve`` is believed to traverse a
  directory junction on Windows; that belief is not tested by this module, and
  a junction is therefore listed as unexamined rather than as covered.
* **Case folding is applied to the containment comparison** (``os.path.normcase``
  on both sides) because NTFS is case-insensitive while the git index is not, so
  a tracked ``MOON_SYNC_INBOX/note.md`` names the same directory on disk here.
  On a case-sensitive filesystem that comparison is wider than the filesystem
  is, which can only ever over-report, never under-report.
* **It does not read a single byte of any file under the inbox**, by design.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import _toolguard
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The cross-project mail directory, repo-relative. One name, used everywhere.
INBOX_DIRNAME = "moon_sync_inbox"

#: Our own outgoing copies live here. Inside the inbox, so covered by the same
#: containment test - named explicitly so the coverage is asserted rather than
#: assumed. See ``ops/outbox.py`` and ``docs/REPLY_PATHS.md``.
OUTBOX_RELPATH = f"{INBOX_DIRNAME}/_outbox"

#: Index mode git records for a symlink entry.
SYMLINK_MODE = "120000"


class GitUnavailable(RuntimeError):
    """Raised when git could not answer. A scan of nothing is not a pass."""


def _git_bytes(repo_root: Path, *args: str) -> bytes:
    """Run a read-only git command in ``repo_root`` and return raw stdout."""
    try:
        completed = subprocess.run(
            [_toolguard.require("git"), *args],
            cwd=str(repo_root),
            capture_output=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover
        raise GitUnavailable(f"git {' '.join(args)} failed in {repo_root}") from exc
    return completed.stdout


def tracked_entries(repo_root: Path) -> list[tuple[str, str, str]]:
    """Return ``(mode, object_id, repo_relative_path)`` for every index entry.

    ``git ls-files -sz`` is used rather than a plain listing for two reasons:
    the ``-z`` form emits raw paths, so a name git would otherwise quote and
    escape is read byte-for-byte; and ``-s`` carries the index MODE, which is
    the only portable way to recognise a symlink entry on a Windows checkout.
    """
    raw = _git_bytes(repo_root, "ls-files", "-sz")
    entries: list[tuple[str, str, str]] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        head, _, path_bytes = record.partition(b"\t")
        fields = head.split()
        if len(fields) < 3:  # pragma: no cover - malformed line
            continue
        mode = fields[0].decode("ascii")
        object_id = fields[1].decode("ascii")
        path = path_bytes.decode("utf-8", "surrogateescape")
        entries.append((mode, object_id, path))
    return entries


def _normalized(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _is_inside(candidate: Path, directory: Path) -> bool:
    """True when ``candidate`` is ``directory`` itself or lies below it."""
    candidate_norm = _normalized(candidate)
    directory_norm = _normalized(directory)
    if candidate_norm == directory_norm:
        return True
    return candidate_norm.startswith(directory_norm + os.sep)


def _symlink_target_from_index(repo_root: Path, object_id: str) -> str:
    """Read a symlink entry's target text out of the index blob."""
    return _git_bytes(repo_root, "cat-file", "blob", object_id).decode("utf-8", "surrogateescape")


def offending_tracked_paths(repo_root: Path) -> list[tuple[str, str]]:
    """Return ``(path, reason)`` for every tracked path resolving in the inbox.

    An empty list is the property holding. Every element is a licensing
    incident, so the reason travels with the path - a bare list of paths would
    make a symlink finding indistinguishable from a direct one, and the two want
    different fixes.
    """
    repo_root = Path(repo_root)
    inbox = repo_root / INBOX_DIRNAME
    inbox_resolved = inbox.resolve()
    findings: list[tuple[str, str]] = []

    for mode, object_id, relpath in tracked_entries(repo_root):
        target = repo_root / relpath

        if _is_inside(target, inbox):
            findings.append((relpath, "tracked path lies inside the inbox directory"))
            continue

        if mode == SYMLINK_MODE:
            link_text = _symlink_target_from_index(repo_root, object_id).strip()
            if link_text:
                pointed_at = Path(os.path.normpath(target.parent / link_text))
                if _is_inside(pointed_at, inbox):
                    findings.append(
                        (
                            relpath,
                            "tracked symlink whose index target resolves inside "
                            f"the inbox ({link_text})",
                        )
                    )
                    continue

        try:
            resolved = target.resolve()
        except OSError:  # pragma: no cover - unreadable path
            continue
        if _is_inside(resolved, inbox_resolved):
            findings.append((relpath, f"tracked path resolves inside the inbox ({resolved})"))

    return findings


def _make_scratch_repo(root: Path) -> None:
    """Build a throwaway repository shaped like this one's inbox arrangement."""
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run([_toolguard.require("git"), "init", "-q"], cwd=str(root), check=True)
    (root / ".gitignore").write_text(f"{INBOX_DIRNAME}/\n", encoding="ascii")
    (root / "README.md").write_text("scratch\n", encoding="ascii")
    outbox = root / OUTBOX_RELPATH
    outbox.mkdir(parents=True, exist_ok=True)
    (root / INBOX_DIRNAME / "from-a-sibling.md").write_text(
        "a neighbour's note\n", encoding="ascii"
    )
    (outbox / "reply.md").write_text("our own reply\n", encoding="ascii")
    subprocess.run(
        [_toolguard.require("git"), "add", "README.md", ".gitignore"],
        cwd=str(root),
        check=True,
    )


# --------------------------------------------------------------------------
# The property, asserted against this repository.
# --------------------------------------------------------------------------


def test_no_tracked_path_resolves_inside_the_inbox() -> None:
    """The load-bearing assertion of ``OPS-35`` criterion 1."""
    try:
        entries = tracked_entries(REPO_ROOT)
        findings = offending_tracked_paths(REPO_ROOT)
    except GitUnavailable as exc:  # pragma: no cover - git is present here
        pytest.fail(
            "DID NOT RUN - could not ask git what is tracked, so this guard has "
            f"not passed, it has failed to execute: {exc}"
        )
    # A scan of nothing is not a pass. If the index came back empty, the empty
    # finding list below is a statement about a listing that never happened.
    assert entries, (
        f"git reported no tracked files at all in {REPO_ROOT}, so the clean result below is vacuous"
    )
    assert findings == [], (
        "A path under "
        f"{INBOX_DIRNAME}/ is tracked by git. This repository is PUBLIC and "
        "Apache-2.0 and those files carry no license statement. Remove it from "
        "the index before committing anything: "
        + "; ".join(f"{path} - {reason}" for path, reason in findings)
    )


def test_the_inbox_is_not_empty_so_the_check_had_something_to_be_wrong_about() -> None:
    """A guard over an absent directory proves nothing about a present one.

    This is not an assertion that mail exists - the inbox can legitimately be
    empty. It records which of the two situations the run above was in, so a
    green result is not read as stronger than it is. It fails only if the
    listing itself cannot be taken.
    """
    inbox = REPO_ROOT / INBOX_DIRNAME
    if not inbox.exists():
        pytest.skip(f"{INBOX_DIRNAME}/ does not exist in this checkout")
    assert inbox.is_dir(), f"{INBOX_DIRNAME} exists but is not a directory"


def test_outbox_paths_are_covered_by_the_containment_test() -> None:
    """Our own outgoing copies are inside the inbox, and judged the same way."""
    inbox = REPO_ROOT / INBOX_DIRNAME
    assert _is_inside(REPO_ROOT / OUTBOX_RELPATH, inbox)
    assert _is_inside(REPO_ROOT / OUTBOX_RELPATH / "deep" / "note.md", inbox)


# --------------------------------------------------------------------------
# The ignore rule, as a SEPARATE and differently-named failure.
# --------------------------------------------------------------------------


def test_gitignore_still_ignores_the_inbox() -> None:
    """``.gitignore`` still covers the inbox and its outbox subdirectory.

    Asked of git via ``check-ignore`` rather than by matching text in
    ``.gitignore``, because the question is whether a path WOULD be ignored -
    a rule can be present and overridden by a later negation, and a rule can be
    spelled several ways. ``check-ignore`` does not require the path to exist.
    """
    for relpath in (
        f"{INBOX_DIRNAME}/a-note.md",
        f"{OUTBOX_RELPATH}/a-reply.md",
        f"{INBOX_DIRNAME}/from-a-sibling/src/module.py",
    ):
        completed = subprocess.run(
            [_toolguard.require("git"), "check-ignore", "-q", "--no-index", relpath],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        assert completed.returncode == 0, (
            f"git no longer ignores {relpath}. The ignore rule is the first line "
            "of defence for a directory of other projects' unlicensed source; "
            "restore it in .gitignore."
        )


# --------------------------------------------------------------------------
# Watching the guard go red, in a throwaway repository.
# --------------------------------------------------------------------------


def test_a_staged_inbox_file_is_reported(tmp_path: Path) -> None:
    """``git add -f`` on an inbox file must be REPORTED, not tolerated.

    This is criterion 1's "watched red by staging a file from there", made
    permanent instead of performed once by hand. It runs against a throwaway
    repository so that no sibling's unlicensed source is ever staged here.

    The anchor is asserted before the result is believed: a mutation that fails
    to apply looks exactly like a passing test, so the file is confirmed to be
    reported by ``git ls-files`` in the scratch repo BEFORE the guard's verdict
    is read.
    """
    root = tmp_path / "scratch"
    _make_scratch_repo(root)

    assert offending_tracked_paths(root) == [], (
        "the scratch repo must start clean, otherwise the red state below proves nothing"
    )

    victim = f"{INBOX_DIRNAME}/from-a-sibling.md"
    subprocess.run([_toolguard.require("git"), "add", "-f", victim], cwd=str(root), check=True)

    # ANCHOR: the staging really happened.
    tracked = [path for _mode, _oid, path in tracked_entries(root)]
    assert victim in tracked, (
        "git add -f did not stage the file, so anything the guard says next is "
        f"about a repository that was never mutated. Tracked: {tracked}"
    )

    findings = offending_tracked_paths(root)
    assert [path for path, _reason in findings] == [victim]


def test_a_staged_outbox_file_is_reported(tmp_path: Path) -> None:
    """The same, for our OWN outgoing note - equally not for git."""
    root = tmp_path / "scratch_outbox"
    _make_scratch_repo(root)

    victim = f"{OUTBOX_RELPATH}/reply.md"
    subprocess.run([_toolguard.require("git"), "add", "-f", victim], cwd=str(root), check=True)

    tracked = [path for _mode, _oid, path in tracked_entries(root)]
    assert victim in tracked, f"git add -f did not stage the file. Tracked: {tracked}"

    findings = offending_tracked_paths(root)
    assert [path for path, _reason in findings] == [victim]


def test_a_tracked_symlink_pointing_into_the_inbox_is_reported(tmp_path: Path) -> None:
    """A tracked path OUTSIDE the inbox that resolves INSIDE it is a finding.

    The symlink is written into the index directly with ``git update-index
    --add --cacheinfo 120000,...`` instead of being created on disk, because
    creating a real symlink on Windows needs a privilege this session may not
    have, and because the index is the axis the criterion is about. That also
    exercises the mode-``120000`` branch, which is the one a Windows checkout
    needs.

    Both spellings a real symlink can carry are pinned, because a link target
    is resolved against the LINK'S OWN directory and not against the repository
    root. The first draft of this test used a root-relative target on a link
    inside ``docs/``, the guard correctly said nothing, and the test was the
    thing that was wrong - recorded here so the next reader does not "fix" the
    guard to match a mistake.
    """
    root = tmp_path / "scratch_symlink"
    _make_scratch_repo(root)

    links = {
        # A link at the repository root - target relative to the root.
        "borrowed.md": f"{INBOX_DIRNAME}/from-a-sibling.md",
        # A link one directory down - target has to climb out first.
        "docs/borrowed.md": f"../{INBOX_DIRNAME}/from-a-sibling.md",
    }
    for link_path, target_text in links.items():
        blob = (
            subprocess.run(
                [_toolguard.require("git"), "hash-object", "-w", "--stdin"],
                cwd=str(root),
                input=target_text.encode("ascii"),
                capture_output=True,
                check=True,
            )
            .stdout.decode("ascii")
            .strip()
        )
        subprocess.run(
            [
                _toolguard.require("git"),
                "update-index",
                "--add",
                "--cacheinfo",
                f"120000,{blob},{link_path}",
            ],
            cwd=str(root),
            check=True,
        )

    # ANCHOR: the index entries exist, and with the mode the branch keys on.
    entries = {path: mode for mode, _oid, path in tracked_entries(root)}
    for link_path in links:
        assert entries.get(link_path) == SYMLINK_MODE, (
            f"the symlink entry {link_path} was not added to the index. Entries: {entries}"
        )

    findings = offending_tracked_paths(root)
    assert sorted(path for path, _reason in findings) == sorted(links)
    assert all("symlink" in reason for _path, reason in findings)


def test_the_guard_reports_git_unavailability_rather_than_a_clean_bill(
    tmp_path: Path,
) -> None:
    """Pointed at a directory that is not a repository, it RAISES.

    Without this the failure mode is the worst possible one: a directory git
    cannot answer for yields an empty index, an empty finding list, and a green
    test that has checked nothing at all.
    """
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    with pytest.raises(GitUnavailable):
        offending_tracked_paths(not_a_repo)
