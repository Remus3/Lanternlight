"""The OUTSIDE-the-repository control - ROADMAP ``OPS-103`` criteria 3, 4 and 5.

Every other guard in this tree has the repository as its population. This one
exists because this project's own files were found in the Git for Windows
install root, where no repository-scoped guard can ever look. What is pinned:

* **It is a CONTROL, not a script a session has to remember.** The declared
  ``SessionStart`` command is read out of ``.claude/settings.json``, expanded
  the way the harness expands it, and RUN as a real process. A test that
  imported the module and called it would prove the module, not the hook.
* **Its default population includes a path OUTSIDE this repository.** Asserted
  on the roots it derives, not on a constant.
* **It reports class, count and path - never a value.** A synthetic key, a
  fake home path and a fake account name are planted, and the output is
  searched for every fragment of each. Paths are printed as a root LABEL and a
  basename, because the temp root itself sits under the account's home.
* **Attribution is evidence, not a guess**, and remediation touches only what
  was attributed: a file naming this project AND a sibling is left
  byte-identical, and nothing is ever deleted.
* **A broken detector does not report clean.** The self-test is broken on
  purpose and the run must say so instead of printing a zero.

Every specimen is invented and assembled at run time; the account name used is
a fake patched in (and handed to child processes as a fake home
directory), so the real one never appears in a test.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import outside_scan  # noqa: E402

SETTINGS = REPO_ROOT / ".claude" / "settings.json"
BACK = chr(92)
FAKE_ACCOUNT = "zyxwvutsrqfake"
FAKE_HOME = "C:" + BACK + "Users" + BACK + FAKE_ACCOUNT + BACK + "AppData" + BACK + "x.txt"
FAKE_HOME_FWD = "C:/Users/" + FAKE_ACCOUNT + "/proj/y.py"
KEY = "".join(("sk-", "ant-", "admin", "01-", "Pq5" * 11))


@pytest.fixture(autouse=True)
def _fake_account(monkeypatch):
    monkeypatch.setattr(outside_scan, "account_name", lambda: FAKE_ACCOUNT)


def _fake_home_env(tmp_path: Path) -> dict[str, str]:
    """A child environment whose home directory is named FAKE_ACCOUNT."""
    home = tmp_path / "home" / FAKE_ACCOUNT
    home.mkdir(parents=True, exist_ok=True)
    return dict(os.environ, USERPROFILE=str(home), HOME=str(home))


def test_the_account_is_read_from_the_home_path_not_an_environment_value():
    """Operator ruling 2026-09-20: no environment VALUE is read for matching."""
    source = (REPO_ROOT / "ops" / "outside_scan.py").read_text(encoding="utf-8")
    assert "os.environ" not in source and "getenv" not in source, "an env value is read"
    code = "from ops import outside_scan; print(outside_scan.account_name())"
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        env = _fake_home_env(Path(tmp))
        out = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    assert out == FAKE_ACCOUNT


def _leaks(value: str, text: str, width: int = 6) -> list[str]:
    runs = {value[i : i + width] for i in range(len(value) - width + 1)}
    return sorted(r for r in runs if r in text)


def _committed_blob_without_marker() -> bytes:
    """The bytes of a committed file that does NOT name the project.

    Chosen at run time from HEAD rather than named here, so the blob arm is
    tested on its own and not rescued by the marker arm. Found to matter: the
    first draft used README.md, which names the project, and the marker arm
    answered first.
    """
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-l", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for line in listing.splitlines():
        meta, name = line.split(chr(9), 1)
        kind, size = meta.split()[1], meta.split()[3]
        if kind != "blob" or not size.isdigit() or not 200 < int(size) < 20000:
            continue
        data = subprocess.run(
            ["git", "show", f"HEAD:{name}"], cwd=REPO_ROOT, capture_output=True, check=True
        ).stdout
        if not outside_scan.OUR_MARKER.search(data.decode("latin-1")):
            return data
    raise AssertionError("no committed blob without the marker - the blob arm cannot be tested")


def _plant(root: Path) -> dict[str, Path]:
    """A bucket like the measured one: ours by marker, ours by blob, a sibling's."""
    root.mkdir(parents=True, exist_ok=True)
    files = {
        "ours": root / "probe_x.py",
        "shared": root / "shared.md",
        "blob": root / "readme_copy.md",
        "clean": root / "clean.txt",
    }
    files["ours"].write_bytes(
        (
            "# Lanternlight probe\r\n"
            f"ROOT = r'{FAKE_HOME}'\r\n"
            f"OTHER = '{FAKE_HOME_FWD}'\r\n"
            f"who = '{FAKE_ACCOUNT}'\r\n"
            f"token = '{KEY}'\r\n"
        ).encode("ascii")
    )
    files["shared"].write_bytes(f"lanternlight and clockspeed both\n{FAKE_HOME}\n".encode("ascii"))
    files["blob"].write_bytes(_committed_blob_without_marker())
    files["clean"].write_bytes(b"nothing here\n")
    return files


