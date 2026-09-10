"""No tracked hook command - and no unpinned permission rule - may name an
absolute path. ``OPS-61`` criterion 3 for the hook commands, ``OPS-70``
criterion 3 for the permission rules.

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

WHY IT ALSO READS ``permissions.*`` NOW - ``OPS-70``
-----------------------------------------------------
This module used to walk ``hooks.*`` and nothing else. Three entries twenty
lines away in the same document read ``Read(//C/Lanternlight/**)``,
``Write(//C/Lanternlight/**)`` and ``Edit(//C/Lanternlight/**)``, and the guard
printed ``OK`` over them - a verdict that was TRUE and answered a narrower
question than the word OK invites a reader to assume. That shape is the defect
``OPS-70`` is about, one level up from the defect this module was written for,
so the fix is to widen what is read rather than to write the blind spot down.

The scan now covers ``permissions.allow``, ``permissions.deny``,
``permissions.ask`` and ``permissions.additionalDirectories``. A rule of the
form ``Tool(content)`` is split first and only its CONTENT is scanned, because
the tool name is not a path and a report that quoted the closing parenthesis as
part of a filesystem root would be a false statement about what was found.

THE PIN, AND WHY AN ABSOLUTE PERMISSION ROOT IS NOT THE SAME DEFECT
--------------------------------------------------------------------
A hook command naming an absolute root FIRES and answers about the wrong tree.
A permission rule naming one merely fails to match in any other tree, so the
session prompts where it would not have. That is a nuisance rather than a wrong
answer, and ``OPS-70`` says so in its own text.

INFERRED for ``OPS-70`` on 2026-09-10, and NOT observed on this machine: the
permission matcher does not expand ``$CLAUDE_PROJECT_DIR``. Read and Edit rule
content is gitignore-syntax with exactly four anchors - ``//path`` from the
filesystem root, ``~/path`` from the home directory, ``/path`` from the settings
source, and a bare or ``./``-led path from the working directory - and no
environment variable is substituted into any of them. On the same sources, the
matcher normalises a Windows path to POSIX form before matching, which is why
the absolute spelling of this drive appears as ``//C/...`` rather than
``C:/...``.

THE PROVENANCE OF THAT PARAGRAPH, BECAUSE IT SHIPPED WITHOUT ONE. Until this
repair the sentences above read "Measured for OPS-70", in three places, one of
them inside the finding text a reader is handed at the moment this guard fires.
Nothing here was measured. The two sources are the published permissions
documentation and the shipped client's own rule-anchoring code read on this
machine. Each is a document rather than a run, so what is written above is an
inference and not an observation of a match - NEITHER SOURCE IS AN OBSERVATION
OF A MATCH ON THIS MACHINE. The session that established it ran in
bypass permissions mode, where every tool call is pre-approved regardless of
the allow list, so a did-it-prompt probe could not have told a
MATCHED rule from a BYPASSED one and would have returned a false green.
Settling it needs a session in default permission mode, in a clone at a
different path, watching whether an edit inside that clone is pre-approved.
This repository's rule is that a claim carrying its source or its instant is
fine while a claim stated FLAT is a defect, and a guard that prints false
provenance at failure time is the worst place to state one flat - the reader
has no way to check it and every reason to believe a guard that just caught
something real. The wording handed to that reader is
:data:`MATCHER_CLAIM_PROVENANCE`, written once so the finding text and this
docstring cannot drift apart.

So the honest statement is that the ``OPS-61`` fix is not expected to transfer,
and that ``//C/Lanternlight/**`` is believed to be the documented absolute form
rather than a mistake in spelling - correct in this checkout and inert
everywhere else. The operator's decision recorded in ``.claude/settings.json``
was to KEEP those three, which is why they are pinned here by their exact rule
strings.

The cost of pinning by value, stated rather than left implicit, because
``OPS-38`` had to generalise past exactly this twice: a guard hardened against a
list of values is scoped to that list. A fourth absolute permission rule, or a
change to any of these three, is a finding - which is the intended behaviour,
since each one is a decision that wants making again rather than inheriting.
The alternative considered and rejected was to accept any absolute root that
names the tree the guard is running in: that needs no literal, but it turns
``//C/Lanternlight/**`` red in every fresh clone, and a fresh clone of this
repository must be green.

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
* Within that file it reads ``hooks.*`` and the four ``permissions`` keys named
  above. Every other key is unread: ``env``, ``attribution``, ``model``,
  ``statusLine``, ``apiKeyHelper`` and anything a later harness adds could each
  carry an absolute path and none of them is looked at. This bullet is the
  ``OPS-70`` criterion-3 disclosure, and it is a smaller blind spot than the one
  it replaces rather than none at all.
* An EMPTY permissions section is counted and printed but is not itself a
  failure, which is deliberately unlike the hook-command corpus. A settings file
  with no permission rule is a legitimate file, while a settings file with no
  hook command has nothing for this module to check at all. The vacuity that
  matters here - the live file quietly losing its rules - is pinned by a test
  that asserts the live scan reached a non-empty list, not by the verdict.
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
    "MATCHER_CLAIM_PROVENANCE",
    "PERMISSION_RULE_SECTIONS",
    "absolute_roots_in_permission_content",
    "PINNED_ABSOLUTE_PERMISSION_RULES",
    "REPO_ROOT",
    "SETTINGS_REL_PATH",
    "Finding",
    "Report",
    "absolute_paths_in",
    "check_repo",
    "check_settings_text",
    "iter_hook_commands",
    "iter_permission_rules",
    "main",
    "split_permission_rule",
]

#: Repository root, resolved from this file's location: tools/hook_command_guard.py.
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The one tracked settings file this guard reads. See the blind-spot list.
SETTINGS_REL_PATH = ".claude/settings.json"

#: The provenance of this module's one claim about how the permission matcher
#: behaves, written in ONE place and quoted into the finding text a reader is
#: handed at failure time. It exists because that claim shipped FLAT - as
#: "Measured for OPS-70" in three places, one of them inside the user-facing
#: finding - while nothing on this machine ever observed a permission rule
#: matching anything. Keeping the sentence in a constant is not tidiness: the
#: defect was a docstring and a printed string disagreeing about how sure they
#: were, and two copies of a caveat are two chances for one of them to be
#: quietly dropped.
MATCHER_CLAIM_PROVENANCE = (
    "The permission matcher is not expected to expand $CLAUDE_PROJECT_DIR. "
    "That is an INFERENCE recorded for OPS-70 on 2026-09-10 from two sources - "
    "the published permissions documentation, and the shipped client's own "
    "rule-anchoring code read on this machine - and it is NOT an observation "
    "of a rule matching anything. The session that established it ran in "
    "bypass permissions mode, where every tool call is pre-approved regardless "
    "of the allow list, so a did-it-prompt probe cannot tell a MATCHED rule "
    "from a BYPASSED one and would return a false green either way. Settling "
    "it needs a session in default permission mode, in a clone at a different "
    "path, watching whether an edit inside that clone is pre-approved."
)

#: The keys under ``permissions`` that hold path-bearing strings. The three
#: behaviour lists hold ``Tool(content)`` rules; ``additionalDirectories`` holds
#: bare paths. Order is fixed so a report reads the same way twice.
PERMISSION_RULE_SECTIONS: tuple[str, ...] = (
    "allow",
    "deny",
    "ask",
    "additionalDirectories",
)

#: Permission rules allowed to name an absolute root, by their EXACT rule
#: string. ``OPS-70`` INFERRED that the permission matcher does not expand
#: ``$CLAUDE_PROJECT_DIR`` - see :data:`MATCHER_CLAIM_PROVENANCE`, which names
#: the two documentary sources and says plainly that no match was ever observed
#: here - and the decision recorded in the settings file's own
#: ``$comment`` was to keep these three as primary-checkout-only rather than
#: delete a pre-approval that is correct here. Pinning by value is scoped to
#: these values on purpose - see THE PIN in the module docstring. Anything else
#: absolute under ``permissions.*`` is a finding.
PINNED_ABSOLUTE_PERMISSION_RULES: frozenset[str] = frozenset(
    {
        "Read(//C/Lanternlight/**)",
        "Write(//C/Lanternlight/**)",
        "Edit(//C/Lanternlight/**)",
    }
)

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

#: A permission rule's content naming the FILESYSTEM root: a leading pair of
#: separators, in EITHER spelling. This is deliberately the SAME object the hook
#: scan uses for a UNC root rather than a near-copy of it, and the reason is the
#: defect it repairs: the permission side carried its own hand-written
#: forward-slash-only pattern, so ``Read(\\\\srv\\share\\**)`` sailed past a guard
#: that reported the identical shape in a hook command. Two near-copies of one
#: idea drift; one object cannot.
#:
#: It is also UNANCHORED, where the copy it replaces began with ``^``. See
#: :func:`absolute_roots_in_permission_content` for that decision and its cost.
_PERMISSION_FS_ROOT_RE = _UNC_ROOT_RE

#: Pattern to finding-kind for permission-rule CONTENT. Deliberately NOT
#: :data:`_PATTERNS`, and the reason is the whole reason this is a separate
#: tuple: THE TWO GRAMMARS DISAGREE ABOUT A SINGLE LEADING SLASH. In a hook
#: command ``/opt/x/tool.py`` is an absolute path and a defect. In a permission
#: rule ``/opt/x/**`` is anchored at the SETTINGS SOURCE, which is the portable
#: form this item recommends - the documentation says so in as many words, that
#: a single leading slash is not an absolute path there and that the absolute
#: form needs a second one. A home-shaped example is deliberately not written
#: out here: a home-shaped literal in a tracked file is what the ``OPS-38``
#: sibling guard reports, and this file is inside the corpus it scans.
#: Reusing the hook
#: patterns would report the recommended fix as the defect, which is this
#: repository's own recorded failure of a guard being red because of a fix, so
#: the permission scan looks only for the two spellings that really do leave
#: the running tree.
_PERMISSION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("absolute-permission-root", _PERMISSION_FS_ROOT_RE),
    ("absolute-drive-root", _DRIVE_ROOT_RE),
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
        A hook command names an absolute path in that spelling. A permission
        rule can also raise ``"absolute-drive-root"``, since a drive letter is
        the same mistake in both grammars.
    ``"absolute-permission-root"``
        An unpinned permission rule's content names the filesystem root with a
        leading pair of separators, in either spelling - ``//srv/share`` and the
        backslash form both raise it. It is its own kind rather than reusing the
        hook kinds because the two grammars disagree about a SINGLE leading
        slash - see :data:`_PERMISSION_PATTERNS` - and not because they disagree
        about a pair of them, which is why one kind covers both spellings here
        where the hook side splits them into ``absolute-unc-root`` and
        ``absolute-posix-root``.

    A hook finding carries ``event`` and ``command``; a permission finding
    carries ``location`` such as ``"permissions.allow[9]"``.

    ``event`` is the hook event name (``"SessionStart"``, ...) and ``command``
    the full command string, each ``None`` when the finding is not about one
    specific command - ``None`` rather than an empty string, so "no command
    involved" stays distinguishable from "a command that is empty". ``location``
    is the settings-file position of a permission finding, and is ``None`` for
    every finding that is not about one.
    """

    kind: str
    detail: str
    event: str | None = None
    command: str | None = None
    path: str | None = None
    location: str | None = None


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
    permission_rules_scanned: tuple[str, ...] = ()
    pinned_permission_rules: tuple[str, ...] = ()

    def format(self) -> str:
        """Render the report for a human, one finding per line.

        The counts are in the OK line on purpose. A green verdict over zero
        permission rules and a green verdict over eleven of them are different
        facts, and the word OK alone cannot tell them apart - which is the
        ``OPS-70`` complaint about this module's previous OK line. Any pinned
        absolute rule is named too: a pin nobody can see is a pin nobody
        re-checks.
        """
        if not self.ran:
            return f"hook command guard: DID NOT RUN - {self.reason}"
        scanned = (
            f"{len(self.commands_scanned)} hook command(s), "
            f"{len(self.permission_rules_scanned)} permission rule(s)"
        )
        pinned = (
            ""
            if not self.pinned_permission_rules
            else "\n  pinned absolute permission rule(s): "
            + ", ".join(self.pinned_permission_rules)
        )
        if self.ok:
            return f"hook command guard: OK ({scanned}, no unpinned absolute path){pinned}"
        lines = [f"hook command guard: {len(self.findings)} finding(s) over {scanned}"]
        lines.extend(f"  [{f.kind}] {f.detail}" for f in self.findings)
        return "\n".join(lines) + pinned


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


