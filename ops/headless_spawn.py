"""The one door every headless ``claude`` run from this tree goes through.

OPERATOR RULING, 2026-10-02, recorded in ``CLAUDE.md`` and ``LL-0317``:
headless runs bill the operator's SECOND subscription through a local proxy.
MAIN ORDER 0955 section 2 step 4 (2026-10-03, operator authority, provenance
checked): every headless ``claude`` in every tree goes through MAIN's fleet kit,
``ops/fleet_kit/fleet_headless.spawn``, and each tree deletes its own proxy,
probe, budget, skip, status and console code. So this module is now a THIN
WRAPPER around the kit. Our code still calls only this module; this module is
the only caller of the kit's ``spawn``.

WHAT THE KIT NOW DOES, and this module therefore no longer does: reads the
proxy URL (registry first, so a readable store WITHOUT the value is the kill
switch even over a stale inherited copy), checks it is plain http to loopback,
probes it, fails closed; strips credentials and provider switches from the
child env; enforces the 120-runs-per-rolling-day budget AT THE DOOR (so the
CLI below, which used to bypass the runner's cap, now gets it); adds the lean
flags; hides the console; writes ``ops/loop/control/inbox_status.json``,
``headless_budget.json`` and ``headless_usage.jsonl``.

WHAT THIS WRAPPER KEEPS, because the kit cannot express it (each is a gap
reported to MAIN, never a patch to the vendored copy):

* ``--bare`` and ``--auto-fallback`` are REFUSED wherever they appear, in the
  prompt or in ``extra``, BEFORE the kit is called. ``--bare`` skips hooks and
  this tree's floors live in a PreToolUse hook; ``--auto-fallback`` bills the
  interactive subscription. The kit passes ``extra`` through unchecked, so the
  refusal has to live here. The kit is always called with ``bare=False``.
* USAGE-LIMIT BACKOFF: an exponential hold under ``ops/runtime/``, never a
  retry another way. An unreadable backoff file holds closed. The kit has none.
* The per-tree HALT file ``ops/runtime/INBOX_RUNNER_HALT`` refuses every spawn
  through this door, the CLI included.
* The child is run through the kit's own v4 runner (MAIN 1204 s7 step 3: the
  local ``run_tree`` copy was deleted) - stdin closed, output decoded as UTF-8
  with replacement, the WHOLE tree killed on timeout. This door wraps it only
  to keep the raw stdout and stderr for the usage-limit backoff.
* A timeout, start failure or kit error escaping the kit is reported, not
  raised, and the status file the kit left at ``running`` is set back to
  ``idle``.
* A decision log, ``ops/runtime/headless_spawn.log``: every refusal and every
  run, reason and lengths only. It never carries the URL, a note name, model
  output, or usage numbers - the kit's usage file is the one usage record.

ROUTING, documented because the kit takes different inputs from ours. The kit
picks the MODEL from ``writes_code`` (opus when True) and the EFFORT from
``pick_effort(note)`` - low when the note string contains an ack marker. This
door passes ``note`` from a FIXED vocabulary, never channel text (the kit logs
it): :data:`NOTE_ACK` reads as low, :data:`NOTE_WORK` as medium. The runner maps
ORDER/FIX/RULING mail to ``writes_code=True`` with :data:`NOTE_WORK`, an
all-acknowledgement batch to :data:`NOTE_ACK`, everything else to
:data:`NOTE_WORK`. ``tests/test_spawn_routes_through_fleet_kit.py`` asks the
kit itself what each note string yields.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ops.fleet_kit import fleet_headless as kit

__all__ = [
    "BACKOFF_BASE",
    "BACKOFF_MAX",
    "BACKOFF_NAME",
    "CODE",
    "HALT_NAME",
    "LOG_NAME",
    "NOTE_ACK",
    "NOTE_WORK",
    "SpawnResult",
    "main",
    "spawn",
]

CODE = "LL"
HALT_NAME = "INBOX_RUNNER_HALT"
LOG_NAME = "headless_spawn.log"
BACKOFF_NAME = "headless_backoff.json"
BACKOFF_BASE = timedelta(minutes=30)
BACKOFF_MAX = timedelta(hours=6)
DEFAULT_TIMEOUT = 45 * 60

#: The note strings handed to the kit. FIXED vocabulary: the kit writes the
#: note into its usage log, so channel-chosen text must never reach it.
#: ``kit.pick_effort`` reads NOTE_ACK as "low" (it carries ``ACK``) and
#: NOTE_WORK as "medium" (it carries no ack marker).
NOTE_ACK = "LL-RUNNER-ACK-BATCH"
NOTE_WORK = "LL-RUNNER-MAIL-BATCH"

_USAGE_LIMIT_MARKERS = ("usage limit", "rate_limit_error", "rate limit")
_FORBIDDEN = (
    ("--bare", "REFUSED: --bare skips hooks, and this tree's floors live in a "
               "PreToolUse hook"),
    ("auto-fallback", "REFUSED: --auto-fallback bills the interactive subscription"),
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _kit_run(argv, **kwargs) -> subprocess.CompletedProcess:
    """The ``run`` seam handed to the kit: the kit's own v4 runner (stdin
    DEVNULL by default, whole-tree kill on timeout); the kit itself passes
    UTF-8 with replacement. Kept as a seam so the door can record the result."""
    return kit._run(argv, **kwargs)


def _default_exe() -> str:
    """The kit's own resolver (it prefers the real claude.exe behind the npm
    shim), given the PATH lookup explicitly."""
    return kit.claude_exe(shutil.which)


def _status_idle(root: Path) -> None:
    """Put the kit's status file back to idle after an exception escaped it."""
    with contextlib.suppress(Exception):
        kit.write_status(root, CODE, "idle", "Idle", time.time(),
                         kit.RunBudget(root / kit.BUDGET_REL))


