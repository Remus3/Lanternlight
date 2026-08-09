"""Point this repository's git hooks at the tracked ``.githooks/`` directory.

WHY THIS SCRIPT EXISTS
----------------------

``core.hooksPath`` is **local** git configuration. It lives in ``.git/config``,
which is not part of the tree and is never cloned. That means the hooks in
``.githooks/`` are tracked, reviewed and versioned like any other file - and a
fresh clone of this repository still runs **zero** of them until somebody sets
``core.hooksPath``. Nothing warns you. ``git commit`` succeeds, quietly, with
no protection at all.

For Lanternlight that gap is not cosmetic. The ``pre-commit`` hook is the
second fence keeping operator PII out of a public repo: the game writes logs
and saves carrying a SteamID64, a Steam persona name, GSDK openID/userId, an
EOS ProductUserId and IP-resolved geolocation, and local screen captures of the
game are just as identifying. ``.gitignore`` is the first fence, but a
``git add -f`` or an unanticipated path walks straight past it. On a fresh
clone with no hooks installed, the second fence is simply absent.

So: **the first thing to do in a fresh clone is run this script.**

    python scripts/install_hooks.py

It is idempotent - running it again on an already-configured clone reports that
nothing needed changing and exits 0. It never rewrites a hook file; it only
wires up the path and verifies the tracked hooks are present.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

HOOKS_DIRNAME = ".githooks"
REQUIRED_HOOKS = ("pre-commit", "commit-msg")


def run_git(args: list[str], cwd: Path) -> tuple[int, str]:
    """Run a git command and return ``(returncode, stripped stdout)``."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def find_repo_root(start: Path) -> Path | None:
    """Return the top level of the git work tree containing ``start``."""
    code, out = run_git(["rev-parse", "--show-toplevel"], start)
    if code != 0 or not out:
        return None
    return Path(out).resolve()


def make_executable(path: Path) -> bool:
    """Best-effort add the user/group/other execute bits. True if changed.

    On Windows this is largely a no-op and ``core.filemode`` is usually false,
    so git records mode 100644 regardless. Git for Windows runs hooks through
    ``sh`` and does not consult the execute bit, so a hook still fires. The
    call is here for POSIX clones, where the bit is load bearing.
    """
    try:
        current = path.stat().st_mode
    except OSError:
        return False
    wanted = current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    if wanted == current:
        return False
    try:
        path.chmod(wanted)
    except OSError:
        return False
    # Re-stat rather than assume. On Windows the execute bit is not a real
    # thing and chmod silently drops it, so an unconditional "added" here
    # would print on every single run and make the script look non-idempotent.
    try:
        return path.stat().st_mode == wanted
    except OSError:
        return False


def main() -> int:
    here = Path(__file__).resolve().parent
    repo_root = find_repo_root(here)
    if repo_root is None:
        print("ERROR: not inside a git work tree.", file=sys.stderr)
        print(f"       looked upward from: {here}", file=sys.stderr)
        print("       run 'git init' first, then re-run this script.", file=sys.stderr)
        return 2

    print(f"repo root      : {repo_root}")

    hooks_dir = repo_root / HOOKS_DIRNAME
    if not hooks_dir.is_dir():
        print(f"ERROR: {hooks_dir} does not exist.", file=sys.stderr)
        print("       this script wires up hooks, it does not author them.", file=sys.stderr)
        return 2

    missing = [name for name in REQUIRED_HOOKS if not (hooks_dir / name).is_file()]
    if missing:
        print(f"ERROR: missing hook file(s) in {HOOKS_DIRNAME}/: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    for name in REQUIRED_HOOKS:
        hook = hooks_dir / name
        changed = make_executable(hook)
        suffix = " (execute bit added)" if changed else ""
        print(f"hook present   : {HOOKS_DIRNAME}/{name}{suffix}")

    code, current = run_git(["config", "--local", "--get", "core.hooksPath"], repo_root)
    current_value = current if code == 0 else ""

    if current_value == HOOKS_DIRNAME:
        print(f"core.hooksPath : already '{HOOKS_DIRNAME}' - no change needed")
    else:
        set_code, _ = run_git(["config", "--local", "core.hooksPath", HOOKS_DIRNAME], repo_root)
        if set_code != 0:
            print("ERROR: 'git config --local core.hooksPath' failed.", file=sys.stderr)
            return 1
        if current_value:
            print(f"core.hooksPath : changed from '{current_value}' to '{HOOKS_DIRNAME}'")
        else:
            print(f"core.hooksPath : set to '{HOOKS_DIRNAME}' (was unset)")

    verify_code, verify_value = run_git(
        ["config", "--local", "--get", "core.hooksPath"], repo_root
    )
    if verify_code != 0 or verify_value != HOOKS_DIRNAME:
        print(f"ERROR: verification failed - core.hooksPath reads '{verify_value}'",
              file=sys.stderr)
        return 1

    print("verified       : core.hooksPath == " + HOOKS_DIRNAME)
    print("")
    print("Hooks are active for THIS clone only. core.hooksPath is local config")
    print("and is never cloned - every fresh clone must run this script again.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