# ---------------------------------------------------------------------------
# The detectors
# ---------------------------------------------------------------------------


class TestHomePath:
    def test_both_separators_and_the_msys_spelling_match(self):
        for spelling in (FAKE_HOME, FAKE_HOME_FWD, "/c/Users/" + FAKE_ACCOUNT + "/z"):
            assert outside_scan.HOME_PATH.search(spelling), spelling.count(BACK)

    def test_the_backslash_class_is_really_a_backslash(self):
        """``LL-0277``: a collapsed class matched the forward slash only."""
        only_back = "D:" + BACK + "Users" + BACK + "abcdef"
        assert outside_scan.HOME_PATH.search(only_back)

    @pytest.mark.parametrize(
        "innocent",
        [
            "C:/" + "Users/Public/x",
            "C:/" + "Users/<USER>/x",
            "the Users group",
            "C:/" + "Users/Default/x",
        ],
    )
    def test_innocent_spellings_do_not_match(self, innocent):
        assert not outside_scan.HOME_PATH.search(innocent)


class TestAccountName:
    def test_whole_token_and_short_form(self):
        pattern = outside_scan._account_pattern(FAKE_ACCOUNT)
        assert pattern is not None
        assert pattern.search(f"a {FAKE_ACCOUNT} b")
        assert pattern.search(f"C:/Users/{FAKE_ACCOUNT[:6].upper()}~1/x")
        assert not pattern.search(f"a {FAKE_ACCOUNT}z b")

    def test_a_short_name_is_refused_rather_than_shredding_words(self):
        assert outside_scan._account_pattern("ab") is None


def test_the_self_test_passes_and_names_a_broken_pattern(monkeypatch):
    assert outside_scan.self_test() == []
    monkeypatch.setattr(outside_scan, "HOME_PATH", outside_scan.re.compile(r"C:/Users/\w+"))
    failures = outside_scan.self_test()
    assert any("HOME_PATH missed" in f for f in failures), failures


def test_a_broken_detector_does_not_report_clean(monkeypatch, tmp_path, capsys):
    _plant(tmp_path / "bucket")
    monkeypatch.setattr(outside_scan, "HOME_PATH", outside_scan.re.compile(r"(?!x)x"))
    code = outside_scan.main(
        ["--root", str(tmp_path / "bucket"), "--runtime", str(tmp_path / "rt")]
    )
    out = capsys.readouterr().out
    assert code == 2
    assert "SELF-TEST FAILED" in out
    assert "hits: 0" not in out


# ---------------------------------------------------------------------------
# Population, attribution, report
# ---------------------------------------------------------------------------


def test_the_default_population_reaches_outside_the_repository():
    roots = outside_scan.default_roots()
    assert roots, "no default root at all - the control would scan nothing"
    outside = [r for r in roots if not r.resolve().is_relative_to(REPO_ROOT.resolve())]
    assert outside, "every default root is inside the repository"


def test_the_git_install_root_is_derived_on_git_for_windows():
    if sys.platform != "win32":
        pytest.skip("the Git install root is a Git for Windows layout")
    root = outside_scan.git_install_root()
    assert root is not None and (root / "mingw64").is_dir()


def test_attribution_by_marker_and_by_blob_and_not_for_a_shared_file(tmp_path):
    files = _plant(tmp_path / "bucket")
    results, _, _ = outside_scan.scan([tmp_path / "bucket"], FAKE_ACCOUNT, ())
    why = {Path(r.path).name: r.ours for r in results}
    assert why[files["ours"].name] == "marker"
    assert why[files["blob"].name] == "blob"
    assert why[files["shared"].name] == ""
    assert why[files["clean"].name] == ""


def test_counts_per_class(tmp_path):
    files = _plant(tmp_path / "bucket")
    results, _, _ = outside_scan.scan([tmp_path / "bucket"], FAKE_ACCOUNT, ())
    ours = next(r for r in results if Path(r.path) == files["ours"])
    assert ours.credentials == {"ANTHROPIC_ADMIN_KEY": 1}
    assert ours.pii["HOME_PATH"] == 2
    assert ours.pii["ACCOUNT_NAME"] == 3


