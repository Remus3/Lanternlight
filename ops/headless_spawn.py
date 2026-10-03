"""The one door every headless ``claude`` run from this tree goes through.

OPERATOR RULING, 2026-10-02, in this tree's own session - recorded in
``CLAUDE.md`` and ``LL-0317``. Headless runs (inbox runner, lane, loop,
watchdog - anything that starts ``claude`` with no session open) bill the
operator's SECOND subscription through a local proxy, never the interactive one.

THE CONTRACT, and each clause is a test in ``tests/test_headless_spawn.py``:

* The base URL is read AT SPAWN TIME from the USER environment store first
  (``HKCU\\Environment`` through :mod:`winreg`) and the process environment
  second. A process started before the variable was set does not inherit it,
  which is why the store is read directly rather than trusted to ``os.environ``.
* It reaches the CHILD's environment as ``ANTHROPIC_BASE_URL`` and nothing
  else's. This module never writes ``os.environ`` and never sets anything
  user-wide or machine-wide.
* FAIL CLOSED. An unset variable, a URL that is not plain http on a loopback
  host with an explicit port, or a proxy that refuses a TCP connection on
  ``127.0.0.1`` refuses the spawn and logs why. There is NO fallback to a direct
  ``claude``, and ``--auto-fallback`` is refused wherever it appears, because
  both bill the interactive subscription.
* A usage-limit refusal BACKS OFF - an exponential hold written under
  ``ops/runtime/`` - and never retries another way. An unreadable backoff file
  is read as "still backing off", which is the closed direction.
* Deleting the variable is the operator's kill switch for every tree at once.
  Because the variable is re-read on every spawn, that switch takes effect on
  the very next attempt with nothing to restart.

WHAT IS NEVER WRITTEN DOWN. The URL carries an account path segment, so it
appears in no tracked file and in no log line here: the log records the
decision and the reason, never the value. Same for the child's output - only
its length and return code are logged, because a transcript can carry anything.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

__all__ = [
    "BACKOFF_BASE",
    "BACKOFF_MAX",
    "BACKOFF_NAME",
    "HEADLESS_VAR",
    "LOG_NAME",
    "SpawnResult",
    "resolve_base_url",
    "run_tree",
    "spawn",
    "tcp_probe",
]

HEADLESS_VAR = "CLAUDE_HEADLESS_BASE_URL"
LOG_NAME = "headless_spawn.log"
BACKOFF_NAME = "headless_backoff.json"
BACKOFF_BASE = timedelta(minutes=30)
BACKOFF_MAX = timedelta(hours=6)
DEFAULT_TIMEOUT = 45 * 60

_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
_USAGE_LIMIT_MARKERS = ("usage limit", "rate_limit_error", "rate limit")

REPO_ROOT = Path(__file__).resolve().parents[1]


def _default_runtime() -> Path:
    return REPO_ROOT / "ops" / "runtime"


def _user_store(name: str) -> str | None:
    """Read one value from the USER environment store, or None."""
    if os.name != "nt":
        return None
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _kind = winreg.QueryValueEx(key, name)
    except OSError:
        return None
    return value if isinstance(value, str) else None


def resolve_base_url(
    *,
    user_store: Callable[[str], str | None] = _user_store,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """User store first, process env second; blank is unset."""
    env = os.environ if environ is None else environ
    for value in (user_store(HEADLESS_VAR), env.get(HEADLESS_VAR)):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def tcp_probe(host: str, port: int, timeout: float = 3.0) -> bool:
    """True when something accepts a TCP connection at host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@dataclass(frozen=True)
class SpawnResult:
    spawned: bool
    reason: str
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    usage_limited: bool = False


def _atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=target.suffix)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    Path(tmp).replace(target)


def _log(runtime: Path, now: datetime, **fields) -> None:
    runtime.mkdir(parents=True, exist_ok=True)
    rec = {"at": now.isoformat(), **fields}
    with (runtime / LOG_NAME).open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _check_url(url: str) -> tuple[tuple[str, int] | None, str]:
    """Return ((probe_host, port), "") or (None, reason).

    STRICT ON PURPOSE. Python's parser and the CLI's parser disagree about
    some URLs: ``http://evil.invalid\\@localhost:18999`` is host ``localhost``
    to :func:`urllib.parse.urlsplit` and host ``evil.invalid`` to Node, so a
    check that trusts the parsed host would probe our proxy while the child
    talked elsewhere - measured by the 2026-10-02 refutation pass. So any
    backslash, any ``@``, any whitespace, and any netloc that is not EXACTLY
    ``host:port`` is refused before parsing is trusted.
    """
    if any(ch in url for ch in "\\@") or any(ch.isspace() for ch in url):
        return None, "REFUSED: base URL carries userinfo, a backslash or whitespace"
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None, "REFUSED: base URL is malformed"
    if parts.scheme != "http":
        return None, "REFUSED: base URL is not plain http to a local proxy"
    host = (parts.hostname or "").lower()
    if host not in _LOOPBACK_NAMES:
        return None, "REFUSED: base URL host is not loopback"
    if port is None:
        return None, "REFUSED: base URL names no port"
    shown = f"[{host}]" if ":" in host else host
    if parts.netloc.lower() != f"{shown}:{port}":
        return None, "REFUSED: base URL netloc is not exactly host:port"
    return ("::1" if host == "::1" else "127.0.0.1", port), ""


def _backoff_state(runtime: Path) -> tuple[dict | None, bool]:
    """(state, readable). Missing file is (None, True)."""
    path = runtime / BACKOFF_NAME
    if not path.exists():
        return None, True
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        datetime.fromisoformat(state["until"])
        if not isinstance(state["streak"], int) or isinstance(state["streak"], bool):
            return None, False
        return state, True
    except (OSError, ValueError, KeyError, TypeError):
        return None, False


