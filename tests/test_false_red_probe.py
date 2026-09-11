"""Guard ``tools/false_red_probe.py`` - ROADMAP ``OPS-74``.

Nothing here runs the real suite. The probe's outermost function is the only
part that shells out, and every other part of it is a pure function over
recorded pytest output, so this module drives all of them with fixture text.
A test that ran the real suite twice would take minutes and would make this
file hostage to every other test in the repository, which is precisely the
coupling the item's criterion 4 forbids.

What is asserted here, in the order the probe uses it:

* the recorded per-test JSON is parsed back into outcomes and instrument flags;
* the three outcomes of criterion 2 are classified and never collapsed;
* the delta is reported per test id AND per file, so a file that lost five
  tests while another gained five is visible - the lesson ``ops/merge_gate.py``
  already learned and wrote down;
* ``PATH`` stripping happens BY VALUE, removing exactly the entries that carry
  a tool executable and leaving the interpreter's own directory alone;
* the positive control is planted, seen, and torn down, and a control that was
  not seen makes the whole report UNPROVEN rather than green;
* an unrecognised command-line argument is refused loudly and non-zero, which
  is the defect ``OPS-66`` and ``OPS-67`` closed elsewhere.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import false_red_probe as probe  # noqa: E402


def _record(entries: dict[str, tuple[str, bool, bool]]) -> str:
    """Render the JSON the in-run plugin writes, from a compact mapping.

    Each value is ``(outcome, invoked, looked_up)``. Written as text rather
    than as a dict so the parser under test is exercised on the real wire
    shape and not on a structure this file handed it directly.
    """
    return json.dumps(
        {
            "tool": "git",
            "tests": {
                nodeid: {
                    "outcome": outcome,
                    "invoked": invoked,
                    "looked_up": looked_up,
                }
                for nodeid, (outcome, invoked, looked_up) in entries.items()
            },
        }
    )


class TestParsingTheRecord:
    def test_it_reads_outcome_and_both_instrument_flags(self):
        parsed = probe.parse_record(
            _record({"tests/test_a.py::test_one": ("passed", True, True)})
        )
        assert set(parsed) == {"tests/test_a.py::test_one"}
        one = parsed["tests/test_a.py::test_one"]
        assert one.outcome == "passed"
        assert one.invoked is True
        assert one.looked_up is True

    def test_a_malformed_entry_is_dropped_rather_than_raising(self):
        text = json.dumps({"tool": "git", "tests": {"a::b": "not a mapping"}})
        assert probe.parse_record(text) == {}

    def test_unparseable_text_is_an_empty_record_not_an_exception(self):
        assert probe.parse_record("{not json") == {}

    def test_a_missing_flag_reads_as_false_never_as_unknown(self):
        text = json.dumps({"tool": "git", "tests": {"a::b": {"outcome": "passed"}}})
        parsed = probe.parse_record(text)
        assert parsed["a::b"].invoked is False
        assert parsed["a::b"].looked_up is False


class TestTheThreeOutcomes:
    """Criterion 2: three outcomes, never collapsed into one another."""

    def test_a_clean_skip_is_its_own_kind(self):
        with_tool = probe.parse_record(
            _record({"tests/t.py::test_guarded": ("passed", True, True)})
        )
        without = probe.parse_record(
            _record({"tests/t.py::test_guarded": ("skipped", False, True)})
        )
        kinds = {c.nodeid: c.kind for c in probe.classify(with_tool, without)}
        assert kinds["tests/t.py::test_guarded"] == "clean_skip"

    def test_a_false_red_is_its_own_kind(self):
        with_tool = probe.parse_record(
            _record({"tests/t.py::test_bare": ("passed", True, False)})
        )
        without = probe.parse_record(
            _record({"tests/t.py::test_bare": ("failed", True, False)})
        )
        kinds = {c.nodeid: c.kind for c in probe.classify(with_tool, without)}
        assert kinds["tests/t.py::test_bare"] == "false_red"

    def test_an_error_without_the_tool_is_a_false_red_too(self):
        with_tool = probe.parse_record(
            _record({"tests/t.py::test_e": ("passed", True, False)})
        )
        without = probe.parse_record(
            _record({"tests/t.py::test_e": ("error", False, False)})
        )
        kinds = {c.nodeid: c.kind for c in probe.classify(with_tool, without)}
        assert kinds["tests/t.py::test_e"] == "false_red"

    def test_a_silent_pass_needs_a_lookup_and_no_invocation(self):
        entries = {"tests/t.py::test_quiet": ("passed", False, True)}
        classified = probe.classify(
            probe.parse_record(_record(entries)),
            probe.parse_record(_record(entries)),
        )
        assert {c.kind for c in classified} == {"silent_pass"}

    def test_a_test_that_never_touched_the_tool_is_not_a_candidate(self):
        """The rule that keeps the third outcome from meaning every test.

        A test that passes both ways and never looked the tool up is not
        evidence of a guard that did not fire - it is evidence of a test that
        has nothing to do with the tool. Collapsing the two would report the
        whole suite as suspicious and the finding would mean nothing.
        """
        entries = {"tests/t.py::test_unrelated": ("passed", False, False)}
        classified = probe.classify(
            probe.parse_record(_record(entries)),
            probe.parse_record(_record(entries)),
        )
        assert {c.kind for c in classified} == {"untouched"}

    def test_a_test_that_invoked_the_tool_is_not_a_silent_candidate(self):
        entries = {"tests/t.py::test_real": ("passed", True, True)}
        classified = probe.classify(
            probe.parse_record(_record(entries)),
            probe.parse_record(_record(entries)),
        )
        assert {c.kind for c in classified} == {"exercised"}

    def test_the_three_outcomes_stay_distinct_in_one_run(self):
        with_tool = probe.parse_record(
            _record(
                {
                    "tests/t.py::test_skips": ("passed", True, True),
                    "tests/t.py::test_reds": ("passed", True, False),
                    "tests/t.py::test_quiet": ("passed", False, True),
                }
            )
        )
        without = probe.parse_record(
            _record(
                {
                    "tests/t.py::test_skips": ("skipped", False, True),
                    "tests/t.py::test_reds": ("failed", False, False),
                    "tests/t.py::test_quiet": ("passed", False, True),
                }
            )
        )
        kinds = {c.nodeid: c.kind for c in probe.classify(with_tool, without)}
        assert kinds == {
            "tests/t.py::test_skips": "clean_skip",
            "tests/t.py::test_reds": "false_red",
            "tests/t.py::test_quiet": "silent_pass",
        }
        assert len(set(kinds.values())) == 3

    def test_only_the_two_real_defects_count_as_findings(self):
        assert set(probe.FINDING_KINDS) == {"false_red", "silent_pass", "vanished"}
        assert "clean_skip" not in probe.FINDING_KINDS

    def test_a_test_that_vanished_without_the_tool_is_a_finding(self):
        with_tool = probe.parse_record(
            _record({"tests/t.py::test_gone": ("passed", True, False)})
        )
        classified = probe.classify(with_tool, {})
        assert [c.kind for c in classified] == ["vanished"]


class TestTheDelta:
    def test_per_file_counts_do_not_net_out_against_each_other(self):
        """The per-file lesson, restated for this instrument.

        One file loses five tests and another gains five, so the repository
        total is unchanged. A total-only report calls that green; this one
        must name both files.
        """
        with_tool = probe.parse_record(
            _record(
                {f"tests/test_lost.py::test_{i}": ("passed", False, False) for i in range(5)}
            )
        )
        without = probe.parse_record(
            _record(
                {
                    f"tests/test_gained.py::test_{i}": ("passed", False, False)
                    for i in range(5)
                }
            )
        )
        deltas = {d.path: d for d in probe.delta_by_file(with_tool, without)}
        assert len(with_tool) == len(without), "the fixture must keep the total flat"
        assert deltas["tests/test_lost.py"].with_total == 5
        assert deltas["tests/test_lost.py"].without_total == 0
        assert deltas["tests/test_gained.py"].with_total == 0
        assert deltas["tests/test_gained.py"].without_total == 5

    def test_per_file_outcome_counts_are_reported(self):
        with_tool = probe.parse_record(
            _record(
                {
                    "tests/t.py::test_a": ("passed", False, True),
                    "tests/t.py::test_b": ("passed", False, True),
                }
            )
        )
        without = probe.parse_record(
            _record(
                {
                    "tests/t.py::test_a": ("skipped", False, True),
                    "tests/t.py::test_b": ("failed", False, True),
                }
            )
        )
        delta = probe.delta_by_file(with_tool, without)[0]
        assert delta.with_counts == {"passed": 2}
        assert delta.without_counts == {"skipped": 1, "failed": 1}

    def test_delta_by_test_id_names_what_was_lost_and_gained(self):
        with_tool = probe.parse_record(
            _record({"tests/t.py::test_only_with": ("passed", False, False)})
        )
        without = probe.parse_record(
            _record({"tests/t.py::test_only_without": ("passed", False, False)})
        )
        lost, gained = probe.delta_by_test_id(with_tool, without)
        assert lost == ("tests/t.py::test_only_with",)
        assert gained == ("tests/t.py::test_only_without",)

    def test_file_of_splits_a_nodeid_at_the_first_separator(self):
        assert probe.file_of("tests/t.py::TestC::test_m[a::b]") == "tests/t.py"


class TestPathStripping:
    """Criterion 5: strip BY VALUE, and leave the interpreter findable."""

    def test_only_entries_that_actually_carry_the_tool_are_removed(self, tmp_path):
        has_tool = tmp_path / "withtool"
        no_tool = tmp_path / "without"
        has_tool.mkdir()
        no_tool.mkdir()
        (has_tool / "git.exe").write_text("", encoding="ascii")
        (no_tool / "python.exe").write_text("", encoding="ascii")
        original = os.pathsep.join([str(no_tool), str(has_tool)])
        stripped, removed = probe.strip_tool_from_path(
            original, tool="git", pathext=".COM;.EXE;.BAT"
        )
        assert removed == (str(has_tool),)
        assert stripped == str(no_tool)

    def test_an_extension_outside_pathext_is_not_an_executable(self, tmp_path):
        entry = tmp_path / "bin"
        entry.mkdir()
        (entry / "git.txt").write_text("", encoding="ascii")
        stripped, removed = probe.strip_tool_from_path(
            str(entry), tool="git", pathext=".EXE"
        )
        assert removed == ()
        assert stripped == str(entry)

    def test_an_extensionless_tool_still_counts(self, tmp_path):
        entry = tmp_path / "bin"
        entry.mkdir()
        (entry / "git").write_text("", encoding="ascii")
        _, removed = probe.strip_tool_from_path(str(entry), tool="git", pathext=".EXE")
        assert removed == (str(entry),)

    def test_a_stripped_path_still_resolves_the_interpreter(self, tmp_path):
        pydir = tmp_path / "py"
        gitdir = tmp_path / "g"
        pydir.mkdir()
        gitdir.mkdir()
        (pydir / "python.exe").write_text("", encoding="ascii")
        (gitdir / "git.exe").write_text("", encoding="ascii")
        original = os.pathsep.join([str(pydir), str(gitdir)])
        stripped, _ = probe.strip_tool_from_path(
            original, tool="git", pathext=".EXE"
        )
        entries = stripped.split(os.pathsep)
        assert str(pydir) in entries
        assert str(gitdir) not in entries

    def test_the_real_path_keeps_the_interpreters_own_directory(self):
        """By value, against this machine's live PATH.

        If the interpreter's directory is on PATH and carries no git
        executable, stripping must leave it there. Without this the second run
        measures its own breakage rather than the absence of the tool.
        """
        interpreter_dir = str(Path(sys.executable).resolve().parent)
        original = os.environ.get("PATH", "")
        entries = [e for e in original.split(os.pathsep) if e]
        resolved = {str(Path(e).resolve()) for e in entries if e}
        if interpreter_dir not in resolved:
            pytest.skip("the interpreter's directory is not on this PATH")
        if probe.entry_carries_tool(interpreter_dir, "git", probe.executable_suffixes(None)):
            pytest.skip("the interpreter's directory carries git on this machine")
        stripped, _ = probe.strip_tool_from_path(original, tool="git")
        survivors = {
            str(Path(e).resolve()) for e in stripped.split(os.pathsep) if e
        }
        assert interpreter_dir in survivors

    def test_executable_suffixes_always_include_the_bare_name(self):
        assert "" in probe.executable_suffixes(".EXE;.BAT")
        assert "" in probe.executable_suffixes(None)

    def test_executable_suffixes_are_lowercased_and_deduplicated(self):
        suffixes = probe.executable_suffixes(".EXE;.exe;.BAT")
        assert suffixes.count(".exe") == 1
        assert ".bat" in suffixes


class TestThePositiveControl:
    """Criterion 3: the instrument is proved before any zero is believed."""

    def test_the_control_module_source_compiles_and_is_ascii(self):
        source = probe.CONTROL_MODULE_SOURCE
        source.encode("ascii")
        compile(source, "<control>", "exec")

    def test_the_control_is_planted_outside_the_repository_and_torn_down(self):
        seen: list[Path] = []
        with probe.planted_controls() as control_path:
            seen.append(control_path)
            assert control_path.is_file()
            assert REPO_ROOT not in control_path.parents, (
                "the planted site must never be written into the tree"
            )
        assert not seen[0].exists()
        assert not seen[0].parent.exists()

    def test_every_control_has_a_named_expectation(self):
        expected = probe.control_expectations()
        source = probe.CONTROL_MODULE_SOURCE
        for name in expected:
            assert f"def {name}(" in source, f"{name} is expected but never defined"
        defined = {
            line.split("(")[0].removeprefix("def ").strip()
            for line in source.splitlines()
            if line.startswith("def test_")
        }
        assert defined == set(expected)

    def _control(self, name: str) -> str:
        return f"{probe.CONTROL_MODULE_NAME}::{name}"

    def _all_controls_seen(self) -> tuple[probe.Classification, ...]:
        return tuple(
            probe.Classification(
                nodeid=self._control(name),
                kind=kind,
                detail="fixture",
                with_outcome="passed",
                without_outcome="x",
            )
            for name, kind in probe.control_expectations().items()
        )

    def test_all_three_controls_seen_proves_the_instrument(self):
        with_run = {
            self._control(name): probe.TestOutcome(
                nodeid=self._control(name),
                outcome="passed",
                invoked=name != "test_control_silent_pass",
                looked_up=True,
            )
            for name in probe.control_expectations()
        }
        result = probe.evaluate_controls(self._all_controls_seen(), with_run)
        assert result.proved is True
        assert result.missing == ()

    def test_a_control_the_probe_did_not_see_leaves_it_unproven(self):
        classified = tuple(
            c for c in self._all_controls_seen() if "false_red" not in c.kind
        )
        with_run = {
            c.nodeid: probe.TestOutcome(c.nodeid, "passed", True, True)
            for c in classified
        }
        result = probe.evaluate_controls(classified, with_run)
        assert result.proved is False
        assert any("false_red" in m for m in result.missing)

    def test_a_control_classified_as_the_wrong_kind_leaves_it_unproven(self):
        wrong = tuple(
            probe.Classification(
                nodeid=c.nodeid,
                kind="untouched",
                detail="fixture",
                with_outcome="passed",
                without_outcome="passed",
            )
            for c in self._all_controls_seen()
        )
        with_run = {
            c.nodeid: probe.TestOutcome(c.nodeid, "passed", True, True) for c in wrong
        }
        assert probe.evaluate_controls(wrong, with_run).proved is False

    def test_the_guarded_path_must_have_actually_run_with_the_tool_present(self):
        """Criterion 5, applied to the probe's own control.

        The clean-skip control skipping without the tool is only half the
        evidence. If it did not invoke the tool in the WITH run either, its
        green is a negative assertion that pins nothing down, so the
        instrument counts as unproven.
        """
        classified = self._all_controls_seen()
        with_run = {
            c.nodeid: probe.TestOutcome(c.nodeid, "passed", False, True)
            for c in classified
        }
        result = probe.evaluate_controls(classified, with_run)
        assert result.proved is False
        assert any("clean_skip" in note or "invoke" in note for note in result.missing)


class TestTheProbeItself:
    def _runner(self, calls: list[tuple[list[str], dict[str, str]]]):
        def runner(args, env, record_path):
            calls.append((list(args), dict(env)))
            entries = {
                "tests/t.py::test_x": ("passed", True, True),
                f"{probe.CONTROL_MODULE_NAME}::test_control_false_red": (
                    "passed" if len(calls) == 1 else "failed",
                    True,
                    False,
                ),
                f"{probe.CONTROL_MODULE_NAME}::test_control_clean_skip": (
                    "passed" if len(calls) == 1 else "skipped",
                    len(calls) == 1,
                    True,
                ),
                f"{probe.CONTROL_MODULE_NAME}::test_control_silent_pass": (
                    "passed",
                    False,
                    True,
                ),
            }
            Path(record_path).write_text(_record(entries), encoding="ascii")
            return 0
        return runner

    def test_it_runs_twice_and_strips_the_path_only_the_second_time(self, tmp_path):
        calls: list[tuple[list[str], dict[str, str]]] = []
        gitdir = tmp_path / "g"
        gitdir.mkdir()
        (gitdir / "git.exe").write_text("", encoding="ascii")
        keep = tmp_path / "k"
        keep.mkdir()
        base_env = {
            "PATH": os.pathsep.join([str(keep), str(gitdir)]),
            "PATHEXT": ".EXE",
        }
        report = probe.probe(runner=self._runner(calls), base_env=base_env)
        assert len(calls) == 2
        assert calls[0][1]["PATH"] == base_env["PATH"]
        assert calls[1][1]["PATH"] == str(keep)
        assert report.removed_path_entries == (str(gitdir),)
        assert report.ran is True

    def test_it_proves_its_instrument_and_reports_the_control_every_run(self, tmp_path):
        calls: list[tuple[list[str], dict[str, str]]] = []
        base_env = {"PATH": "", "PATHEXT": ".EXE"}
        report = probe.probe(runner=self._runner(calls), base_env=base_env)
        assert report.controls.proved is True
        rendered = probe.format_report(report)
        assert "positive control" in rendered.lower()

    def test_a_repo_finding_is_separated_from_the_controls(self, tmp_path):
        calls: list[tuple[list[str], dict[str, str]]] = []
        report = probe.probe(
            runner=self._runner(calls), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        finding_ids = {f.nodeid for f in report.findings}
        assert all(probe.CONTROL_MODULE_NAME not in n for n in finding_ids), (
            "a control must never be counted as a finding about this tree"
        )
        assert "tests/t.py::test_x" not in finding_ids

    def test_an_unproven_instrument_is_not_a_green_report(self, tmp_path):
        def broken_runner(args, env, record_path):
            Path(record_path).write_text(
                _record({"tests/t.py::test_x": ("passed", True, True)}),
                encoding="ascii",
            )
            return 0

        report = probe.probe(
            runner=broken_runner, base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        assert report.controls.proved is False
        assert report.ok is False
        assert "UNPROVEN" in probe.format_report(report)


class TestTheCommandLine:
    """``OPS-66`` and ``OPS-67``: an unknown argument is refused, never read.

    EVERY CALL HERE INJECTS A RUNNER, and that is not tidiness. The probe runs
    the WHOLE ``tests`` directory, this module included, so a test in this file
    that reached the default runner would spawn two suite runs, each of which
    would run this file again and spawn two more. Measured 2026-09-11 while
    watching a mutation go red: with ``allow_abbrev`` flipped to ``True`` the
    abbreviation test stopped being refused, fell through to a real run, and
    the machine was carrying five nested suite processes within two minutes.
    A refusal test that only asserts the exit code cannot see that, so each
    one below also asserts the runner was NEVER CALLED - the argument has to
    be refused BEFORE anything is spawned, not merely reported afterwards.
    """

    @staticmethod
    def _never_called():
        calls: list[int] = []

        def runner(args, env, record_path):
            calls.append(1)
            Path(record_path).write_text(_record({}), encoding="ascii")
            return 0

        return runner, calls

    def test_an_unknown_flag_is_a_usage_error(self, capsys):
        runner, calls = self._never_called()
        assert probe.main(["--not-a-real-flag"], runner=runner) == probe.USAGE_EXIT_CODE
        assert calls == [], "a refused argument must not reach a run"

    def test_a_positional_argument_is_a_usage_error(self, capsys):
        runner, calls = self._never_called()
        assert probe.main(["something.txt"], runner=runner) == probe.USAGE_EXIT_CODE
        assert calls == []

    def test_an_abbreviated_flag_is_refused_rather_than_guessed(self, capsys):
        runner, calls = self._never_called()
        assert probe.main(["--to", "git"], runner=runner) == probe.USAGE_EXIT_CODE
        assert calls == [], (
            "an abbreviation that fell through to a run is the recursion "
            "this module's class docstring records"
        )

    def test_help_exits_zero(self, capsys):
        runner, calls = self._never_called()
        assert probe.main(["--help"], runner=runner) == 0
        assert calls == []

    def test_the_tool_option_is_real(self, capsys, tmp_path):
        seen: list[str] = []

        def runner(args, env, record_path):
            seen.append(env.get("FALSE_RED_PROBE_TOOL", ""))
            Path(record_path).write_text(_record({}), encoding="ascii")
            return 0

        probe.main(["--tool", "hg"], runner=runner)
        assert seen and set(seen) == {"hg"}

    def test_an_unproven_run_gets_its_own_exit_code(self, tmp_path):
        def runner(args, env, record_path):
            Path(record_path).write_text(_record({}), encoding="ascii")
            return 0

        code = probe.main([], runner=runner)
        assert code == probe.UNPROVEN_EXIT_CODE
        assert probe.UNPROVEN_EXIT_CODE not in {0, 1, probe.USAGE_EXIT_CODE}


class TestTheModuleSaysWhatItCannotProve:
    def test_the_docstring_states_the_limits_of_the_third_outcome(self):
        collapsed = " ".join(probe.__doc__.split()).lower()
        assert "candidate" in collapsed
        assert "not a conviction" in collapsed

    def test_the_docstring_names_the_instrumentation_it_does_not_cover(self):
        collapsed = " ".join(probe.__doc__.split()).lower()
        assert "os.system" in collapsed


class TestTheDefaultRunnerShellsOutOnlyFromTheOutermostFunction:
    def test_the_default_runner_spawns_this_interpreter_and_nothing_else(self):
        source = Path(probe.__file__).read_text(encoding="utf-8")
        assert "sys.executable" in source
        assert "shell=True" not in source

    def test_the_default_runner_is_the_only_subprocess_call_site(self):
        source = Path(probe.__file__).read_text(encoding="utf-8")
        assert source.count("subprocess.run(") == 1

    def test_the_control_run_asks_pytest_for_the_repo_tests_and_the_control(self):
        args = probe.pytest_args(
            control_path=Path("C:/tmp/x/test_false_red_control.py"),
            plugin_dir=Path("C:/tmp/x"),
        )
        assert args[:3] == [sys.executable, "-m", "pytest"]
        assert "tests" in args
        assert str(Path("C:/tmp/x/test_false_red_control.py")) in args
        assert "-p" in args


def test_subprocess_is_imported_only_for_the_outermost_runner():
    """A cheap anchor: this module names subprocess, the probe uses it once."""
    assert subprocess.run is not None


class TestThisModuleCanNeverSpawnTheRealSuite:
    """The probe collects this file too, so a stray default runner recurses."""

    def test_every_call_into_the_probe_here_injects_a_runner(self):
        import ast

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        offenders: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name) or func.value.id != "probe":
                continue
            if func.attr not in ("main", "probe"):
                continue
            if not any(kw.arg == "runner" for kw in node.keywords):
                offenders.append(f"line {node.lineno}: probe.{func.attr} with no runner=")
        assert offenders == [], (
            "each of these would run the real suite, which runs this file, "
            "which would run the real suite again: " + "; ".join(offenders)
        )

    def test_the_anchor_this_guard_depends_on_is_really_there(self):
        """A negative assertion pins nothing down without this.

        If no ``probe.main``/``probe.probe`` call existed in this module at
        all, the check above would pass on an empty list and mean nothing.
        """
        source = Path(__file__).read_text(encoding="utf-8")
        assert source.count("probe.main(") >= 4
        assert source.count("probe.probe(") >= 1


#: The EXACT node id shape pytest produced on this machine for a control file
#: planted outside the repository root, measured 2026-09-11 with
#: ``python -m pytest --collect-only tests <planted control path>``. pytest
#: builds the id for an out-of-tree file by joining its collector chain with
#: ``::`` rather than by relative path, so the id STARTS with the separator and
#: its file half contains no ``/`` at all. The directory segments below are
#: synthetic on purpose: this repository never commits a real home directory
#: path, which ``tests/test_no_hardcoded_home_path.py`` enforces.
MANGLED_CONTROL_FILE = "::tmp::false_red_probe_ab12::test_false_red_control.py"


def _mangled(name: str) -> str:
    """One planted control's node id in the shape pytest really emitted."""
    return f"{MANGLED_CONTROL_FILE}::{name}"


