"""Check that the continuity documents' sha and ``path:line`` cites resolve.

ROADMAP ``OPS-113``, the citation half. The four documents checked are
``ROADMAP.md``, ``docs/LEDGER.md`` and both archives (:data:`DOCS`). The item's
acceptance has four points and this module answers three of them; the fourth
is registration, in ``tests/test_citation_check.py`` and ``ops/preflight.py``.

THE SHA EXTRACTION RULE, STATED EXACTLY. A sha cite is a token that is

* 7 to 40 characters of LOWERCASE hex, ``[0-9a-f]`` - git prints shas in
  lowercase, and an uppercase run is a constant or a digest, never a cite;
* holding at least one letter ``a-f`` AND at least one digit. Measured
  2026-10-03: every backticked hex token in ``ROADMAP.md`` that failed to
  resolve was a pure-digit game id, buildid or byte string, so a rule that took
  any hex run would be noise. A PURE-DIGIT token is a cite only in COMMIT
  CONTEXT, below; a token with no digit at all is never one;
* a whole WORD: the characters on either side may not be a letter, digit,
  underscore or hyphen. That excludes a hex run inside a longer identifier,
  ``0x``-prefixed constants, and the hex stems in this project's note filenames
  (``...-LL-FYI-fc22e86eebe9-LL-...``). The length bound is applied to the
  whole word, so a 64-character SHA-256 digest is not cut into a 40-character
  "sha" - it is simply too long;
* NOT preceded by ``@``. ``Owner/Repo@sha`` is GitHub's own cross-repository
  reference syntax, and it is the documented way to cite a SIBLING's commit
  without it being read as one of ours;
* NOT preceded by ``/``, so a commit inside a URL path is not taken as ours;
* NOT followed by ``...``. This repository writes a truncated digest as
  ``296547c5...``; a git range uses two dots and still yields both ends;
* NOT immediately preceded by a DIGEST WORD (:data:`DIGEST_WORDS`, compared
  case-insensitively after stripping backticks and punctuation from the word's
  ends). ``sha256 1c44235c``, ``git blob d81fb50``, ``tree object 802027e`` and
  ``bytes 61895d00`` name objects that are not commits. ONLY the immediately
  preceding word counts, on purpose: a byte count earlier in the sentence
  ("150,904 bytes at commit abc1234") must not be able to hide a real cite.

THE PURE-DIGIT RULE. A 7-to-40 digit token is far more often a game item id
(``3030403``), a skill id, a Steam buildid (``24813185``), a CI run number or
an epoch than a commit, so it is taken as a sha cite ONLY when, after the
whole-word, ``@``, ``/``, ``...`` and digest-word exclusions above:

* one of the THREE preceding words (stripped and lowercased as for the digest
  word) is in :data:`COMMIT_WORDS` - ``commit 6074631``, ``the COMMITTED tree
  at 6074631``, ``a worktree at 7661391^``; or
* its nearest hex token on the same line, on either side, is a letter-bearing
  sha cite and the text between the two is only backticks, commas, spaces and
  at most one of ``,`` ``and`` ``to`` ``->`` ``..`` - a sha list or range such
  as ``commits 9380317, f12a1b9, 7971473 and 06d113c`` or
  ``434818c -> 4718293``.

Measured 2026-10-03 on the four documents: 182 pure-digit tokens matching the
whole-word token pattern, of which the rule takes 12 and all 12 are commit cites (zero false
positives). Its LIMIT, measured the same day: it MISSES two real cites,
``added by 6074631`` and ``git show 8442072:tests/...``, because neither has a
commit word within three words or a letter-bearing neighbour. Both shas are
cited elsewhere in commit context, so neither escapes the check. A pure-digit
sha written alone in prose with no commit word nearby is NOT checked, and a
green run says nothing about it.

Cites are extracted from the whole document, inside and outside backticks and
code fences alike - "HEAD e2ffe31" and "commit 0bff3f8" are cites as surely as
`` `dfe7c63` `` is.

RESOLUTION is one ``git cat-file --batch-check`` call with ``<token>^{commit}``
per unique token, which is ``git cat-file -e <sha>^{commit}`` answered in bulk.
A token that names a blob or a tree does not resolve, and neither does an
AMBIGUOUS short sha, exactly as ``-e`` would refuse it.

THE ``path:line`` EXTRACTION RULE. A cite is a relative path ending in a
dotted file name, followed by ``:N``, ``:N-M``, ``:N:col`` or ``#LN``. The path
must start at a word boundary that is not ``/``, ``.`` or ``-`` - except that a
leading ``.`` directory such as ``.claude/`` is kept. A range is checked at its
far end; a ``line:col`` pair is checked at the line. The path is resolved
against the REPOSITORY ROOT and checked only if it names an existing file; a
cite of a file that does not exist here (``m.py`` in a quoted lint message, a
sibling's ``docs/...`` path) is SKIPPED and counted, never guessed at. A line
past end of file, or line 0, is red. Lines are counted with
``str.splitlines``, so a trailing newline does not add one.

WHAT THIS DOES NOT DO, stated so a green run is not over-read:

* It does not decide whether an in-range line still says what the cite meant.
  That is acceptance point (3)'s explicit out-of-scope clause and it is not
  decidable by a program. The measured "four to six" wrong-text cites in
  ``OPS-113`` are of that class and are not caught here.
* A path wrapped across a hard line break is not seen, because extraction is
  per line. Measured 2026-10-03: two such cites exist in the archives
  (``.claude/com`` / ``mands/loop.md:48``); both have unwrapped twins nearby.
* Prose forms such as "line 233 of foo.py" are not cites under this rule.

THE ALLOWLIST, ``tools/citation_allowlist.txt``. One entry per line:
``<key> <reason> <why...>``, ``#`` comments allowed. The key is a sha token or
a ``path:N`` pair; the reason is one of :data:`SHA_REASONS` for a sha and
:data:`LINE_REASONS` for a line cite, and the why is free text that must not be
empty, so no entry is a silent mute. It may only SHRINK:
``tests/test_citation_check.py`` pins the admitted keys in
``PINNED_ALLOWLIST_KEYS`` and fails if the allowlist holds a key outside it -
no git history is consulted, so the rule holds on a fresh or shallow clone and
while the file is untracked or staged. Admitting a key means editing that
pinned set, which is the forbidden move unless a ledger entry records why. A
red check here also fails on an entry that now RESOLVES or that no document
CITES any more, so a stale row cannot linger. A NEW false positive is fixed in the
extraction rule above, reviewed as code, never by adding a row. A fresh clone
has no ``.git/filter-repo/commit-map``, which is why the pre-rewrite shas have
to be named in a tracked file rather than derived.

Run ``python -m tools.citation_check``. Exit 0 clean, 1 red, 2 usage error.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DOCS: tuple[str, ...] = (
    "ROADMAP.md",
    "docs/LEDGER.md",
    "docs/ROADMAP_ARCHIVE.md",
    "docs/LEDGER_ARCHIVE.md",
)

ALLOWLIST = "tools/citation_allowlist.txt"

SHA_REASONS: dict[str, str] = {
    "pre-rewrite": "a commit of this repository from before the 2026-09-07 "
    "history rewrite; survives only in .git/filter-repo/commit-map",
    "foreign-repo": "a commit of another repository, written before the "
    "Owner/Repo@sha convention existed",
    "throwaway": "a commit made in a scratch repository or reset away before "
    "it reached any published ref, cited as evidence of an experiment",
    "not-a-commit": "a hex token that is a digest, a tree, a blob or an id, "
    "phrased in a way the extraction rule cannot tell apart from a cite",
}

LINE_REASONS: dict[str, str] = {
    "out-of-range": "a historical path:line cite whose file has since shrunk",
}

DIGEST_WORDS = frozenset(
    {"sha256", "sha-256", "sha512", "md5", "digest", "blob", "tree", "object", "bytes", "prefix"}
)

COMMIT_WORDS = frozenset(
    {"commit", "commits", "committed", "sha", "shas", "head", "rewrite", "worktree"}
)

_COMMIT_WINDOW = 3
_LIST_GAP_RE = re.compile(r"[\s`,]*(?:,|and|to|->|\.\.)?[\s`,]*")

_SHA_RE = re.compile(r"(?<![0-9A-Za-z_@/-])[0-9a-f]{7,40}(?![0-9A-Za-z_-])(?!\.\.\.)")
_LINE_RE = re.compile(
    r"(?<![\w/.-])"
    r"(?P<path>(?:\.?[\w-][\w.-]*/)*[\w-][\w.-]*\.[A-Za-z0-9]+)"
    r"(?::(?P<line>\d+)(?:-(?P<end>\d+))?|#L(?P<anchor>\d+))"
)
_WORD_STRIP = "`*_()[]{}\"',;:."

Resolver = Callable[[Iterable[str]], set[str]]


@dataclass(frozen=True)
class AllowEntry:
    key: str
    reason: str
    why: str


@dataclass(frozen=True)
class ShaCite:
    doc: str
    line: int
    token: str


@dataclass(frozen=True)
class LineCite:
    doc: str
    line: int
    path: str
    cited_line: int
    file_lines: int


@dataclass
class Report:
    sha_cites: int = 0
    unique_shas: int = 0
    line_cites_checked: int = 0
    line_cites_skipped: int = 0
    dead_shas: list[ShaCite] = field(default_factory=list)
    allowlisted: list[ShaCite] = field(default_factory=list)
    out_of_range: list[LineCite] = field(default_factory=list)
    allowlisted_lines: list[LineCite] = field(default_factory=list)
    stale_resolvable: list[str] = field(default_factory=list)
    stale_unused: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.dead_shas or self.out_of_range or self.stale_resolvable or self.stale_unused
        )

    def format(self) -> str:
        out = [
            f"sha cites {self.sha_cites} ({self.unique_shas} unique), "
            f"line cites checked {self.line_cites_checked}, "
            f"skipped (path absent) {self.line_cites_skipped}, "
            f"allowlisted {len({c.token for c in self.allowlisted})} shas "
            f"+ {len(self.allowlisted_lines)} line cites"
        ]
        for c in self.dead_shas:
            out.append(f"DEAD SHA  {c.doc}:{c.line}  {c.token}  (not a commit here)")
        for c in self.out_of_range:
            out.append(
                f"OUT OF RANGE  {c.doc}:{c.line}  {c.path}:{c.cited_line}"
                f"  (file has {c.file_lines} lines)"
            )
        for k in self.stale_resolvable:
            out.append(f"STALE ALLOWLIST  {k} now resolves - delete the row")
        for k in self.stale_unused:
            out.append(f"STALE ALLOWLIST  {k} is cited nowhere - delete the row")
        named = sorted({c.token for c in self.allowlisted})
        if named:
            out.append("named, not hidden (allowlisted): " + " ".join(named))
        out.append("CITATIONS OK" if self.ok else "CITATIONS RED")
        return "\n".join(out)


def _prev_word(line: str, start: int) -> str:
    """The nearest preceding word that is not pure punctuation.

    A lone opening backtick is skipped rather than taken as the word, or
    ``(bytes `61895d00`)`` would see "`" and miss "bytes" - measured on the
    real ``ROADMAP.md`` the first time this ran.
    """
    for word in reversed(line[:start].split()):
        stripped = word.strip(_WORD_STRIP).lower()
        if stripped:
            return stripped
    return ""


def _prev_words(line: str, start: int, count: int) -> list[str]:
    """Up to ``count`` nearest preceding non-punctuation words, nearest first."""
    out: list[str] = []
    for word in reversed(line[:start].split()):
        stripped = word.strip(_WORD_STRIP).lower()
        if stripped:
            out.append(stripped)
            if len(out) == count:
                break
    return out


def _is_lettered_cite(line: str, m: re.Match[str]) -> bool:
    token = m.group(0)
    return (
        bool(re.search(r"[a-f]", token))
        and bool(re.search(r"[0-9]", token))
        and _prev_word(line, m.start()) not in DIGEST_WORDS
    )


def extract_shas(text: str) -> list[tuple[int, str]]:
    """``(line_number, token)`` for every sha cite, in document order."""
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), 1):
        matches = list(_SHA_RE.finditer(line))
        for i, m in enumerate(matches):
            token = m.group(0)
            if _prev_word(line, m.start()) in DIGEST_WORDS:
                continue
            if token.isdigit():
                if not _in_commit_context(line, matches, i):
                    continue
            elif not re.search(r"[0-9]", token):
                continue
            found.append((number, token))
    return found


def _in_commit_context(line: str, matches: list[re.Match[str]], i: int) -> bool:
    """The pure-digit rule in the module docstring, for ``matches[i]``."""
    m = matches[i]
    if set(_prev_words(line, m.start(), _COMMIT_WINDOW)) & COMMIT_WORDS:
        return True
    for j in (i - 1, i + 1):
        if not 0 <= j < len(matches):
            continue
        other = matches[j]
        if not _is_lettered_cite(line, other):
            continue
        gap = line[m.end():other.start()] if j > i else line[other.end():m.start()]
        if _LIST_GAP_RE.fullmatch(gap):
            return True
    return False


def extract_line_cites(text: str) -> list[tuple[int, str, int]]:
    """``(line_number, path, cited_line)``; a range yields its far end."""
    found: list[tuple[int, str, int]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for m in _LINE_RE.finditer(line):
            cited = m.group("end") or m.group("line") or m.group("anchor")
            found.append((number, m.group("path"), int(cited)))
    return found


def parse_allowlist(text: str) -> dict[str, AllowEntry]:
    entries: dict[str, AllowEntry] = {}
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 2)
        key = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        why = parts[2].strip() if len(parts) > 2 else ""
        is_line = ":" in key
        allowed = LINE_REASONS if is_line else SHA_REASONS
        if reason not in allowed:
            raise ValueError(
                f"allowlist line {number}: reason {reason!r} is not one of {sorted(allowed)}"
            )
        if not why:
            raise ValueError(f"allowlist line {number}: {key} says no why")
        if key in entries:
            raise ValueError(f"allowlist line {number}: duplicate entry {key}")
        entries[key] = AllowEntry(key, reason, why)
    return entries


def load_allowlist(path: Path) -> dict[str, AllowEntry]:
    return parse_allowlist(path.read_text(encoding="utf-8"))


def git_resolver(root: Path) -> Resolver:
    """A resolver answering "which of these name a commit" in ONE git call."""

    def resolve(tokens: Iterable[str]) -> set[str]:
        unique = sorted(set(tokens))
        if not unique:
            return set()
        completed = subprocess.run(
            ["git", "cat-file", "--batch-check"],
            cwd=root,
            input="".join(f"{t}^{{commit}}\n" for t in unique),
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        answers = completed.stdout.splitlines()
        if len(answers) != len(unique):
            raise RuntimeError(f"git answered {len(answers)} lines for {len(unique)} queries")
        return {
            t for t, a in zip(unique, answers, strict=True)
            if a.endswith(" commit") or a.split()[1:2] == ["commit"]
        }

    return resolve


def _file_lines(path: Path) -> int:
    return len(path.read_bytes().decode("utf-8", errors="replace").splitlines())


def check(
    texts: Mapping[str, str],
    allowlist: Mapping[str, AllowEntry],
    resolver: Resolver,
    tree_root: Path,
) -> Report:
    report = Report()
    sha_cites: list[ShaCite] = []
    for doc, text in texts.items():
        sha_cites.extend(ShaCite(doc, n, t) for n, t in extract_shas(text))
    report.sha_cites = len(sha_cites)
    unique = {c.token for c in sha_cites}
    report.unique_shas = len(unique)
    resolved = resolver(unique | {k for k in allowlist if ":" not in k})
    used: set[str] = set()
    for c in sha_cites:
        if c.token in resolved:
            continue
        if c.token in allowlist:
            report.allowlisted.append(c)
            used.add(c.token)
        else:
            report.dead_shas.append(c)

    line_cache: dict[str, int | None] = {}
    for doc, text in texts.items():
        for n, path, cited in extract_line_cites(text):
            if path not in line_cache:
                target = tree_root / path
                line_cache[path] = _file_lines(target) if target.is_file() else None
            total = line_cache[path]
            if total is None:
                report.line_cites_skipped += 1
                continue
            report.line_cites_checked += 1
            if 1 <= cited <= total:
                continue
            cite = LineCite(doc, n, path, cited, total)
            key = f"{path}:{cited}"
            if key in allowlist:
                report.allowlisted_lines.append(cite)
                used.add(key)
            else:
                report.out_of_range.append(cite)

    for key in sorted(allowlist):
        if ":" not in key and key in resolved:
            report.stale_resolvable.append(key)
        elif key not in used:
            report.stale_unused.append(key)
    return report


def check_repo(root: Path | str = REPO_ROOT) -> Report:
    root = Path(root)
    texts = {d: (root / d).read_text(encoding="utf-8") for d in DOCS}
    return check(texts, load_allowlist(root / ALLOWLIST), git_resolver(root), root)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(f"usage: python -m tools.citation_check  (takes no arguments; got {args})",
              file=sys.stderr)
        return 2
    report = check_repo(REPO_ROOT)
    print(report.format())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
