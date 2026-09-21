"""A control whose population is OUTSIDE this repository - ROADMAP ``OPS-103`` gap 2.

WHY IT EXISTS. Every other guard in this tree has the REPOSITORY as its
population: the pre-commit gate reads the staged set and ``tests/test_no_pii.py``
walks the tracked tree. A file written outside the repository root is outside
both by construction, and no amount of strengthening a repository-scoped guard
reaches it. On 2026-09-20 this project's own files were found sitting in the
Git for Windows install root, because ``$TMPDIR`` is unset under Git Bash and a
redirect into ``"$TMPDIR/name"`` silently becomes ``/name``, which Git Bash maps
to the install root. A scan a session runs by hand is not a control; this runs
from a ``SessionStart`` hook in ``.claude/settings.json``, so it runs without
being remembered.

THE POPULATION, derived rather than hard-coded, because a literal install path
names a machine layout and a literal temp path names the account:

* the TOP LEVEL of the Git for Windows install root, found from
  ``git --exec-path`` (``<root>/mingw64/libexec/git-core``) - the measured leak
  destination;
* the TOP LEVEL of the system temp directory, ``tempfile.gettempdir()`` - the
  other place an unanchored scratch write lands.

Top level only, and files of at most :data:`MAX_BYTES`. That is a stated scope,
not a claim that nothing lives deeper.

WHAT IT REPORTS. Two classes, and only as class, count and path - never a value
(``OPS-103`` criterion 5):

* CREDENTIAL class, from ``tools/secret_scan.py``, reported for EVERY file in
  the population whoever wrote it. A live key sitting in a world-readable
  directory is worth knowing about regardless of which tree left it there.
* PII class - ``HOME_PATH`` (a path through a named user's home directory),
  ``ACCOUNT_NAME`` (the running account's name, and its 8.3 short form, derived
  from the home directory's name at run time and never stored), and ``OPERATOR_ID`` (an
  address or the derived git identity, via ``lanternlight.redact``). Listed per
  file ONLY for files ATTRIBUTED to this project; for everything else a single
  aggregate count, because another tree's file is not ours to itemise.

The PII classes OVERLAP by design: a home path spelled with the account name is
one ``HOME_PATH`` and one ``ACCOUNT_NAME``. They answer different questions -
"does this file name a home directory" and "does this file name the account" -
and the 2026-09-20 measurement that filed ``OPS-103`` counted them the same way.

ATTRIBUTION - which files are ours - uses two independent pieces of evidence and
never a guess:

* the file names this project (``lanternlight``, any case) and NO other tree on
  this machine - the rule a sibling published and this project adopted as
  falsifiable;
* or the file is NON-EMPTY and byte-identical to a blob in this repository's own
  object database - an earlier revision of one of our tracked files.

REMEDIATION. ``--remediate`` rewrites the PII occurrences IN PLACE in attributed
files only, replacing them with placeholders. It never deletes a file, and never
touches a file it cannot attribute: deleting or editing another tree's file is
not ours to do.

It always exits 0 in hook mode. A ``SessionStart`` hook that fails breaks the
session it runs in, and a finding is reported, not enforced.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import redact  # noqa: E402
from tools import secret_scan  # noqa: E402

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Files larger than this are listed as skipped, never read. The measured
#: population on 2026-09-20 had a largest file well under it; a bigger one is
#: an installer or an archive, not a scratch file.
MAX_BYTES = 4 * 1024 * 1024

RUNTIME_DIR = REPO_ROOT / "ops" / "runtime" / "outside_scan"

#: Other trees on this machine, by the word each one's files carry. A file
#: naming any of these as well as us is not attributed to us by marker.
OTHER_TREE_MARKERS: dict[str, re.Pattern[str]] = {
    "CS": re.compile(r"clockspeed", re.I),
    "LW": re.compile(r"legion[ _-]?wallpaper", re.I),
    "RC": re.compile(r"amberstone", re.I),
    "RSC": re.compile(r"resin[ _-]?compute", re.I),
    "RM": re.compile(r"red[ _-]?moon", re.I),
    "DS": re.compile(r"daemon[ _-]?slayer", re.I),
    "SS": re.compile(r"substrate", re.I),
}
OUR_MARKER = re.compile(r"lanternlight", re.I)

#: A path through a NAMED user's home directory. The separator class is built
#: with chr(92) so no heredoc or escape pass can collapse it - ``LL-0277`` is a
#: measured case of a doubled backslash arriving as one and the class then
#: matching the forward slash only. :func:`self_test` asserts both separators.
_SEP = "[" + chr(92) * 2 + "/]"
HOME_PATH = re.compile(
    r"(?i)(?:[A-Za-z]:" + _SEP + r"+|/[A-Za-z]/)Users" + _SEP + r"+"
    r"(?!(?:Public|Default|All Users|Default User)(?![A-Za-z0-9])|<)"
    r"[^" + chr(92) * 2 + r"/\s\"'<>:*?|]+"
)

PLACEHOLDER_USER = "<USER>"
PLACEHOLDER_ACCOUNT = "<ACCOUNT>"
PLACEHOLDER_OPERATOR = "<OPERATOR_ID>"

PII_CLASSES = ("HOME_PATH", "ACCOUNT_NAME", "OPERATOR_ID")


def account_name() -> str:
    """The running account's name, as the last segment of the home directory.

    Read from the home PATH, never from an environment variable's value: by
    operator ruling 2026-09-20 no code here reads environment VALUES to match
    against findings, because reading secret values is how they leak. A path
    that locates a directory is the permitted kind of read. Never stored.
    """
    try:
        return Path.home().name
    except RuntimeError:
        return ""


def _account_pattern(name: str) -> re.Pattern[str] | None:
    """The account name as a whole token, plus its 8.3 short form.

    ``None`` for a name under three characters, which would shred ordinary
    words - the same floor ``lanternlight.redact`` applies to a persona.
    """
    if len(name) < 3:
        return None
    alternatives = [re.escape(name)]
    if len(name) > 8:
        alternatives.append(re.escape(name[:6]) + r"~\d")
    return re.compile(r"(?i)(?<![A-Za-z0-9])(?:" + "|".join(alternatives) + r")(?![A-Za-z0-9])")


@dataclass
class FileResult:
    """One file's result. Classes and counts - never a value."""

    path: str
    """The real path. Used to read and remediate; NEVER printed, because the
    temp root lives under the account's home directory."""
    display: str
    """What a report prints: ``<LABEL>/name``, a root label and a basename."""
    size: int
    ours: str = ""
    """Why the file is attributed to this project, or empty when it is not."""
    credentials: dict[str, int] = field(default_factory=dict)
    pii: dict[str, int] = field(default_factory=dict)


