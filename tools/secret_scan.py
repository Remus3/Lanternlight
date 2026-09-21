"""Provider-credential detector - ROADMAP ``OPS-103`` gap 1.

WHY THIS IS A SEPARATE MODULE. ``lanternlight/redact.py`` is scoped to OPERATOR
IDENTIFIERS by design and by ``ADR-004`` - persona, SteamID64, the game's
platform ids, the git identity. A provider API key is a different CLASS of
data, and ``OPS-103`` says in so many words that this item is not a licence to
widen ``redact.py``: conflating the two in one module would make both harder
to reason about. Measured 2026-09-20 before this module existed: ZERO
credential-shaped detections anywhere in the tracked tree, because nothing
looked.

WHAT IT REPORTS, AND WHAT IT NEVER REPORTS (criterion 5). A :class:`Finding`
is a class name and a line number. There is no field that could carry the
matched value, in full, in part or redacted, and that is structural rather
than a promise: the matched text never leaves :func:`scan_text`. A partially
redacted secret in a report is still a secret in a report, and this repository
publishes its reports.

WHERE IT RUNS.

* At commit time over the STAGED SET, through ``tools/precommit_gate.py
  secrets-staged``, which ``.githooks/pre-commit`` calls. The staged BLOB is
  read with ``git show :<path>``, never the working-tree copy, because the two
  can differ and only one of them lands.
* Outside the repository, through ``ops/outside_scan.py``, which a
  ``SessionStart`` hook runs so that it does not depend on being remembered.

PATTERN DESIGN. Every pattern is anchored on a vendor PREFIX or on an explicit
context word, so the false-positive budget is spent where the shape is least
ambiguous. The measured false-positive rate over this repository's full tracked
tree is ZERO, and ``tests/test_secret_scan.py`` holds it there rather than
recording it once. If it goes red, the remedy is to narrow a pattern AND add
the case as a negative specimen - never to exclude a file, which would make a
path a place where a real key can live unseen.

THE SPECIMENS below are INVENTED and ASSEMBLED AT RUN TIME. This file is
committed through the gate it implements and sits in a public repository that
GitHub scans for exactly these shapes, so a literal specimen would refuse its
own commit and look like a leak. :func:`self_test` runs every positive and
every negative, and a caller that is about to report "clean" runs it first:
a detector whose pattern silently stopped matching looks exactly like a clean
tree.

STATED LIMITS, so nobody assumes more coverage than exists:

* An unprefixed secret - a bare 40-character AWS SECRET access key, a random
  password in prose - is caught only by ``ASSIGNED_SECRET``, which needs a
  context word (``api_key``, ``password``, ...) and a QUOTED literal of 12 or
  more characters mixing letters and digits. A secret with no context word
  and no vendor prefix is not detected; there is no pattern for "random-looking
  string" that would not fire on every hash in this repository.
* ``ASSIGNED_SECRET`` declines a value opening with ``<``, ``$``, ``%``, ``{``
  or ``*`` (a placeholder or an interpolation), and a value with no digit. An
  all-letter password assigned in a config file is therefore a blind spot,
  chosen because the alternative fires on every assigned English word.
* UTF-16 text IS reached, through :func:`scan_bytes`'s wide view. UTF-16
  is the only non-ASCII encoding reached: UTF-32, and any encoding with no
  NUL half, is not.
* Encoded content (base64 of a key, a key split across a string
  concatenation) is not decoded. This module deliberately does not repeat
  ``redact.py``'s encoded pass.
* ``BEARER_TOKEN`` requires a digit AND a letter in a 20-plus character token,
  so a bearer token of letters only is not caught.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

#: See ``tools/precommit_gate.py`` - a console-subsystem child of a windowless
#: parent flashes a window unless the spawn carries this flag. 0 elsewhere.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Characters a vendor token body may use. The negative look-behind on each
#: prefixed pattern stops a match starting in the MIDDLE of a longer token.
_TOK = r"[A-Za-z0-9_-]"

#: class name -> compiled pattern. ORDER is report order.
PATTERNS: dict[str, re.Pattern[str]] = {
    "ANTHROPIC_ADMIN_KEY": re.compile(r"(?<![A-Za-z0-9_-])sk-ant-admin\d{2}-" + _TOK + r"{20,}"),
    "ANTHROPIC_API_KEY": re.compile(r"(?<![A-Za-z0-9_-])sk-ant-api\d{2}-" + _TOK + r"{20,}"),
    "OPENAI_PROJECT_KEY": re.compile(r"(?<![A-Za-z0-9_-])sk-proj-" + _TOK + r"{20,}"),
    # The legacy and service-account shapes. The look-ahead hands every
    # Anthropic and project key to its own class, so one secret is one count.
    "OPENAI_KEY": re.compile(
        r"(?<![A-Za-z0-9_-])sk-(?!ant-|proj-)(?:[a-z]+-)?(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{32,}"
    ),
    "AWS_ACCESS_KEY_ID": re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])"),
    "GITHUB_TOKEN": re.compile(r"(?<![A-Za-z0-9_])gh[pousr]_[A-Za-z0-9]{36,}"),
    "GITHUB_FINE_GRAINED_PAT": re.compile(
        r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9]{20,}_[A-Za-z0-9]{40,}"
    ),
    "GOOGLE_API_KEY": re.compile(r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}"),
    "SLACK_TOKEN": re.compile(r"(?<![A-Za-z0-9])xox[abpr]-[0-9]{6,}-[A-Za-z0-9-]{8,}"),
    "BEARER_TOKEN": re.compile(
        r"(?<![A-Za-z0-9])[Bb]earer[ \t]+"
        r"(?=[A-Za-z0-9._~+/-]*[0-9])(?=[A-Za-z0-9._~+/-]*[A-Za-z])"
        r"[A-Za-z0-9._~+/-]{20,}=*"
    ),
    "JWT": re.compile(
        r"(?<![A-Za-z0-9_-])eyJ" + _TOK + r"{10,}\.eyJ" + _TOK + r"{10,}\." + _TOK + r"{10,}"
    ),
    "PRIVATE_KEY_HEADER": re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----"),
    "ASSIGNED_SECRET": re.compile(
        r"(?i)(?<![A-Za-z0-9])"
        r"(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token"
        r"|private[_-]?key|password|passwd|secret)"
        r"[\"']?[ \t]*(?::=|=|:)[ \t]*"
        r"(?P<q>[\"'])(?![<$%{*])(?=[^\"'\s]*[0-9])(?=[^\"'\s]*[A-Za-z])[^\"'\s]{12,}(?P=q)"
    ),
}

#: The declared class names, in report order.
CLASSES: tuple[str, ...] = tuple(PATTERNS)


@dataclass(frozen=True)
class Finding:
    """One detection. A class and a 1-based line number - and NOTHING ELSE.

    There is deliberately no field for the matched text. ``OPS-103`` criterion
    5: no detector output ever carries a value, not in full, not in part, not
    redacted.
    """

    cls: str
    line: int


def scan_text(text: str) -> list[Finding]:
    """Every credential-class detection in ``text``, in class then line order."""
    findings: list[Finding] = []
    if not text:
        return findings
    for cls, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(Finding(cls, text.count("\n", 0, match.start()) + 1))
    return findings


def scan_bytes(data: bytes) -> list[Finding]:
    """:func:`scan_text` over raw bytes, narrow AND wide.

    The narrow view decodes latin-1: every pattern is ASCII, so that is a
    lossless, never-failing decode that keeps line counts. Binary files are
    scanned rather than skipped: a key does not stop being a key because it
    sits in a file with a NUL in it.

    THE WIDE VIEW, added after an adversarial pass planted a UTF-16 key and
    watched it walk through: ASCII stored as UTF-16 has a NUL between every
    character, so no narrow pattern can match it. When the data carries any
    NUL, the NULs are removed and the result is scanned again. A class is
    reported from the wide view only BEYOND the count the narrow view already
    found, so a narrow key in a file that merely contains NULs elsewhere is
    one finding and not two. Line numbers from the wide view are line numbers
    of the NUL-stripped text. Stripping every NUL can in principle join
    fragments of unrelated binary fields into a key shape; every pattern here
    is anchored on a vendor prefix or a context word, and the full published
    tree still measures zero findings with this view on.
    """
    narrow = scan_text(data.decode("latin-1"))
    if b"\x00" not in data:
        return narrow
    wide = scan_text(data.replace(b"\x00", b"").decode("latin-1"))
    seen = Counter(f.cls for f in narrow)
    extra: list[Finding] = []
    for finding in wide:
        if seen[finding.cls] > 0:
            seen[finding.cls] -= 1
        else:
            extra.append(finding)
    return narrow + extra


def format_report(findings_by_path: Mapping[str, Iterable[Finding]]) -> str:
    """``CLASS count path`` per line, sorted. Class, count and path ONLY."""
    lines: list[str] = []
    for path in sorted(findings_by_path):
        counts = Counter(f.cls for f in findings_by_path[path])
        for cls in CLASSES:
            if counts.get(cls):
                lines.append(f"{cls} {counts[cls]} {path}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Runtime self-test. Specimens are INVENTED and assembled here, never literal.
# ---------------------------------------------------------------------------


def _specimens() -> dict[str, tuple[str, str]]:
    """class -> (synthetic positive, near-miss negative), built at run time."""
    body = "Wm3" * 10 + "Tq8"
    upper = "ZK9W" * 4

    def j(*parts: str) -> str:
        return "".join(parts)

    return {
        "ANTHROPIC_ADMIN_KEY": (
            j("sk-", "ant-", "admin", "01-", body),
            j("sk-", "ant-", "admin", "01-", "x"),
        ),
        "ANTHROPIC_API_KEY": (
            j("sk-", "ant-", "api", "03-", body),
            j("sk-", "ant-", "api", "-", body),
        ),
        "OPENAI_PROJECT_KEY": (j("sk-", "proj-", body), j("sk-", "proj-", "short")),
        "OPENAI_KEY": (j("sk-", body, "A1"), j("sk-", "learn")),
        "AWS_ACCESS_KEY_ID": (j("AS", "IA", upper), j("AS", "IA", upper[:10])),
        "GITHUB_TOKEN": (j("gh", "s_", body, "xyz"), j("gh", "q_", body, "xyz")),
        "GITHUB_FINE_GRAINED_PAT": (
            j("github", "_pat_", "A1" * 11, "_", body, body),
            j("github", "_pat_", "short"),
        ),
        "GOOGLE_API_KEY": (j("AI", "za", "Sy", body), j("AI", "za", "short")),
        "SLACK_TOKEN": (
            j("xo", "xp-", "1234567", "-", "abcdEFGH12"),
            j("xo", "xz-", "1234567", "-", "abcdEFGH12"),
        ),
        "BEARER_TOKEN": (j("Bea", "rer ", body), j("Bea", "rer ", "tokenswithoutdigits")),
        "JWT": (
            j("ey", "J", "abcdefghij12", ".", "ey", "J", "klmnopqrst34", ".", body),
            j("ey", "J", "abcdefghij12", ".", "nope"),
        ),
        "PRIVATE_KEY_HEADER": (
            j("-----", "BEGIN ", "OPENSSH ", "PRIVATE ", "KEY", "-----"),
            j("-----", "BEGIN ", "CERTIFICATE", "-----"),
        ),
        "ASSIGNED_SECRET": (
            j("pass", "word", ": '", "Hx4", body, "'"),
            j("pass", "word", ' = "', "<REDACTED>", '"'),
        ),
    }


def self_test() -> list[str]:
    """Run every class against its positive and negative. ``[]`` means sound.

    A caller about to report "clean" runs this first and refuses to report
    clean if it returns anything - a clean scan by a broken detector is the
    one result worse than no scan.
    """
    failures: list[str] = []
    specimens = _specimens()
    for cls in CLASSES:
        if cls not in specimens:
            failures.append(f"{cls}: no specimen")
            continue
        positive, negative = specimens[cls]
        pattern = PATTERNS[cls]
        if not pattern.search(positive):
            failures.append(f"{cls}: positive not matched")
        if pattern.search(negative):
            failures.append(f"{cls}: negative matched")
    return failures


# ---------------------------------------------------------------------------
# The staged set.
# ---------------------------------------------------------------------------


class StagedScanFailed(RuntimeError):
    """git could not answer. A scan that did not run has not passed."""


def _git(repo: Path, *args: str) -> bytes:
    """Run git in ``repo`` and return raw stdout, or raise.

    The ambient environment is KEPT: under ``git commit -a`` the index being
    committed is a temporary one named only by ``GIT_INDEX_FILE``.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            timeout=120,
            check=False,
            creationflags=_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StagedScanFailed(f"git {args[0]} could not run: {exc}") from exc
    if result.returncode != 0:
        raise StagedScanFailed(f"git {args[0]} exited {result.returncode}")
    return result.stdout


