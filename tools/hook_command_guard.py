"""No tracked hook command may name an absolute path - ``OPS-61`` criterion 3.

WHY THIS EXISTS
---------------
Every hook command in ``.claude/settings.json`` used to name an absolute
repository root, e.g. an interpreter followed by ``C:/Lanternlight/ops/...``.
Each hook script resolves the repository root from its own ``__file__``, so the
command decides which TREE the hook reports about. Measured for ``OPS-61`` in a
real clone at a foreign path: such a hook FIRES, SUCCEEDS, and answers about the
ORIGINAL tree without saying so. That is worse than not firing - a hook that
does not fire reports nothing, while this one looks exactly like coverage. Git
worktrees are the case that bites, because that is where lane sessions run.

Measured in the same clone: a command written through ``$CLAUDE_PROJECT_DIR``
ran the CLONE's own script, because the harness expands that variable itself.
So the property this module checks is that a hook command reaches its script
through the harness-provided root or through a repo-relative path, and never
through a literal absolute one.

WHY THE EXISTING GUARD DOES NOT REACH IT
----------------------------------------
``tests/test_no_hardcoded_home_path.py`` (``OPS-38``) matches the SHAPE of any
user home directory under any account name. ``C:/Lanternlight`` carries no
account name, so it passes that guard cleanly. This module is that guard's
SIBLING, not its replacement: OPS-38 asks "does a published string carry
machine-specific identity", and this one asks "does a hook command name a root
the running tree cannot verify is its own". A string can fail either check
without failing the other.

THE DECISION THIS MODULE MAKES DELIBERATELY, AND WHAT IT COSTS
--------------------------------------------------------------
Every absolute path in a hook command is reported, not only one that looks like
a repository root. An absolutely-named INTERPRETER is the same class of defect -
``OPS-38``'s own docstring records four hook commands that carried one - and
"is this particular absolute path the repo root?" is not a question a string can
answer: ``D:/Elsewhere/tool.py`` is somebody's repo root and
``C:/Windows/System32/where.exe`` is not, and nothing in the text distinguishes
them. A guard that tried would need a list of roots, and a guard hardened
against a list of values is scoped to that list, which is the exact failure
``OPS-38`` had to generalise past twice.

The cost, stated rather than left implicit: a hook that genuinely needs an
absolute path to something OUTSIDE the repository would be reported here and
would have to be dealt with. There is no such command today. If one is ever
needed the fix is an explicitly pinned entry naming that one command, with the
measurement behind it - never a widened pattern, because a pattern loose enough
to permit the legitimate case is loose enough to permit the defect it was
written for.

A SCAN OF NOTHING IS NOT A PASS
-------------------------------
Three answers, kept distinct. ``ran=False`` means the check could not execute
(no settings file). ``ran=True, ok=False`` means it executed and found
something - including the case where the file parses but declares NO hook
command at all, reported as ``no-commands``: an empty finding list over an empty
corpus is the same output as a clean tree, which is the defect this whole file
is written against. Only ``ran=True, ok=True`` over a non-empty command list is
a pass.

The JSON parse is itself a finding, not an exception. ``CLAUDE.md`` records that
a single-backslash Windows path makes this file invalid JSON, and then NOTHING
parses, no hook registers, and nothing warns you. A guard that crashed on that
input would report a traceback where the interesting fact is "every hook on this
machine is silently dead".

WHAT THIS GUARD IS BLIND TO, written here because a caveat that lives only in
conversation is a lie in the artifact:

* It reads ``.claude/settings.json`` only. ``.claude/settings.local.json`` is
  untracked and a user-level settings file lives outside the repository; both
  are out of scope, because only tracked content is published and only tracked
  content reaches a fresh clone.
* It reads the LITERAL command string. A command that reaches an absolute root
  through an environment variable set elsewhere is invisible - and must be,
  since ``$CLAUDE_PROJECT_DIR`` is exactly that shape and is the CORRECT form.
* A single-segment POSIX root (``/tool.py``) is deliberately NOT reported. A
  Windows-style switch shares that shape - ``taskkill /F`` is the example this
  repository already documents - so :data:`_POSIX_ROOT_RE` requires a second
  separator. The accepted cost is a blind spot for a script sitting directly at
  a POSIX filesystem root, which no hook here has ever used.
* A drive-RELATIVE path (``C:ops/x.py``, no separator after the colon) is not
  reported. It is not absolute; it resolves against the current directory of
  that drive, which is a different defect with a different fix.
* Percent-encoded separators (``C%3A%5C...``) are not reported, for the same
  reason ``OPS-38`` decided that case out of scope: the pattern needs the
  literal ``:`` and ``/``/``\\`` characters, and no hook command in this
  repository has ever been URL-encoded.
* It says NOTHING about whether a clean command actually resolves the right
  tree. That is ``OPS-61`` criteria 1 and 2, and only an end-to-end run in a
  real clone and a real worktree can answer it. Presence, registration and a
  green exit are three different facts and none of them is the fact that the
  hook read the right tree.

Nothing here returns early. Every offending command in one run is collected, so
a fix does not have to be discovered one failure at a time.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "REPO_ROOT",
    "SETTINGS_REL_PATH",
    "Finding",
    "Report",
    "absolute_paths_in",
    "check_repo",
    "check_settings_text",
    "iter_hook_commands",
    "main",
]

#: Repository root, resolved from this file's location: tools/hook_command_guard.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The one tracked settings file this guard reads. See the blind-spot list.
SETTINGS_REL_PATH = ".claude/settings.json"

#: A drive-letter absolute root: a letter, a colon, then a separator. The
#: lookbehind keeps the letter from being the tail of a longer token (a URL
#: scheme's ``s:`` in ``https://``, say). The separator is required: ``C:ops``
#: is drive-relative, not absolute.
_DRIVE_ROOT_RE = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z]:[\\/][^\s\"']*)")

#: A UNC root: two separators, a host, a separator, then anything. The
#: lookbehind excludes a colon so ``https://host/x`` is a URL rather than a UNC
#: share - a URL in a hook command is a different thing entirely and reporting
#: it as a filesystem root would be a false claim about what was found.
_UNC_ROOT_RE = re.compile(r"(?<![A-Za-z0-9:])((?:\\\\|//)[^\s\\/\"']+[\\/][^\s\"']*)")

#: A POSIX absolute root, requiring at least TWO separators - see the
#: single-segment blind spot in the module docstring. The lookbehind excludes a
#: preceding word character, ``:``, ``%``, ``$``, ``.``, ``-`` or a separator,
#: so the tail of an already-matched drive path (``C:/Lanternlight/ops``), an
#: expanded variable (``$CLAUDE_PROJECT_DIR/ops/x.py``) and a relative path
#: (``./ops/x.py``) are not reported a second time or at all.
_POSIX_ROOT_RE = re.compile(r"(?<![\w:.$%/\\-])(/[^\s\\/\"']+/[^\s\"']*)")

#: Pattern to finding-kind. Order is fixed so a report reads the same way twice.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("absolute-drive-root", _DRIVE_ROOT_RE),
    ("absolute-unc-root", _UNC_ROOT_RE),
    ("absolute-posix-root", _POSIX_ROOT_RE),
)


@dataclass(frozen=True)
class Finding:
    """One problem found in a single run.

    ``kind`` is one of:

    ``"unparseable"``
        The settings file is not valid JSON. Nothing registers and nothing
        warns; this is the loudest finding here, not the quietest.
    ``"malformed"``
        The ``hooks`` section is not shaped the way the harness reads it - a
        non-object ``hooks``, a non-list event, an entry that is not an object,
        or a hook with no ``command`` string. Such an entry cannot be scanned,
        and skipping it silently would hide whatever it names.
    ``"no-commands"``
        The file parsed and declared no hook command at all. Reported so a scan
        of an empty corpus can never be mistaken for a clean bill.
    ``"absolute-drive-root"``, ``"absolute-unc-root"``, ``"absolute-posix-root"``
        A hook command names an absolute path in that spelling.

    ``event`` is the hook event name (``"SessionStart"``, ...) and ``command``
    the full command string, each ``None`` when the finding is not about one
    specific command - ``None`` rather than an empty string, so "no command
    involved" stays distinguishable from "a command that is empty".
    """

    kind: str
    detail: str
    event: str | None = None
    command: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class Report:
    """The composed verdict over one settings file.

    ``ran`` says whether the check executed; ``ok`` says whether it passed.
    Separate on purpose - a report with ``ran=False`` has ``ok=False`` and no
    findings, and a caller reading only ``findings`` would otherwise take it for
    a pass. ``commands_scanned`` carries what was actually looked at, so a green
    verdict over nothing is visible as "0 command(s)" instead of hiding behind
    the word OK.
    """

    ran: bool
    ok: bool
    findings: tuple[Finding, ...]
    commands_scanned: tuple[str, ...] = ()
    reason: str = ""

    def format(self) -> str:
        """Render the report for a human, one finding per line."""
        if not self.ran:
            return f"hook command guard: DID NOT RUN - {self.reason}"
        if self.ok:
            return (
                "hook command guard: OK "
                f"({len(self.commands_scanned)} hook command(s), no absolute path)"
            )
        lines = [
            f"hook command guard: {len(self.findings)} finding(s) over "
            f"{len(self.commands_scanned)} hook command(s)"
        ]
        lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        return "\n".join(lines)


def absolute_paths_in(command: str) -> list[tuple[str, str]]:
    """Return ``[(kind, matched_path)]`` for every absolute path in ``command``.

    Kinds are the three ``absolute-*`` strings documented on :class:`Finding`.
    Matches are returned in pattern order, then in position order within a
    pattern, so two runs over one command read identically. A command with no
    absolute path returns an empty list - which is the clean answer, and is why
    every caller must also know how many commands were scanned.
    """
    found: list[tuple[str, str]] = []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(command):
            found.append((kind, match.group(1)))
    return found


def iter_hook_commands(data: object) -> tuple[list[tuple[str, str]], list[Finding]]:
    """Walk a parsed settings object, returning commands and shape findings.

    Returns ``([(event, command)], [malformed findings])``. The walk is
    tolerant in the sense that one badly shaped entry does not stop the others
    being read, and intolerant in the sense that it REPORTS the bad shape
    rather than skipping it - an entry the guard could not read is an entry
    whose command was never checked, and reporting nothing about it would be the
    silent-skip failure this module exists to convert into a red suite.
    """
    commands: list[tuple[str, str]] = []
    findings: list[Finding] = []

    if not isinstance(data, dict):
        findings.append(
            Finding(
                kind="malformed",
                detail=(
                    "the settings file's top level is "
                    f"{type(data).__name__}, not an object - no hook can be read from it"
                ),
            )
        )
        return commands, findings

    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        findings.append(
            Finding(
                kind="malformed",
                detail=f"'hooks' is {type(hooks).__name__}, not an object",
            )
        )
        return commands, findings

    for event, entries in hooks.items():
        if not isinstance(entries, list):
            findings.append(
                Finding(
                    kind="malformed",
                    detail=f"hooks.{event} is {type(entries).__name__}, not a list",
                    event=event,
                )
            )
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                findings.append(
                    Finding(
                        kind="malformed",
                        detail=(
                            f"hooks.{event}[{index}] is "
                            f"{type(entry).__name__}, not an object"
                        ),
                        event=event,
                    )
                )
                continue
            inner = entry.get("hooks", [])
            if not isinstance(inner, list):
                findings.append(
                    Finding(
                        kind="malformed",
                        detail=(
                            f"hooks.{event}[{index}].hooks is "
                            f"{type(inner).__name__}, not a list"
                        ),
                        event=event,
                    )
                )
                continue
            for hook_index, hook in enumerate(inner):
                if not isinstance(hook, dict):
                    findings.append(
                        Finding(
                            kind="malformed",
                            detail=(
                                f"hooks.{event}[{index}].hooks[{hook_index}] is "
                                f"{type(hook).__name__}, not an object"
                            ),
                            event=event,
                        )
                    )
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or not command.strip():
                    findings.append(
                        Finding(
                            kind="malformed",
                            detail=(
                                f"hooks.{event}[{index}].hooks[{hook_index}] carries "
                                "no non-empty 'command' string"
                            ),
                            event=event,
                        )
                    )
                    continue
                commands.append((event, command))
    return commands, findings


def check_settings_text(text: str) -> Report:
    """Check one settings file's TEXT. Never raises on bad input."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return Report(
            ran=True,
            ok=False,
            findings=(
                Finding(
                    kind="unparseable",
                    detail=(
                        f"{SETTINGS_REL_PATH} is not valid JSON ({exc.msg} at line "
                        f"{exc.lineno} column {exc.colno}). No hook registers from an "
                        "unparseable settings file and nothing warns you - a single "
                        "backslash in a Windows path is the way this happens here."
                    ),
                ),
            ),
        )

    commands, findings = iter_hook_commands(data)

    for event, command in commands:
        for kind, matched in absolute_paths_in(command):
            findings.append(
                Finding(
                    kind=kind,
                    detail=(
                        f"hooks.{event}: command names the absolute path "
                        f"{matched!r} - reach the script through "
                        "$CLAUDE_PROJECT_DIR or a repo-relative path instead, so "
                        "the hook resolves the tree it is running in. Command: "
                        f"{command!r}"
                    ),
                    event=event,
                    command=command,
                    path=matched,
                )
            )

    if not commands and not findings:
        findings.append(
            Finding(
                kind="no-commands",
                detail=(
                    "the settings file parsed and declared no hook command at all. "
                    "An empty finding list over an empty corpus is the same output "
                    "as a clean tree, so this is a FAILURE to have anything to "
                    'check, not a pass.'
                ),
            )
        )

    return Report(
        ran=True,
        ok=not findings,
        findings=tuple(findings),
        commands_scanned=tuple(command for _, command in commands),
    )


