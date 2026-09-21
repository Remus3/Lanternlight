"""``scripts/history_scan.py`` - the one-off full-history scan, ROADMAP ``OPS-106``.

Every hygiene guard in this repository scans the TREE. A value committed and
later deleted is absent from the tree and present in every clone, so a green
tree guard says nothing about history. The script walks every blob reachable
from every ref and runs the same detectors the tree guards run.

The load-bearing test is the planted one: a synthetic identifier committed in a
file that is then DELETED must still be found, because that is the exact case
no tree guard can see. The clean-repository test is its control - a scanner
that reports everything is as useless as one that reports nothing.

Every planted value is ASSEMBLED AT RUN TIME, so this file does not itself
carry the shapes it tests for, and every assertion about the report checks
that the planted value - and any fragment of it - is ABSENT from the output.
A counts-only report that quotes the thing it counted is a leak with a count
attached.
"""

from __future__ import annotations

import base64
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "history_scan.py"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load():
    spec = importlib.util.spec_from_file_location("history_scan", SCRIPT)
    assert spec is not None and spec.loader is not None, "the script under test is missing"
    module = importlib.util.module_from_spec(spec)
    # Registered first: a dataclass resolves its module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


hs = _load()

#: A SteamID64-shaped value, assembled so this file never carries the shape.
PLANTED_STEAMID = "76561190" + "000000042"
#: A provider-credential shape, assembled the same way (secret_scan specimen).
PLANTED_KEY = "gh" + "s_" + ("Wm3" * 10) + "Tq8xyz"
#: A synthetic identity for the throwaway repositories. `.invalid` is reserved.
PROBE_EMAIL = "probe@example.invalid"


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, timeout=120, check=True
    )
    return out.stdout


def _init(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", PROBE_EMAIL)
    _git(repo, "config", "user.name", "probe")
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "core.hooksPath", str(repo / "no-hooks"))


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "clean"
    _init(repo)
    (repo / "README.md").write_bytes(b"plain ascii text\n")
    (repo / "src.py").write_bytes(b"x = 1\n")
    _commit(repo, "seed")
    (repo / "src.py").write_bytes(b"x = 2\n")
    _commit(repo, "edit")
    return repo


@pytest.fixture
def planted_repo(tmp_path: Path) -> tuple[Path, str]:
    """A repository whose ONLY leak lives in a file that no longer exists."""
    repo = tmp_path / "planted"
    _init(repo)
    (repo / "README.md").write_bytes(b"plain ascii text\n")
    _commit(repo, "seed")
    (repo / "notes").mkdir()
    (repo / "notes" / "leak.txt").write_bytes(
        ("player " + PLANTED_STEAMID + " connected\n").encode("ascii")
    )
    introducing = _commit(repo, "add a leak")
    (repo / "notes" / "leak.txt").unlink()
    _commit(repo, "delete the leak")
    assert not (repo / "notes" / "leak.txt").exists()
    assert "notes/leak.txt" not in _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    return repo, introducing


def test_a_clean_history_reports_zero_findings(clean_repo: Path) -> None:
    result = hs.scan_history(clean_repo, identities=())
    assert result.blobs_scanned >= 3, "a scan that read nothing reports clean vacuously"
    assert result.findings == []
    report = hs.format_report(result)
    assert "findings: 0" in report


def test_an_identifier_in_a_deleted_file_is_found(planted_repo) -> None:
    repo, introducing = planted_repo
    result = hs.scan_history(repo, identities=())
    labels = {f.cls for f in result.findings}
    assert "STEAMID64" in labels, "the deleted file's identifier was not found"
    hit = next(f for f in result.findings if f.cls == "STEAMID64")
    assert hit.path == "notes/leak.txt"
    assert hit.hits >= 1
    assert hit.first_commit == introducing, "the first-introducing commit is wrong"


