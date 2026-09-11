"""The vendored write tracer, and the obligations that came with it.

``OPS-84``. ``third_party/lw_write_tracer/lw_write_tracer.py`` is a work
Lanternlight did not write. It arrived on the cross-project note channel from
Legion Wallpaper, was refused once because the drop carried no license
statement, and was vendored on 2026-09-11 after LW named Apache-2.0 explicitly
and the operator ruled to vendor.

WHAT THIS MODULE IS FOR. Apache-2.0 section 4(b) requires a statement of
changes, and a statement of changes is worth exactly as much as the reader's
ability to check it. ``third_party/lw_write_tracer/NOTICE.md`` says one change
was made - CRLF normalised to LF for this repository's ``.gitattributes``
policy - and that no other byte differs. These arms are what make that a
checkable claim rather than a promise.

WHY THE ASSERTION RESTORES CRLF RATHER THAN PINNING A DIGEST. A hash of a
working file is not a hash of the commit, and this repository has already paid
for that lesson once - ``.gitattributes`` pins ``*.py`` to ``eol=lf`` while the
file arrived with CRLF on all 274 of its lines. Pinning the on-disk digest would
bind the test to a line-ending policy rather than to the licensed content, and it
would have to be rewritten the day that policy changed. Restoring CRLF and
comparing against the digest LW PUBLISHED binds it to the content, which is the
thing the license is about.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / "third_party" / "lw_write_tracer"
PLUGIN = VENDOR_DIR / "lw_write_tracer.py"
NOTICE = VENDOR_DIR / "NOTICE.md"
RECEIVED_DROP = REPO_ROOT / "moon_sync_inbox" / "lw_write_tracer.py.from-lw"

#: The digest LW published in its note of 2026-09-11 14:15, verified against the
#: drop before a byte was copied in. This records WHAT WAS LICENSED and never
#: what is on disk - see the module docstring.
RECEIVED_SHA256 = "17c3c748f0f04b85701cff41c2df8706f77b46a10aa3a98a3dc0ca60b7136479"
RECEIVED_BYTES = 11267


class TestTheVendoredWorkIsTheWorkThatWasLicensed:
    def test_the_plugin_is_present_and_not_empty(self) -> None:
        assert PLUGIN.is_file(), f"the vendored plugin is missing: {PLUGIN}"
        assert PLUGIN.stat().st_size > 0

    def test_restoring_crlf_reproduces_the_digest_lw_published(self) -> None:
        """The whole claim of ``NOTICE.md``, in one assertion.

        If this is red, either the file was edited - in which case it is a
        derivative work and the change must be declared in ``NOTICE.md`` - or
        the line-ending policy changed in a way this test's inverse no longer
        models. Both need a human; neither is fixed by editing the constant.
        """
        on_disk = PLUGIN.read_bytes()
        assert b"\r\n" not in on_disk, (
            "the vendored copy carries CRLF, so the inverse below would be "
            "applied to bytes that are not purely LF and would prove nothing"
        )
        restored = on_disk.replace(b"\n", b"\r\n")
        assert len(restored) == RECEIVED_BYTES, (
            f"restored to {len(restored)} bytes, not the {RECEIVED_BYTES} that "
            "were received - the content differs, not just the line endings"
        )
        assert hashlib.sha256(restored).hexdigest() == RECEIVED_SHA256, (
            "the vendored file is no longer byte-identical to the work that was "
            "licensed. It is now a derivative work: declare the change in "
            "third_party/lw_write_tracer/NOTICE.md rather than editing this "
            "constant, which records what LW published and not what is on disk"
        )

    def test_the_only_change_claimed_is_the_only_change_made(self) -> None:
        """The anchor for the arm above, from the other direction.

        Proves the two forms differ ONLY in line endings, without trusting the
        digest to have been computed over the right bytes. Skips rather than
        fails when the drop is gone: ``moon_sync_inbox/`` is gitignored live
        mail, so a fresh clone has no copy of it and its absence is not a defect.
        """
        if not RECEIVED_DROP.is_file():
            pytest.skip("the original drop is no longer in the gitignored inbox")
        assert RECEIVED_DROP.read_bytes().replace(b"\r\n", b"\n") == PLUGIN.read_bytes()


class TestTheAttributionObligationsAreActuallyMet:
    """Apache-2.0 does not permit vendoring silently, so silence is a defect."""

    def _notice(self) -> str:
        assert NOTICE.is_file(), f"the vendored work has no NOTICE: {NOTICE}"
        return NOTICE.read_text(encoding="ascii")

    def test_the_notice_names_the_license(self) -> None:
        assert "Apache-2.0" in self._notice()

    def test_the_notice_names_the_upstream_and_the_holder(self) -> None:
        text = self._notice()
        assert "Legion-Wallpaper" in text, "the upstream repository is not named"
        assert "copyright holder" in text.lower()

    def test_the_notice_carries_a_statement_of_changes(self) -> None:
        """Section 4(b). A vendored work with no change statement is a breach."""
        text = self._notice()
        assert "CHANGES MADE TO THE WORK" in text
        assert RECEIVED_SHA256 in text, (
            "the notice does not record the digest of what was licensed, so a "
            "reader cannot check the change statement against anything"
        )

    def test_the_notice_records_both_digests_and_says_which_is_which(self) -> None:
        text = self._notice()
        assert "AS RECEIVED" in text and "AS VENDORED" in text, (
            "one digest for a file whose bytes differ on disk and in the blob is "
            "the trap CLAUDE.md records, not a record"
        )


class TestTheVendoredPluginActuallyRunsHere:
    """Vendoring a file that does not load would be a licensing exercise only."""

    def test_it_loads_as_a_plugin_and_proves_its_own_control(
        self, tmp_path: Path
    ) -> None:
        """End to end through a real pytest subprocess - ``OPS-84`` #3.

        The control is the reason this is worth running at all. The plugin
        plants a specimen through each patched route AND a negative specimen
        outside every watched root, then reports whether it saw the first and
        not the second. A tracer that cannot prove it SEES reports a zero that
        means nothing; one that cannot prove it does not INVENT reports a
        finding that means nothing.
        """
        subject = tmp_path / "test_nothing.py"
        subject.write_text("def test_ok():\n    assert True\n", encoding="ascii")
        watched = tmp_path / "watched"
        watched.mkdir()
        out = tmp_path / "trace.json"

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(subject),
                "-p",
                "lw_write_tracer",
                "--trace-roots",
                str(watched),
                "--trace-out",
                str(out),
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(tmp_path),
            env=_env_with_plugin_on_path(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert out.is_file(), f"no report was written: {proc.stdout}"

        report = json.loads(out.read_text(encoding="utf-8"))
        assert report["control"]["proved"] is True, report["control"]
        assert report["control"]["negative_clean"] is True, report["control"]
        assert report["restored"] is True, (
            "the plugin did not put the interpreter back the way it found it"
        )

    def test_its_stated_subprocess_limit_travels_with_its_report(self) -> None:
        """The limit that made LW's finding about this tree wrong - ``OPS-82``.

        Asserted rather than trusted, because every number this plugin produces
        for this suite is a LOWER BOUND for that reason, and a limit that is not
        in the report is a limit that gets dropped when the number is quoted.
        """
        source = PLUGIN.read_text(encoding="ascii")
        assert '"subprocess"' in source and "LOWER BOUND" in source


def _env_with_plugin_on_path() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(VENDOR_DIR) + (os.pathsep + existing if existing else "")
    return env
