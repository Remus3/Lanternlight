"""Last line of defence before a public push: no identifiers in the tree.

The Mistfall Hunter log this project reads carries the operator's SteamID64,
Steam persona name, platform account ids, an Epic ProductUserId and an
IP-resolved location. Lanternlight is a public repository. A single pasted log
line in a fixture, a docstring or a bug report would publish those
permanently, because git history keeps them after the file is deleted.

So this test scans every published file in the repository with
:mod:`lanternlight.redact`'s own detectors and fails if any of them fire. It
uses the redactor's rules rather than a private copy of the patterns on
purpose: a rule added to the scrubber must automatically start guarding the
repository too, or the guard drifts behind the thing it guards.

Two passes, because there are two ways to carry an identifier:

1. **Plain.** :func:`lanternlight.redact.iter_sensitive` over the file as
   bytes.
2. **Encoded.** :func:`lanternlight.redact.iter_encoded_sensitive` over the
   same bytes, which decodes base64 and hex runs and scans what comes out.
   Encoding is not redaction, and before this pass existed a base64 blob
   defeated every detector in the module at once.

Both passes walk :func:`tests._tracked.iter_scannable_files` - **every**
published file, binaries included. The ASCII guard cannot say anything useful
about a PNG, but a PNG is exactly where an identifier hides best, and a file
this guard refuses to open is a file it cannot testify about. "Nothing found"
and "nothing looked" are different facts.

``IPV4`` is excluded from the file scan and only that label. A four-part
version string is indistinguishable from a dotted quad by pattern, and a
source tree is full of version strings. The exclusion is scoped to file
scanning; :func:`lanternlight.redact.assert_clean` on log text still enforces
it.

The directory walk deliberately mirrors ``tests/test_ascii_hygiene.py`` rather
than importing it, so that neither guard can be disabled by breaking the
other.
"""

import base64
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _tracked  # noqa: E402  (sits beside this file in tests/)

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    ALL_LABELS,
    FILE_SCAN_LABELS,
    iter_encoded_sensitive,
    iter_sensitive,
)

MIN_EXPECTED_FILES = _tracked.MIN_EXPECTED_FILES


def iter_scannable_files(root: Path = REPO_ROOT):
    """Yield every published file, binaries included.

    Wider than the ASCII guard's walker on purpose - see
    :func:`tests._tracked.iter_scannable_files` for why a binary is scanned
    rather than skipped.
    """
    return _tracked.iter_scannable_files(root)


#: Kept as the ASCII guard's view of the tree, for the tests below that pin
#: the difference between the two.
iter_text_files = _tracked.iter_authored_files


def _read(path: Path) -> str | None:
    """Return the file as latin-1 text, or None if it cannot be read.

    latin-1 rather than utf-8-with-replace: a scanned file may be a binary, and
    ``replace`` fuses invalid byte sequences into a single U+FFFD, which
    silently destroys the runs being looked for and shifts every offset after
    it. latin-1 is total and length-preserving, so an offset is a byte offset.
    """
    try:
        return path.read_bytes().decode("latin-1")
    except OSError:
        return None


