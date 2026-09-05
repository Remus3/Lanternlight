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
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import sys
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


if __name__ == "__main__":
    try:
        _exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a gate must never wedge the session
        _say(f"precommit_gate soft-failed, allowing: {exc}\n")
        _exit(0)