def pii_counts(text: str, account: str, identities: tuple[str, ...]) -> dict[str, int]:
    """PII-class counts in ``text``. Counts only; the values stay here."""
    counts: dict[str, int] = {}
    homes = len(HOME_PATH.findall(text))
    if homes:
        counts["HOME_PATH"] = homes
    pattern = _account_pattern(account)
    if pattern is not None:
        names = len(pattern.findall(text))
        if names:
            counts["ACCOUNT_NAME"] = names
    ids = sum(1 for _ in redact.iter_operator_identifiers(text, identities))
    if ids:
        counts["OPERATOR_ID"] = ids
    return counts


def scrub(text: str, account: str, identities: tuple[str, ...]) -> tuple[str, int]:
    """Replace every PII-class occurrence in ``text`` with a placeholder.

    Returns the new text and the number of substitutions. Operator identifiers
    first, then the user segment of each home path, then any remaining account
    name - so a home path is rewritten once and not twice.
    """
    total = 0
    spans = sorted(
        {
            (offset, offset + len(matched))
            for _, matched, offset in redact.iter_operator_identifiers(text, identities)
        },
        reverse=True,
    )
    for start, end in spans:
        text = text[:start] + PLACEHOLDER_OPERATOR + text[end:]
        total += 1

    def _home(match: re.Match[str]) -> str:
        whole = match.group(0)
        head = re.match(r"(?i)(?:[A-Za-z]:" + _SEP + r"+|/[A-Za-z]/)Users" + _SEP + r"+", whole)
        assert head is not None
        return whole[: head.end()] + PLACEHOLDER_USER

    text, homes = HOME_PATH.subn(_home, text)
    total += homes
    pattern = _account_pattern(account)
    if pattern is not None:
        text, names = pattern.subn(PLACEHOLDER_ACCOUNT, text)
        total += names
    return text, total


def self_test(account: str = "someoneexample") -> list[str]:
    """Prove both detectors fire before a clean result is believed."""
    failures = [f"credential {f}" for f in secret_scan.self_test()]
    back = chr(92)
    for spelling in (
        "C:" + back + "Users" + back + "someone" + back + "x",
        "C:/" + "Users/someone/x",
        "/c/" + "Users/someone/x",
    ):
        if not HOME_PATH.search(spelling):
            failures.append(f"HOME_PATH missed {spelling.count(back)}-backslash spelling")
    # Spelled in pieces: tests/test_no_hardcoded_home_path.py rightly refuses a
    # whole home path in any tracked file, including one naming nobody.
    for innocent in ("C:/" + "Users/Public/x", "C:/" + "Users/<USER>/x", "the Users group"):
        if HOME_PATH.search(innocent):
            failures.append("HOME_PATH fired on an innocent spelling")
    pattern = _account_pattern(account)
    if pattern is None or not pattern.search(f"x {account} y"):
        failures.append("ACCOUNT_NAME missed its synthetic positive")
    elif pattern.search(f"x {account}z y"):
        failures.append("ACCOUNT_NAME matched inside a longer token")
    return failures