def _relative(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _scan(path: Path):
    """Return formatted findings for one file, reading it as written."""
    text = _read(path)
    if text is None:
        return [f"{_relative(path)}: unreadable"]

    rel = _relative(path)
    findings = []
    for label, matched, offset in iter_sensitive(text, labels=FILE_SCAN_LABELS):
        line_no = text.count("\n", 0, offset) + 1
        findings.append(f"{rel}:{line_no} {label} -> {matched!r}")
    return findings


def _scan_encoded(path: Path):
    """Return findings for identifiers hidden inside encoded runs in one file.

    The description never quotes the decoded value. This message can land in CI
    output, and echoing the identifier at the moment the guard fires would
    publish the thing the guard exists to protect.
    """
    text = _read(path)
    if text is None:
        return [f"{_relative(path)}: unreadable"]

    rel = _relative(path)
    findings = []
    for label, description, offset in iter_encoded_sensitive(text, labels=FILE_SCAN_LABELS):
        line_no = text.count("\n", 0, offset) + 1
        findings.append(f"{rel}:{line_no} (byte {offset}) {label} in {description}")
    return findings


def _scan_tree(scan):
    """Run one scanner over every published file.

    Returns ``(findings, scanned_count)``. Both repository tests go through
    here, and so does the end-to-end proof below, so a short circuit anywhere
    in walk-read-scan shows up as a red test rather than as a clean tree.
    """
    findings = []
    scanned = 0
    for path in iter_scannable_files():
        scanned += 1
        findings.extend(scan(path))
    return findings, scanned


def _assert_scanned_enough(scanned: int) -> None:
    # Count what the LOOP touched, not what the walker offered. A scan of
    # nothing produces no findings and looks exactly like a clean tree.
    assert scanned >= MIN_EXPECTED_FILES, (
        f"only {scanned} file(s) were actually scanned under {REPO_ROOT} - "
        "a guard that scans nothing passes forever"
    )


def test_no_identifiers_anywhere_in_the_repository():
    findings, scanned = _scan_tree(_scan)
    _assert_scanned_enough(scanned)

    assert not findings, (
        f"{len(findings)} potential identifier(s) found in the tree. Run the "
        "text through lanternlight.redact.redact() before committing it, and "
        "remember that deleting the file later does not remove it from git "
        "history.\n" + "\n".join(findings)
    )


def test_the_tree_scan_pipeline_flags_a_planted_file():
    """End-to-end proof that both repository scans are live.

    A clean tree and a broken pipeline return the same empty list, so the
    clean results above mean nothing on their own. Mutation testing found
    exactly that: emptying a scan loop left the guard green, because the
    file-count floor measures the walker rather than the loop.

    So this plants two probes in the working tree - one raw identifier inside a
    binary suffix, one base64-encoded - runs the SAME pipeline the guards use,
    and requires both to be flagged. Every identifier is invented and assembled
    at runtime, and both probes are removed in ``finally``.
    """
    fake_id = "76561190" + "000000042"
    binary_probe = REPO_ROOT / "_pipeline_probe_binary.png"
    encoded_probe = REPO_ROOT / "_pipeline_probe_encoded.b64"
    try:
        binary_probe.write_bytes(b"\x89PNG\r\n\x1a\n" + fake_id.encode("ascii") + b"\x00\xff")
        encoded_probe.write_bytes(
            base64.b64encode(("role " + fake_id + " end").encode("ascii")) + b"\n"
        )

        plain_findings, plain_scanned = _scan_tree(_scan)
        encoded_findings, encoded_scanned = _scan_tree(_scan_encoded)

        _assert_scanned_enough(plain_scanned)
        _assert_scanned_enough(encoded_scanned)

        assert any("_pipeline_probe_binary.png" in f for f in plain_findings), (
            "the plain pipeline missed a raw identifier planted in a binary. "
            f"findings: {plain_findings}"
        )
        assert any("_pipeline_probe_encoded.b64" in f for f in encoded_findings), (
            "the encoded pipeline missed a base64-encoded identifier. "
            f"findings: {encoded_findings}"
        )
    finally:
        binary_probe.unlink(missing_ok=True)
        encoded_probe.unlink(missing_ok=True)


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


def test_the_scanner_sees_through_base64():
    # The hole this closes, measured before it was closed: every detector in
    # lanternlight.redact works on plain text, so one base64 pass defeats all
    # of them at once. `.gitignore` blocks `*.sav`, which means the pressure to
    # commit an ENCODED copy of a binary the game wrote is permanent, and the
    # guard could not see into one at all.
    #
    # Assembled at runtime, like every other planted identifier in this file,
    # so the file does not itself carry the shape it tests for.
    planted = "player " + "76561190" + "000000042" + " connected"
    plain = {label for label, _, _ in iter_sensitive(planted, labels=FILE_SCAN_LABELS)}
    assert "STEAMID64" in plain, "the plain-text detector must fire, or this proves nothing"

    encoded = base64.b64encode(planted.encode("ascii")).decode("ascii")
    assert not list(iter_sensitive(encoded, labels=FILE_SCAN_LABELS)), (
        "the plain scan is expected to be blind here - that is the defect"
    )

    found = {label for label, _, _ in iter_encoded_sensitive(encoded, labels=FILE_SCAN_LABELS)}
    assert "STEAMID64" in found, (
        "a base64-encoded SteamID64 must be caught. Encoding is not redaction."
    )


def test_the_repository_carries_no_encoded_identifiers():
    findings, scanned = _scan_tree(_scan_encoded)
    _assert_scanned_enough(scanned)

    assert not findings, (
        f"{len(findings)} identifier(s) found inside encoded content in the "
        "tree. Base64 and hex are transport encodings, not redaction - redact "
        "the bytes before encoding them, and remember that deleting the file "
        "later does not remove it from git history.\n" + "\n".join(findings)
    )


def test_scanner_reaches_its_own_file():
    here = Path(__file__).resolve()
    assert here in {p.resolve() for p in iter_scannable_files()}


def test_the_pii_scan_is_wider_than_the_ascii_scan():
    # Pins the split rather than leaving it to be rediscovered. The ASCII guard
    # must skip binaries; this guard must not, because a binary is where an
    # identifier hides best and `.gitignore` blocking `*.sav` is exactly the
    # pressure that produces a committed encoded or renamed copy.
    scannable = {p.resolve() for p in iter_scannable_files()}
    authored = {p.resolve() for p in iter_text_files()}
    assert authored <= scannable


def test_ipv4_is_the_only_label_excluded_from_the_file_scan():
    assert sorted(ALL_LABELS - FILE_SCAN_LABELS) == ["IPV4"]
