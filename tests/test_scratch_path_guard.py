"""No tracked command may build a scratch path that lands outside the scratchpad.

``OPS-107``. Under Git Bash the variable most shell snippets reach for as a
temp directory is UNSET - measured 2026-09-20 in this harness by testing
presence only, never a value - so a redirect into that variable plus a slash
and a name expands to a slash and a name, which MSYS maps to the Git for
Windows install root. Seventeen of this project's files landed there, written
by subagents, and ``OPS-103`` criterion 3 put a CONTROL over the destination
without stopping the source. This module pins the source-side guard,
:mod:`ops.scratch_path_guard`.

AN ADVERSARIAL PASS REFUTED THE FIRST VERSION, and the specimens it found are
pinned below. The first version refused a path INSIDE the root temp directory,
which Git Bash MOUNTS onto the user temp folder (measured: mount reports it as
usertemp, and cygpath resolves a file under it to the user temp folder), while
it passed a root path that merely STARTS with the temp name - which cygpath
resolves into the Git install root, the exact landing this item exists for.

Every specimen below is assembled at RUN TIME from fragments, so this file
never carries a matching literal and the guard's own full-tree scan does not
have to exempt it. An exemption for the guard's own test is exactly the kind
of safe list the ``OPS-103`` hand-off found the holes in.

The lane-contract half of the item is pinned here too: every generated
contract must name the session scratchpad as the ONLY scratch destination.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ops import lane_contract, lanes, scratch_path_guard as guard

REPO_ROOT = Path(__file__).resolve().parents[1]

# Fragments. Never join these in a literal anywhere in this file.
D = "$"
TMPDIR = D + "TMPDIR"
TMPDIR_BRACED = D + "{" + "TMPDIR" + "}"
TMP = D + "TMP"
TEMP = D + "TEMP"
ENV_TMPDIR = D + "env:" + "TMPDIR"
PCT_TMPDIR = "%" + "TMPDIR" + "%"
ROOT_TMP = "/" + "tmp"
FENCE = "`" * 3
BS = "\\"


def rules(findings: list[tuple[int, str]]) -> set[str]:
    return {rule for _line, rule in findings}


class TestShellRules:
    @pytest.mark.parametrize(
        "line",
        [
            f'python x.py > "{TMPDIR}/out.txt"',
            f'cp a "{TMPDIR_BRACED}/b"',
            f"echo hi > {TMP}/note.txt",
            f"echo hi > {TEMP}/note.txt",
            # The actual OPS-107 landing, measured 2026-09-20 with cygpath: a
            # root path that merely STARTS with the temp name is not the
            # mounted temp directory and resolves into the Git install root.
            f"echo x > {ROOT_TMP}_x",
            f"echo x > {ROOT_TMP}-x",
            f"echo x > {ROOT_TMP}file",
            f"echo x > {ROOT_TMP}.x",
            f'echo x > "{ROOT_TMP}fs/a"',
            # Unset in every shell on this machine, measured 2026-09-20.
            f"cp a {ENV_TMPDIR}/x",
            f"echo x > {PCT_TMPDIR}{BS}a",
        ],
    )
    def test_a_planted_hazard_is_refused(self, line: str) -> None:
        assert guard.scan_shell(line + "\n"), line

    @pytest.mark.parametrize(
        "line",
        [
            'echo x > "$SCRATCH/out.txt"',
            "ls C:" + ROOT_TMP + "/x",
            "ls ./" + "tmp" + "/x",
            "ls $HOME" + ROOT_TMP,
            "ls ${OUT}" + ROOT_TMP,
            "echo " + D + "TMPDIRECTORY_IS_A_DIFFERENT_NAME",
            # Git Bash MOUNTS the user temp folder at this path (usertemp), so
            # a path INSIDE it is not the install root - measured 2026-09-20
            # with mount and cygpath. Not this item's bug.
            f"mkdir -p {ROOT_TMP}/scratch",
            f'echo x > "{ROOT_TMP}/x"',
            f"cd {ROOT_TMP}",
            f"cd {ROOT_TMP}; ls",
            f"x=$(ls {ROOT_TMP})",
            f"ls '{ROOT_TMP}'",
        ],
    )
    def test_a_near_miss_is_not_refused(self, line: str) -> None:
        assert guard.scan_shell(line + "\n") == [], line

    def test_the_finding_carries_the_line_number(self) -> None:
        text = "echo ok\n" + f'echo x > "{TMPDIR}/a"\n'
        assert guard.scan_shell(text) == [(2, "unset-temp-var")]

    def test_the_prefix_form_has_its_own_rule(self) -> None:
        assert rules(guard.scan_shell(f"cd {ROOT_TMP}_x\n")) == {"tmp-prefix-git-root"}


class TestPowerShellRules:
    def test_a_bare_temp_variable_is_refused_because_it_is_NULL_there(self) -> None:
        # Measured 2026-09-20: in PowerShell the bare variable is an ordinary
        # unset PS variable, not the environment one, so it evaluates to null
        # and the path collapses to the root of the current drive.
        assert guard.scan_powershell(f'Set-Content "{TEMP}{BS}x.txt" 1\n')
        assert guard.scan_powershell(f'Set-Content "{TMPDIR}{BS}x.txt" 1\n')

    def test_the_environment_TMPDIR_is_refused_because_it_is_UNSET(self) -> None:
        # Measured 2026-09-20: the environment has no TMPDIR on this machine,
        # so the environment form is null exactly like the bare one.
        assert guard.scan_powershell(f'Set-Content "{ENV_TMPDIR}{BS}x" 1\n')
        assert guard.scan_powershell(D + "{env:TMPDIR}" + BS + "x\n")
        assert guard.scan_powershell(D + "ENV:tmpdir" + BS + "x\n")

    def test_the_environment_TEMP_and_TMP_are_not_refused(self) -> None:
        assert guard.scan_powershell(f'Set-Content "{D}env:TEMP{BS}x.txt" 1\n') == []
        assert guard.scan_powershell(D + "{env:TEMP}\n") == []
        assert guard.scan_powershell(D + "env:TMP" + BS + "x\n") == []

    def test_case_does_not_hide_it(self) -> None:
        assert guard.scan_powershell(D + "temp" + BS + "x\n")


class TestCmd:
    def test_percent_TMPDIR_is_refused_in_a_batch_file(self) -> None:
        assert guard.scan_file("tools/x.bat", f"echo x > {PCT_TMPDIR}{BS}a\n")
        assert guard.scan_file("tools/x.cmd", f"echo x > {PCT_TMPDIR.lower()}{BS}a\n")

    def test_percent_TEMP_is_not_refused(self) -> None:
        # cmd reads the environment, where TEMP is set.
        assert guard.scan_file("tools/x.cmd", f"echo x > %TEMP%{BS}a\n") == []


class TestMarkdown:
    def test_a_hazard_inside_a_shell_fence_is_refused(self) -> None:
        text = f"Prose.\n\n{FENCE}bash\necho x > {TMPDIR}/a\n{FENCE}\n"
        assert guard.scan_markdown(text) == [(4, "unset-temp-var")]

    def test_an_untagged_fence_is_treated_as_shell(self) -> None:
        text = f"{FENCE}\ncd {ROOT_TMP}_x\n{FENCE}\n"
        assert guard.scan_markdown(text) == [(2, "tmp-prefix-git-root")]

    def test_a_powershell_fence_gets_powershell_rules(self) -> None:
        text = f"{FENCE}powershell\nSet-Content {TEMP}{BS}x 1\n{FENCE}\n"
        assert guard.scan_markdown(text) == [(2, "unset-temp-var")]
        ok = f"{FENCE}powershell\nSet-Content {D}env:TEMP{BS}x 1\n{FENCE}\n"
        assert guard.scan_markdown(ok) == []

    @pytest.mark.parametrize("tag", ["python", "yaml", "cmd", "text", "json"])
    def test_EVERY_fence_is_scanned_whatever_its_tag(self, tag: str) -> None:
        # A fence is text a reader copies. Exempting a tag nobody thought
        # about is the safe-list failure; measured zero findings tree-wide.
        text = f"{FENCE}{tag}\necho x > {TMPDIR}/a\n{FENCE}\n"
        assert guard.scan_markdown(text) == [(2, "unset-temp-var")]

    def test_an_indented_code_block_is_scanned(self) -> None:
        text = f"Prose.\n\n    echo x > {TMPDIR}/a\n\nMore prose.\n"
        assert guard.scan_markdown(text) == [(3, "unset-temp-var")]

    def test_prose_that_DESCRIBES_the_hazard_is_not_refused(self) -> None:
        # The ROADMAP entry for this very item has to be able to say what the
        # bug is. Prose - inline code included - is description.
        text = f'Under Git Bash `{TMPDIR}` is unset, so `"{TMPDIR}/name"` breaks.\n'
        assert guard.scan_markdown(text) == []

    def test_an_agent_instruction_file_is_scanned_WHOLE(self) -> None:
        # A slash command or a hand-off prompt is executed by an agent, so its
        # prose IS a command. Describe the hazard there without the literal.
        text = f"Write your output to `{TMPDIR}/out.txt` and report.\n"
        assert guard.scan_markdown(text, whole=True) == [(1, "unset-temp-var")]

    @pytest.mark.parametrize("rel", ["CLAUDE.md", "docs/HEADLESS.md"])
    def test_the_documents_every_agent_loads_are_scanned_WHOLE(self, rel: str) -> None:
        assert guard.scan_file(rel, f"Write to `{TMPDIR}/out.txt`.\n")


class TestPython:
    def test_a_shell_string_in_code_is_refused(self) -> None:
        src = f'import subprocess\nsubprocess.run(["bash", "-c", "ls > {TMPDIR}/x"])\n'
        assert guard.scan_python(src) == [(2, "unset-temp-var")]

    def test_a_root_temp_path_in_code_is_refused(self) -> None:
        # Native Python resolves it against the current DRIVE root, measured
        # 2026-09-20 - never the scratchpad, whatever Git Bash mounts there.
        src = f'name = "a"\ncmd = f"cp x {ROOT_TMP}/{{name}}"\n'
        assert guard.scan_python(src) == [(2, "drive-root-tmp")]
        assert guard.scan_python(f'p = b"{ROOT_TMP}/x"\n') == [(1, "drive-root-tmp")]

    @pytest.mark.parametrize(
        "expr",
        [
            "os.environ['TMPDIR']",
            'os.environ.get("TMPDIR", "")',
            "os.getenv('TMPDIR')",
            "environ['TMPDIR']",
        ],
    )
    def test_reading_TMPDIR_from_the_environment_is_refused(self, expr: str) -> None:
        src = f"import os\nfrom os import environ\np = {expr}\n"
        assert guard.scan_python(src) == [(3, "unset-temp-var")]

    def test_reading_TEMP_from_the_environment_is_not_refused(self) -> None:
        assert guard.scan_python("import os\np = os.environ['TEMP']\n") == []

    def test_a_docstring_or_comment_describing_it_is_not_refused(self) -> None:
        src = (
            f'"""Module: {TMPDIR} is unset under Git Bash."""\n'
            f"# a comment naming {ROOT_TMP}/x\n"
            "def f():\n"
            f'    """{TMPDIR}/name breaks."""\n'
            "    return 1\n"
        )
        assert guard.scan_python(src) == []

    def test_unparseable_python_is_reported_not_passed(self) -> None:
        # A file the guard cannot read is not a clean file.
        assert rules(guard.scan_python("def (:\n")) == {"unparseable"}


class TestDispatch:
    def test_each_file_kind_is_routed_to_its_rules(self) -> None:
        shell = f"#!/bin/sh\necho x > {TMPDIR}/a\n"
        assert guard.scan_file(".githooks/pre-commit", shell)
        assert guard.scan_file("scripts/x.sh", f"cd {ROOT_TMP}_x\n")
        assert guard.scan_file("tools/x.ps1", f"cd {TEMP}\n")
        assert guard.scan_file(".claude/settings.json", f'{{"c": "ls {TMPDIR}/a"}}\n')
        assert guard.scan_file(".github/workflows/t.yml", f"run: cd {ROOT_TMP}file\n")
        assert guard.scan_file(".claude/commands/x.md", f"write to {TMPDIR}/a\n")
        assert guard.scan_file("LL-NEXT-SESSION.txt", f"write to {TMPDIR}/a\n")

    def test_ordinary_markdown_prose_is_not_whole_scanned(self) -> None:
        assert guard.scan_file("docs/X.md", f"`{TMPDIR}` is unset.\n") == []

    def test_an_unknown_text_kind_defaults_to_WHOLE_scan(self) -> None:
        # Default strict. A new file kind is not exempt because nobody thought
        # about it; that is the safe-list failure the hand-off recorded.
        assert guard.scan_file("misc/thing.cfg", f"path={ROOT_TMP}x\n")


class TestTheTrackedTree:
    def test_the_population_is_not_vacuous(self) -> None:
        files = guard.population(REPO_ROOT)
        names = {p.relative_to(REPO_ROOT).as_posix() for p in files}
        assert len(files) > 100
        for required in (
            ".githooks/pre-commit",
            ".claude/settings.json",
            ".claude/commands/lane-ops.md",
            "CLAUDE.md",
            "ops/scratch_path_guard.py",
        ):
            assert required in names, required

    def test_the_tracked_tree_is_clean(self) -> None:
        # The measured false-positive rate. The hazard IS described in prose
        # across this tree - ROADMAP, the ledger archive, the wake-up notes and
        # a docstring - and none of it may count, while no command may carry it.
        findings = guard.scan_tree(REPO_ROOT)
        assert findings == [], guard.format_findings(findings)

    def test_a_planted_file_in_the_tree_is_found(self, tmp_path: Path) -> None:
        (tmp_path / "run.sh").write_text(f'echo x > "{TMPDIR}/a"\n', encoding="ascii")
        (tmp_path / "ok.md").write_text(f"`{TMPDIR}` in prose.\n", encoding="ascii")
        findings = guard.scan_tree(tmp_path, files=[tmp_path / "run.sh", tmp_path / "ok.md"])
        assert [(f.path, f.line, f.rule) for f in findings] == [
            ("run.sh", 1, "unset-temp-var")
        ]

    def test_the_guard_is_in_the_preflight(self) -> None:
        from ops import preflight

        assert "tests/test_scratch_path_guard.py" in preflight.MODULES


class TestLaneContracts:
    @pytest.mark.parametrize("lane", lanes.LANES, ids=lambda lane: lane.lane_id)
    def test_every_contract_names_the_scratchpad_as_the_only_destination(
        self, lane: lanes.Lane
    ) -> None:
        text = lane_contract.render(lane)
        assert "## Scratch files - the session scratchpad only" in text
        assert "the ONLY scratch destination" in text
        assert "OPS-107" in text

    @pytest.mark.parametrize("lane", lanes.LANES, ids=lambda lane: lane.lane_id)
    def test_no_contract_itself_carries_the_hazard(self, lane: lanes.Lane) -> None:
        text = lane_contract.render(lane)
        assert guard.scan_markdown(text, whole=True) == []

    def test_no_contract_claims_the_mounted_temp_directory_is_the_hazard(self) -> None:
        # The first version said a bare root temp directory lands in the Git
        # install root. Refuted: Git Bash mounts the user temp folder there.
        for lane in lanes.LANES:
            assert "bare root temp directory" not in lane_contract.render(lane)
