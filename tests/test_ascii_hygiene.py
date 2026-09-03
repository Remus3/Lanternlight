"""Enforce the 7-bit ASCII authoring rule across the repository.

Every authored text file in this repository must be pure 7-bit ASCII. No
em-dashes, no en-dashes, no smart quotes, no non-breaking spaces. Use " - "
for a clause break.

This is not decoration. Non-ASCII characters smuggled into source have caused
real, expensive failures: a UTF-8 em-dash inside a double-quoted string in a
no-BOM script gets ANSI-decoded by some Windows tooling into a smart quote,
which the tokenizer then treats as a string terminator, and the parse failure
cascades far from its cause. Smart quotes pasted from a document look correct
in a diff and are invisible in most terminals.

This test is the enforcement arm of that rule, so its failure output has to be
genuinely actionable: it names the file, the byte offset, the line and column,
the codepoint and the character itself, and it shows the surrounding text. A
lint failure that says only "non-ASCII found" costs more than it saves.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

import _tracked  # noqa: E402  (sits beside this file in tests/)

MIN_EXPECTED_FILES = _tracked.MIN_EXPECTED_FILES


def iter_text_files(root: Path = REPO_ROOT):
    """Yield every authored text file that would be published from ``root``.

    Delegates to :mod:`tests._tracked`, which asks git what is tracked instead
    of guessing from file extensions. The previous extension allowlist here
    silently skipped LICENSE, NOTICE, .gitignore, .gitattributes and the
    .githooks scripts - all suffixless, all published, none ever scanned.
    """
    return _tracked.iter_authored_files(root)


def _offenses(data: bytes, limit: int = 5):
    """Return up to ``limit`` non-ASCII byte offenses as detail dicts."""
    found = []
    line = 1
    col = 1
    for index, byte in enumerate(data):
        if byte >= 0x80:
            found.append({"offset": index, "byte": byte, "line": line, "col": col})
            if len(found) >= limit:
                break
        if byte == 0x0A:
            line += 1
            col = 1
        else:
            col += 1
    return found


def _describe(path: Path, data: bytes, offense: dict) -> str:
    index = offense["offset"]
    chunk = data[index : index + 4]
    try:
        char = chunk.decode("utf-8")[0]
        codepoint = f"U+{ord(char):04X}"
        shown = repr(char)
    except (UnicodeDecodeError, IndexError):
        char = ""
        codepoint = "not-valid-utf8"
        shown = repr(chunk[:1])

    start = max(0, index - 40)
    end = min(len(data), index + 40)
    context = data[start:end].decode("utf-8", errors="replace").replace("\n", "\\n")

    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)

    return (
        f"{rel}:{offense['line']}:{offense['col']} "
        f"byte offset {offense['offset']} "
        f"raw byte 0x{offense['byte']:02X} "
        f"char {shown} ({codepoint})\n"
        f"    context: ...{context}..."
    )


def test_repository_is_seven_bit_ascii():
    files = list(iter_text_files())
    assert len(files) >= MIN_EXPECTED_FILES, (
        "the ASCII walker found "
        f"{len(files)} candidate files under {REPO_ROOT}, which is too few to "
        "be a real scan - the walker or the skip list is wrong, and a test "
        "that scans nothing passes forever"
    )

    problems = []
    for path in files:
        data = path.read_bytes()
        offenses = _offenses(data)
        for offense in offenses:
            problems.append(_describe(path, data, offense))

    assert not problems, (
        f"{len(problems)} non-ASCII byte(s) found in authored text. "
        "Replace em-dashes and en-dashes with ' - ', and smart quotes with "
        "plain ASCII quotes.\n" + "\n".join(problems)
    )


def _git(args, cwd):
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=120
    )


def test_the_hook_survives_a_reader_that_closes_the_pipe():
    """End to end, in a throwaway repo: stage a banned glyph, commit, assert HEAD.

    **Measured 2026-09-02, and it is why this test exists.** Piping a commit
    through a reader that stops after one line -
    ``git commit ... 2>&1 | head -1`` - killed the pre-commit hook mid-message
    with SIGPIPE. Git exited 141 and **the banned commit landed**, while the
    word BLOCKED still appeared on screen. A guard that prints its refusal and
    then lets the commit through is worse than no guard at all, because the
    operator reads the refusal and believes it. The hook now ignores PIPE.

    The pipe is the whole point of this test, so it runs the commit through a
    real shell. It SKIPS when no POSIX shell is available rather than passing
    vacuously - a skip is honest, and a test that quietly stops exercising the
    pipe would leave exactly the hole it was written to close.
    """
    import shutil
    import subprocess
    import tempfile

    sh = shutil.which("sh") or shutil.which("bash")
    if sh is None:
        import pytest

        pytest.skip("no POSIX shell on this machine, so the pipe cannot be exercised")
    hooks = REPO_ROOT / ".githooks"
    assert (hooks / "pre-commit").is_file(), "the hook under test is missing"

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "probe"
        repo.mkdir()
        assert _git(["init", "-q"], repo).returncode == 0
        _git(["config", "user.email", "probe@example.invalid"], repo)
        _git(["config", "user.name", "probe"], repo)
        shutil.copytree(hooks, repo / ".githooks")
        _git(["config", "core.hooksPath", ".githooks"], repo)

        (repo / "seed.txt").write_text("seed\n", encoding="ascii")
        _git(["add", "seed.txt"], repo)
        assert _git(["commit", "-q", "-m", "seed"], repo).returncode == 0, (
            "the hook must ALLOW a clean commit - otherwise this test proves "
            "nothing except that the hook refuses everything"
        )
        before = _git(["rev-parse", "HEAD"], repo).stdout.strip()

        (repo / "bad.py").write_bytes('x = "em dash \u2014 here"\n'.encode("utf-8"))
        _git(["add", "bad.py"], repo)
        piped = subprocess.run(
            [sh, "-c", 'git commit -m "must be refused" 2>&1 | head -1'],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=120,
        )
        after = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        assert after == before, (
            "THE BANNED COMMIT LANDED THROUGH A CLOSED PIPE. "
            f"HEAD moved {before[:8]} -> {after[:8]}; shell exit {piped.returncode}"
        )


def test_walker_actually_reaches_this_test_file():
    # Cheap self-check: if the walker cannot see the file it lives in, its
    # skip list or its root is wrong and every other assertion here is
    # vacuous.
    here = Path(__file__).resolve()
    assert here in {p.resolve() for p in iter_text_files()}


def test_walker_prunes_skipped_directories():
    for path in iter_text_files():
        parts = set(path.relative_to(REPO_ROOT).parts[:-1])
        assert not (parts & _tracked.SKIP_DIRS), path


def test_walker_reaches_the_suffixless_published_files():
    # The regression this guards: both hygiene walkers used to filter on a
    # file-extension allowlist, so LICENSE, NOTICE and the dotfiles were
    # published without ever being scanned. Green, and blind.
    seen = {p.relative_to(REPO_ROOT).as_posix() for p in iter_text_files()}
    for expected in ("LICENSE", "NOTICE", ".gitignore", ".gitattributes"):
        assert expected in seen, f"{expected} is published but not scanned"