def check_repo(
    repo_root: Path = REPO_ROOT,
    settings_rel_path: str = SETTINGS_REL_PATH,
) -> Report:
    """Run the check against the real settings file under ``repo_root``.

    A missing settings file is DID-NOT-RUN with its own reason. There is no tree
    to check hook commands in without it, and an empty pass there would be the
    vacuous answer this module exists to avoid.
    """
    path = repo_root / settings_rel_path
    if not path.is_file():
        return Report(
            ran=False,
            ok=False,
            findings=(),
            reason=f"{settings_rel_path} does not exist under {repo_root}",
        )
    return check_settings_text(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Run the real check and print a human report.

    Takes NO arguments, and says so instead of ignoring them - ``OPS-64`` is
    filed against a sibling guard for accepting any argv and silently
    discarding it, which makes a mistyped invocation look like a clean run.
    Unexpected arguments exit 2, distinct from the 1 that means a real finding.

    A did-not-run report exits 1 here, unlike the sibling guard's 0: this
    module's input is a TRACKED file that a working tree always has, so its
    absence is itself the defect rather than a not-yet-done migration.
    """
    args = sys.argv[1:] if argv is None else argv
    if args:
        print(
            "hook command guard: takes no arguments, got "
            f"{args!r} - refusing rather than ignoring them (OPS-64)",
            file=sys.stderr,
        )
        return 2
    report = check_repo()
    print(report.format())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
