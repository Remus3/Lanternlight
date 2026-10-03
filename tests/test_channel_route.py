"""OPS-109 criteria 2 and 3: the run-time route to a channel code.

Every tree here is synthetic, under ``tmp_path``. The helper must find a
sibling's inbox by the ONE-MATCH rule and REFUSE - raise, deliver nothing -
on zero or on several matches. The refusal tests are the half that matters.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ops import channel_route as cr


def _sibling(root: Path, dirname: str, code: str | None, *, depth: int = 1) -> Path:
    base = root / dirname
    for i in range(depth - 1):
        base = base / f"nest{i}"
    inbox = base / "moon_sync_inbox"
    inbox.mkdir(parents=True)
    if code is not None:
        (inbox / "README.txt").write_text(
            f"Code on this channel: {code}. Drop notes here.\nSecond line.\n",
            encoding="ascii",
        )
    return inbox


def _own(root: Path) -> Path:
    own = root / "OwnRepo"
    own.mkdir(exist_ok=True)
    return own


def test_exactly_one_match_returns_that_inbox(tmp_path):
    want = _sibling(tmp_path, "Supervisor", "MAIN")
    _sibling(tmp_path, "Other", "SS")
    got = cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))
    assert got == want


def test_zero_matches_raise(tmp_path):
    _sibling(tmp_path, "Other", "SS")
    with pytest.raises(cr.RouteRefused) as exc:
        cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))
    assert "0 unreadable" in str(exc.value)


def test_two_matches_raise_naming_the_count_not_the_paths(tmp_path):
    _sibling(tmp_path, "AlphaTree", "MAIN")
    _sibling(tmp_path, "BetaTree", "MAIN")
    with pytest.raises(cr.RouteRefused) as exc:
        cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))
    msg = str(exc.value)
    assert "2" in msg
    assert "AlphaTree" not in msg and "BetaTree" not in msg
    assert str(tmp_path) not in msg


@pytest.mark.parametrize("near_miss", ["MAINX", "main", "Main", "XMAIN"])
def test_a_near_miss_code_does_not_match(tmp_path, near_miss):
    _sibling(tmp_path, "Near", near_miss)
    with pytest.raises(cr.RouteRefused):
        cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))


def test_a_short_code_does_not_match_inside_another_word(tmp_path):
    _sibling(tmp_path, "Near", "XSS")
    _sibling(tmp_path, "Near2", "SSX")
    with pytest.raises(cr.RouteRefused):
        cr.find_inbox("SS", tmp_path, own_repo=_own(tmp_path))


def test_a_readme_two_levels_deep_is_not_found(tmp_path):
    _sibling(tmp_path, "Deep", "MAIN", depth=2)
    with pytest.raises(cr.RouteRefused):
        cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))


def test_our_own_repo_inbox_is_excluded(tmp_path):
    own = tmp_path / "OwnRepo"
    _sibling(tmp_path, "OwnRepo", "MAIN")
    with pytest.raises(cr.RouteRefused):
        cr.find_inbox("MAIN", tmp_path, own_repo=own)
    # And excluding ours leaves a genuine single sibling as the one match.
    want = _sibling(tmp_path, "Supervisor", "MAIN")
    assert cr.find_inbox("MAIN", tmp_path, own_repo=own) == want


def test_an_unreadable_readme_is_skipped_and_counted(tmp_path):
    # A README.txt that is a DIRECTORY exists but cannot be read as a file.
    (tmp_path / "Broken" / "moon_sync_inbox" / "README.txt").mkdir(parents=True)
    _sibling(tmp_path, "Other", "SS")
    with pytest.raises(cr.RouteRefused) as exc:
        cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path))
    assert "1 unreadable" in str(exc.value)


def test_an_unreadable_readme_does_not_block_a_real_match(tmp_path):
    (tmp_path / "Broken" / "moon_sync_inbox" / "README.txt").mkdir(parents=True)
    want = _sibling(tmp_path, "Supervisor", "MAIN")
    assert cr.find_inbox("MAIN", tmp_path, own_repo=_own(tmp_path)) == want


def test_inboxes_for_returns_the_deliver_override_shape(tmp_path):
    want = _sibling(tmp_path, "Supervisor", "MAIN")
    got = cr.inboxes_for(["MAIN"], tmp_path, own_repo=_own(tmp_path))
    assert got == {"MAIN": str(want)}
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in got.items())


def test_default_search_root_is_this_repo_drive_anchor():
    assert cr.default_search_root() == Path(Path(cr.REPO_ROOT).anchor)


def _outbox_files(repo: Path) -> list[Path]:
    box = repo / "moon_sync_inbox"
    return [p for p in box.rglob("*") if p.is_file()] if box.exists() else []


@pytest.mark.parametrize("matches", [0, 2])
def test_deliver_refuses_and_writes_nothing_on_zero_or_two(tmp_path, matches):
    search = tmp_path / "drive"
    search.mkdir()
    for i in range(matches):
        _sibling(search, f"Tree{i}", "MAIN")
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(cr.RouteRefused):
        cr.deliver_to(
            "MAIN", "ll-test-note.md", "hello\n",
            search_root=search, own_repo=repo, root=repo,
            now="2026-10-03T00:00:00Z", answers=[],
        )
    assert _outbox_files(repo) == []
    for i in range(matches):
        box = search / f"Tree{i}" / "moon_sync_inbox"
        assert [p.name for p in box.iterdir()] == ["README.txt"]


def test_deliver_reaches_the_one_match_and_keeps_our_copy(tmp_path):
    search = tmp_path / "drive"
    search.mkdir()
    target = _sibling(search, "Supervisor", "MAIN")
    repo = tmp_path / "repo"
    repo.mkdir()
    cr.deliver_to(
        "MAIN", "ll-test-note.md", "hello\n",
        search_root=search, own_repo=repo, root=repo,
        now="2026-10-03T00:00:00Z", answers=[],
    )
    assert (target / "ll-test-note.md").read_text(encoding="ascii") == "hello\n"
    assert any(p.name == "ll-test-note.md" for p in _outbox_files(repo))


def test_module_source_carries_no_drive_qualified_path():
    src = Path(cr.__file__).read_text(encoding="utf-8")
    assert not re.search(r"\b[A-Za-z]:[\\/]", src), "a drive-qualified path is in the source"