def test_the_report_carries_no_value_and_no_real_path(tmp_path):
    bucket = tmp_path / "bucket"
    _plant(bucket)
    results, skipped, unreadable = outside_scan.scan([bucket], FAKE_ACCOUNT, ())
    report = outside_scan.format_report(results, [bucket], skipped, unreadable, 0.1)
    assert "CREDENTIAL ANTHROPIC_ADMIN_KEY 1 <ROOT0>/probe_x.py" in report
    assert "PII HOME_PATH 2 <ROOT0>/probe_x.py" in report
    for value in (KEY, FAKE_ACCOUNT, FAKE_HOME, str(tmp_path)):
        assert not _leaks(
            value.replace("ANTHROPIC", ""), report.replace("ANTHROPIC_ADMIN_KEY", "")
        ), "the report carries a fragment of a planted value or of the real root"


# ---------------------------------------------------------------------------
# Remediation - in place, attributed files only, never a delete
# ---------------------------------------------------------------------------


def test_remediation_rewrites_ours_and_leaves_the_rest_byte_identical(tmp_path):
    bucket = tmp_path / "bucket"
    files = _plant(bucket)
    before = {name: p.read_bytes() for name, p in files.items()}
    names_before = sorted(p.name for p in bucket.iterdir())

    results, _, _ = outside_scan.scan([bucket], FAKE_ACCOUNT, ())
    done = outside_scan.remediate(results, FAKE_ACCOUNT, ())

    assert sorted(p.name for p in bucket.iterdir()) == names_before, "a file appeared or vanished"
    assert [(d[1] > 0, d[2]) for d in done] == [(True, 0)], done
    assert files["shared"].read_bytes() == before["shared"], "a sibling's file was edited"
    assert files["blob"].read_bytes() == before["blob"]
    assert files["clean"].read_bytes() == before["clean"]
    after = files["ours"].read_bytes().decode("ascii")
    assert FAKE_ACCOUNT not in after and FAKE_ACCOUNT[:6].upper() not in after
    assert "Users" + BACK + "<USER>" + BACK + "AppData" in after, "path shape not kept"
    assert "\r\n" in after, "line endings were not preserved"
    rescan, _, _ = outside_scan.scan([bucket], FAKE_ACCOUNT, ())
    assert all(not r.pii for r in rescan if r.ours), "the re-measurement still finds PII"


# ---------------------------------------------------------------------------
# The cache
# ---------------------------------------------------------------------------


def test_a_changed_file_is_rescanned_and_a_new_fingerprint_drops_the_cache(tmp_path):
    bucket = tmp_path / "bucket"
    files = _plant(bucket)
    cache: dict = {}
    outside_scan.scan([bucket], FAKE_ACCOUNT, (), cache)
    assert cache, "nothing was cached"
    files["clean"].write_bytes(("x " + KEY + " and more bytes\n").encode("ascii"))
    os.utime(files["clean"], ns=(1_000_000_000, 1_000_000_000))
    results, _, _ = outside_scan.scan([bucket], FAKE_ACCOUNT, (), cache)
    clean = next(r for r in results if Path(r.path) == files["clean"])
    assert clean.credentials == {"ANTHROPIC_ADMIN_KEY": 1}, "a stale cached row answered"

    runtime = tmp_path / "rt"
    outside_scan._write_json(runtime / "cache.json", {"fingerprint": "old", "rows": cache})
    assert outside_scan.load_cache(runtime, "new") == {}
    assert outside_scan.load_cache(runtime, "old") == cache


# ---------------------------------------------------------------------------
# The hook - the DECLARED command, run as a real process
# ---------------------------------------------------------------------------


def _declared_command() -> str:
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    hooks = [h for entry in settings["hooks"]["SessionStart"] for h in entry.get("hooks", [])]
    matching = [h["command"] for h in hooks if "outside_scan" in h.get("command", "")]
    assert len(matching) == 1, f"expected ONE SessionStart hook running outside_scan: {hooks}"
    return matching[0]


def test_the_declared_command_is_anchored_and_in_hook_mode():
    command = _declared_command()
    assert '"$CLAUDE_PROJECT_DIR/ops/outside_scan.py"' in command
    assert "--session-start" in command


