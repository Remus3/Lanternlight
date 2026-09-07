"""Which test modules read tracked Markdown - derived at run time, never listed.

ROADMAP ``OPS-31``. A wrap measures the suite, THEN writes the ledger and
roadmap entry recording that measurement, and the entry's own PROSE reddens the
tree it is committed into. It has fired three times - ``ac7fd5e``
(``LL-0087``), ``c9a0f76`` (``LL-0140``) and ``LL-0147``. The mechanism is that
several test modules READ TRACKED ``.md`` FILES and assert on their content, so
a prose edit is a code change as far as the suite is concerned, and the gate
never sees the tree that lands.

This module answers the one question a pre-commit guard needs: given a staged
``.md``, which tests could its prose possibly redden? The answer is computed
from the tree in front of it, every time.

**Why there is no list.** A hand-maintained module list is silently green over
every module added after it was written, and silently green over every doc
added after it was written. ``OPS-31`` names that exact failure mode as the
reason a sibling project's YAML list was worth copying the IDEA of and not the
wire. So :func:`tracked_docs` shells out to ``git`` on every call and
:func:`doc_reading_modules` re-reads every test module's source on every call.
Nothing here is cached; a cache is a list with extra steps.

**The idea, not the wire.** ``tests/_tracked.py`` already asks git what is
published and records why - untracked-but-not-ignored files are included
deliberately, because a brand-new file is invisible to a guard that only sees
history. The same reasoning applies here and the same behaviour is
implemented. It is NOT imported: ``tests/_tracked.py`` is importable as a
top-level ``_tracked`` only because pytest inserts ``tests/`` on ``sys.path``,
and ``ops/`` reaching into ``tests/`` for that would make this module
unimportable from the pre-commit hook, which is the one place it has to work.

**Two derivations, on purpose.** This module reads SOURCE TEXT. The audit hook
in ``tests/conftest.py`` watches REAL file opens during a suite run and
persists what it saw. Neither is trusted alone: :func:`coverage_gap` reports
modules the observed map saw opening a doc that this module did not select, and
``.githooks/pre-commit`` refuses the commit when that set is non-empty. Two
derivations disagreeing is the only signal a hole in either one produces.

WHAT THIS IS BLIND TO. Stated here, in the artifact, because a caveat that
lives only in a chat log is a lie in the artifact:

* A module that assembles a doc path at run time - ``REPO_ROOT / "docs" /
  name`` - names no doc and matches no idiom, so the static pass misses it.
  Only the observed map catches that, and only after a complete run.
* The import hop is ONE LEVEL. A test importing a helper that imports a second
  helper that reads a doc is not reached.
* :data:`DOC_READING_IDIOMS` is an enumerated set. An idiom nobody thought of
  is invisible here by construction; that is what the second derivation is for.
* Selection is deliberately GENEROUS. A module that merely names a doc in a
  docstring is selected. Over-selection costs seconds in the pre-commit hook;
  under-selection is the failure this exists to stop.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

__all__ = [
    "DOC_READING_IDIOMS",
    "OBSERVED_NAME",
    "REPO_ROOT",
    "SESSION_KEY",
    "coverage_gap",
    "doc_readers",
    "doc_reading_modules",
    "load_observed",
    "main",
    "observed_modules",
    "observed_path",
    "observed_status",
    "selected_node_ids",
    "staged_docs",
    "test_module_digests",
    "tracked_docs",
    "write_observed",
]

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The key the recorder files opens under before any module is in scope -
#: session start, and the gap between collection and the first test. It is not
#: a module and never takes part in :func:`coverage_gap`.
SESSION_KEY = "<session>"

#: Name of the persisted observed map, under ``ops/runtime/`` which is
#: gitignored. Runtime state, never committed.
OBSERVED_NAME = "docguard_observed.json"

#: Ways a module reaches tracked Markdown without naming a single file. Every
#: member was read out of this repository's own test tree before being added.
#: ``_tracked`` covers everything in ``tests/_tracked.py`` - the two walkers
#: and the constants - in one token, because importing that module at all is
#: enough to put the whole published tree in reach.
DOC_READING_IDIOMS = (
    re.compile(r"\brglob\(\s*[\"'](?:\*\*/)?\*\.md[\"']"),
    re.compile(r"\bglob\(\s*[\"'](?:\*\*/)?\*\.md[\"']"),
    re.compile(r"\biter_authored_files\b"),
    re.compile(r"\biter_scannable_files\b"),
    re.compile(r"\b_tracked\b"),
)

_GIT_TIMEOUT = 60


# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------


def _git(root: Path, args: list[str]) -> list[str] | None:
    """Run one NUL-separated git listing, or None when git cannot answer.

    None and an empty list are different facts and are kept apart. "git could
    not tell me" must never read as "there are no documents", which would make
    every caller below silently green.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]