def spawn(
    prompt: str,
    *,
    note: str = NOTE_WORK,
    writes_code: bool = False,
    extra: Sequence[str] = (),
    root: Path | None = None,
    runtime: Path | None = None,
    now: datetime | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    run: Callable[..., subprocess.CompletedProcess] | None = None,
    url_source: Callable[[], str | None] | None = None,
    connect: Callable | None = None,
    exe_source: Callable[[], str] | None = None,
    kit_spawn: Callable[..., dict] | None = None,
) -> SpawnResult:
    """Run ONE headless ``claude -p prompt`` through the fleet kit, or refuse.

    ``url_source``, ``connect`` and ``exe_source`` are the kit's own seams and
    are passed only when given, so in production the kit's defaults decide.
    """
    root = Path(root) if root is not None else REPO_ROOT
    runtime = Path(runtime) if runtime is not None else root / "ops" / "runtime"
    now = now or datetime.now(UTC)
    extra = [str(a) for a in extra]

    def refuse(reason: str) -> SpawnResult:
        _log(runtime, now, spawned=False, reason=reason)
        return SpawnResult(False, reason)

    if (runtime / HALT_NAME).exists():
        return refuse(f"HALT: {HALT_NAME} present; nothing spawned")
    for token, why in _FORBIDDEN:
        if any(token in a for a in [prompt, *extra]):
            return refuse(why)
    state, readable = _backoff_state(runtime)
    if not readable:
        return refuse("REFUSED: BACKOFF file unreadable; holding until an operator removes it")
    if state is not None and datetime.fromisoformat(state["until"]) > now:
        return refuse(f"REFUSED: BACKOFF after a usage limit, until {state['until']}")

    captured: dict = {}

    def recording_run(argv, **kwargs):
        done = (run or _kit_run)(argv, **kwargs)
        captured["done"] = done
        return done

    kwargs: dict = {"note": note, "writes_code": writes_code, "bare": False,
                    "timeout": timeout, "extra": tuple(extra), "run": recording_run,
                    "exe_source": exe_source or _default_exe}
    if url_source is not None:
        kwargs["url_source"] = url_source
    if connect is not None:
        kwargs["connect"] = connect

    try:
        line = (kit_spawn or kit.spawn)(root, CODE, prompt, **kwargs)
    except kit.Refused as exc:
        why = str(exc)
        prefix = "LIMIT: " if "budget" in why else "REFUSED: "
        return refuse(prefix + why)
    except subprocess.TimeoutExpired:  # a kit_spawn seam that still raises
        _status_idle(root)
        _log(runtime, now, spawned=True, reason="TIMEOUT", returncode=None)
        return SpawnResult(True, "TIMEOUT: the child outlived its budget", None)
    except OSError as exc:
        _status_idle(root)
        return refuse(f"REFUSED: could not start the CLI ({type(exc).__name__})")
    except ValueError as exc:  # the kit's URL parse raises on a malformed port
        return refuse(f"REFUSED: the kit rejected the proxy URL ({type(exc).__name__})")
    except Exception as exc:
        # Since kit v4 a non-dict stdout yields null fields, but any other
        # error after the child ran still re-raises; the run happened and is
        # counted, so say so.
        _status_idle(root)
        done = captured.get("done")
        if done is None:
            return refuse(f"REFUSED: the kit raised {type(exc).__name__}")
        _log(runtime, now, spawned=True, reason=f"KIT ERROR: {type(exc).__name__}",
             returncode=done.returncode)
        return SpawnResult(True, f"KIT ERROR: {type(exc).__name__} after the child ran",
                           done.returncode, done.stdout or "", done.stderr or "")

    done = captured.get("done")
    stdout = (done.stdout or "") if done is not None else ""
    stderr = (done.stderr or "") if done is not None else ""
    rc = line.get("rc") if isinstance(line, dict) else None
    if isinstance(line, dict) and line.get("error") == "timeout":
        # Kit v4 catches the timeout, kills the tree and resets its status.
        _log(runtime, now, spawned=True, reason="TIMEOUT", returncode=None)
        return SpawnResult(True, "TIMEOUT: the child outlived its budget", None)
    limited = rc not in (0, None) and _is_usage_limited(stdout, stderr)
    if limited:
        streak = (state or {}).get("streak", 0) + 1
        span = min(BACKOFF_BASE * (2 ** (streak - 1)), BACKOFF_MAX)
        _atomic_write(runtime / BACKOFF_NAME,
                      json.dumps({"until": (now + span).isoformat(), "streak": streak}))
        reason = f"USAGE LIMIT: backing off {int(span.total_seconds())} s, no retry"
    else:
        if rc == 0 and (runtime / BACKOFF_NAME).exists():
            (runtime / BACKOFF_NAME).unlink()
        reason = "RAN"
    _log(runtime, now, spawned=True, reason=reason, returncode=rc,
         stdout_chars=len(stdout), stderr_chars=len(stderr))
    return SpawnResult(True, reason, rc, stdout, stderr, limited)


def main(argv: Sequence[str] | None = None) -> int:
    """``python -m ops.headless_spawn [--writes-code] [--note N] -- PROMPT [EXTRA...]``.

    One gated spawn through the same door as the runner: the HALT file, the
    ``--bare``/``--auto-fallback`` refusal, the backoff, and - because it now
    lives in the kit door - the run budget all apply.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    writes_code, note = False, NOTE_WORK
    while args and args[0] in ("--writes-code", "--note"):
        flag = args.pop(0)
        if flag == "--writes-code":
            writes_code = True
        elif args:
            note = args.pop(0)
    if args[:1] == ["--"]:
        args = args[1:]
    if not args:
        print("usage: python -m ops.headless_spawn [--writes-code] [--note N] -- PROMPT [EXTRA...]")
        return 2
    res = spawn(args[0], note=note, writes_code=writes_code, extra=args[1:])
    print(res.reason)
    if res.stdout:
        print(res.stdout.rstrip())
    return 0 if res.spawned and res.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