def test_the_report_never_carries_the_value_or_a_fragment(planted_repo) -> None:
    repo, _ = planted_repo
    report = hs.format_report(hs.scan_history(repo, identities=()))
    assert "STEAMID64" in report and "notes/leak.txt" in report
    for width in (6, 8, 17):
        for start in range(0, len(PLANTED_STEAMID) - width + 1):
            assert PLANTED_STEAMID[start : start + width] not in report


def test_a_credential_class_in_history_is_found_and_not_quoted(tmp_path: Path) -> None:
    repo = tmp_path / "cred"
    _init(repo)
    (repo / "cfg.txt").write_bytes(("token " + PLANTED_KEY + "\n").encode("ascii"))
    _commit(repo, "add")
    (repo / "cfg.txt").unlink()
    _commit(repo, "remove")
    result = hs.scan_history(repo, identities=())
    assert "GITHUB_TOKEN" in {f.cls for f in result.findings}
    report = hs.format_report(result)
    assert PLANTED_KEY not in report and PLANTED_KEY[:12] not in report


def test_non_ascii_in_an_authored_blob_is_found_and_a_binary_is_not(tmp_path: Path) -> None:
    repo = tmp_path / "ascii"
    _init(repo)
    (repo / "doc.md").write_bytes("clause \u2014 break\n".encode())
    (repo / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    _commit(repo, "add")
    (repo / "doc.md").write_bytes(b"clause - break\n")
    _commit(repo, "fix")
    result = hs.scan_history(repo, identities=())
    ascii_hits = [f for f in result.findings if f.cls == hs.NON_ASCII]
    assert [f.path for f in ascii_hits] == ["doc.md"], (
        "binary suffixes are exempt, as in the tree guard"
    )


def test_an_encoded_identifier_in_history_is_found(tmp_path: Path) -> None:
    repo = tmp_path / "enc"
    _init(repo)
    encoded = base64.b64encode(("player " + PLANTED_STEAMID + " connected").encode("ascii"))
    (repo / "blob.txt").write_bytes(encoded + b"\n")
    _commit(repo, "add")
    (repo / "blob.txt").unlink()
    _commit(repo, "remove")
    result = hs.scan_history(repo, identities=())
    assert "ENCODED:STEAMID64" in {f.cls for f in result.findings}


def test_the_git_identity_value_half_is_run(tmp_path: Path) -> None:
    repo = tmp_path / "ident"
    _init(repo)
    (repo / "who.txt").write_bytes(("reach me at " + PROBE_EMAIL + "\n").encode("ascii"))
    _commit(repo, "add")
    result = hs.scan_history(repo, identities=(PROBE_EMAIL,))
    classes = {f.cls for f in result.findings}
    assert "GIT_IDENTITY" in classes, "a reserved-domain identity must be reached by value"
    assert PROBE_EMAIL not in hs.format_report(result)


def test_an_unreachable_repository_is_an_error_not_a_clean_bill(tmp_path: Path) -> None:
    not_a_repo = tmp_path / "nothing"
    not_a_repo.mkdir()
    with pytest.raises(hs.HistoryScanFailed):
        hs.scan_history(not_a_repo, identities=())


def test_the_cli_exit_codes(clean_repo: Path, planted_repo) -> None:
    repo, _ = planted_repo
    assert hs.main(["--repo", str(clean_repo), "--no-derive-identities"]) == 0
    assert hs.main(["--repo", str(repo), "--no-derive-identities"]) == 1


# ---------------------------------------------------------------------------
# Arms added after an adversarial mutation pass found five survivors. Each one
# names the mutant it exists to kill.
# ---------------------------------------------------------------------------


def test_a_value_reachable_only_from_a_side_branch_or_a_tag_is_found(tmp_path: Path) -> None:
    """Kills: walking ``HEAD`` instead of ``--all``."""
    repo = tmp_path / "refs"
    _init(repo)
    (repo / "README.md").write_bytes(b"plain\n")
    _commit(repo, "seed")
    main_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    _git(repo, "checkout", "-q", "-b", "side")
    (repo / "side.txt").write_bytes(("player " + PLANTED_STEAMID + " connected\n").encode())
    side_commit = _commit(repo, "side only")
    _git(repo, "checkout", "-q", "--orphan", "tagged")
    _git(repo, "rm", "-q", "-r", "--cached", ".")
    for leftover in ("README.md", "side.txt"):
        (repo / leftover).unlink(missing_ok=True)
    (repo / "tag.txt").write_bytes(("AccountName" + "=" + "someone_real\n").encode())
    tag_commit = _commit(repo, "tag only")
    _git(repo, "tag", "only-a-tag")
    _git(repo, "checkout", "-q", main_branch)
    _git(repo, "branch", "-q", "-D", "tagged")
    assert "side.txt" not in _git(repo, "ls-tree", "-r", "--name-only", "HEAD")
    rows = {(f.cls, f.path): f for f in hs.scan_history(repo, identities=()).findings}
    assert rows[("STEAMID64", "side.txt")].first_commit == side_commit
    assert rows[("ACCOUNT_NAME", "tag.txt")].first_commit == tag_commit


def test_more_than_one_identifier_label_is_run(tmp_path: Path) -> None:
    """Kills: narrowing the plain pass to a single label."""
    repo = tmp_path / "labels"
    _init(repo)
    (repo / "a.txt").write_bytes(("puid " + "0f1e2d3c4b5a6978" + "8796a5b4c3d2e1f0\n").encode())
    (repo / "b.txt").write_bytes(("AccountName" + "=" + "someone_real\n").encode())
    _commit(repo, "add")
    classes = {(f.cls, f.path) for f in hs.scan_history(repo, identities=()).findings}
    assert ("PRODUCTUSERID", "a.txt") in classes
    assert ("ACCOUNT_NAME", "b.txt") in classes


def test_a_path_that_is_itself_an_identifier_is_withheld(tmp_path: Path) -> None:
    """Kills: printing the raw path. A path is output too."""
    repo = tmp_path / "pathleak"
    _init(repo)
    name = "player_" + PLANTED_STEAMID + ".txt"
    (repo / name).write_bytes(("clause " + chr(0x2014) + " break" + chr(10)).encode())
    _commit(repo, "add")
    result = hs.scan_history(repo, identities=())
    report = hs.format_report(result)
    assert [f.path for f in result.findings if f.cls == hs.NON_ASCII] == [
        f"<path withheld: {len(name)} chars>"
    ]
    assert PLANTED_STEAMID not in report and PLANTED_STEAMID[:8] not in report


def test_an_identity_built_by_concatenation_is_found_by_the_joined_pass(tmp_path: Path) -> None:
    """Kills: dropping the joined-literal pass."""
    repo = tmp_path / "joined"
    _init(repo)
    local, _, domain = PROBE_EMAIL.partition("@")
    source = 'ADDR = "' + local + '" + "@' + domain + '"\n'
    assert PROBE_EMAIL not in source
    (repo / "addr.py").write_bytes(source.encode())
    _commit(repo, "add")
    result = hs.scan_history(repo, identities=(PROBE_EMAIL,))
    classes = {f.cls for f in result.findings}
    assert "JOINED:GIT_IDENTITY" in classes
    assert PROBE_EMAIL not in hs.format_report(result)


def test_first_commit_is_the_earliest_when_the_blob_reappears(tmp_path: Path) -> None:
    """Kills: last-wins first-commit tracking. The same blob re-added later
    must still be attributed to the commit that FIRST introduced it."""
    repo = tmp_path / "reappear"
    _init(repo)
    payload = ("player " + PLANTED_STEAMID + " connected\n").encode()
    (repo / "leak.txt").write_bytes(payload)
    first = _commit(repo, "introduce")
    (repo / "leak.txt").unlink()
    _commit(repo, "delete")
    (repo / "copy.txt").write_bytes(payload)
    later = _commit(repo, "reintroduce at a second path")
    assert later != first
    rows = [f for f in hs.scan_history(repo, identities=()).findings if f.cls == "STEAMID64"]
    assert len(rows) == 1 and rows[0].first_commit == first