def _is_usage_limited(stdout: str, stderr: str) -> bool:
    text = f"{stdout}\n{stderr}".lower()
    return any(marker in text for marker in _USAGE_LIMIT_MARKERS)


# Names stripped from the CHILD's environment, and why. A credential in the
# child would let the CLI bill something other than the proxy's subscription,
# and a provider switch makes the CLI ignore ANTHROPIC_BASE_URL altogether.
# The 2026-10-02 refutation pass found ANTHROPIC_API_KEY present in this
# machine's environment, so a scheduled-task child inherited it.
_STRIP_EXACT = frozenset({"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"})
_STRIP_PREFIXES = ("CLAUDE_CODE_USE_",)


def _must_not_inherit(name: str) -> bool:
    upper = name.upper()
    if upper in _STRIP_EXACT or upper.startswith(_STRIP_PREFIXES):
        return True
    return upper.startswith("ANTHROPIC_") and upper.endswith("_BASE_URL")


def run_tree(argv, *, timeout=None, **kwargs) -> subprocess.CompletedProcess:
    """:func:`subprocess.run` that kills the WHOLE process tree on timeout.

    ``claude`` on this machine is an npm ``.cmd`` shim, so the direct child is
    cmd.exe and the CLI is its grandchild; ``subprocess.run`` kills only the
    direct child and then waits on pipes the grandchild still holds - measured
    by the refutation pass as a 1 s timeout returning after 10 s. ``taskkill /T``
    takes the tree. It is called with an argument LIST, never through a shell,
    so no MSYS path conversion can rewrite ``/F``.
    """
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = kwargs["stderr"] = subprocess.PIPE
    with subprocess.Popen(argv, **kwargs) as proc:
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                proc.kill()
            proc.communicate()
            raise
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def _default_claude() -> str:
    return shutil.which("claude") or "claude"


def spawn(
    args: Sequence[str],
    *,
    base_url: str | None | object = ...,
    probe: Callable[[str, int], bool] = tcp_probe,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
    runtime: Path | None = None,
    now: datetime | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    cwd: Path | None = None,
    claude: str | None = None,
    user_store: Callable[[str], str | None] = _user_store,
    environ: Mapping[str, str] | None = None,
) -> SpawnResult:
    """Run ``claude <args>`` through the headless proxy, or refuse and say why.

    ``base_url`` left at its default is resolved here, at spawn time; a test
    passes it explicitly, ``None`` included.
    """
    runtime = Path(runtime) if runtime is not None else _default_runtime()
    now = now or datetime.now(UTC)
    url = resolve_base_url(user_store=user_store, environ=environ) if base_url is ... else base_url

    def refuse(reason: str) -> SpawnResult:
        _log(runtime, now, spawned=False, reason=reason)
        return SpawnResult(False, reason)

    if any("auto-fallback" in a for a in args):
        return refuse("REFUSED: --auto-fallback bills the interactive subscription")
    if not url:
        return refuse(f"REFUSED: {HEADLESS_VAR} is UNSET in the user store and the process env")
    target, why = _check_url(str(url))
    if target is None:
        return refuse(why)
    probe_host, port = target
    state, readable = _backoff_state(runtime)
    if not readable:
        return refuse("REFUSED: BACKOFF file unreadable; holding until an operator removes it")
    if state is not None and datetime.fromisoformat(state["until"]) > now:
        return refuse(f"REFUSED: BACKOFF after a usage limit, until {state['until']}")
    if not probe(probe_host, port):
        return refuse("REFUSED: the local proxy refused a TCP connection")

    child_env = {k: v for k, v in os.environ.items() if not _must_not_inherit(k)}
    child_env["ANTHROPIC_BASE_URL"] = str(url)
    kwargs: dict = {
        "env": child_env,
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
        "stdin": subprocess.DEVNULL,
    }
    if cwd is not None:
        kwargs["cwd"] = str(cwd)
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    argv = [claude or _default_claude(), *args]

    try:
        done = (runner or run_tree)(argv, **kwargs)
    except subprocess.TimeoutExpired:
        _log(runtime, now, spawned=True, reason="TIMEOUT", returncode=None)
        return SpawnResult(True, "TIMEOUT: the child outlived its budget", None)
    except OSError as exc:
        return refuse(f"REFUSED: could not start the CLI ({type(exc).__name__})")

    stdout, stderr = done.stdout or "", done.stderr or ""
    limited = done.returncode != 0 and _is_usage_limited(stdout, stderr)
    if limited:
        streak = (state or {}).get("streak", 0) + 1
        span = min(BACKOFF_BASE * (2 ** (streak - 1)), BACKOFF_MAX)
        _atomic_write(runtime / BACKOFF_NAME,
                      json.dumps({"until": (now + span).isoformat(), "streak": streak}))
        reason = f"USAGE LIMIT: backing off {int(span.total_seconds())} s, no retry"
    else:
        if done.returncode == 0 and (runtime / BACKOFF_NAME).exists():
            (runtime / BACKOFF_NAME).unlink()
        reason = "RAN"
    _log(runtime, now, spawned=True, reason=reason, returncode=done.returncode,
         stdout_chars=len(stdout), stderr_chars=len(stderr))
    return SpawnResult(True, reason, done.returncode, stdout, stderr, limited)


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m ops.headless_spawn -- <claude args>``: one gated spawn."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["--"]:
        args = args[1:]
    res = spawn(args)
    print(res.reason)
    if res.stdout:
        print(res.stdout.rstrip())
    return 0 if res.spawned and res.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
