"""Did the object store move underneath this slice? - ``OPS-54``.

This project's default is several agents working in parallel, and they are
given non-overlapping FILE lists. That rule holds for edits and does nothing at
all for a COMMAND whose scope is the repository. ``git stash`` takes the whole
working tree and the whole index, including every file the stashing slice was
told not to touch. An agent can obey its file list perfectly and still do it.

**How this was found, which matters, because nobody was looking for it.** An
audit reported a ``git cat-file --batch-all-objects`` histogram of 1219 blobs,
303 commits and 860 trees. An independent re-derivation minutes later got 1223,
305 and 864. Neither reading was wrong: a concurrently running slice was writing
objects into the shared repository between them. ``git reflog`` then showed
``HEAD@{0}: reset: moving to HEAD`` and ``git fsck --unreachable`` listed six
unreachable commits whose subjects are the ``WIP on `` / ``index on `` pair that
``git stash`` writes - four inside that session's dispatch window, two from the
session before. An audit taken while other agents work in the repository is an
audit of a moving target, and nothing in the merge gate noticed.

What this module does about it: :func:`snapshot` records the store at dispatch,
:func:`snapshot` again at merge, and :func:`compare` says what appeared in
between and NAMES any stash-shaped commit. Naming is the whole point. A count
that rose is precisely what the original audit saw, and it told nobody anything;
the failure mode here is a number moving for an unexplained reason, so a report
that only reports the number reproduces the failure instead of catching it.

**It reports. It does not block.** And it never raises: it runs at merge time in
a repository other agents are writing to, where ``git`` may be missing, the
directory may not be a repository, and a command may hang. Every probe failure
becomes a recorded string on the snapshot. A guard that explodes at merge time
is a guard somebody deletes, and then the hazard is uncovered AND unwatched.

The perishability is worth stating plainly rather than discovering later: the
evidence lives in unreachable objects, and ``git gc --prune=now`` deletes
exactly those. Detection is after the fact and the fact does not keep forever.

Criterion 4 - the recorded decision
-----------------------------------

**Decided this session: the ban plus this detector is the accepted answer.
Ad-hoc parallel dispatch does NOT move to per-slice git worktrees.** This is a
session decision about session machinery; the operator has not ruled on it, and
it is recorded here so that a cold session finds a decision rather than an open
question it re-litigates.

The alternative - each slice in its own worktree on its own branch, as
``CLAUDE.md`` section 1b describes - makes the hazard structurally impossible
rather than merely forbidden, which is strictly better as a property. It was not
chosen because ad-hoc dispatch through the Agent tool has no worktree plumbing
today: it would need a worktree created and destroyed per slice, a branch per
slice, and a merge step the merger does not currently run. Every one of those is
a new way for a slice's work to be lost, and losing work to the fix for a
work-losing bug is a bad trade to make on a near miss.

**The cost accepted, stated so it is not rediscovered as a surprise:**

- The ban is advisory. Nothing prevents an agent from running ``git stash``.
- Detection is after the fact, so a clobber is discovered rather than prevented.
  Nothing here recovers a sibling's overwritten file.
- The evidence is perishable, as above.
- A slice that obeys the ban but crashes mid-write still leaves the shared tree
  in a half-edited state. That is a different item and this does not fix it.

Revisit it if the ban is observed being broken again after it is carried in the
dispatch ritual, because at that point "advisory" has been measured to fail.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "CommitFact",
    "DriftReport",
    "SHARED_WORKTREE_BAN",
    "STASH_SUBJECT_PREFIXES",
    "StoreSnapshot",
    "compare",
    "is_stash_subject",
    "parse_batch_check",
    "parse_commit_subject",
    "parse_unreachable",
    "snapshot",
]

#: Repository root, resolved from this file's location: ops/store_drift.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The two subjects ``git stash`` writes, in the order git writes them. The
#: trailing space is load-bearing: without it "WIPocalypse" and "reindex on
#: main" both read as stashes, and a report full of false alarms is a report
#: the reader learns to skip.
STASH_SUBJECT_PREFIXES = ("WIP on ", "index on ")

#: A git object name. Forty hex digits for SHA-1, sixty-four for a SHA-256
#: repository - both are accepted so this does not quietly report an empty
#: store on a repository built with the newer hash.
_OBJECT_NAME = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


#: Criterion 1. The enumerated ban, written where a dispatching session reads
#: it - ``ops.loop.state.in_flight_summary`` renders this verbatim, so there is
#: exactly one copy of it and no second copy to go stale.
#:
#: Derived from what git can do, not only from what has already bitten us. Two
#: of these were OBSERVED here on 2026-09-08 (``git stash`` and ``git reset``);
#: the rest are reasoned from the same property - a repo-wide scope - and are
#: banned before they are measured rather than after.
SHARED_WORKTREE_BAN = """\
NEVER run a repo-wide git command in the shared worktree - OPS-54.
Your file list scopes your EDITS. It does not scope a command whose reach is
the whole repository, and every command below reaches past it. Do experiments
in a throwaway repository under the session scratchpad instead.

  1. git stash / git stash push / git stash -u
     Takes the entire working tree and index, not your file list. A sibling's
     half-written module is removed from disk and parked on a ref the sibling
     never looks at; its next read of its own file sees pre-edit content and it
     redoes or mis-merges the work. -u also sweeps up untracked files.
  2. git stash pop / git stash apply
     Restores a whole-tree snapshot from an earlier instant on top of whatever
     siblings have written since. Overlapping files either conflict - leaving
     conflict markers in a file you were told not to touch - or apply cleanly
     over a sibling's newer content. pop then drops the stash, so the newer
     content is unrecoverable except through git fsck.
  3. git reset (mixed, the default)
     Rewrites the whole index. Every sibling's staged work is unstaged at once,
     so a sibling that staged a new file to satisfy a tracked-listing guard
     silently stops satisfying it.
  4. git reset --hard
     Rewrites index AND working tree. Every sibling's uncommitted edit is
     destroyed with no stash and no reflog entry for the file contents. This is
     the unrecoverable one: there is nothing to fsck for afterwards.
  5. git reset --soft <ref> - any reset that moves HEAD
     Moves the branch pointer under every slice at once. A sibling that commits
     next writes onto a parent it did not intend, and the merger reading
     git log gets a history that does not match what the slices did.
  6. git checkout -- . / git restore . / any pathspec wider than your own files
     Overwrites working-tree files from the index. A sibling's unstaged edits
     are gone silently, because discarding someone's work and restoring an
     unmodified file look identical to the command.
  7. git checkout <branch> / git switch
     Changes HEAD for the whole worktree. Siblings' in-progress edits are
     carried onto a branch they were not written for, or refused outright, and
     every path differing between branches is rewritten underneath them.
  8. git clean -fd / git clean -fdx
     Deletes untracked files. A sibling's brand-new module is untracked until
     it is staged, so it is deleted outright. -x also deletes gitignored
     runtime state - ops/runtime/ and moon_sync_inbox/ among it.
  9. git add -A / git add . / git add :/
     Stages every sibling's in-progress edit. Harmless alone, and it is the
     setup step for 3 and 10.
 10. git commit -a, or git commit with no pathspec after a broad add
     Commits siblings' half-finished files under your message. The merge gate
     then reads green while unfinished work sits in history.
 11. git rebase / git merge / git cherry-pick / git revert
     All rewrite working tree and index repo-wide, and all either refuse or
     clobber depending on what siblings have in flight. A rebase additionally
     rewrites shas a sibling may already have recorded.
 12. git gc --prune=now / git reflog expire --expire-unreachable=now
     Destroys the unreachable objects the OPS-54 drift detector reads, so it
     both races siblings and blinds the check to a stash that already happened.

