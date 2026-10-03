"""Tests for scripts/arm_inbox_runner.py - the trigger's definition. LL-0317."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "arm_inbox_runner", ROOT / "scripts" / "arm_inbox_runner.py"
)
arm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(arm)


def test_task_lives_in_our_own_namespace():
    assert arm.TASK_NAME.startswith("\\Lanternlight\\")


def test_create_runs_the_runner_every_fifteen_minutes_under_pythonw():
    argv = arm.create_argv("PYW", Path("R/ops/inbox_runner.py"))
    assert argv[:3] == ["schtasks", "/Create", "/F"]
    assert argv[argv.index("/SC") + 1] == "MINUTE"
    assert argv[argv.index("/MO") + 1] == "15"
    tr = argv[argv.index("/TR") + 1]
    assert tr.startswith('"PYW"') and "inbox_runner.py" in tr
    assert argv[argv.index("/RL") + 1] == "LIMITED"


def test_the_task_is_never_elevated_and_never_stored_with_a_password():
    argv = arm.create_argv("PYW")
    assert "HIGHEST" not in argv and "/RP" not in argv and "/RU" not in argv


def test_runner_path_points_at_the_real_module():
    assert arm.RUNNER.is_file() and arm.RUNNER.name == "inbox_runner.py"


def test_disarm_deletes_only_our_task():
    assert arm.delete_argv() == ["schtasks", "/Delete", "/F", "/TN", arm.TASK_NAME]