def split_permission_rule(rule: str) -> str:
    """Return the PATH-BEARING part of one permission rule.

    ``"Read(//C/Lanternlight/**)"`` becomes ``"//C/Lanternlight/**"``. A string
    with no ``(`` is returned stripped but otherwise UNCHANGED, which covers
    both an ``additionalDirectories`` entry - a bare path, the whole string
    being the thing to scan - and a bare tool name such as ``"Bash"``, which
    contains no path and so finds nothing either way.

    THE PROMISE THIS DOCSTRING MAKES, AND HOW IT WAS FALSE. It says a shape this
    function does not recognise is still scanned instead of being silently
    exempted. That was untrue as written, and an ``OPS-70`` refutation pass
    proved it with one character: this function used to require
    ``rule.endswith(")")`` and to hand back the WHOLE rule when it did not, so
    ``"Read(//C/Evil/**) "`` - one trailing space, the likeliest thing to
    survive a hand edit of a settings file - was returned with its ``Read(``
    prefix still on the front, and every filesystem-root pattern then failed to
    reach the path behind it. The rule was not scanned. It was exempted, exactly
    as the docstring said it would not be, and the guard printed OK.

    So the parsing is now permissive on purpose rather than strict:
    surrounding whitespace is discarded, everything after the first ``(`` is
    taken as the content, and a closing ``)`` is removed only if one is there.
    An unterminated ``"Read(//C/Evil/**"`` therefore yields its path and is
    reported, which is the behaviour the sentence above always claimed. The one
    case that still returns the whole string is an EMPTY pair of parentheses,
    where handing back ``""`` would be the silent exemption in another costume.

    The parentheses are stripped rather than scanned around for one reason
    worth writing down: the closing ``)`` would otherwise be swallowed by the
    trailing ``[^\\s"']*`` of every pattern here, and the report would name
    ``'//C/Lanternlight/**)'`` as the absolute root it found. That is a false
    statement about what is in the file, and a guard that misquotes its own
    evidence teaches a reader to distrust the parts it got right.

    Whitespace is NOT stripped in order to normalise a rule for the pin.
    :data:`PINNED_ABSOLUTE_PERMISSION_RULES` is still compared against the raw
    rule string, so ``"Read(//C/Lanternlight/**) "`` with a trailing space is a
    different string from the pinned one and is a finding. That asymmetry is
    deliberate: a permissive SCANNER errs toward reporting, while a permissive
    PIN would erode toward exempting.
    """
    stripped = rule.strip()
    open_index = stripped.find("(")
    if open_index == -1:
        return stripped
    content = stripped[open_index + 1 :]
    if content.endswith(")"):
        content = content[:-1]
    return content.strip() or stripped


