"""One-off scan of EVERY blob reachable from EVERY ref - ROADMAP ``OPS-106``.

WHY. Every hygiene guard in this repository scans the TREE. A value committed
and later removed is absent from the tree and present in every clone, and this
repository is public, so a green tree guard is not a claim about history. This
script is the history half: it walks ``git rev-list --objects --all``, reads
each blob through one ``git cat-file --batch`` process, and runs the SAME
detectors the tree guards run over it.

WHAT IT RUNS - reused, never copied, so a rule added to a detector starts
guarding history too:

* ``lanternlight.redact.iter_sensitive`` over ``FILE_SCAN_LABELS`` - the plain
  ADR-004 identifier rules, exactly as ``tests/test_no_pii.py`` scans the tree.
* ``lanternlight.redact.iter_encoded_sensitive`` - the same labels inside base64
  and hex runs. Reported as ``ENCODED:<label>``.
* ``lanternlight.redact.iter_operator_identifiers`` - only its ``GIT_IDENTITY``
  and ``GIT_IDENTITY_SPLIT`` halves, because its ``EMAIL`` half is already in
  the plain pass above and one address must be one count. The identities are
  DERIVED from the scanned repository by ``operator_git_identities``, never
  typed. ``iter_literal_joined_operator_identifiers`` runs too, reported as
  ``JOINED:<label>`` and only BEYOND what the plain value half already counted.
* ``tools.secret_scan.scan_bytes`` - the provider-credential classes, after its
  own ``self_test`` passes; a clean result from a broken detector is refused.
* The 7-bit ASCII rule of ``tests/test_ascii_hygiene.py``: any byte at or above
  0x80, in any blob whose path suffix is NOT in ``tests/_tracked.py``'s
  ``BINARY_SUFFIXES`` - the tree guard's one exemption, imported rather than
  restated. Reported as ``NON_ASCII``.

WHAT IT PRINTS. Class, hit count, distinct blob count, commit-relative path and
the first commit that introduced a flagged blob at that path. NEVER a value,
never a fragment, never a line of context: the matched text does not leave the
scanning function. A path that itself matches a detector is withheld and
described by its length, because a path is output too.

STATED LIMITS.

* ``--all`` is every ref under ``refs/`` - branches, tags, remotes and the
  ``refs/stash`` TIP. NOT COVERED: stash entries older than that tip (they
  live only in the stash reflog), any other reflog-only object, dangling or
  unreachable objects, blobs that are staged but not committed, and the
  NON-BLOB surfaces of a commit - its message and its author and committer
  fields. Only blob CONTENT is scanned. ``OPS-52`` records the ruling on the
  author and committer fields; this script says nothing about them.
* ``rev-list --objects`` names each blob by the FIRST path it was reached at,
  so a blob that lived at two paths is reported under one of them.
* The persona pass of ``redact.assert_clean`` is a LOG-TEXT mechanism that
  ``iter_sensitive`` deliberately omits for source files, as the tree guard
  does; this script inherits that scope and is not a persona scanner.
* The first-introducing commit comes from one ``git log --raw -m`` pass over
  every ref. A blob it cannot place is reported with ``first=unknown`` rather
  than a guess.

Exit 0 clean, 1 findings, 2 the scan could not run or a detector self-test
failed. A scan that did not run has not passed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
_TESTS_DIR = str(REPO_ROOT / "tests")
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

import _tracked  # noqa: E402  (the tree guards' own walker - BINARY_SUFFIXES)

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    FILE_SCAN_LABELS,
    iter_encoded_sensitive,
    iter_literal_joined_operator_identifiers,
    iter_operator_identifiers,
    iter_sensitive,
    operator_git_identities,
)
from tools import secret_scan  # noqa: E402

#: Class name for the 7-bit ASCII rule.
NON_ASCII = "NON_ASCII"

#: The value halves of the operator-identifier scan. ``EMAIL`` is excluded here
#: because the plain pass already counts it.
_VALUE_HALF_LABELS = frozenset({"GIT_IDENTITY", "GIT_IDENTITY_SPLIT"})

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_GIT_TIMEOUT_SECONDS = 600


class HistoryScanFailed(RuntimeError):
    """git or a detector could not answer. Not a clean result."""


@dataclass
class Finding:
    """One (class, path) row. Counts and a commit id - no field for a value."""

    cls: str
    path: str
    hits: int = 0
    blobs: set[str] = field(default_factory=set)
    first_commit: str = "unknown"


@dataclass
class ScanResult:
    blobs_scanned: int
    bytes_scanned: int
    refs: int
    findings: list[Finding]


def _git_env() -> dict[str, str]:
    """The ambient environment minus variables that would redirect git.

    A hook exports ``GIT_DIR`` and ``GIT_INDEX_FILE``; left in place they would
    point this scan at a different repository than ``--repo`` names.
    """
    redirecting = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"}
    return {k: v for k, v in os.environ.items() if k not in redirecting}


def _git(repo: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=_git_env(),
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HistoryScanFailed(f"git {args[0]} could not run: {exc}") from exc
    if result.returncode != 0:
        raise HistoryScanFailed(f"git {args[0]} exited {result.returncode}")
    return result.stdout


def reachable_objects(repo: Path) -> list[tuple[str, str]]:
    """``(sha, path)`` for every object reachable from every ref.

    Commits and root trees carry no path and come back with ``""``.
    """
    out = _git(Path(repo), "rev-list", "--objects", "--all")
    pairs: list[tuple[str, str]] = []
    for line in out.decode("utf-8", "surrogateescape").splitlines():
        if not line:
            continue
        sha, _, path = line.partition(" ")
        pairs.append((sha, path))
    return pairs


def _blob_shas(repo: Path, pairs: list[tuple[str, str]]) -> dict[str, str]:
    """sha -> path, for the blobs among ``pairs``."""
    if not pairs:
        return {}
    payload = "".join(sha + "\n" for sha, _ in pairs).encode("ascii")
    try:
        result = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
            cwd=repo,
            input=payload,
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
            env=_git_env(),
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise HistoryScanFailed(f"git cat-file could not run: {exc}") from exc
    if result.returncode != 0:
        raise HistoryScanFailed(f"git cat-file exited {result.returncode}")
    paths = dict(pairs)
    blobs: dict[str, str] = {}
    for line in result.stdout.decode("ascii", "replace").splitlines():
        sha, _, kind = line.partition(" ")
        if kind == "blob":
            blobs[sha] = paths.get(sha, "")
    return blobs


def _iter_blob_contents(repo: Path, shas: list[str]) -> Iterator[tuple[str, bytes]]:
    """Stream ``(sha, content)`` through ONE ``git cat-file --batch`` process.

    Input is fed from a thread so a large history cannot deadlock the pipe.
    """
    if not shas:
        return
    try:
        proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=repo,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=_git_env(),
            creationflags=_NO_WINDOW,
        )
    except OSError as exc:
        raise HistoryScanFailed(f"git cat-file could not run: {exc}") from exc
    assert proc.stdin is not None and proc.stdout is not None

    def feed() -> None:
        try:
            for sha in shas:
                proc.stdin.write(sha.encode("ascii") + b"\n")
            proc.stdin.close()
        except OSError:
            pass

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    try:
        for _ in shas:
            header = proc.stdout.readline()
            parts = header.split()
            if len(parts) != 3 or parts[1] != b"blob":
                raise HistoryScanFailed("git cat-file returned an unexpected header")
            size = int(parts[2])
            data = proc.stdout.read(size)
            proc.stdout.read(1)
            if len(data) != size:
                raise HistoryScanFailed("git cat-file returned a short blob")
            yield parts[0].decode("ascii"), data
    finally:
        writer.join(timeout=5)
        proc.stdout.close()
        proc.wait(timeout=_GIT_TIMEOUT_SECONDS)


def _first_commits(repo: Path) -> tuple[dict[str, str], dict[str, int]]:
    """blob sha -> first commit whose diff introduced it, and commit -> order.

    Oldest first by topology, with ``-m`` so a blob that only appears through a
    merge is still placed. ``setdefault`` keeps the earliest.
    """
    out = _git(
        repo,
        "log",
        "--all",
        "--topo-order",
        "--reverse",
        "--root",
        "-m",
        "--raw",
        "--no-abbrev",
        "--no-renames",
        "--format=commit %H",
    )
    first: dict[str, str] = {}
    order: dict[str, int] = {}
    current = ""
    for line in out.decode("utf-8", "surrogateescape").splitlines():
        if line.startswith("commit "):
            current = line[7:].strip()
            order.setdefault(current, len(order))
        elif line.startswith(":") and current:
            fields = line.split("\t", 1)[0].split()
            if len(fields) >= 4:
                first.setdefault(fields[3], current)
    return first, order


def _is_authored(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() not in _tracked.BINARY_SUFFIXES


def classify_blob(
    data: bytes, path: str, identities: tuple[str, ...]
) -> dict[str, int]:
    """class -> hit count for one blob. Nothing else leaves this function."""
    counts: dict[str, int] = {}

    def bump(cls: str, n: int = 1) -> None:
        if n > 0:
            counts[cls] = counts.get(cls, 0) + n

    text = data.decode("latin-1")
    for label, _matched, _offset in iter_sensitive(text, labels=FILE_SCAN_LABELS):
        bump(label)
    for label, _desc, _offset in iter_encoded_sensitive(text, labels=FILE_SCAN_LABELS):
        bump("ENCODED:" + label)
    plain_value: dict[str, int] = {}
    for label, _matched, _offset in iter_operator_identifiers(text, identities):
        if label in _VALUE_HALF_LABELS:
            bump(label)
            plain_value[label] = plain_value.get(label, 0) + 1
    joined: dict[str, int] = {}
    for label, _matched, _offset in iter_literal_joined_operator_identifiers(text, identities):
        joined[label] = joined.get(label, 0) + 1
    for label, n in joined.items():
        bump("JOINED:" + label, n - plain_value.get(label, 0))
    for finding in secret_scan.scan_bytes(data):
        bump(finding.cls)
    if _is_authored(path):
        bump(NON_ASCII, sum(1 for byte in data if byte >= 0x80))
    return counts


def _safe_path(path: str, identities: tuple[str, ...]) -> str:
    """The path, or a length-only description if the path itself is a hit."""
    if not path:
        return "<no path>"
    if any(True for _ in iter_sensitive(path, labels=FILE_SCAN_LABELS)) or any(
        True for _ in iter_operator_identifiers(path, identities)
    ):
        return f"<path withheld: {len(path)} chars>"
    return path


def scan_history(
    repo: Path | str, identities: Iterable[str] | None = None
) -> ScanResult:
    """Scan every blob reachable from every ref of ``repo``.

    ``identities=None`` derives the operator identities from ``repo`` itself;
    pass a sequence (``()`` for none) to supply them, as a test does.
    """
    repo = Path(repo)
    failures = secret_scan.self_test()
    if failures:
        raise HistoryScanFailed("secret_scan self-test failed: " + "; ".join(failures))
    ids = tuple(operator_git_identities(repo) if identities is None else identities)
    refs = [r for r in _git(repo, "for-each-ref", "--format=%(refname)").splitlines() if r]
    pairs = reachable_objects(repo)
    blobs = _blob_shas(repo, pairs)
    first, order = _first_commits(repo) if blobs else ({}, {})

    rows: dict[tuple[str, str], Finding] = {}
    scanned = 0
    total = 0
    for sha, data in _iter_blob_contents(repo, sorted(blobs)):
        scanned += 1
        total += len(data)
        path = blobs[sha]
        for cls, n in classify_blob(data, path, ids).items():
            shown = _safe_path(path, ids)
            row = rows.setdefault((cls, shown), Finding(cls=cls, path=shown))
            row.hits += n
            row.blobs.add(sha)
            commit = first.get(sha)
            if commit is not None and (
                row.first_commit == "unknown"
                or order.get(commit, 1 << 62) < order.get(row.first_commit, 1 << 62)
            ):
                row.first_commit = commit
    if scanned != len(blobs):
        raise HistoryScanFailed(f"read {scanned} of {len(blobs)} blobs")
    findings = sorted(rows.values(), key=lambda f: (f.cls, f.path))
    return ScanResult(blobs_scanned=scanned, bytes_scanned=total, refs=len(refs), findings=findings)


def format_report(result: ScanResult) -> str:
    """Counts, classes, paths and commit ids ONLY."""
    lines = [
        f"refs: {result.refs}",
        f"blobs scanned: {result.blobs_scanned}",
        f"bytes scanned: {result.bytes_scanned}",
        f"findings: {len(result.findings)}",
    ]
    totals: dict[str, list[int]] = {}
    for f in result.findings:
        entry = totals.setdefault(f.cls, [0, 0, 0])
        entry[0] += f.hits
        entry[1] += len(f.blobs)
        entry[2] += 1
    for cls in sorted(totals):
        hits, nblobs, npaths = totals[cls]
        lines.append(f"class {cls} hits={hits} blobs={nblobs} paths={npaths}")
    for f in result.findings:
        lines.append(
            f"{f.cls} hits={f.hits} blobs={len(f.blobs)} path={f.path} first={f.first_commit}"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(REPO_ROOT))
    parser.add_argument(
        "--no-derive-identities",
        action="store_true",
        help="skip the git-identity value half (the shape half still runs)",
    )
    args = parser.parse_args(argv)
    try:
        result = scan_history(args.repo, identities=() if args.no_derive_identities else None)
    except HistoryScanFailed as exc:
        sys.stderr.write(f"history_scan: DID NOT RUN - {exc}\n")
        return 2
    sys.stdout.write(format_report(result) + "\n")
    return 1 if result.findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