def git_install_root() -> Path | None:
    """The Git for Windows install root, from ``git --exec-path``, or ``None``."""
    try:
        out = subprocess.run(
            ["git", "--exec-path"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if out.returncode != 0:
        return None
    exec_path = Path(out.stdout.strip())
    parts = [p.lower() for p in exec_path.parts]
    for marker in ("mingw64", "mingw32", "clangarm64"):
        if marker in parts:
            return Path(*exec_path.parts[: parts.index(marker)])
    return None


def default_roots() -> list[Path]:
    roots: list[Path] = []
    git_root = git_install_root()
    if git_root is not None and git_root.is_dir():
        roots.append(git_root)
    temp = Path(tempfile.gettempdir())
    if temp.is_dir() and temp not in roots:
        roots.append(temp)
    return roots


def _objects_known_here(paths: list[Path]) -> set[Path]:
    """The subset of ``paths`` whose blob exists in this repository's objects.

    Two git processes for the whole population rather than two per file.
    """
    if not paths:
        return set()
    listing = "\n".join(str(p) for p in paths) + "\n"
    try:
        hashed = subprocess.run(
            ["git", "hash-object", "--no-filters", "--stdin-paths"],
            cwd=REPO_ROOT,
            input=listing,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=_NO_WINDOW,
        )
        if hashed.returncode != 0:
            return set()
        shas = hashed.stdout.split()
        if len(shas) != len(paths):
            return set()
        checked = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
            cwd=REPO_ROOT,
            input="\n".join(shas) + "\n",
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except OSError, subprocess.SubprocessError:
        return set()
    known = {line.split()[0] for line in checked.stdout.splitlines() if line.endswith(" blob")}
    return {p for p, sha in zip(paths, shas, strict=True) if sha in known}


def attribution(text: str) -> str:
    """``"marker"`` when ``text`` names this project and no other tree."""
    if OUR_MARKER.search(text) and not any(r.search(text) for r in OTHER_TREE_MARKERS.values()):
        return "marker"
    return ""


def root_label(root: Path, roots: list[Path]) -> str:
    """A printable name for ``root`` that carries no home-directory path."""
    git_root = git_install_root()
    if git_root is not None and root == git_root:
        return "GIT_ROOT"
    if root == Path(tempfile.gettempdir()):
        return "TEMP"
    return f"ROOT{roots.index(root)}"


def population(roots: list[Path]) -> tuple[list[Path], int]:
    """Top-level files under each root, and how many were skipped for size."""
    files: list[Path] = []
    skipped = 0
    for root in roots:
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                if not entry.is_file():
                    continue
                if entry.stat().st_size > MAX_BYTES:
                    skipped += 1
                    continue
            except OSError:
                continue
            files.append(entry)
    return files, skipped


def fingerprint(account: str, identities: tuple[str, ...]) -> str:
    """What a cached result depends on, as a digest - never the inputs.

    Every pattern's source, the account and the identities. A change to any of
    them invalidates the whole cache, so an edited pattern is never answered
    from results the old pattern produced.
    """
    parts = [p.pattern for p in secret_scan.PATTERNS.values()]
    parts += [HOME_PATH.pattern, OUR_MARKER.pattern, account.lower(), *sorted(identities)]
    parts += [r.pattern for r in OTHER_TREE_MARKERS.values()]
    return hashlib.sha256("|".join(parts).encode("utf-8", "surrogatepass")).hexdigest()


def safe_name(name: str, account: str, identities: tuple[str, ...]) -> str:
    """A basename fit to print: PII rewritten, game identifiers redacted.

    A FILENAME is output too. An adversarial pass planted a file whose NAME
    carried the account name and watched the name reach the hook's stdout and
    the cache file, while every CONTENT check stayed green. So every basename
    this module prints or persists goes through :func:`scrub` - home path,
    account name, operator identifier - and then ``lanternlight.redact``.
    """
    name = scrub(name, account, identities)[0]
    # A NAME can carry the account GLUED between letters - a path flattened
    # into a filename reads "CUsers" + account + "AppData...", which the
    # whole-token pattern cannot see. Measured live 2026-09-20 in the temp
    # root, AFTER the whole-token fix. In a display name over-redaction costs
    # nothing, so here the account is replaced as a bare substring.
    if len(account) >= 3:
        name = re.sub(re.escape(account), PLACEHOLDER_ACCOUNT, name, flags=re.I)
        if len(account) > 8:
            name = re.sub(re.escape(account[:6]) + "~", PLACEHOLDER_ACCOUNT + "~", name, flags=re.I)
    return redact.redact(name)


def _path_key(path: Path) -> str:
    """The cache key for ``path``: a digest, so the cache never holds a name."""
    return hashlib.sha256(str(path).encode("utf-8", "surrogateescape")).hexdigest()


def scan(
    roots: list[Path],
    account: str,
    identities: tuple[str, ...],
    cache: dict | None = None,
) -> tuple[list[FileResult], int, int]:
    """Scan every file in the population. Returns results, skipped, unreadable.

    ``cache`` maps a digest of each real path to the previous result for that
    file, keyed on a SHA-256 of its CONTENT. Size and mtime were the first
    key and an adversarial pass defeated it: a rewrite of the same length with
    the old mtime restored was answered from the stale row. Hashing costs one
    read of every file - measured 0.24 s for 1,444 files on 2026-09-20 - while
    the regex scan it avoids was measured at about 7 s cold, so the content key
    keeps almost all of the saving and has no such hole. The caller owns
    invalidation of the PATTERNS through :func:`fingerprint`.
    """
    cache = {} if cache is None else cache
    files, skipped = population(roots)
    labels = {root: root_label(root, roots) for root in roots}
    contents: dict[Path, tuple[bytes, str]] = {}
    unreadable = 0
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            unreadable += 1
            continue
        contents[path] = (data, hashlib.sha256(data).hexdigest())
    fresh = {
        p
        for p, (_, digest) in contents.items()
        if cache.get(_path_key(p), {}).get("sha256") != digest
    }
    by_blob = _objects_known_here([p for p in fresh if contents[p][0]])
    results: list[FileResult] = []
    for path, (data, digest) in contents.items():
        key = _path_key(path)
        if path not in fresh:
            row = cache[key]
            results.append(
                FileResult(
                    path=str(path),
                    display=row["display"],
                    size=len(data),
                    ours=row["ours"],
                    credentials=dict(row["credentials"]),
                    pii=dict(row["pii"]),
                )
            )
            continue
        text = data.decode("latin-1")
        display = f"<{labels[path.parent]}>/{safe_name(path.name, account, identities)}"
        result = FileResult(path=str(path), display=display, size=len(data))
        result.ours = attribution(text) or ("blob" if path in by_blob else "")
        creds = Counter(f.cls for f in secret_scan.scan_bytes(data))
        result.credentials = dict(creds)
        result.pii = pii_counts(text, account, identities)
        results.append(result)
        cache[key] = {
            "sha256": digest,
            "display": display,
            "ours": result.ours,
            "credentials": result.credentials,
            "pii": result.pii,
        }
    live = {_path_key(Path(r.path)) for r in results}
    for stale in [k for k in cache if k not in live]:
        del cache[stale]
    return results, skipped, unreadable


def load_cache(runtime: Path, print_: str) -> dict:
    """The cached rows, or an empty dict when absent, unreadable or stale."""
    try:
        payload = json.loads((runtime / "cache.json").read_text(encoding="ascii"))
    except OSError, ValueError:
        return {}
    if not isinstance(payload, dict) or payload.get("fingerprint") != print_:
        return {}
    rows = payload.get("rows")
    return rows if isinstance(rows, dict) else {}


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def format_report(
    results: list[FileResult], roots: list[Path], skipped: int, unreadable: int, seconds: float
) -> str:
    """The session-start report. Class, count and path ONLY."""
    ours = [r for r in results if r.ours]
    lines = [
        f"OUTSIDE-REPO SCAN (OPS-103): {len(results)} files, top level of "
        f"{len(roots)} root(s) outside the repository, {seconds:.1f}s; "
        f"{len(ours)} attributed to Lanternlight; {skipped} over size cap; "
        f"{unreadable} unreadable."
    ]
    cred_lines = [
        f"  CREDENTIAL {cls} {n} {r.display}"
        for r in results
        for cls, n in sorted(r.credentials.items())
    ]
    if cred_lines:
        hit_files = sum(1 for r in results if r.credentials)
        lines.append(f"  CREDENTIAL-class hits in {hit_files} file(s):")
        lines.extend(cred_lines)
    else:
        lines.append("  CREDENTIAL-class hits: 0")
    our_pii = [f"  PII {cls} {n} {r.display}" for r in ours for cls, n in sorted(r.pii.items())]
    if our_pii:
        lines.append(
            "  PII-class hits in files ATTRIBUTED to Lanternlight (run "
            "`python ops/outside_scan.py --remediate` to rewrite in place):"
        )
        lines.extend(our_pii)
    else:
        lines.append("  PII-class hits in files attributed to Lanternlight: 0")
    others = [r for r in results if not r.ours and r.pii]
    lines.append(
        f"  PII-class hits in files NOT attributed to us: "
        f"{sum(sum(r.pii.values()) for r in others)} in {len(others)} file(s) (not itemised)"
    )
    return "\n".join(lines)


def _write_json(target: Path, payload: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="ascii")
    tmp.replace(target)


def remediate(
    results: list[FileResult], account: str, identities: tuple[str, ...]
) -> list[tuple[str, int, int]]:
    """Rewrite PII in place in ATTRIBUTED files. Returns (path, before, after)."""
    done: list[tuple[str, int, int]] = []
    for result in results:
        if not result.ours or not result.pii:
            continue
        path = Path(result.path)
        data = path.read_bytes()
        text = data.decode("latin-1")
        before = sum(pii_counts(text, account, identities).values())
        new_text, _ = scrub(text, account, identities)
        tmp = path.with_name(path.name + ".ll-scrub.tmp")
        tmp.write_bytes(new_text.encode("latin-1"))
        tmp.replace(path)
        after = sum(pii_counts(path.read_bytes().decode("latin-1"), account, identities).values())
        done.append((result.display, before, after))
    return done


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", action="append", type=Path, help="scan this root instead of the defaults"
    )
    parser.add_argument(
        "--runtime", type=Path, default=RUNTIME_DIR, help="where the JSON report goes"
    )
    parser.add_argument("--remediate", action="store_true", help="rewrite PII in attributed files")
    parser.add_argument("--session-start", action="store_true", help="hook mode: always exit 0")
    parser.add_argument("--no-cache", action="store_true", help="re-read every file")
    args = parser.parse_args(argv)

    started = time.monotonic()
    account = account_name()
    failures = self_test()
    if failures:
        print("OUTSIDE-REPO SCAN (OPS-103): SELF-TEST FAILED - no result is reported as clean:")
        for failure in failures:
            print(f"  {failure}")
        return 0 if args.session_start else 2
    roots = args.root or default_roots()
    if not roots:
        print(
            "OUTSIDE-REPO SCAN (OPS-103): no root outside the repository could be found - NOT RUN."
        )
        return 0 if args.session_start else 2
    identities = redact.operator_git_identities(REPO_ROOT)
    print_ = fingerprint(account, identities)
    cache = {} if args.no_cache else load_cache(args.runtime, print_)
    results, skipped, unreadable = scan(roots, account, identities, cache)
    print(format_report(results, roots, skipped, unreadable, time.monotonic() - started))
    exit_code = 0
    if args.remediate:
        for path, before, after in remediate(results, account, identities):
            print(f"  REMEDIATED {path}: PII-class hits {before} -> {after}")
            if after:
                exit_code = 1
    if args.remediate:
        cache = {}  # the rewritten files have new stamps; start clean
    with contextlib.suppress(OSError):
        _write_json(args.runtime / "cache.json", {"fingerprint": print_, "rows": cache})
    with contextlib.suppress(OSError):
        _write_json(
            args.runtime / "last.json",
            {
                "roots": sorted({r.display.split("/")[0] for r in results}),
                "files": len(results),
                "skipped_over_cap": skipped,
                "unreadable": unreadable,
                "credential_files": [
                    {"path": r.display, "classes": r.credentials} for r in results if r.credentials
                ],
                "ours": [
                    {"path": r.display, "size": r.size, "why": r.ours, "pii": r.pii}
                    for r in results
                    if r.ours
                ],
                "others_pii_total": sum(sum(r.pii.values()) for r in results if not r.ours),
            },
        )
    return 0 if args.session_start else exit_code


def main(argv: list[str] | None = None) -> int:
    """Hook-safe entry: in ``--session-start`` mode no exception escapes."""
    argv = sys.argv[1:] if argv is None else argv
    if "--session-start" not in argv:
        return run(argv)
    try:
        return run(argv)
    except Exception as exc:  # a SessionStart hook must never break the session
        print(f"OUTSIDE-REPO SCAN (OPS-103): crashed, NOT RUN - {type(exc).__name__}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