Staging (git add of your OWN listed files) is fine. Committing is the merger's
call. If you think you need one of the twelve above, you need a throwaway repo.
"""


def _now() -> str:
    """Return the current UTC time as a second-resolution ISO 8601 string."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def is_stash_subject(subject: object) -> bool:
    """True when ``subject`` is one of the two subjects ``git stash`` writes.

    Accepts any object and answers False for anything that is not a string,
    because it is called on data read back out of a snapshot that may have come
    from a probe that half-failed.
    """
    if not isinstance(subject, str):
        return False
    return subject.startswith(STASH_SUBJECT_PREFIXES)


def parse_batch_check(text: str) -> dict[str, str]:
    """Parse ``git cat-file --batch-all-objects --batch-check`` into sha -> type.

    Each record is ``<sha> <type> <size>``. A line that is not shaped like one
    is SKIPPED rather than raised on: this parser reads the output of a command
    run against a repository other agents are writing to, and one unexpected
    line must not cost the whole reading.

    The shape check is on the sha and the size, not merely on the field count.
    Checking the count alone let any three-word line through - git's own
    warnings are three words often enough - and a junk entry in this map is a
    phantom object that :func:`compare` then reports as drift.
    """
    objects: dict[str, str] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 3 or not fields[2].isdigit():
            continue
        if not _OBJECT_NAME.fullmatch(fields[0]):
            continue
        objects[fields[0]] = fields[1]
    return objects


