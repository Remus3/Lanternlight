"""MAIN's fleet kit conforms in this tree (MAIN 0955 section 2 step 2, OPS-120).

The kit at ``ops/fleet_kit/`` is vendored byte-for-byte under Apache-2.0 (see
``ops/fleet_kit/NOTICE.md``). Its own ``conformance()`` reports a kit file that
was edited, a manifest version that disagrees with the code, and a
``FLEET-COMMON`` block in ``CLAUDE.md`` that is missing or edited. An empty list
is conformance. It hashes ``ops/fleet_kit/FLEET-COMMON.md`` and
``ops/fleet_kit/fleet_headless.py`` against the manifest, so a staged edit to
either document selects this module in the pre-commit subset. A red here is
answered by reporting the defect to MAIN or by installing a new kit version
whole - never by editing a kit file.
"""

from __future__ import annotations

from ops.fleet_kit import fleet_headless
from tests.conftest import REPO_ROOT


def test_fleet_kit_conforms():
    assert fleet_headless.conformance(REPO_ROOT) == []


def test_notice_names_the_license_and_every_pinned_digest():
    import json

    notice = (REPO_ROOT / "ops" / "fleet_kit" / "NOTICE.md").read_text(
        encoding="ascii"
    )
    manifest = json.loads(
        (REPO_ROOT / "ops" / "fleet_kit" / "MANIFEST.json").read_text(
            encoding="ascii"
        )
    )
    assert "Apache-2.0" in notice
    for digest in manifest["files"].values():
        assert digest in notice