def absolute_roots_in_permission_content(content: str) -> list[tuple[str, str]]:
    """Return ``[(kind, matched)]`` for every filesystem-absolute root in one
    permission rule's content.

    Two spellings are reported and no others, because only these two leave the
    tree the session is running in:

    * a pair of leading separators - ``//srv/share`` and the backslash form of
      the same share. BOTH ARE READ, and until an ``OPS-70`` refutation pass
      planted the backslash spelling and watched it pass, only the
      forward-slash one was: the permission side had its own hand-written
      pattern while the hook side already reported a UNC root, so one guard
      disagreed with itself about the same shape in two grammars. This is the
      documented absolute anchor, and it is also the spelling a Windows drive
      is BELIEVED to take once the matcher normalises to POSIX form - believed
      rather than seen, see :data:`MATCHER_CLAIM_PROVENANCE` - which is why
      ``//C/Lanternlight/**`` is here rather than under the drive kind;
    * a drive letter followed by a separator - not one of the four documented
      anchors at all, so it is expected to degrade to a
      working-directory-relative pattern with a literal ``C:`` segment and
      match nothing.

    THE SCAN IS UNANCHORED, AND THAT IS A DECISION - ``OPS-70`` REPAIR
    ------------------------------------------------------------------
    A path is IN SCOPE wherever it appears in a rule's content, not only at
    character zero. Before this repair the drive pattern scanned the whole
    content while the filesystem-root pattern began with ``^``, so
    ``Bash(cd C:/Evil && ls)`` was a finding and ``Bash(cd //C/Evil && ls)``
    was not: the same rule, the same tree, two verdicts decided by which
    pattern happened to carry an anchor. The two now agree.

    They were made to agree in the direction that reports MORE rather than
    less, for two reasons worth separating. The first is that narrowing would
    have DELETED coverage that already existed, and a guard must not move that
    way. The second is that the widening is the answer this module's own
    question implies: it asks whether a rule names a root the running tree
    cannot verify is its own, and a root buried in a ``Bash`` rule's command
    text names one exactly as much as a root at the front of a ``Read`` rule's
    glob does - the ``Bash`` grammar is a command prefix rather than a path
    pattern, so the four gitignore anchors never applied to it in the first
    place and there was never a reason to treat position as meaningful there.

    The cost, stated rather than left implicit: a rule whose argument
    legitimately quotes an absolute path that is NOT a repository root is
    reported and has to be dealt with, by the same pinned-by-exact-string route
    the three ``//C/Lanternlight`` rules take. That is the intended behaviour
    rather than a regrettable side effect, since such a rule is a decision that
    wants making again rather than inheriting.

    Deliberately NOT reported, each for a stated reason rather than by
    omission:

    * a single leading ``/``, which anchors at the settings source and is the
      portable form. This is the one place the permission grammar and the
      hook-command grammar genuinely disagree, and it is why the widening above
      stops short of reusing the hook patterns wholesale;
    * a URL. A ``//`` preceded by a colon is refused by lookbehind, so
      ``Bash(curl https://host/x)`` is clean. Reporting a URL as a filesystem
      root would be a false statement about what was found, and a guard that
      misquotes its evidence teaches a reader to distrust the parts it got
      right;
    * a leading ``~/``, which anchors at the home directory. It travels between
      clones and is a different question from this one - whose TREE does this
      rule name - so reporting it here would widen the guard past what has been
      established about it;
    * a ``$CLAUDE_PROJECT_DIR`` prefix. It is not EXPECTED to be expanded for
      permission rules - :data:`MATCHER_CLAIM_PROVENANCE` says where that
      expectation comes from and why it is not a measurement - so on that
      reading it is not an absolute root but a rule that matches nothing, and
      pretending this pattern check can see the difference is worse than saying
      it cannot.
    """
    found: list[tuple[str, str]] = []
    stripped = content.strip()
    for kind, pattern in _PERMISSION_PATTERNS:
        for match in pattern.finditer(stripped):
            found.append((kind, match.group(1)))
    return found