def parse_unreachable(text: str) -> frozenset[str]:
    """Parse ``git fsck --unreachable`` into the set of unreachable object shas.

    Only lines beginning ``unreachable`` count. ``git fsck`` also emits
    ``dangling`` records and progress chatter, and counting those as
    unreachable would report drift on a repository nobody touched.
    """
    shas = set()
    for line in text.splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0] == "unreachable" and _OBJECT_NAME.fullmatch(fields[2]):
            shas.add(fields[2])
    return frozenset(shas)


def parse_commit_subject(body: str) -> str:
    """Return the subject line of a raw commit object, or ``""`` if it has none.

    A commit object is a header block, one empty line, then the message. A PGP
    signature header continues on lines beginning with a space, so its own
    blank line is emitted as a single space and does not end the block early.
    """
    marker = body.find("\n\n")
    if marker < 0:
        return ""
    message = body[marker + 2 :]
    return message.split("\n", 1)[0].rstrip("\r")


@dataclass(frozen=True)
class CommitFact:
    """One stash-shaped commit, named rather than counted.

    Attributes:
        sha: The commit's object name.
        subject: Its subject line, e.g. ``WIP on main: 6acc6b7 Wrap the...``.
        unreachable: True when ``git fsck`` reports nothing points at it, which
            is the signature of a stash that has been popped or dropped.
    """

    sha: str
    subject: str
    unreachable: bool


@dataclass(frozen=True)
class StoreSnapshot:
    """One reading of a repository's object store.

    Attributes:
        root: The repository the reading was taken in, as a string.
        at: ISO 8601 UTC stamp of the reading.
        objects: Every object in the store, sha -> type.
        subjects: Subject line of every COMMIT object, sha -> subject. Only
            subjects, never the header block: a commit header carries an author
            and committer identity, and this snapshot is written into reports.
        unreachable: Object shas ``git fsck`` reports as unreachable.
        errors: One string per probe that failed. Empty on a clean reading.
    """

    root: str
    at: str
    objects: dict[str, str] = field(default_factory=dict)
    subjects: dict[str, str] = field(default_factory=dict)
    unreachable: frozenset[str] = frozenset()
    errors: tuple[str, ...] = ()

    @property
    def usable(self) -> bool:
        """True when every probe succeeded."""
        return not self.errors

    def histogram(self) -> dict[str, int]:
        """Return the object-type histogram - the number the audit disagreed on."""
        counts: dict[str, int] = {}
        for otype in self.objects.values():
            counts[otype] = counts.get(otype, 0) + 1
        return counts


