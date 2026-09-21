"""This suite must delete its own ``tmp_path`` directories when a test PASSES.

WHY, and the numbers below were measured on this machine rather than reasoned
about.

A session overlooking the machine from ``C:/`` reported that a scheduled
hygiene sweep deletes ``pytest`` run directories older than TWO DAYS, and that
the rule was matching nothing on every run. Re-measured here 2026-09-20,
walking the shared temp root directly:

- ``pytest-of-Administrator`` held 46 run directories.
- The OLDEST was 1.22 days old. **Zero were older than two days**, so a
  two-day cutoff removes zero of 46 - the sweep was correct in its own terms
  and simply never had a candidate.
- The same walk counted 266,336 files under that one base. The relayed figure
  was 192,202, which was already stale by roughly 74,000 files when it reached
  us. A count from a shared directory carries the timestamp of the read, and
  two of this session's own suite runs are inside that difference.

**The relayed diagnosis needed one correction, and it changes where the fix
belongs.** The report said that base had been "accumulating since 2026-04-22".
Measured, nothing in it is older than about 29 hours: the DIRECTORY dates from
April, its CONTENTS do not. So this is not a slow accumulation that a longer
retention window would catch up with - it is churn, produced faster than any
cutoff expressed in days can ever match. Raising or lowering somebody else's
cutoff is treating the symptom. The suites producing the churn are the only
place it can actually be fixed.

**So this repository fixes its own share and nothing else.** The sweep script
is not in this tree, the ``pytest-substrate-*`` bases belong to another
project, and ``CLAUDE.md`` permits this project to write into the sync inboxes
and nowhere else outside its own root. Our contribution, and only ours, is
controlled here.

THE EFFECT, measured before it was believed. The same two modules, the same 88
tests, run twice into isolated base directories:

- ``tmp_path_retention_policy=all`` (the stock default): 589 files, 401 dirs.
- ``tmp_path_retention_policy=failed``: 175 files, 236 dirs.

A 70 per cent reduction in files from one ini line. It does not reach zero, and
that is expected rather than a shortfall: session-scoped factory directories
and the base itself are not per-test and survive either way.

**Why ``failed`` and not something more aggressive.** A directory belonging to
a test that FAILED is evidence, and deleting it turns a debuggable failure into
a mystery. ``failed`` keeps exactly the ones worth keeping.

**Why the retention COUNT is written down even though it equals the stock
default.** ``--strict-config`` is already on, so a value here cannot be a typo
that silently does nothing. Pinning it means a future pytest changing its own
default cannot quietly change what this repository leaves on the operator's
disk - which is the class of silent behaviour change this file exists to stop.
"""

from __future__ import annotations

import configparser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTEST_INI = REPO_ROOT / "pytest.ini"

#: A passing test's directory is removed; a FAILING test's is kept, because it
#: is the evidence someone will want.
REQUIRED_POLICY = "failed"

#: Numbered run directories kept under the base. Equal to the stock default,
#: pinned deliberately - see the module docstring.
REQUIRED_COUNT = "3"


def _config() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    # pytest.ini uses ';' comments, which configparser handles, and inline
    # values that must not be interpolated.
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(PYTEST_INI, encoding="utf-8")
    return parser


def test_pytest_ini_parses_at_all():
    """A negative from an unparseable file is a claim about the parser.

    Without this arm, a malformed ``pytest.ini`` would make every assertion
    below fail for the wrong reason and read as a missing setting.
    """
    parser = _config()
    assert parser.has_section("pytest"), (
        "pytest.ini has no [pytest] section - the file did not parse as "
        "expected, so nothing below is a statement about its settings"
    )


def test_the_retention_policy_is_set_to_failed():
    parser = _config()
    assert parser.has_option("pytest", "tmp_path_retention_policy"), (
        "pytest.ini does not set tmp_path_retention_policy. Without it this "
        "suite keeps every passing test's tmp_path on the operator's disk - "
        "measured at 589 files against 175 for the same 88 tests."
    )
    assert parser.get("pytest", "tmp_path_retention_policy").strip() == REQUIRED_POLICY


def test_the_retention_count_is_pinned():
    parser = _config()
    assert parser.has_option("pytest", "tmp_path_retention_count"), (
        "pytest.ini does not pin tmp_path_retention_count. It equals the stock "
        "default today; pinning it stops a future pytest silently changing what "
        "this repository leaves on disk."
    )
    assert parser.get("pytest", "tmp_path_retention_count").strip() == REQUIRED_COUNT


def test_the_reason_is_written_down_beside_the_settings():
    """The measurement must survive in the file a reader opens.

    A setting with no reason beside it is a setting the next person deletes
    while tidying. This asserts the ini carries a pointer to this module, which
    carries the numbers.
    """
    body = PYTEST_INI.read_text(encoding="utf-8")
    assert "tests/test_tmp_retention.py" in body, (
        "pytest.ini sets the retention options without pointing at the module "
        "that records why - so the first reader to tidy them has no reason not to"
    )


def test_the_settings_are_live_and_not_merely_declared(pytestconfig):
    """The running pytest must actually HAVE these values.

    This is the arm that makes the three above more than a text check. An ini
    key that pytest does not recognise would sit in the file looking correct
    while changing nothing, and ``--strict-config`` only catches a key pytest
    knows to be unknown. Asking the live config asks the tool.
    """
    assert pytestconfig.getini("tmp_path_retention_policy") == REQUIRED_POLICY
    assert str(pytestconfig.getini("tmp_path_retention_count")) == REQUIRED_COUNT