def iter_permission_rules(data: object) -> tuple[list[tuple[str, str]], list[Finding]]:
    """Walk a parsed settings object's ``permissions``, returning rules and findings.

    Returns ``([(location, rule)], [malformed findings])`` where ``location`` is
    a settings-file position such as ``"permissions.allow[9]"``. Same contract
    as :func:`iter_hook_commands`: an entry that cannot be read is REPORTED
    rather than skipped, because an entry the guard could not read is an entry
    whose path was never checked.

    A missing ``permissions`` key returns no rules and no findings. That is not
    a pass on its own - see the empty-section bullet in the module docstring for
    why the vacuity is pinned by a test over the live file instead of by this
    walk's verdict.
    """
    rules: list[tuple[str, str]] = []
    findings: list[Finding] = []

    if not isinstance(data, dict):
        return rules, findings

    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        findings.append(
            Finding(
                kind="malformed",
                detail=(
                    f"'permissions' is {type(permissions).__name__}, not an object"
                ),
                location="permissions",
            )
        )
        return rules, findings

    for section in PERMISSION_RULE_SECTIONS:
        entries = permissions.get(section)
        if entries is None:
            continue
        if not isinstance(entries, list):
            findings.append(
                Finding(
                    kind="malformed",
                    detail=(
                        f"permissions.{section} is "
                        f"{type(entries).__name__}, not a list"
                    ),
                    location=f"permissions.{section}",
                )
            )
            continue
        for index, entry in enumerate(entries):
            location = f"permissions.{section}[{index}]"
            if not isinstance(entry, str) or not entry.strip():
                findings.append(
                    Finding(
                        kind="malformed",
                        detail=(
                            f"{location} is "
                            f"{type(entry).__name__}, not a non-empty string"
                        ),
                        location=location,
                    )
                )
                continue
            rules.append((location, entry))
    return rules, findings


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
    rules, rule_findings = iter_permission_rules(data)
    findings.extend(rule_findings)

    pinned: list[str] = []
    for location, rule in rules:
        matches = absolute_roots_in_permission_content(split_permission_rule(rule))
        if not matches:
            continue
        if rule in PINNED_ABSOLUTE_PERMISSION_RULES:
            pinned.append(rule)
            continue
        for kind, matched in matches:
            findings.append(
                Finding(
                    kind=kind,
                    detail=(
                        f"{location}: permission rule names the absolute path "
                        f"{matched!r}, and it is not one of this repository's "
                        "pinned rules. A permission rule anchored at a "
                        "filesystem root is expected to match in the checkout "
                        "it names and nowhere else, so in a clone or a worktree "
                        "it would silently do nothing. "
                        + MATCHER_CLAIM_PROVENANCE
                        + " On that reading the OPS-61 fix does not transfer: "
                        "anchor the rule at the settings source instead, or add "
                        "it to PINNED_ABSOLUTE_PERMISSION_RULES with the reason "
                        "in the settings file's own $comment. Rule: "
                        f"{rule!r}"
                    ),
                    path=matched,
                    location=location,
                )
            )

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
        permission_rules_scanned=tuple(rule for _, rule in rules),
        pinned_permission_rules=tuple(pinned),
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
