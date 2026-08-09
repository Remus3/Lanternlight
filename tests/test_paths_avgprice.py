"""Regression tests for the AvgPrice path resolution defect.

Measured on a live install on 2026-08-09: the market cache sits at
``<Saved>/AvgPrice_937566.ini`` - directly in ``Saved``, and with the publisher
app id in the filename. Before this fix the module looked for
``<Saved>/Config/WindowsClient/AvgPrice.ini``, which is wrong in the directory
AND in the name, so ``find_avg_price_ini()`` returned ``None`` on a machine
where the file plainly existed.

The docstring on ``avg_price_ini`` had honestly labelled that location
UNVERIFIED. It is now verified, and it was wrong - which is the good outcome of
labelling a guess rather than letting it read as a measurement.

``937566`` is the publisher app id and is already public in ``docs/FINDINGS.md``
and in the game's own GSDK config; it is not operator PII.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight import paths  # noqa: E402

# The real filename, measured. Assembled rather than pasted so the app id is
# obvious as data rather than looking like a magic constant.
REAL_NAME = "AvgPrice_937566.ini"


def _env(tmp_path: Path) -> dict[str, str]:
    """Point the whole module at a throwaway Saved tree."""
    return {paths.ENV_SAVED_DIR: str(tmp_path)}


class TestExpectedLocation:
    def test_avg_price_ini_sits_directly_in_saved_not_under_config(self, tmp_path):
        result = paths.avg_price_ini(_env(tmp_path))
        assert result.parent == tmp_path, (
            "the market cache is written directly into Saved; the old "
            "Config/WindowsClient guess was measured wrong"
        )

    def test_the_expected_filename_carries_the_app_id(self, tmp_path):
        assert paths.avg_price_ini(_env(tmp_path)).name == REAL_NAME

    def test_the_bare_name_is_not_what_the_game_writes(self, tmp_path):
        # The precise defect: a literal "AvgPrice.ini" can never match.
        assert paths.avg_price_ini(_env(tmp_path)).name != "AvgPrice.ini"


class TestFinder:
    def test_finds_the_real_filename_in_saved(self, tmp_path):
        target = tmp_path / REAL_NAME
        target.write_text("[PriceTime]\n", encoding="utf-8")
        assert paths.find_avg_price_ini(_env(tmp_path)) == target

    def test_finds_a_different_app_id_because_the_suffix_may_vary(self, tmp_path):
        # Only one app id has ever been observed. Matching the pattern rather
        # than the exact string costs nothing and avoids a silent None if the
        # publisher ships a different id.
        target = tmp_path / "AvgPrice_111222.ini"
        target.write_text("[PriceTime]\n", encoding="utf-8")
        assert paths.find_avg_price_ini(_env(tmp_path)) == target

    def test_finds_it_nested_too(self, tmp_path):
        nested = tmp_path / "Config" / "WindowsClient"
        nested.mkdir(parents=True)
        target = nested / REAL_NAME
        target.write_text("[PriceTime]\n", encoding="utf-8")
        assert paths.find_avg_price_ini(_env(tmp_path)) == target

    def test_absent_file_is_none_not_a_raise(self, tmp_path):
        assert paths.find_avg_price_ini(_env(tmp_path)) is None

    def test_absent_saved_tree_is_none_not_a_raise(self, tmp_path):
        missing = tmp_path / "does_not_exist"
        assert paths.find_avg_price_ini({paths.ENV_SAVED_DIR: str(missing)}) is None

    def test_a_directory_named_like_the_file_is_not_a_hit(self, tmp_path):
        (tmp_path / REAL_NAME).mkdir()
        assert paths.find_avg_price_ini(_env(tmp_path)) is None

    def test_result_is_deterministic_when_several_match(self, tmp_path):
        (tmp_path / "AvgPrice_111111.ini").write_text("a", encoding="utf-8")
        (tmp_path / "AvgPrice_222222.ini").write_text("b", encoding="utf-8")
        first = paths.find_avg_price_ini(_env(tmp_path))
        second = paths.find_avg_price_ini(_env(tmp_path))
        assert first == second
        assert first is not None


class TestAgainstTheLiveInstall:
    def test_the_finder_locates_the_real_file_when_the_game_is_installed(self):
        # Skips cleanly on a machine without the game rather than failing, but
        # when the tree IS present this is the assertion that would have caught
        # the original defect - and did not exist before.
        saved = paths.saved_dir()
        if not saved.is_dir():
            import pytest

            pytest.skip("no live Mistfall Hunter Saved tree on this machine")
        found = paths.find_avg_price_ini()
        assert found is not None, (
            f"the Saved tree exists at {saved} but the finder returned None - "
            "this is exactly the defect this module regressed on"
        )
        assert found.is_file()
        assert found.name.startswith("AvgPrice")