class TestAnOutOfTreeControlIsStillRecognised:
    """The measured defect behind the first UNPROVEN run - ROADMAP ``OPS-74``.

    The control was collected in both runs all along; 2985 repository tests
    plus 3 planted ones is exactly the 2988 the first run reported, and the
    printed kind tally summed to 2988 rather than 2985, which is only possible
    if the three controls were counted as repository tests. What failed was
    RECOGNITION: the probe split the node id at the first ``::`` to find the
    file, and an out-of-tree id begins with that separator, so the file half
    came back empty and no control ever matched.
    """

    def test_the_file_half_of_an_out_of_tree_nodeid_is_not_empty(self):
        assert probe.file_of(_mangled("test_control_false_red")).endswith(
            probe.CONTROL_MODULE_NAME
        )

    def test_a_mangled_nodeid_is_recognised_as_a_planted_control(self):
        assert probe.is_control(_mangled("test_control_silent_pass")) is True

    def test_an_ordinary_repository_nodeid_is_not_a_control(self):
        assert probe.is_control("tests/test_a.py::test_one") is False

    def test_the_control_name_is_the_last_segment_and_not_the_first(self):
        assert (
            probe.control_test_name(_mangled("test_control_clean_skip"))
            == "test_control_clean_skip"
        )

    def _mangled_classifications(self) -> tuple[probe.Classification, ...]:
        return tuple(
            probe.Classification(
                nodeid=_mangled(name),
                kind=kind,
                detail="fixture",
                with_outcome="passed",
                without_outcome="x",
            )
            for name, kind in probe.control_expectations().items()
        )

    def test_three_mangled_controls_prove_the_instrument(self):
        classified = self._mangled_classifications()
        with_run = {
            c.nodeid: probe.TestOutcome(
                nodeid=c.nodeid,
                outcome="passed",
                invoked=probe.control_test_name(c.nodeid)
                != "test_control_silent_pass",
                looked_up=True,
            )
            for c in classified
        }
        result = probe.evaluate_controls(classified, with_run)
        assert result.missing == ()
        assert result.proved is True
        assert set(result.seen) == set(probe.control_expectations())


