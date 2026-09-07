"""PreToolUse gate for Bash calls that look like a git commit.

Defence in depth only. The AUTHORITATIVE gate is `.githooks/`, wired by
`scripts/install_hooks.py`. This hook exists because a fresh clone runs zero git
hooks until someone runs that script, and because a Claude session can reach for
`git commit` before anyone has.

Reads the tool-call payload on stdin as JSON, and:
  - blocks a commit whose staged set contains a PII-hazard path
  - blocks a commit message carrying a banned glyph
  - blocks a CALL to the banned process-stopping cmdlet, while letting a
    MENTION of its name through - see :func:`_forbidden_cmdlet_reason`

Exit 0 allows. Exit 2 blocks and the stderr text is shown to the model. The
exit code is the verdict and the stderr text is best-effort - see `_say`, and
`OPS-15` for the fail-open this ordering used to produce.
Never raises - a crashing gate that blocks every command is worse than no gate,
so anything unexpected exits 0 and says why on stderr.

SECOND ENTRY POINT, added for ROADMAP ``OPS-37``. Run with the single argument
``lint-staged`` this module is not a PreToolUse hook at all: it lints the
STAGED content of the staged ``.py`` files and exits 1 if any finding sits on a
line THIS COMMIT ADDS. ``.githooks/pre-commit`` calls it that way. See
:func:`lint_staged` for why the scoping and the staged-content rule are both
load-bearing, and :class:`StagedEntry` for the decision this makes about every
git status letter - a renamed file used to be excluded from that listing
outright, which permitted every line such a commit added.
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Built with chr() on purpose: this source file is itself subject to the 7-bit
# ASCII rule, so the banned characters must not appear literally here. An
# earlier draft pasted them in and would have failed tests/test_ascii_hygiene.
BANNED_GLYPHS = {
    chr(0x2014): "em-dash",
    chr(0x2013): "en-dash",
    chr(0x2018): "left smart quote",
    chr(0x2019): "right smart quote",
    chr(0x201C): "left smart double quote",
    chr(0x201D): "right smart double quote",
}

PII_HAZARD = re.compile(
    r"(^|/)(frames|logs|scratchpad|_scratch)/|\.sav$|\.log$|\.log\.\d+$",
    re.IGNORECASE,
)

# `OPS-22`. The process-stopping PowerShell cmdlet CLAUDE.md bans in favour of
# `taskkill /F /PID`, plus its shipped alias. Assembled from parts rather than
# written out, for the same reason BANNED_GLYPHS uses chr(): the literal string
# in this file would otherwise be a landmine for anyone grepping the repo with
# this very hook armed. `kill` is the cmdlet's OTHER alias and is deliberately
# absent - see _forbidden_cmdlet_reason.
FORBIDDEN_CMDLETS = ("Stop" + "-Process", "spps")

_CMDLET_ALTERNATION = "|".join(re.escape(name) for name in FORBIDDEN_CMDLETS)

#: An INVOCATION: the name in COMMAND POSITION. That means the start of the
#: string or of a line, or the first token after a statement separator (`;`), a
#: pipe (`|`, and so also `||`), the call or background operator (`&`, and so
#: also `&&`), an opening paren (covering `(`, `$(` and `@(`), a script-block
#: brace (`{`, covering if/else/foreach/-ScriptBlock bodies), an assignment
#: (`=`), or a module qualifier (`\`).
CMDLET_CALL = re.compile(
    r"(?:^|[;|&({=\\])[ \t]*(?:" + _CMDLET_ALTERNATION + r")\b",
    re.IGNORECASE | re.MULTILINE,
)

#: The name ANYWHERE, quoted or not. Only consulted together with
#: POWERSHELL_INVOKER, below.
CMDLET_ANYWHERE = re.compile(r"\b(?:" + _CMDLET_ALTERNATION + r")\b", re.IGNORECASE)

#: A token that hands a string to PowerShell to RUN. Quoting is what separates
#: a mention from a call everywhere else, so it cannot also be what excuses
#: `powershell -Command "<cmdlet> -Id 1"`.
POWERSHELL_INVOKER = re.compile(
    r"\b(?:powershell|pwsh|iex|invoke-expression)\b|-encodedcommand\b",
    re.IGNORECASE,
)


def _forbidden_cmdlet_reason(command: str) -> str | None:
    """Return why ``command`` CALLS the banned cmdlet, or ``None`` if it does not.

    **`OPS-22`, and the class of bug it belongs to.** This check used to be
    ``if "<cmdlet>" in command``. A bare substring test cannot tell a CALL from
    a MENTION, so the name inside a grep pattern, a string literal, a comment
    or a filename was refused exactly as hard as an invocation - and it fired
    on the analysis pass that found it. It is the same shape as `OPS-18`: a
    sentinel that is also a legal datum. ``lanternlight/gvas.py``'s
    ``KeyMapping`` refuses to fold Unreal's ``"None"`` onto Python ``None`` for
    the same reason.

    **WHAT THIS CAN SEE.** Two things, and it is a pattern matcher, not a
    PowerShell parser:

    1. The name in COMMAND POSITION - see :data:`CMDLET_CALL` for the exact
       list of positions. Case-insensitively, because PowerShell is, which the
       old substring test was not: ``stop-process -id 1`` used to sail through.
       The ``spps`` alias is caught for the same reason; it was not before.
    2. The name ANYWHERE in a command that also carries a PowerShell-invoking
       token (:data:`POWERSHELL_INVOKER`). Without this rule, moving from
       "anywhere" to "command position" would have turned
       ``powershell -Command "<cmdlet> -Id 1"`` from blocked into allowed, and
       a false pass is the one outcome this file exists to prevent.

    **WHAT THIS CANNOT SEE.** Stated plainly, because a guard whose limits are
    undocumented gets trusted past them:

    * **The ``kill`` alias.** PowerShell ships it as a third name for this
      cmdlet and it is NOT blocked here. It is a first-class POSIX command in
      the shell these tool calls actually run in, so blocking it in command
      position would refuse ordinary, correct commands all day. Note that the
      sanctioned replacement, ``taskkill``, would survive either way - it has
      no word boundary before ``kill``. The old substring test did not catch
      this alias either, so nothing was lost; it is simply still open.
    * **Any name it does not hold literally.** ``&("Stop" + "-Process")``,
      ``-EncodedCommand`` base64, ``$c = 'Stop-Pro'+'cess'; & $c``, or a
      splatted invocation defeat it. So does a heredoc that writes a script to
      disk and a later command that runs it.
    * **Nesting.** Quoting is treated as one flat level. A mention inside a
      quoted string is allowed unless rule 2 fires, and rule 2 fires on the
      whole command, so a merely-quoted mention that happens to sit beside the
      word ``powershell`` is blocked. That is a FALSE BLOCK and it is the
      intended trade: an annoyance costs a rephrase, a false pass costs the
      thing the rule protects.

      **IT FIRED IN PRACTICE WITHIN MINUTES OF SHIPPING**, on the commit
      MESSAGE describing this very fix - text that was never going to be
      executed. That is recorded here rather than left sounding hypothetical.
      ``OPS-24`` then evaluated narrowing rule 2 for a lone ``git commit`` and
      **DECLINED IT ON A MEASUREMENT.** The only safe narrowing must refuse to
      apply whenever the command could introduce a second command, so it must
      treat ``;``, ``|``, ``&``, ``(``, ``)``, ``{``, ``}``, ``=``, a backslash,
      ``$(`` and a backtick as disqualifying - and a commit MESSAGE is part of
      that same command string. Measured over this repo's last 40 real commit
      messages: **39 of them contain at least one of those characters**, so the
      narrowing would decline to apply 97 percent of the time while adding a
      branch to a guard that is now demonstrably catching four invocation
      spellings the old substring test missed. The rephrase is cheaper.

    This is defence in depth against an accidental call, not a sandbox against
    a determined one. Nothing here is a substitute for the rule itself.
    """
    if CMDLET_CALL.search(command):
        return (
            "that cmdlet hangs the MCP pipe. Use taskkill /F /PID instead. "
            "(Blocked because the name is in COMMAND POSITION. To talk ABOUT "
            "it, quote it or pass it as an argument.)"
        )
    if CMDLET_ANYWHERE.search(command) and POWERSHELL_INVOKER.search(command):
        return (
            "that cmdlet hangs the MCP pipe. Use taskkill /F /PID instead. "
            "(Blocked because the name is quoted but the command hands the "
            "quoted text to PowerShell to run.)"
        )
    return None


def _staged_paths() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# ROADMAP OPS-37 criterion 2 - the commit-time lint gate.
# ---------------------------------------------------------------------------

#: A unified-diff hunk header. Only the ``+`` side matters here: ``c`` is the
#: first line number in the NEW file and ``d`` is how many lines follow it.
#:
#: ``d`` IS OPTIONAL, and that is the whole trap. git writes ``@@ -3 +7 @@``
#: for a single-line change, and a parser that reads the missing count as 0
#: gives every one-line addition an EMPTY range - so the gate stays green over
#: exactly the commits it exists to catch, and looks like it is working. The
#: trailing ``@@`` is required by the pattern so the section heading git
#: appends (``@@ -12 +12 @@ def enclosing():``) cannot be read as a number.
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


@dataclass(frozen=True)
class LintFinding:
    """One ruff finding, reduced to what the gate decides on."""

    path: str
    line: int
    code: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line} {self.code} {self.message}"


class GateFailed(RuntimeError):
    """The lint gate could not reach a verdict, so it must REFUSE.

    Every subclass names a way the gate stopped being able to answer its own
    question. None of them is the fresh-clone case (that is ruff simply being
    absent, handled in :func:`lint_staged_main` by permitting), and reporting
    a gate that did not run as a pass is the failure this file exists to
    avoid.
    """


class RuffFailed(GateFailed):
    """ruff was present but could not lint the staged content."""


class StagedListingFailed(GateFailed):
    """git's staged listing could not be read, or could not be parsed.

    Dropping an unreadable record instead would silently narrow the set of
    files the gate judges, which is exactly the shape of the ``--diff-filter``
    defect this listing replaced: a file the gate cannot see is a file the
    gate permits.
    """


_RUFF_COMMAND: list[str] | None = None
_RUFF_PROBED = False


def ruff_command() -> list[str] | None:
    """The argv prefix that runs ruff, or ``None`` when ruff is not installed.

    ``python -m ruff`` is preferred over a bare ``ruff`` so the linter that
    runs is the one installed for the interpreter running this gate, rather
    than whichever copy happens to be first on PATH.

    ruff is NOT a declared dependency of this project (``pyproject.toml`` has
    an empty ``dependencies``), so a fresh clone can legitimately be without
    it. Returning ``None`` here is how the caller learns to stand down instead
    of refusing every commit on a machine that was never set up to lint.
    """
    global _RUFF_COMMAND, _RUFF_PROBED
    if _RUFF_PROBED:
        return _RUFF_COMMAND
    _RUFF_PROBED = True
    for candidate in ([sys.executable, "-m", "ruff"], ["ruff"]):
        try:
            probe = subprocess.run(
                [*candidate, "--version"],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            _RUFF_COMMAND = candidate
            return _RUFF_COMMAND
    return None


def parse_added_ranges(diff_text: str) -> list[tuple[int, int]]:
    """Inclusive ``(start, end)`` line ranges that ``diff_text`` ADDS.

    Line numbers are in the NEW file - which, for a ``git diff --cached``, is
    the staged content and not the working tree. A hunk that adds nothing
    (``+3,0``, a pure deletion) contributes no range at all: the lines around
    a deletion were not written by this commit, and blaming them is how a
    scoped gate quietly becomes a tree-wide one.
    """
    ranges: list[tuple[int, int]] = []
    for match in HUNK_HEADER.finditer(diff_text):
        start = int(match.group(1))
        raw_count = match.group(2)
        count = 1 if raw_count is None else int(raw_count)
        if count <= 0:
            continue
        ranges.append((start, start + count - 1))
    return ranges


def line_is_added(line: int, ranges: list[tuple[int, int]]) -> bool:
    """Is ``line`` inside any of ``ranges``? Both ends inclusive."""
    return any(start <= line <= end for start, end in ranges)


def _git_stdout(repo: Path, *args: str) -> str | None:
    """Run git in ``repo`` and return stdout, or ``None`` if it failed.

    THE AMBIENT ENVIRONMENT IS KEPT ON PURPOSE. This runs from a pre-commit
    hook, where git names the index being committed through ``GIT_INDEX_FILE``
    - under ``git commit -a`` that is a TEMPORARY index, and scrubbing the
    variable would point every read below at the wrong one.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


#: One record of ``git diff --cached --raw -z``:
#: ``:<srcmode> <dstmode> <srcsha> <dstsha> <status>`` followed by a NUL and
#: then one path, or TWO paths when the status is a rename or a copy. The
#: shas are abbreviated by default, hence the open-ended hex run.
RAW_HEADER = re.compile(r":(\d{6}) (\d{6}) [0-9a-fA-F]+ [0-9a-fA-F]+ ([A-Z])(\d*)")

#: Statuses whose record carries a SECOND path - the destination. Reading one
#: of these as a single-path record would consume the wrong number of tokens
#: and desynchronise every record after it, so this set is about parsing
#: correctness and not about policy.
TWO_PATH_STATUSES = frozenset("RC")

#: Statuses the gate is willing to lint. See :class:`StagedEntry` for the
#: decision behind each letter, including the ones deliberately absent.
LINTABLE_STATUSES = frozenset("AMRCT")

#: Destination modes that mean "a regular file blob is being staged here".
#: ``000000`` is a deletion or an unmerged path, ``120000`` a symlink and
#: ``160000`` a submodule gitlink - none of them is Python source, and
#: ``git show :<path>`` on an unmerged path fails outright.
LINTABLE_DST_MODES = frozenset({"100644", "100755"})


@dataclass(frozen=True)
class StagedEntry:
    """One staged change, as the gate needs to see it.

    **THE DECISION FOR EVERY GIT STATUS LETTER**, written out because the
    predecessor of this class was a ``--diff-filter=ACM`` string that silently
    excluded one and permitted a real violation because of it.

    * ``A`` added - LINTED. Every line is this commit's.
    * ``M`` modified - LINTED, on the lines the diff marks added.
    * ``R`` renamed - LINTED. THIS IS THE FIX. ``ACM`` excluded ``R``, so a
      file that was renamed AND rewritten in one commit was invisible and the
      lines it added were permitted. :attr:`origin` carries the path it came
      FROM, which is what lets :func:`staged_diff` pair the two sides; without
      it git reports the destination as a brand-new file and the gate blames
      every pre-existing line in it instead.
    * ``C`` copied - LINTED, and parsed for its two paths. It cannot actually
      arrive through :func:`staged_raw_listing`, which passes an explicit
      ``--find-renames`` and so turns a would-be copy into a plain ``A`` with
      every line added. That is the stricter reading and it is deliberate:
      copy detection would arrive pre-forgiving the lines a genuinely new file
      happens to share with an old one. The two-path shape is still parsed,
      because a record read with the wrong arity desynchronises the stream.
    * ``T`` type change - LINTED ONLY when the destination is a regular file.
      symlink to blob means real Python text is arriving. Blob to symlink does
      not: the staged bytes are a link target, and linting them produces
      findings about a path string.
    * ``D`` deleted - NOT linted. Nothing to read, nothing to blame. Excluded
      by the destination mode being ``000000``.
    * ``U`` unmerged - NOT linted. There is no single staged blob; ``git show
      :<path>`` answers "is in the index, but not at stage 0". Also excluded
      by the ``000000`` destination mode.
    * Anything else (``B``, ``X``) - NOT linted, by not being in
      :data:`LINTABLE_STATUSES`.
    """

    path: str
    """The NEW path. What ``git show :<path>`` reads and what ruff judges."""

    origin: str
    """Where the content came from. Equal to :attr:`path` unless R or C."""

    status: str
    """The bare status letter, with any similarity score stripped."""

    dst_mode: str
    """The staged mode at :attr:`path`. ``000000`` when nothing lands there."""

    @property
    def lintable(self) -> bool:
        return self.status in LINTABLE_STATUSES and self.dst_mode in LINTABLE_DST_MODES


def parse_raw_records(raw: str) -> list[StagedEntry]:
    """Parse ``git diff --cached --raw -z`` output into :class:`StagedEntry`.

    Record boundaries come from the STATUS LETTER'S ARITY and never from a
    leading colon, because a path may legitimately begin with one. A record
    whose header does not parse raises :class:`StagedListingFailed` rather
    than being skipped - see that class for why silence is the wrong answer.
    """
    tokens = raw.split("\0")
    while tokens and tokens[-1] == "":
        tokens.pop()

    entries: list[StagedEntry] = []
    index = 0
    while index < len(tokens):
        header = RAW_HEADER.fullmatch(tokens[index])
        if header is None:
            raise StagedListingFailed(
                f"git raw record could not be parsed: {tokens[index]!r}"
            )
        status = header.group(3)
        wanted = 2 if status in TWO_PATH_STATUSES else 1
        paths = tokens[index + 1 : index + 1 + wanted]
        if len(paths) != wanted:
            raise StagedListingFailed(
                f"git raw record {tokens[index]!r} is missing a path"
            )
        entries.append(
            StagedEntry(
                path=paths[-1],
                origin=paths[0],
                status=status,
                dst_mode=header.group(2),
            )
        )
        index += 1 + wanted
    return entries


def staged_raw_listing(repo: Path) -> str:
    """The staged change list, one raw record per change.

    ``--raw -z`` rather than ``--name-only``, because a rename has TWO paths
    and the gate needs both: the destination to read and lint, the origin to
    pair the diff against. It also carries the destination mode, which is how
    a deletion, an unmerged path and a symlink are told apart from a real
    staged blob.

    ``--find-renames`` IS PASSED EXPLICITLY and is not left to configuration.
    ``diff.renames`` is a local setting: ``false`` splits a rename into a
    delete plus an add, which blames the commit for every pre-existing line in
    the moved file, and ``copies`` enables copy detection, which excuses the
    lines a new file shares with an old one. Both are wrong for a guard, and
    both would be invisible here. The explicit flag wins over either.
    """
    out = _git_stdout(repo, "diff", "--cached", "--raw", "-z", "--find-renames")
    if out is None:
        raise StagedListingFailed("git could not list the staged changes")
    return out


def staged_python_entries(repo: Path) -> list[StagedEntry]:
    """The staged changes the gate will lint, in git's order.

    The DESTINATION decides whether a change is Python. ``mod.py`` renamed to
    ``notes.txt`` leaves no Python file behind to lint; ``notes.txt`` renamed
    to ``mod.py`` creates one, and the lines that rename rewrites are this
    commit's.
    """
    return [
        entry
        for entry in parse_raw_records(staged_raw_listing(repo))
        if entry.lintable and entry.path.endswith(".py")
    ]


def staged_diff(repo: Path, path: str, origin: str | None = None) -> str:
    """The staged diff for one path, with zero lines of context.

    Zero context is what makes the hunk headers mean "added", rather than
    "added, plus the three unchanged lines either side".

    One CHANGE per call, which is deliberate: parsing a multi-file diff means
    parsing its ``+++ b/<path>`` headers, and git quotes those for paths
    carrying unusual bytes. Asking per change removes that failure mode from a
    guard whose whole value is that it fires on the right lines.

    **PASS ``origin`` FOR A RENAME, or the answer is wrong twice over.** A
    pathspec is applied before rename detection, so
    ``git diff --cached -- <new path>`` hides the old path's deletion, leaves
    rename detection with nothing to pair, and makes git report the
    destination as a brand-new file whose every line was added. The gate then
    blocks on findings the commit only moved. Naming BOTH sides puts the
    deletion back in the diff, git re-pairs them, and the added ranges shrink
    to the lines the rewrite actually wrote - none at all for a pure rename,
    exactly like a pure deletion.
    """
    pathspecs = [path] if origin is None or origin == path else [origin, path]
    return (
        _git_stdout(
            repo,
            "diff",
            "--cached",
            "--unified=0",
            "--find-renames",
            "--",
            *pathspecs,
        )
        or ""
    )


def staged_source(repo: Path, path: str) -> str | None:
    """The STAGED bytes of ``path``, decoded, or ``None`` if unreadable."""
    return _git_stdout(repo, "show", f":{path}")


def ruff_findings(repo: Path, path: str, source: str) -> list[LintFinding]:
    """Every ruff finding in ``source``, attributed to ``path``. Unscoped.

    ``source`` is handed to ruff on STDIN with ``--stdin-filename`` set to the
    real repo-relative path. That keeps two things true at once: ruff judges
    the exact text that is about to be committed, and it still applies the
    per-file rules in ``ruff.toml`` that are keyed on where the file lives.

    ruff reports an ABSOLUTE filename even for stdin input, so the path here
    is normalised back to repo-relative and falls back to the path that was
    asked about. That fallback cannot mis-attribute anything, because ruff is
    invoked once per staged path.

    Raises :class:`RuffFailed` when ruff runs but does not produce findings -
    a broken ``ruff.toml`` or an unparseable payload. Exit 0 is "clean" and
    exit 1 is "findings"; anything else is a linter that did not lint, and
    reporting that as clean would be a silent hole.
    """
    command = ruff_command()
    if command is None:
        return []
    args = [*command, "check", "--output-format", "json", "--no-cache", "--force-exclude"]
    config = repo / "ruff.toml"
    if config.is_file():
        # Explicit, so the answer does not depend on where the caller stood.
        args += ["--config", str(config)]
    args += ["--stdin-filename", path, "-"]
    try:
        result = subprocess.run(
            args,
            cwd=repo,
            input=source,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuffFailed(f"could not run ruff on {path}: {exc}") from exc
    if result.returncode not in (0, 1):
        raise RuffFailed(
            f"ruff exited {result.returncode} on {path}: "
            f"{(result.stderr or result.stdout).strip()}"
        )
    try:
        raw = json.loads(result.stdout or "[]")
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuffFailed(f"ruff produced unparseable output for {path}: {exc}") from exc

    findings: list[LintFinding] = []
    for item in raw:
        location = item.get("location") or {}
        row = location.get("row")
        if not isinstance(row, int):
            continue
        findings.append(
            LintFinding(
                path=_relative_to(repo, item.get("filename"), path),
                line=row,
                code=str(item.get("code") or "?"),
                message=str(item.get("message") or "").strip(),
            )
        )
    return findings


def _relative_to(repo: Path, reported: object, fallback: str) -> str:
    if not isinstance(reported, str) or not reported:
        return fallback
    try:
        return Path(reported).resolve().relative_to(repo.resolve()).as_posix()
    except (OSError, ValueError):
        return fallback


def lint_staged(repo: Path) -> list[LintFinding]:
    """Lint findings that sit on a line THIS COMMIT ADDS. The blocking set.

    **WHY SCOPED AND NOT TREE-WIDE.** A tree-wide gate refuses every commit the
    moment one pre-existing finding exists anywhere, including in files the
    commit never opened. That guard does not get fixed, it gets disabled - and
    a disabled guard is worse than none, because the badge stays up. So the
    question asked here is narrow: did THIS commit write a bad line.

    **WHY THE STAGED CONTENT AND NOT THE WORKING TREE.** The added ranges come
    from the index. Line numbers only mean something against the text they were
    computed from, so the text linted has to be the index's too. Point ruff at
    the working tree instead and one unstaged edit shifts every line: the gate
    then waves through a staged violation whose line moved out of range, and
    refuses a clean staged change because of an edit that is not being
    committed. Both directions are wrong and neither announces itself, which is
    why ``tests/test_precommit_gate_lint.py`` pins each one separately.

    **WHY A RENAME IS NOT A SPECIAL CASE HERE.** It is handled entirely by
    :class:`StagedEntry` carrying an :attr:`~StagedEntry.origin` alongside the
    destination. The destination is what gets read and linted; the origin is
    what :func:`staged_diff` needs to pair the rename so the added ranges come
    out right. A pure rename produces no hunks and therefore no ranges, and
    falls out of the loop below at the same ``continue`` a pure deletion does.
    """
    blocking: list[LintFinding] = []
    for entry in staged_python_entries(repo):
        ranges = parse_added_ranges(staged_diff(repo, entry.path, entry.origin))
        if not ranges:
            continue
        source = staged_source(repo, entry.path)
        if source is None:
            continue
        blocking += [
            finding
            for finding in ruff_findings(repo, entry.path, source)
            if line_is_added(finding.line, ranges)
        ]
    return blocking


def lint_staged_main(repo: Path) -> int:
    """CLI entry for ``lint-staged``. 0 permits, 1 refuses.

    Two stand-downs, and they are deliberately different:

    * **ruff absent** - permit, and say so. It is not a declared dependency,
      so refusing here would block every commit on a fresh clone over a tool
      the project never promised was installed.
    * **ruff present but failing, or git's staged listing unreadable** -
      REFUSE. Neither is the fresh-clone case; both are a gate that did not
      run, and reporting a gate that did not run as a pass is the failure this
      whole file exists to avoid. Both arrive as :class:`GateFailed`.
    """
    if ruff_command() is None:
        _say("precommit_gate lint-staged: ruff is not installed, skipping.\n")
        return 0
    try:
        findings = lint_staged(repo)
    except GateFailed as exc:
        _say(f"precommit_gate lint-staged: {exc}\n")
        return 1
    if not findings:
        return 0
    _say(
        f"{len(findings)} lint finding(s) on lines this commit ADDS "
        "(pre-existing findings elsewhere are ignored):\n"
    )
    for finding in findings:
        _say(f"  {finding.format()}\n")
    return 1


def _say(message: str) -> None:
    """Report ``message`` on stderr, best-effort, without risking the exit code.

    **`OPS-15`, and the coupling it removes.** This gate's verdict IS its exit
    code - a PreToolUse hook blocks on 2 and permits on everything else. The
    reason text is a courtesy. Before this, the two were coupled: :func:`_block`
    wrote first and exited second, so a stderr that could not be written took
    the refusal with it and the gate FAILED OPEN.

    Two distinct paths lost the code, and the second is the one that makes a
    bare ``try``/``except`` at each call site insufficient:

    * the write raises, the outer handler in ``__main__`` writes again, raises
      again, and the process exits 1;
    * the write is merely BUFFERED and never flushed. CPython flushes the
      standard streams at interpreter shutdown and **exits 120 if that flush
      raises**, overriding whatever this script exited with. Measured at exit
      120 on a blocking payload and on a benign one alike.

    **What is actually load-bearing here, corrected after a refutation pass.**
    The ``try``/``except`` is: without it a raising write propagates and the
    exit code goes with it. The ``sys.stderr = None`` inside the handler is
    NOT - it is measurably inert. Replacing that line with ``pass`` leaves
    ``tests/test_precommit_gate.py`` at 5 passed and every behaviour case
    unchanged, because :func:`_exit` detaches an unflushable stream anyway and
    every call site here is immediately followed by ``_exit``.

    An earlier version of this docstring claimed the detach was "the whole
    reason this is a function". That was a behaviour claim the artifact does
    not support, which this repository treats as a defect in its own right. The
    line is kept as defence in depth against a FUTURE call site that does not
    reach ``_exit``; it is not what makes the current code correct. If you
    simplify it away, nothing will fail - so read :func:`_exit` first.

    Losing the message is an acceptable trade. Losing the verdict is not.
    """
    try:
        sys.stderr.write(message)
        sys.stderr.flush()
    except Exception:
        with contextlib.suppress(Exception):
            sys.stderr = None


def _exit(code: int) -> None:
    """Exit with ``code``, making sure interpreter shutdown cannot change it.

    **The other half of `OPS-15`.** :func:`_say` detaches a stderr it failed to
    write, but a run that never NEEDS to report never calls it - and a benign
    command is exactly that run. The stream stays attached and unflushable,
    CPython's shutdown flush raises, and the process exits 120 instead of 0.
    Measured on ``ls -la`` with a broken stderr, after the ``_say`` fix had
    already corrected both blocking paths.

    Exit 120 is not a fail-open - only exit 2 blocks - so this half is noise
    rather than a hole. It is still a gate reporting failure on every command
    it was perfectly happy with, which is how a guard gets switched off.

    Both streams are checked: nothing here writes to stdout, but a broken
    stdout fails the same shutdown flush and produces the same 120.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            stream.flush()
        except Exception:
            with contextlib.suppress(Exception):
                setattr(sys, name, None)
    sys.exit(code)


def _block(reason: str) -> None:
    _say(f"BLOCKED by tools/precommit_gate.py: {reason}\n")
    _exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = str(payload.get("tool_input", {}).get("command", ""))
    if not command:
        return 0

    reason = _forbidden_cmdlet_reason(command)
    if reason is not None:
        _block(reason)

    if "git commit" not in command:
        return 0

    for glyph, name in BANNED_GLYPHS.items():
        if glyph in command:
            _block(f"commit message contains a {name}. This repo is 7-bit ASCII only.")

    for path in _staged_paths():
        if PII_HAZARD.search(path):
            _block(
                f"staged path '{path}' matches a PII-hazard pattern. "
                "Game logs, saves and capture frames carry the operator's "
                "SteamID64, persona and geolocation and must never be committed."
            )

    return 0


#: The ``lint-staged`` entry point does NOT read stdin as JSON and does NOT
#: exit 2 - it is a git hook helper, not a PreToolUse hook, and git reads any
#: non-zero exit as a refusal. Spelled with and without dashes because both
#: are the obvious thing to type.
_LINT_ARGV = {"lint-staged", "--lint-staged"}

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1 and sys.argv[1] in _LINT_ARGV:
            # NOT covered by the soft-fail below on purpose. That fail-open is
            # correct for a PreToolUse hook, where a crash must not wedge the
            # session. Here a crash means the lint gate did not run, and a
            # gate that did not run has not passed.
            try:
                _exit(lint_staged_main(REPO))
            except SystemExit:
                raise
            except Exception as exc:
                _say(f"precommit_gate lint-staged crashed, REFUSING: {exc}\n")
                _exit(1)
        _exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a gate must never wedge the session
        _say(f"precommit_gate soft-failed, allowing: {exc}\n")
        _exit(0)