def staged_paths(repo: Path) -> list[str]:
    """Every path whose staged blob lands in the commit.

    ``ACMRT`` for the reason ``.githooks/pre-commit`` gives: a rename is ``R``
    and carries real content, and ``--find-renames`` is explicit so local
    configuration cannot reopen that hole. ``-z`` because a path may contain a
    newline or a quote and git would otherwise C-quote it.
    """
    out = _git(
        repo, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMRT", "--find-renames"
    )
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def scan_staged(repo: Path) -> dict[str, list[Finding]]:
    """path -> findings, over the STAGED blob of every staged path."""
    hits: dict[str, list[Finding]] = {}
    for path in staged_paths(repo):
        # A symlink's staged blob is its target string; scanning it is harmless.
        blob = _git(repo, "show", f":{path}")
        found = scan_bytes(blob)
        if found:
            hits[path] = found
    return hits


def scan_files(paths: Iterable[Path], root: Path | None = None) -> dict[str, list[Finding]]:
    """path -> findings over files on disk. Unreadable files are skipped by the
    caller's choice of population, not silently here: an OSError propagates."""
    hits: dict[str, list[Finding]] = {}
    for path in paths:
        found = scan_bytes(path.read_bytes())
        if found:
            key = path.relative_to(root).as_posix() if root else str(path)
            hits[key] = found
    return hits


def main(argv: list[str]) -> int:
    """``secret_scan.py FILE...`` - scan files on disk and print the report.

    Exit 0 clean, 1 findings, 2 the self-test failed (the scan is untrusted).
    """
    failures = self_test()
    if failures:
        sys.stderr.write("secret_scan: SELF-TEST FAILED, refusing to report clean:\n")
        for failure in failures:
            sys.stderr.write(f"  {failure}\n")
        return 2
    hits = scan_files(Path(p) for p in argv)
    if hits:
        sys.stdout.write(format_report(hits) + "\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
