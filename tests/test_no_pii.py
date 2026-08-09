"""Last line of defence before a public push: no identifiers in the tree.

The Mistfall Hunter log this project reads carries the operator's SteamID64,
Steam persona name, platform account ids, an Epic ProductUserId and an
IP-resolved location. Lanternlight is a public repository. A single pasted log
line in a fixture, a docstring or a bug report would publish those
permanently, because git history keeps them after the file is deleted.

So this test scans every authored text file in the repository with
:mod:`lanternlight.redact`'s own detectors and fails if any of them fire. It
uses the redactor's rules rather than a private copy of the patterns on
purpose: a rule added to the scrubber must automatically start guarding the
repository too, or the guard drifts behind the thing it guards.

``IPV4`` is excluded from the file scan and only that label. A four-part
version string is indistinguishable from a dotted quad by pattern, and a
source tree is full of version strings. The exclusion is scoped to file
scanning; :func:`lanternlight.redact.assert_clean` on log text still enforces
it.

The directory walk deliberately mirrors ``tests/test_ascii_hygiene.py`` rather
than importing it, so that neither guard can be disabled by breaking the
other.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _tracked  # noqa: E402  (sits beside this file in tests/)

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    ALL_LABELS,
    FILE_SCAN_LABELS,
    iter_sensitive,
)

MIN_EXPECTED_FILES = _tracked.MIN_EXPECTED_FILES


def iter_text_files(root: Path = REPO_ROOT):
    """Yield every authored text file that would be published from ``root``.

    Delegates to :mod:`tests._tracked` - one walker, shared with the ASCII
    guard, so the two cannot drift apart. It asks git what is tracked rather
    than filtering on extensions, which is what let LICENSE, NOTICE and the
    dotfiles escape this scan entirely.
    """
    return _tracked.iter_authored_files(root)


def _scan(path: Path):
    """Return formatted findings for one file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return [f"{path}: unreadable ({exc})"]

    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = str(path)

    findings = []
    for label, matched, offset in iter_sensitive(text, labels=FILE_SCAN_LABELS):
        line_no = text.count("\n", 0, offset) + 1
        findings.append(f"{rel}:{line_no} {label} -> {matched!r}")
    return findings


def test_no_identifiers_anywhere_in_the_repository():
    files = list(iter_text_files())
    assert len(files) >= MIN_EXPECTED_FILES, (
        "the PII walker found "
        f"{len(files)} candidate files under {REPO_ROOT}, which is too few to "
        "be a real scan - a guard that scans nothing passes forever"
    )

    findings = []
    for path in files:
        findings.extend(_scan(path))

    assert not findings, (
        f"{len(findings)} potential identifier(s) found in the tree. Run the "
        "text through lanternlight.redact.redact() before committing it, and "
        "remember that deleting the file later does not remove it from git "
        "history.\n" + "\n".join(findings)
    )


def test_the_scanner_would_actually_catch_a_leak():
    # A guard that cannot fail is not a guard. Prove the detectors fire on a
    # synthetic leak before trusting the clean result above. Both fragments
    # are assembled at runtime so this file does not itself contain the shape
    # it is testing for.
    leak = "player " + "76561190" + "000000042" + " connected"
    labels = {label for label, _, _ in iter_sensitive(leak, labels=FILE_SCAN_LABELS)}
    assert "STEAMID64" in labels

    hex_leak = "puid " + "0f1e2d3c4b5a6978" + "8796a5b4c3d2e1f0"
    hex_labels = {
        label for label, _, _ in iter_sensitive(hex_leak, labels=FILE_SCAN_LABELS)
    }
    assert "PRODUCTUSERID" in hex_labels

    keyed_leak = "AccountName" + "=" + "someone_real"
    keyed_labels = {
        label for label, _, _ in iter_sensitive(keyed_leak, labels=FILE_SCAN_LABELS)
    }
    assert "ACCOUNT_NAME" in keyed_labels


def test_scanner_reaches_its_own_file():
    here = Path(__file__).resolve()
    assert here in {p.resolve() for p in iter_text_files()}


def test_ipv4_is_the_only_label_excluded_from_the_file_scan():
    assert sorted(ALL_LABELS - FILE_SCAN_LABELS) == ["IPV4"]