def test_the_declared_session_start_command_runs_and_reports(tmp_path):
    bucket = tmp_path / "bucket"
    _plant(bucket)
    argv = shlex.split(_declared_command().replace("$CLAUDE_PROJECT_DIR", REPO_ROOT.as_posix()))
    argv += ["--root", str(bucket), "--runtime", str(tmp_path / "rt")]
    env = _fake_home_env(tmp_path)
    proc = subprocess.run(
        argv, cwd=str(tmp_path), capture_output=True, text=True, timeout=300, env=env, check=False
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert out.startswith("OUTSIDE-REPO SCAN (OPS-103):"), out
    assert "CREDENTIAL ANTHROPIC_ADMIN_KEY 1 <ROOT0>/probe_x.py" in out
    assert "PII HOME_PATH 2 <ROOT0>/probe_x.py" in out
    assert FAKE_ACCOUNT not in out and KEY[:12] not in out
    assert (tmp_path / "rt" / "last.json").is_file()


def test_hook_mode_never_fails_the_session(tmp_path, monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(outside_scan, "scan", boom)
    code = outside_scan.main(
        ["--session-start", "--root", str(tmp_path), "--runtime", str(tmp_path / "rt")]
    )
    assert code == 0
    assert "NOT RUN" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Adversarial-pass fixes: a FILENAME is output too, and mtime is not identity.
# ---------------------------------------------------------------------------


def _account_bearing_bucket(tmp_path: Path) -> Path:
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    (bucket / f"notes_{FAKE_ACCOUNT}_draft.txt").write_bytes(
        f"lanternlight\ntoken = '{KEY}'\n".encode("ascii")
    )
    return bucket


def test_an_account_name_in_a_filename_never_reaches_report_or_runtime_files(tmp_path, capsys):
    bucket = _account_bearing_bucket(tmp_path)
    runtime = tmp_path / "rt"
    assert outside_scan.main(["--root", str(bucket), "--runtime", str(runtime)]) == 0
    out = capsys.readouterr().out
    assert "CREDENTIAL ANTHROPIC_ADMIN_KEY 1 <ROOT0>/notes_<ACCOUNT>_draft.txt" in out, out
    written = {p.name: p.read_text(encoding="ascii") for p in runtime.iterdir()}
    assert {"cache.json", "last.json"} <= set(written)
    for text in [out, *written.values()]:
        assert FAKE_ACCOUNT.lower() not in text.lower()
        assert FAKE_ACCOUNT[:6].lower() + "~" not in text.lower()


def test_the_declared_hook_does_not_print_an_account_bearing_filename(tmp_path):
    bucket = _account_bearing_bucket(tmp_path)
    argv = shlex.split(_declared_command().replace("$CLAUDE_PROJECT_DIR", REPO_ROOT.as_posix()))
    argv += ["--root", str(bucket), "--runtime", str(tmp_path / "rt")]
    env = _fake_home_env(tmp_path)
    proc = subprocess.run(
        argv, cwd=str(tmp_path), capture_output=True, text=True, timeout=300, env=env, check=False
    )
    assert proc.returncode == 0, proc.stderr
    assert "ANTHROPIC_ADMIN_KEY 1" in proc.stdout
    assert FAKE_ACCOUNT.lower() not in proc.stdout.lower()


def test_a_same_size_same_mtime_rewrite_is_not_served_from_cache(tmp_path):
    bucket = tmp_path / "bucket"
    bucket.mkdir()
    target = bucket / "note.txt"
    padding = "x" * len(KEY)
    target.write_bytes(f"k = {padding}\n".encode("ascii"))
    stamp = target.stat().st_mtime_ns
    cache: dict = {}
    first, _, _ = outside_scan.scan([bucket], FAKE_ACCOUNT, (), cache)
    assert first[0].credentials == {}
    target.write_bytes(f"k = {KEY}\n".encode("ascii"))
    os.utime(target, ns=(stamp, stamp))
    assert target.stat().st_size == len(f"k = {padding}\n")
    second, _, _ = outside_scan.scan([bucket], FAKE_ACCOUNT, (), cache)
    assert second[0].credentials == {"ANTHROPIC_ADMIN_KEY": 1}, "stale cached row served"


@pytest.mark.parametrize(
    "stem",
    [
        "CUsers" + FAKE_ACCOUNT + "AppDataLocal",
        "x" + FAKE_ACCOUNT.upper() + "y",
        "C_Users_" + FAKE_ACCOUNT[:6].upper() + "~1_tmp",
    ],
    ids=["flattened-path", "glued-upper", "short-form"],
)
def test_an_account_glued_inside_a_filename_is_still_scrubbed(stem):
    """Found LIVE in the temp root after the whole-token fix had gone green."""
    shown = outside_scan.safe_name(stem + ".txt", FAKE_ACCOUNT, ())
    assert FAKE_ACCOUNT.lower() not in shown.lower()
    assert FAKE_ACCOUNT[:6].lower() + "~" not in shown.lower()
    assert shown.endswith(".txt")