@dataclass(frozen=True)
class DriftReport:
    """What moved between two snapshots, and what of it was stash-shaped."""

    moved: bool
    appeared: dict[str, int]
    vanished: dict[str, int]
    stash_commits: tuple[CommitFact, ...]
    before_histogram: dict[str, int]
    after_histogram: dict[str, int]
    errors: tuple[str, ...] = ()

    @property
    def answered(self) -> bool:
        """True when both snapshots were clean, so the answer means something.

        A report built on a failed probe is not "no drift". Those are different
        facts and conflating them is how a check starts lying quietly.
        """
        return not self.errors

    def format(self) -> str:
        """Render the report for a human reading a merge log."""
        lines = ["store drift (OPS-54):"]
        if self.errors:
            lines.append("  COULD NOT ANSWER - a probe failed, so this is not a clean bill:")
            lines.extend(f"    {one}" for one in self.errors)
        if not self.moved:
            lines.append(
                "  the object store did not move between the two readings"
                if self.answered
                else "  no movement seen, but see the probe failures above"
            )
        else:
            lines.append(f"  before: {_render_counts(self.before_histogram)}")
            lines.append(f"  after:  {_render_counts(self.after_histogram)}")
            if self.appeared:
                lines.append(f"  appeared: {_render_counts(self.appeared)}")
            if self.vanished:
                lines.append(
                    f"  vanished: {_render_counts(self.vanished)} "
                    "- something pruned or repacked the store under you"
                )
        if self.stash_commits:
            lines.append(f"  STASH-SHAPED COMMITS: {len(self.stash_commits)}")
            for fact in self.stash_commits:
                state = "unreachable - popped or dropped" if fact.unreachable else "live"
                lines.append(f"    {fact.sha} [{state}] {fact.subject}")
            lines.append(
                "  A stash takes the WHOLE working tree and index, including files the "
                "stashing slice was told not to touch. Check every sibling slice's "
                "files against what it believes it wrote before merging."
            )
        elif self.moved:
            lines.append(
                "  no stash-shaped commit appeared - the movement looks like ordinary "
                "commits, but any audit spanning these two readings still measured a "
                "moving target."
            )
        return "\n".join(lines)


def _render_counts(counts: dict[str, int]) -> str:
    """Render a type histogram in a stable order."""
    if not counts:
        return "nothing"
    return ", ".join(f"{key}={counts[key]}" for key in sorted(counts))


