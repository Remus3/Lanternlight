"""Refuse a tracked command that builds a scratch path outside the scratchpad.

``OPS-107``, the source-side half of the gap ``OPS-103`` criterion 3 put a
control over. Under Git Bash ``$TMPDIR`` is UNSET - measured 2026-09-20 by
testing presence only, never a value - so ``"$TMPDIR/name"`` expands to
``/name``, which MSYS maps to the Git for Windows install root. Seventeen of
this project's files landed in that root, every one written by a subagent
following a command it had been given or had composed.

AN ADVERSARIAL PASS REFUTED THE FIRST VERSION OF THIS MODULE, and the
correction is the reason for the rules below. That version refused ``/tmp/x``
and passed ``/tmp_x``. Measured 2026-09-20: ``mount`` shows Git Bash mounting
the user temp folder at ``/tmp`` (``usertemp``), and ``cygpath -w`` resolves
``/tmp/x`` to the user temp folder but ``/tmp_x``, ``/tmp-x``, ``/tmpfile`` and
``/tmp.x`` to the Git install root. So inside Git Bash a path INSIDE the
mounted directory is not this item's bug, and a root path that merely STARTS
with the name is. The first version also generalised a PowerShell measurement
from ``TEMP`` to ``TMPDIR``: ``$env:TEMP`` is set, ``$env:TMPDIR`` is not.

WHAT IS REFUSED:

* ``unset-temp-var`` - in a shell context ``$TMPDIR``, ``${TMPDIR}``, ``$TMP``
  and ``$TEMP``, braced or not, with or without a default. ``TMP`` and
  ``TEMP`` were measured SET in this harness's Git Bash; they are refused
  anyway, because presence depends on whatever launched the shell, and none of
  them is the session scratchpad. In PowerShell the same names in BARE form,
  case-insensitive, because a bare ``$TEMP`` there is an ordinary PS variable
  that is NULL (measured), so the path collapses to the current drive root.
  ``$env:TMPDIR`` in any context, measured unset. ``%TMPDIR%`` in any context,
  which is how cmd spells the same unset variable. In Python, reading
  ``TMPDIR`` from the environment by subscript, ``get``, ``getenv`` or ``pop``.
  ``$env:TEMP``, ``$env:TMP`` and ``%TEMP%`` are the environment forms, set on
  this machine, and are not refused.
* ``tmp-prefix-git-root`` - in a shell context, ``/tmp`` at the start of a path
  and immediately followed by anything other than ``/``, whitespace, a quote,
  a shell word terminator (``; | & ) < >``) or the end of the line.
* ``drive-root-tmp`` - in a Python string or bytes constant, ``/tmp`` at the
  start of a path, followed by anything. Native Python does not see the Git
  Bash mount: ``os.path.abspath`` resolves it against the current DRIVE root
  (measured), which is never the scratchpad.

A path beginning ``/tmp/`` in a shell context is NOT refused, because the
measurement above says it is the user temp folder. It is still not the session
scratchpad, which is what the lane contracts say to use; that is an
instruction, not something this guard can enforce without refusing a correct
path.

HOW PROSE IS HANDLED, decided and measured rather than exempted. A document
has to be able to DESCRIBE this bug - the ROADMAP entry for this item does,
and so do the ledger archive, the wake-up notes and ``ops/outside_scan.py``'s
docstring. So the scope is a CONTEXT, not a file list:

* shell scripts, git hooks, batch files, PowerShell, JSON, YAML, TOML, INI and
  any file kind this module does not recognise - EVERY line. Unknown means
  strict: a new file kind is not exempt because nobody thought about it, which
  is the safe-list failure the ``OPS-103`` hand-off recorded.
* text an agent EXECUTES or is loaded with - ``.claude/**``,
  ``LL-NEXT-SESSION.txt``, ``CLAUDE.md`` and ``docs/HEADLESS.md`` - EVERY line,
  prose and inline code included. Describe the hazard there without the literal.
* other Markdown - EVERY fenced block whatever its tag (PowerShell rules for a
  PowerShell fence, shell rules otherwise) and every indented code block.
  Measured 2026-09-20 over the whole tree: zero findings with every fence and
  indented block scanned, so no tag needed exempting.
* Python - string and bytes constants via ``ast``, docstrings excluded, plus
  environment reads of ``TMPDIR``. Comments never reach the tree.

Measured 2026-09-20 over every tracked and untracked-not-ignored file: ZERO
findings, while the literal occurs in prose or a docstring in five tracked
files (``ROADMAP.md``, ``WAKEUP_NOTES.md``, ``docs/LEDGER_ARCHIVE.md``,
``ops/outside_scan.py`` and this module).
``tests/test_scratch_path_guard.py`` pins that zero.

HONEST NEGATIVES - what this guard does NOT see, stated because a caveat kept
out of the artifact is a lie in it:

* PROSE AND INLINE CODE in ordinary Markdown, including ``WAKEUP_NOTES.md``,
  which agents read. Measured 2026-09-20: scanning every line of ordinary
  Markdown gives 4 findings - 2 in ``ROADMAP.md``, 1 in ``WAKEUP_NOTES.md``, 1
  in ``docs/LEDGER_ARCHIVE.md`` - and all 4 are descriptions of this very bug,
  i.e. a 100 per cent false-positive rate. So it is left out as a context
  rather than exempted file by file. A command written only
  in inline code in such a document is invisible.
* Any OTHER unset variable, and any other root path (``/name``), both of which
  also land in the Git install root under Git Bash. The guard knows the temp
  spellings only.
* A path assembled at run time from fragments (as the test module does on
  purpose), PowerShell rules inside Python strings, a non-UTF-8 file, and a
  command a subagent composes itself and never writes to a tracked file - the
  last is what the lane contracts' scratchpad section is for, and
  ``ops/outside_scan.py`` remains the control at the destination.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_ROOT_TMP = re.escape("/" + "tmp")
_NAMES = r"(?:TMPDIR|TMP|TEMP)"

#: Shell: the three temp names, bare or braced, not followed by a name char.
_SHELL_VAR = re.compile(r"\$\{?" + _NAMES + r"(?![A-Za-z0-9_])")

#: PowerShell: the same names in BARE form, case-insensitive. ``$env:TEMP`` and
#: ``${env:TEMP}`` never match because ``env:`` sits between the sigil and name.
_PS_VAR = re.compile(r"\$\{?" + _NAMES + r"(?![A-Za-z0-9_:])", re.IGNORECASE)

#: Everywhere: the environment spellings of the one name measured UNSET.
_ENV_TMPDIR = re.compile(
    r"\$\{?env:TMPDIR(?![A-Za-z0-9_])|" + "%" + "TMPDIR" + "%", re.IGNORECASE
)

_ROOT_START = r"(?<![\w.:/~}\)$-])"

#: Shell: a root path that STARTS with the temp name but is not inside it.
_TMP_PREFIX = re.compile(_ROOT_START + _ROOT_TMP + r"(?=[^/\s\"'`;|&)<>])")

#: Python: any root temp path, which native code resolves on the drive root.
_PY_ROOT_TMP = re.compile(_ROOT_START + _ROOT_TMP)

_PS_FENCES = frozenset({"powershell", "ps1", "pwsh", "ps"})

#: Markdown that an agent is loaded with or executes, scanned line by line.
_WHOLE_SCAN_FILES = frozenset({"LL-NEXT-SESSION.txt", "CLAUDE.md", "docs/HEADLESS.md"})

_BINARY_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".zip", ".gz",
     ".pyc", ".pyd", ".so", ".dll", ".exe", ".pak", ".sav"}
)
_PS_SUFFIXES = frozenset({".ps1", ".psm1", ".psd1"})
_MD_SUFFIXES = frozenset({".md", ".markdown"})


@dataclass(frozen=True)
class Finding:
    """One refused line. Path is repo-relative POSIX; no line content is kept."""

    path: str
    line: int
    rule: str


def _scan_lines(
    text: str, var: re.Pattern[str], offset: int = 0
) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1 + offset):
        if var.search(line) or _ENV_TMPDIR.search(line):
            found.append((number, "unset-temp-var"))
        if _TMP_PREFIX.search(line):
            found.append((number, "tmp-prefix-git-root"))
    return found


def scan_shell(text: str) -> list[tuple[int, str]]:
    """Every line of a shell (or cmd) context."""
    return _scan_lines(text, _SHELL_VAR)


def scan_powershell(text: str) -> list[tuple[int, str]]:
    """Every line of a PowerShell context."""
    return _scan_lines(text, _PS_VAR)


def _one_line(line: str, number: int, powershell: bool) -> list[tuple[int, str]]:
    return _scan_lines(line, _PS_VAR if powershell else _SHELL_VAR, offset=number - 1)


def scan_markdown(text: str, whole: bool = False) -> list[tuple[int, str]]:
    """Every fence and indented block, or every line when ``whole``.

    ``whole`` is for text an agent executes. Fences inside such a file still
    get their own rules, so a PowerShell fence there is judged as PowerShell.
    """
    found: list[tuple[int, str]] = []
    fence: str | None = None
    fence_marker = ""
    previous_blank = True
    in_indented = False
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if fence is not None:
            if stripped.startswith(fence_marker) and not stripped.rstrip().strip(
                fence_marker[0]
            ):
                fence = None
            else:
                found += _one_line(line, number, fence in _PS_FENCES)
            previous_blank = False
            continue
        match = re.match(r"(`{3,}|~{3,})\s*([\w+-]*)", stripped)
        if match:
            fence_marker = match.group(1)
            fence = match.group(2).lower()
            in_indented = False
            previous_blank = False
            continue
        blank = not line.strip()
        indented = not blank and (line.startswith("    ") or line.startswith("\t"))
        in_indented = indented and (in_indented or previous_blank)
        if whole or in_indented:
            found += _one_line(line, number, powershell=False)
        if not blank and not indented:
            in_indented = False
        previous_blank = blank
    return found


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _is_tmpdir(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value == "TMPDIR"


def _is_environ(node: ast.AST) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "environ") or (
        isinstance(node, ast.Name) and node.id == "environ"
    )


def _reads_tmpdir(node: ast.AST) -> bool:
    """``os.environ['TMPDIR']``, ``.get('TMPDIR')``, ``getenv('TMPDIR')``."""
    if isinstance(node, ast.Subscript):
        return _is_environ(node.value) and _is_tmpdir(node.slice)
    if isinstance(node, ast.Call) and node.args and _is_tmpdir(node.args[0]):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        return name in {"get", "getenv", "pop", "getenvb"}
    return False


def scan_python(text: str) -> list[tuple[int, str]]:
    """String and bytes constants in code, docstrings excluded, plus env reads.

    Unparseable is a finding: a file the guard cannot read is not clean.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return [(1, "unparseable")]
    skip = _docstring_ids(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if _reads_tmpdir(node):
            found.append((node.lineno, "unset-temp-var"))
        if not isinstance(node, ast.Constant) or id(node) in skip:
            continue
        value = node.value
        if isinstance(value, bytes):
            value = value.decode("latin-1")
        if not isinstance(value, str):
            continue
        if _SHELL_VAR.search(value) or _ENV_TMPDIR.search(value):
            found.append((node.lineno, "unset-temp-var"))
        if _PY_ROOT_TMP.search(value):
            found.append((node.lineno, "drive-root-tmp"))
    return sorted(set(found))


def _is_agent_instruction(rel: str) -> bool:
    return rel.startswith(".claude/") or rel in _WHOLE_SCAN_FILES


def scan_file(rel: str, text: str) -> list[tuple[int, str]]:
    """Route one file to its context's rules. ``rel`` is repo-relative POSIX."""
    suffix = Path(rel).suffix.lower()
    if suffix == ".py":
        return scan_python(text)
    if suffix in _PS_SUFFIXES:
        return scan_powershell(text)
    if _is_agent_instruction(rel):
        return scan_markdown(text, whole=True)
    if suffix in _MD_SUFFIXES:
        return scan_markdown(text)
    return scan_shell(text)


def _git_listing(root: Path, extra: list[str]) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", *extra],
            cwd=root,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return [n for n in proc.stdout.decode("utf-8", "replace").split("\0") if n]


def population(root: Path | str = REPO_ROOT) -> list[Path]:
    """Tracked plus untracked-not-ignored files: what is about to be published.

    Untracked files are included for the reason ``tests/_tracked.py`` gives: a
    guard that only sees committed files sees a new file after it has landed.
    """
    root = Path(root)
    tracked = _git_listing(root, [])
    if tracked is None:
        return sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)
    untracked = _git_listing(root, ["--others", "--exclude-standard"]) or []
    names = dict.fromkeys([*tracked, *untracked])
    return [root / n for n in names if (root / n).is_file()]


def scan_tree(root: Path = REPO_ROOT, files: list[Path] | None = None) -> list[Finding]:
    """Scan ``files`` (default: the population of ``root``)."""
    findings: list[Finding] = []
    for path in population(root) if files is None else files:
        if path.suffix.lower() in _BINARY_SUFFIXES:
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        for line, rule in scan_file(rel, text):
            findings.append(Finding(rel, line, rule))
    return findings


def format_findings(findings: list[Finding]) -> str:
    """Path, line and rule only. The fix is the session scratchpad."""
    if not findings:
        return "scratch-path guard: 0 findings"
    lines = [f"scratch-path guard: {len(findings)} finding(s) - OPS-107"]
    lines += [f"  {f.path}:{f.line}: {f.rule}" for f in findings]
    lines.append("  Write scratch output under the session scratchpad only.")
    return "\n".join(lines)


def main() -> int:
    findings = scan_tree()
    print(format_findings(findings))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