def tracked_docs(root: Path | str = REPO_ROOT) -> tuple[str, ...]:
    """Every ``.md`` git would publish from ``root``, as relative posix paths.

    Derived from ``git ls-files`` on every call - see the module docstring for
    why there is no list and no cache.

    Untracked-but-not-ignored documents are included, for the reason
    ``tests/_tracked.py`` records: ``git ls-files`` alone lists only what is
    already in the index, so a brand-new document is invisible to the guard
    right up to the moment it lands, which is when the guard stops being able
    to help. ``--exclude-standard`` keeps ``.gitignore`` authoritative, so
    ``ops/runtime`` and the caches stay out.
    """
    root = Path(root)
    tracked = _git(root, ["ls-files", "-z", "--", "*.md"])
    if tracked is None:
        return ()
    others = _git(root, ["ls-files", "-z", "--others", "--exclude-standard", "--", "*.md"])
    names = dict.fromkeys([*tracked, *(others or [])])
    return tuple(sorted(n for n in names if n.endswith(".md")))


def staged_docs(root: Path | str = REPO_ROOT) -> tuple[str, ...]:
    """The ``.md`` paths staged for the next commit, as relative posix paths.

    Added, copied and modified only. A deletion stages no content that could
    redden anything.
    """
    root = Path(root)
    names = _git(
        root,
        ["diff", "--cached", "--name-only", "--diff-filter=ACM", "-z", "--", "*.md"],
    )
    if names is None:
        # No HEAD yet - `git diff --cached` has nothing to diff against. Fall
        # back to the empty tree so a first commit is still inspected rather
        # than silently waved through.
        empty = _git(root, ["hash-object", "-t", "tree", os.devnull])
        if not empty:
            return ()
        names = (
            _git(
                root,
                [
                    "diff",
                    "--cached",
                    "--name-only",
                    "--diff-filter=ACM",
                    "-z",
                    empty[0].strip(),
                    "--",
                    "*.md",
                ],
            )
            or []
        )
    return tuple(sorted(n for n in names if n.endswith(".md")))


# ---------------------------------------------------------------------------
# the selector
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _token_to_docs(root: Path) -> dict[str, frozenset[str]]:
    """Citable token -> the tracked docs it could denote.

    Both the full path and the basename, because source cites both:
    ``docs/LEDGER.md`` in one module and a bare ``LEDGER.md`` in the next. A
    basename can be ambiguous - ``README.md`` is both the repository's and
    ``docs/adr/README.md`` - so a token maps to a SET and a module naming it is
    treated as being about all of them. Widening here is safe; narrowing is
    what would lose a guard.
    """
    mapping: dict[str, set[str]] = {}
    for rel in tracked_docs(root):
        mapping.setdefault(rel, set()).add(rel)
        mapping.setdefault(PurePosixPath(rel).name, set()).add(rel)
    return {token: frozenset(docs) for token, docs in mapping.items()}


def _walks_docs(text: str) -> bool:
    """True when this source reaches Markdown without naming any single file."""
    return any(pattern.search(text) for pattern in DOC_READING_IDIOMS)


def _named_docs(text: str, tokens: dict[str, frozenset[str]]) -> frozenset[str]:
    """The tracked docs this source names outright."""
    named: set[str] = set()
    for token, docs in tokens.items():
        if token in text:
            named |= docs
    return frozenset(named)