def _run(args: list[str], root: Path, timeout: float) -> tuple[str, str | None]:
    """Run a command, returning ``(stdout, error)``. Never raises.

    ``error`` is None on success and a description otherwise. Every failure
    mode a probe has at merge time is folded in here: the binary is missing,
    the directory is not a repository, the command hangs, the OS refuses.
    """
    label = " ".join(args)
    try:
        proc = subprocess.run(
            args,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return "", f"{label}: the git program was not found"
    except subprocess.TimeoutExpired:
        return "", f"{label}: timed out after {timeout}s"
    except OSError as exc:
        return "", f"{label}: {exc.__class__.__name__}: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        first = detail[0] if detail else "no output"
        return proc.stdout or "", f"{label}: exit {proc.returncode}: {first}"
    return proc.stdout or "", None


def _commit_subjects(
    shas: list[str], root: Path, git: str, timeout: float
) -> tuple[dict[str, str], str | None]:
    """Read the subject line of each commit in ``shas``. Never raises.

    Uses one ``git cat-file --batch`` rather than one process per commit. The
    output is length-framed - ``<sha> <type> <size>`` then exactly ``size``
    bytes - so it is read as bytes and sliced by the declared size rather than
    split on newlines, which a commit message full of newlines would defeat.
    """
    if not shas:
        return {}, None
    label = f"{git} cat-file --batch"
    try:
        proc = subprocess.run(
            [git, "cat-file", "--batch"],
            cwd=root,
            input=("\n".join(shas) + "\n").encode("ascii"),
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {}, f"{label}: the git program was not found"
    except subprocess.TimeoutExpired:
        return {}, f"{label}: timed out after {timeout}s"
    except OSError as exc:
        return {}, f"{label}: {exc.__class__.__name__}: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        return {}, f"{label}: exit {proc.returncode}: {detail[0] if detail else 'no output'}"

    data = proc.stdout or b""
    subjects: dict[str, str] = {}
    pos = 0
    while pos < len(data):
        end = data.find(b"\n", pos)
        if end < 0:
            break
        header = data[pos:end].decode("utf-8", "replace").split()
        if len(header) < 3 or not header[2].isdigit():
            # "<sha> missing" and anything else unexpected: skip the line only.
            pos = end + 1
            continue
        size = int(header[2])
        start = end + 1
        body = data[start : start + size].decode("utf-8", "replace")
        subjects[header[0]] = parse_commit_subject(body)
        pos = start + size + 1
    return subjects, None


def snapshot(
    root: Path | str = REPO_ROOT,
    *,
    git: str = "git",
    timeout: float = 120.0,
) -> StoreSnapshot:
    """Read a repository's object store. Never raises.

    Args:
        root: Repository to read.
        git: The git program to invoke. A parameter so a test can point it at
            a name that does not exist and prove the missing-binary path.
        timeout: Per-command timeout in seconds.

    Returns:
        The reading. ``errors`` is non-empty and ``usable`` is False if any
        probe failed; the fields that did succeed are still populated, because
        a partial reading beats no reading when the alternative is a traceback.
    """
    target = Path(root)
    errors: list[str] = []

    batch_check = [git, "cat-file", "--batch-all-objects", "--batch-check"]
    listing, error = _run(batch_check, target, timeout)
    if error:
        errors.append(error)
    objects = parse_batch_check(listing)

    fsck, error = _run([git, "fsck", "--unreachable", "--no-progress"], target, timeout)
    if error:
        errors.append(error)
    unreachable = parse_unreachable(fsck)

    commits = [sha for sha, otype in objects.items() if otype == "commit"]
    subjects, error = _commit_subjects(commits, target, git, timeout)
    if error:
        errors.append(error)

    return StoreSnapshot(
        root=str(target),
        at=_now(),
        objects=objects,
        subjects=subjects,
        unreachable=unreachable,
        errors=tuple(errors),
    )


def compare(before: StoreSnapshot, after: StoreSnapshot) -> DriftReport:
    """Say what appeared between two readings, naming any stash-shaped commit.

    Pure: it touches no repository and spawns no process, so a report can be
    re-derived from two stored snapshots long after the fact.

    Naming rather than counting is the whole contract. The failure this exists
    for is a count moving for an unexplained reason, so a report carrying only
    a count reproduces the failure it was built to catch.
    """
    appeared_shas = [sha for sha in after.objects if sha not in before.objects]
    vanished_shas = [sha for sha in before.objects if sha not in after.objects]

    appeared: dict[str, int] = {}
    for sha in appeared_shas:
        otype = after.objects[sha]
        appeared[otype] = appeared.get(otype, 0) + 1
    vanished: dict[str, int] = {}
    for sha in vanished_shas:
        otype = before.objects[sha]
        vanished[otype] = vanished.get(otype, 0) + 1

    facts = [
        CommitFact(
            sha=sha,
            subject=after.subjects[sha],
            unreachable=sha in after.unreachable,
        )
        for sha in sorted(appeared_shas)
        if after.objects[sha] == "commit" and is_stash_subject(after.subjects.get(sha))
    ]

    return DriftReport(
        moved=bool(appeared_shas or vanished_shas),
        appeared=appeared,
        vanished=vanished,
        stash_commits=tuple(facts),
        before_histogram=before.histogram(),
        after_histogram=after.histogram(),
        errors=tuple(before.errors) + tuple(after.errors),
    )
