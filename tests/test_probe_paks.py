"""The pak probe must refuse a command line it cannot read, and name its scope.

ROADMAP ``OPS-67``. ``OPS-64``'s sweep found nine ``tools/`` entry points that
read an unknown argument as a pass. Three of them were answered under this item
and the three answers differ on purpose:
``tools/ascii_check.py`` and ``tools/syntax_check_hook.py`` keep ignoring argv,
because they are ``PostToolUse`` hooks whose only caller passes none and whose
non-zero exit would wedge the session (pinned in
``tests/test_syntax_check_hook.py``). ``tools/probe_paks.py``, this module's
subject, REFUSES, because it has no automated caller at all: it is typed by a
person, and nothing reads its exit code that a non-zero could break.

TWO PROPERTIES, AND THE SECOND IS THE ONE THE OLD CODE LACKED.

1. An unrecognised argument exits ``USAGE_EXIT_CODE`` and prints a refusal that
   quotes the argument back. Before the change it exited 0 and printed a full,
   confident report about the hardcoded directory instead.
2. A completed run NAMES the directory it read. The old output was one line per
   container carrying ``path.name`` only, so a pasted transcript could not be
   told apart from a run of some other directory - which is what made the
   ignored flag dangerous rather than merely untidy.

THE REFUSAL IS ASSERTED AS AN EXIT CODE, NOT AS TEXT ALONE. A test that only
looked for the word REFUSING on stdout would stay green on a script that
printed the refusal and then went on to probe anyway.

MACHINE INDEPENDENCE. The real :data:`PAKS` directory exists only where the
game is installed, so the scope assertion drives the module in-process with
``PAKS`` monkeypatched at a temporary directory. The refusal assertions spawn
the real script, because an exit code is not observable from inside the
interpreter doing the asserting, and they hold whether or not the game is
installed - the refusal is returned before the directory is ever consulted.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "probe_paks.py"

#: Deliberately plausible. A caller who had read a sibling tool's options might
#: well type this, believing it re-points the probe; the point of OPS-67 is
#: that it silently did not.
UNKNOWN_ARGV = ["--paks", "D:/elsewhere"]

#: The head of the refusal message. Asserted alongside the exit code so a
#: silent non-zero cannot pass for a refusal that explains itself.
REFUSAL_MARKER = "REFUSING"

#: The head of the scope line every completed run must print.
SCOPE_MARKER = "SCANNING:"


def load_module():
    """Import ``tools/probe_paks.py`` by path, without importing the package."""
    spec = importlib.util.spec_from_file_location("ll_probe_paks_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_script(argv: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *argv],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )


def test_the_script_exists_and_is_not_empty() -> None:
    assert SCRIPT.is_file(), f"the probe script is missing: {SCRIPT}"
    assert SCRIPT.stat().st_size > 0, "the probe script is empty"


def test_an_unrecognised_argument_is_refused() -> None:
    module = load_module()

    result = run_script(UNKNOWN_ARGV)

    assert result.returncode == module.USAGE_EXIT_CODE, (
        "an unrecognised argument did not draw a usage refusal: "
        f"rc={result.returncode} stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert REFUSAL_MARKER in result.stdout, (
        f"the refusal does not say it refused: {result.stdout!r}"
    )
    assert "--paks" in result.stdout, (
        f"the refusal does not quote the argument back: {result.stdout!r}"
    )


def test_a_refused_run_probes_nothing() -> None:
    """The exit code and the silence together. Either alone would be weak."""
    result = run_script(UNKNOWN_ARGV)

    # Paired with a positive assertion on purpose. The absence of the scope
    # line rules something out while pinning nothing down - it passed just as
    # happily against the PRE-CHANGE script, which printed no scope line under
    # any circumstances. Measured while proving these pins.
    assert REFUSAL_MARKER in result.stdout, (
        f"nothing was refused, so the silence proves nothing: {result.stdout!r}"
    )
    assert SCOPE_MARKER not in result.stdout, (
        "the script refused and then scanned anyway, which is the failure this "
        f"item exists to close: {result.stdout!r}"
    )


def test_no_arguments_is_not_refused() -> None:
    """The bare invocation - the only contract this script has - still works.

    ``0`` means the containers were read; ``1`` means the directory is absent,
    which is the correct answer on a machine without the game installed. Only
    the usage code is wrong here.
    """
    module = load_module()

    result = run_script([])

    assert result.returncode in (0, 1), (
        f"a bare invocation returned {result.returncode}: {result.stdout!r}"
    )
    assert result.returncode != module.USAGE_EXIT_CODE, (
        "the bare invocation was refused as a usage error"
    )
    assert REFUSAL_MARKER not in result.stdout, (
        f"the bare invocation drew a refusal: {result.stdout!r}"
    )


def test_a_completed_run_names_the_directory_it_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The scope line, pinned without needing the game installed."""
    module = load_module()
    fake_paks = tmp_path / "Paks"
    fake_paks.mkdir()
    # A container the reader will look at, so this is a real completed run
    # rather than an empty directory that would print the scope and nothing
    # else whatever the loop did.
    (fake_paks / "probe_subject.utoc").write_bytes(b"\x00" * 200)
    monkeypatch.setattr(module, "PAKS", fake_paks)

    rc = module.main([])
    out = capsys.readouterr().out

    assert rc == 0, f"the probe did not complete: rc={rc} out={out!r}"
    assert f"{SCOPE_MARKER} {fake_paks}" in out, (
        "a completed run does not name the directory it read, so its report "
        f"cannot be checked against the scope the caller meant: {out!r}"
    )
    assert "probe_subject.utoc" in out, (
        f"the run named its scope but read no container: {out!r}"
    )


def test_the_module_records_its_argv_decision() -> None:
    """The reason lives in the module, per OPS-67 criterion 1."""
    text = SCRIPT.read_text(encoding="ascii")

    assert "THE COMMAND LINE REFUSES WHAT IT DOES NOT UNDERSTAND" in text, (
        "probe_paks.py no longer explains why it refuses unknown argv"
    )
    assert "OPS-67" in text, "probe_paks.py no longer cites the item that decided this"