def _imported_dotted_names(text: str) -> tuple[str, ...]:
    """Dotted module names this source imports, parsed rather than grepped.

    ``ast`` rather than a regex because a regex over import lines cannot tell
    ``from ops import lanes`` from the same words inside a docstring, and this
    hop decides whether a module is guarded.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level or not node.module:
                continue
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return tuple(dict.fromkeys(names))


def _helper_sources(root: Path, module_dir: Path, text: str) -> tuple[Path, ...]:
    """Resolve one level of imports to files inside ``root``.

    Only one level - see the module docstring. Resolution is by EXISTENCE
    rather than against a list of package names: ``import os`` finds no
    ``os.py`` under this repository and is dropped on its own, and a package
    added later is picked up without anyone remembering to widen a constant.
    That is the same failure mode the module docstring refuses for documents,
    and it applies just as well to directories.

    Anything outside ``root`` is dropped. The standard library and
    site-packages do not read this repository's documents, and walking them
    would make this slow for nothing.
    """
    resolved_root = root.resolve()
    found: list[Path] = []
    for dotted in _imported_dotted_names(text):
        parts = dotted.split(".")
        for base in (root, module_dir):
            for candidate in (
                base.joinpath(*parts[:-1], parts[-1] + ".py"),
                base.joinpath(*parts, "__init__.py"),
            ):
                if not candidate.is_file():
                    continue
                try:
                    inside = candidate.resolve().is_relative_to(resolved_root)
                except OSError:
                    inside = False
                if inside:
                    found.append(candidate)
    return tuple(dict.fromkeys(found))


def doc_readers(root: Path | str = REPO_ROOT) -> dict[str, frozenset[str] | None]:
    """Every ``tests/test_*.py`` that reads tracked Markdown, and WHICH.

    The value is the set of documents the module names, or ``None`` when the
    module walks for Markdown instead of naming any file - in which case every
    document is in its blast radius and it runs whatever is staged.

    A module qualifies on its own source, or through ONE level of imports
    resolved with :mod:`ast` and restricted to files under ``root``. A helper
    that walks makes its importers walkers too; a helper that names documents
    lends those names to its importers.

    Only files pytest would collect appear, so each key is directly usable as a
    pytest node id. ``conftest.py`` and ``_tracked.py`` are read as helpers but
    never returned; pytest loads the first automatically and the second holds
    no tests.
    """
    root = Path(root)
    tests_dir = root / "tests"
    if not tests_dir.is_dir():
        return {}
    tokens = _token_to_docs(root)
    helper_verdicts: dict[Path, tuple[bool, frozenset[str]]] = {}
    readers: dict[str, frozenset[str] | None] = {}
    for path in sorted(tests_dir.glob("test_*.py")):
        text = _read(path)
        rel = path.relative_to(root).as_posix()
        walks = _walks_docs(text)
        named = set(_named_docs(text, tokens))
        if not walks:
            for helper in _helper_sources(root, path.parent, text):
                verdict = helper_verdicts.get(helper)
                if verdict is None:
                    helper_text = _read(helper)
                    verdict = (_walks_docs(helper_text), _named_docs(helper_text, tokens))
                    helper_verdicts[helper] = verdict
                helper_walks, helper_named = verdict
                walks = walks or helper_walks
                named |= helper_named
        if walks:
            readers[rel] = None
        elif named:
            readers[rel] = frozenset(named)
    return readers


def doc_reading_modules(
    root: Path | str = REPO_ROOT, docs: object = None
) -> tuple[str, ...]:
    """The modules whose result could change if ``docs`` changed.

    ``docs=None`` is the conservative answer - every module that reads any
    tracked Markdown at all. Pass the STAGED documents to narrow it: a module
    that names only ``docs/FINDINGS.md`` cannot be reddened by an edit to
    ``docs/LEDGER.md``, and running it would be a tax paid on every wrap.

    Narrowing is safe only because it is guarded by the other derivation.
    :func:`coverage_gap` reports any module the recorder watched open a
    document it does not name, so a module that reaches a document by a path it
    never spells out shows up as a gap rather than as a silent miss. A module
    that WALKS for Markdown is never narrowed away - it reads whatever is
    there.
    """
    readers = doc_readers(root)
    if docs is None:
        return tuple(sorted(readers))
    wanted = frozenset(docs)
    return tuple(
        sorted(
            module
            for module, named in readers.items()
            if named is None or (named & wanted)
        )
    )


def selected_node_ids(
    root: Path | str = REPO_ROOT, docs: object = None
) -> tuple[str, ...]:
    """The pytest node ids the pre-commit hook runs for the staged documents.

    A module path IS a node id, so this is :func:`doc_reading_modules` under
    the name the caller cares about. It exists separately so the hook's
    contract does not depend on that staying true.
    """
    return doc_reading_modules(root, docs)


# ---------------------------------------------------------------------------
# the observed map - the second, independent derivation
# ---------------------------------------------------------------------------


def observed_path(root: Path | str = REPO_ROOT) -> Path:
    """Where the audit hook persists what it really saw opened."""
    return Path(root) / "ops" / "runtime" / OBSERVED_NAME


def write_observed(payload: dict, root: Path | str = REPO_ROOT) -> Path:
    """Write the observed map atomically. Returns the path written.

    Atomic because the pre-commit hook reads this file and a reader that
    catches a half-written map would refuse a good commit for no reason.
    """
    target = observed_path(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.{os.getpid()}.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
        newline="\n",
    )
    tmp.replace(target)
    return target


def load_observed(root: Path | str = REPO_ROOT) -> dict | None:
    """The persisted observed map, or None when there is not a usable one.

    None means "nothing to compare against" and is never an empty success. The
    hook treats it as a refusal; see its comment block for why.
    """
    try:
        raw = observed_path(root).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def observed_modules(root: Path | str = REPO_ROOT) -> tuple[str, ...]:
    """Modules the recorder watched really open a tracked doc."""
    data = load_observed(root)
    if not data:
        return ()
    modules = data.get("modules")
    if not isinstance(modules, dict):
        return ()
    return tuple(sorted(name for name in modules if name != SESSION_KEY))


def coverage_gap(root: Path | str = REPO_ROOT) -> tuple[str, ...]:
    """Modules the recorder caught reading a document the selector did not give
    them.

    Two kinds of gap, both reported:

    * the module is not selected at all - the static pass missed it outright;
    * the module IS selected but really opened a document it never names, so
      the per-document narrowing in :func:`doc_reading_modules` would leave it
      out for exactly that document.

    Non-empty means the static pass has a hole and the pre-commit subset is
    blind to it. This is the whole reason there are two derivations.
    """
    root = Path(root)
    data = load_observed(root)
    if not data:
        return ()
    modules = data.get("modules")
    if not isinstance(modules, dict):
        return ()
    readers = doc_readers(root)
    gaps: set[str] = set()
    for module, opened in modules.items():
        if module == SESSION_KEY:
            continue
        if module not in readers:
            gaps.add(module)
            continue
        named = readers[module]
        if named is not None and not set(opened or ()) <= set(named):
            gaps.add(module)
    return tuple(sorted(gaps))


def test_module_digests(root: Path | str = REPO_ROOT) -> dict[str, str]:
    """SHA-256 of every ``tests/*.py``, keyed by relative posix path.

    Bytes as they sit on disk, deliberately. The question is whether the tree
    in front of the hook is the tree the recorded run measured, and CRLF on
    disk against LF in a git blob is a real difference to a Python interpreter
    reading the file.
    """
    root = Path(root)
    tests_dir = root / "tests"
    digests: dict[str, str] = {}
    if not tests_dir.is_dir():
        return digests
    for path in sorted(tests_dir.glob("*.py")):
        try:
            digests[path.relative_to(root).as_posix()] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
        except OSError:
            continue
    return digests


def observed_status(root: Path | str = REPO_ROOT) -> tuple[bool, tuple[str, ...]]:
    """``(usable, reasons)`` for the persisted observed map.

    Usable means: it exists, a COMPLETE run wrote it, that run was green, it
    was written from this checkout, the test modules on disk are byte-for-byte
    the ones it measured, and it names no module the selector missed.

    A stale map is refused rather than warned about. The coverage cross-check
    can only speak about the modules it watched, so a module added or edited
    since the run is a module neither derivation covers - which is precisely
    the hole ``OPS-31`` is about.

    KNOWN LIMIT, in the artifact rather than in a chat log: staleness is
    measured over ``tests/*.py`` only. A change to ``ops/`` or
    ``lanternlight/`` that makes a helper start reading documents leaves the
    map looking current. The selector's one-level import hop is what covers
    that case, and neither mechanism covers a two-level hop.
    """
    root = Path(root)
    data = load_observed(root)
    if data is None:
        return False, (
            "no observed map at ops/runtime/" + OBSERVED_NAME,
            "run the full suite once: python -m pytest",
        )
    reasons: list[str] = []
    if not data.get("complete"):
        reasons.append("the observed map was written by a partial run")
    recorded_root = data.get("root")
    if recorded_root and Path(recorded_root) != root.resolve():
        reasons.append(f"the observed map was written from {recorded_root}")
    exitstatus = data.get("exitstatus")
    if exitstatus not in (0, "0"):
        reasons.append(f"the last complete run exited {exitstatus}, so it was not green")
    recorded = data.get("test_module_digests")
    if not isinstance(recorded, dict):
        reasons.append("the observed map records no test module digests")
    else:
        current = test_module_digests(root)
        added = sorted(set(current) - set(recorded))
        removed = sorted(set(recorded) - set(current))
        changed = sorted(k for k in set(current) & set(recorded) if current[k] != recorded[k])
        if added:
            reasons.append(f"test modules added since the run: {', '.join(added)}")
        if removed:
            reasons.append(f"test modules removed since the run: {', '.join(removed)}")
        if changed:
            reasons.append(f"test modules edited since the run: {', '.join(changed)}")
    gap = coverage_gap(root)
    if gap:
        reasons.append(
            "the recorder watched these modules open a tracked .md and the "
            f"selector did not pick them: {', '.join(gap)}"
        )
    if reasons and not data.get("complete"):
        reasons.append("run the full suite once: python -m pytest")
    return (not reasons), tuple(reasons)


# ---------------------------------------------------------------------------
# command line - the only interface /bin/sh has
# ---------------------------------------------------------------------------


_USAGE = (
    "usage: python -m ops.docguards {select|select-staged|staged-docs|check-observed}"
)


def main(argv: list[str] | None = None) -> int:
    # LF, not CRLF. The caller is /bin/sh: a trailing CR on every line survives
    # word splitting and turns `tests/test_x.py` into a filename that does not
    # exist, which pytest reports as "file or directory not found" and exits 4.
    # Measured while wiring the hook - the selector was right and the transport
    # was wrong, which is the same shape as this repository's `grep -iF` trap.
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(newline="\n")
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "select"
    if command == "select":
        # Conservative: every module that reads any tracked Markdown. Extra
        # arguments narrow it to those documents.
        for node in selected_node_ids(REPO_ROOT, args[1:] or None):
            print(node)
        return 0
    if command == "select-staged":
        # What the hook uses. The staged set is computed here rather than
        # passed in, so no quoting mistake in /bin/sh can silently narrow the
        # subset to nothing.
        staged = staged_docs(REPO_ROOT)
        if not staged:
            return 0
        for node in selected_node_ids(REPO_ROOT, staged):
            print(node)
        return 0
    if command == "staged-docs":
        for doc in staged_docs(REPO_ROOT):
            print(doc)
        return 0
    if command == "check-observed":
        usable, reasons = observed_status(REPO_ROOT)
        for reason in reasons:
            print(reason, file=sys.stderr)
        return 0 if usable else 1
    print(f"{_USAGE}\nunknown subcommand: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
