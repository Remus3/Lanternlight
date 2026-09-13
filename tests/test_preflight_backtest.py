"""The back-test must be able to report a MISS, or it is not a back-test.

``OPS-87`` criterion 3: "Run the new pre-flight against the tree as it stood
when each historical finding was filed, and report how many it would have
CAUGHT and how many it would have MISSED. A gate that cannot show it would have
caught a finding that really happened is a hypothesis wearing a result's
clothes."

The failure mode a back-test harness falls into is reporting a catch it did not
earn, so the pure parts of :mod:`tools.preflight_backtest` are pinned here:

* a tree where the guard module did not yet EXIST must classify as NO-GUARD and
  never as CAUGHT or MISSED - a check that postdates a finding cannot have
  caught it, and counting it as a catch is how a hypothesis dresses as a result;
* a red run is only a CATCH if a module in the pre-flight set failed, so the
  failing test names are parsed out and carried, not summarised away;
* a tree the harness could not build at all is UNBUILDABLE and is reported
  separately from a clean run, because "the experiment did not happen" and "the
  experiment says no" are different facts.
"""

from __future__ import annotations

from pathlib import Path

from tools import preflight_backtest as bt

REPO_ROOT = Path(__file__).resolve().parents[1]

_RED = """
tests/test_lanes.py .F..
=================================== FAILURES ===================================
FAILED tests/test_lanes.py::TestNoFileIsOrphaned::test_every_tracked_file_is_owned
FAILED tests/test_inventory.py::test_every_test_module_is_named
1 failed, 40 passed in 2.10s
"""

_GREEN = """
tests/test_lanes.py ....
43 passed in 1.30s
"""


class TestParsingPytestOutput:
    def test_failing_test_names_are_carried_rather_than_counted(self) -> None:
        assert bt.failing_tests(_RED) == (
            "tests/test_lanes.py::TestNoFileIsOrphaned::test_every_tracked_file_is_owned",
            "tests/test_inventory.py::test_every_test_module_is_named",
        )

    def test_a_green_run_has_no_failing_tests(self) -> None:
        assert bt.failing_tests(_GREEN) == ()

    def test_the_summary_line_is_the_last_one_and_not_the_first(self) -> None:
        assert bt.summary_line(_RED) == "1 failed, 40 passed in 2.10s"


class TestClassification:
    def test_a_tree_without_the_guard_is_NO_GUARD_and_never_a_catch(self) -> None:
        # The guard postdates the finding. Counting that as a catch would let
        # the harness claim credit for work done after the fact, which is the
        # single way this experiment can lie in its own favour.
        verdict = bt.classify(returncode=0, present=(), failures=())
        assert verdict == "NO-GUARD"

    def test_a_red_run_with_a_preflight_failure_is_a_CATCH(self) -> None:
        verdict = bt.classify(
            returncode=1,
            present=("tests/test_lanes.py",),
            failures=("tests/test_lanes.py::T::t",),
        )
        assert verdict == "CAUGHT"

    def test_a_green_run_with_the_guard_present_is_a_MISS(self) -> None:
        verdict = bt.classify(
            returncode=0, present=("tests/test_lanes.py",), failures=()
        )
        assert verdict == "MISSED"

    def test_a_nonzero_exit_with_no_parsed_failure_is_UNBUILDABLE(self) -> None:
        # A collection error, an interpreter crash, a tree that will not stand
        # up. Reporting it as a catch would be counting a broken experiment as
        # evidence, and this repository has already been burned once by a
        # silence that read as a result.
        verdict = bt.classify(
            returncode=2, present=("tests/test_lanes.py",), failures=()
        )
        assert verdict == "UNBUILDABLE"


class TestPresence:
    def test_only_modules_present_in_that_tree_are_run(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_lanes.py").write_text("", encoding="ascii")
        assert bt.present_modules(
            tmp_path, ("tests/test_lanes.py", "tests/test_inventory.py")
        ) == ("tests/test_lanes.py",)


class TestTheTally:
    def test_the_tally_counts_verdicts_and_is_recomputed_from_the_rows(self) -> None:
        rows = [
            bt.Outcome("LL-0001", "abc", "CAUGHT", ("t",), "1 failed"),
            bt.Outcome("LL-0002", "def", "MISSED", (), "2 passed"),
            bt.Outcome("LL-0003", "ghi", "CAUGHT", ("t",), "1 failed"),
        ]
        assert bt.tally(rows) == {
            "CAUGHT": 2,
            "MISSED": 1,
            "NO-GUARD": 0,
            "UNBUILDABLE": 0,
        }

    def test_the_report_states_caught_and_missed_as_the_item_asks(self) -> None:
        rows = [bt.Outcome("LL-0001", "abc", "CAUGHT", ("t",), "1 failed")]
        text = bt.format_report(rows)
        assert "CAUGHT: 1" in text
        assert "MISSED: 0" in text


class TestCommitResolution:
    def test_the_commit_that_introduced_a_real_ledger_entry_resolves(self) -> None:
        # Measured against this repository rather than a fixture: the entry
        # heading is a string that appears in exactly one commit's diff, so
        # `git log -S` names the commit that filed the finding, and its parent
        # is the tree as it stood when the finding was filed.
        sha = bt.entry_commit("LL-0236", REPO_ROOT)
        assert sha and len(sha) == 40, sha

    def test_an_entry_nobody_ever_wrote_resolves_to_nothing(self) -> None:
        assert bt.entry_commit("LL-9999", REPO_ROOT) is None

class TestReconstruction:
    """The commit graph cannot address the state these findings lived in.

    Measured 2026-09-12 and it is the reason this mode exists. The naive
    back-test stands up the PARENT of the commit that filed a finding and runs
    the pre-flight there. For every one of 17 gate-reachable findings it
    reported MISSED - and the reason is not that the guards are weak. It is
    that a new test module, its inventory row, its lane owner and its ledger
    entry all land in ONE commit, so the tree where the registration was
    missing existed for twenty minutes inside a session and was never committed
    at all. A back-test that cannot address that state is measuring a tree in
    which the defect is absent, and calling the resulting green a MISS is a
    claim about the instrument wearing the costume of a claim about the guard.

    So the state is RECONSTRUCTED from the fix commit itself: take the tree as
    the fix left it, and remove the registration lines naming the new module.
    Nothing is invented - every removed line is one that commit is on record as
    adding.
    """

    def test_lines_naming_the_module_are_removed_and_others_are_kept(self) -> None:
        text = chr(10).join(
            (
                "| `tests/test_new.py` | what it guards |",
                "| `tests/test_old.py` | something else |",
                "",
            )
        )
        stripped = bt.strip_mentions(text, "tests/test_new.py")
        assert "test_new.py" not in stripped
        assert "test_old.py" in stripped

    def test_the_basename_alone_counts_as_a_mention(self) -> None:
        # ops/lanes.py names a module as "tests/test_new.py" but a lane contract
        # may name it without the directory. Missing that would leave the
        # reconstruction half-done and the guard green for the wrong reason.
        text = "owns test_new.py here" + chr(10)
        assert bt.strip_mentions(text, "tests/test_new.py") == ""

    def test_a_text_that_never_named_it_is_returned_unchanged(self) -> None:
        text = "nothing here" + chr(10)
        assert bt.strip_mentions(text, "tests/test_new.py") == text

    def test_the_reconstruction_names_the_files_it_will_change(self) -> None:
        # A reconstruction that silently changed nothing would run the
        # pre-flight against the FIXED tree and report a MISS, which is exactly
        # the false negative this mode exists to remove.
        assert bt.registration_files() == ("docs/INVENTORY.md", "ops/lanes.py")