class TestTheControlsNeverPolluteTheRepositoryFigures:
    """Criterion 3's accounting: classified, required, and never counted."""

    @staticmethod
    def _runner():
        """A two-run fixture that tells the runs apart by CALL ORDER.

        Not by the record file's name: the probe writes ``record_with.json``
        and ``record_without.json``, and ``"record_with" in name`` is true of
        both. That mistake made this fixture emit the with-tool record twice
        and every assertion below went green against a run that never varied.
        """
        calls: list[int] = []

        def runner(args, env, record_path):
            calls.append(1)
            first = len(calls) == 1
            entries = {
                "tests/t.py::test_real_false_red": (
                    "passed" if first else "failed",
                    True,
                    False,
                ),
                "tests/t.py::test_plain": ("passed", False, False),
                _mangled("test_control_false_red"): (
                    "passed" if first else "failed",
                    True,
                    False,
                ),
                _mangled("test_control_clean_skip"): (
                    "passed" if first else "skipped",
                    first,
                    True,
                ),
                _mangled("test_control_silent_pass"): ("passed", False, True),
            }
            Path(record_path).write_text(_record(entries), encoding="ascii")
            return 0

        return runner

    def test_the_run_is_proved_by_the_mangled_controls(self):
        report = probe.probe(
            runner=self._runner(), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        assert report.controls.proved is True

    def test_no_control_id_appears_among_the_findings(self):
        report = probe.probe(
            runner=self._runner(), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        assert [f.nodeid for f in report.findings] == [
            "tests/t.py::test_real_false_red"
        ]

    def test_the_kind_tally_counts_only_repository_tests(self):
        report = probe.probe(
            runner=self._runner(), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        rendered = probe.format_report(report)
        kinds_line = next(
            line for line in rendered.splitlines() if line.strip().startswith("kinds:")
        )
        assert "false_red=1" in kinds_line
        assert "clean_skip" not in kinds_line
        assert "silent_pass" not in kinds_line

    def test_the_collected_totals_exclude_the_planted_controls(self):
        report = probe.probe(
            runner=self._runner(), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        assert report.with_total == 2
        assert report.without_total == 2
        assert report.with_control_total == 3
        assert report.without_control_total == 3

    def test_the_controls_get_their_own_stanza_in_the_report(self):
        report = probe.probe(
            runner=self._runner(), base_env={"PATH": "", "PATHEXT": ".EXE"}
        )
        rendered = probe.format_report(report)
        stanza = next(
            line
            for line in rendered.splitlines()
            if line.strip().startswith("planted controls")
        )
        for name, kind in probe.control_expectations().items():
            assert f"{name}={kind}" in stanza


class TestThePlantedSiteIsAlwaysTornDown:
    """Criterion 2: the planted file may never survive the run."""

    def test_the_directory_is_removed_when_the_body_raises(self):
        seen: list[Path] = []
        with (
            pytest.raises(RuntimeError, match="deliberate"),
            probe.planted_controls() as control_path,
        ):
            seen.append(control_path)
            assert control_path.is_file(), "the anchor: the plant must exist"
            raise RuntimeError("deliberate")
        assert seen, "the context manager never yielded, so nothing was proved"
        assert not seen[0].exists()
        assert not seen[0].parent.exists()

    def test_no_file_under_tests_is_named_like_the_planted_control(self):
        """Matching a control by BASENAME is only safe while this holds."""
        collisions = [
            str(path)
            for path in (REPO_ROOT / "tests").rglob(probe.CONTROL_MODULE_NAME)
        ]
        assert collisions == []


class TestTheDocstringRecordsTheAccountingDecision:
    def test_it_says_control_ids_are_excluded_from_the_counts(self):
        collapsed = " ".join(probe.__doc__.split()).lower()
        assert "planted controls" in collapsed
        assert "excluded" in collapsed

    def test_it_records_the_out_of_tree_nodeid_shape_that_broke_recognition(self):
        collapsed = " ".join(probe.__doc__.split()).lower()
        assert "node id" in collapsed
        assert "first ``::``" in collapsed or "first separator" in collapsed
