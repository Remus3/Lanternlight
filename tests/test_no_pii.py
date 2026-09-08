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
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _tracked  # noqa: E402  (sits beside this file in tests/)

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    ALL_LABELS,
    FILE_SCAN_LABELS,
    OPERATOR_IDENTIFIER_LABELS,
    RedactionError,
    assert_no_operator_identifier,
    iter_encoded_sensitive,
    iter_operator_identifiers,
    iter_sensitive,
    operator_git_identities,
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
    binary_probe = _tracked.probe_path("pipeline_binary.png")
    encoded_probe = _tracked.probe_path("pipeline_encoded.b64")
    try:
        binary_probe.write_bytes(b"\x89PNG\r\n\x1a\n" + fake_id.encode("ascii") + b"\x00\xff")
        encoded_probe.write_bytes(
            base64.b64encode(("role " + fake_id + " end").encode("ascii")) + b"\n"
        )

        plain_findings, plain_scanned = _scan_tree(_scan)
        encoded_findings, encoded_scanned = _scan_tree(_scan_encoded)

        _assert_scanned_enough(plain_scanned)
        _assert_scanned_enough(encoded_scanned)

        assert any(binary_probe.name in f for f in plain_findings), (
            "the plain pipeline missed a raw identifier planted in a binary. "
            f"findings: {plain_findings}"
        )
        assert any(encoded_probe.name in f for f in encoded_findings), (
            "the encoded pipeline missed a base64-encoded identifier. "
            f"findings: {encoded_findings}"
        )
    finally:
        binary_probe.unlink(missing_ok=True)
        encoded_probe.unlink(missing_ok=True)


def test_the_tree_scan_pipeline_flags_a_raw_utf16_binary():
    """The raw wide-character case, end to end through the real walker.

    Measured gap before this existed: a UTF-16 identifier inside a base64 blob
    was caught, and the same identifier written RAW into a file was not. The
    NUL-stripped reading only ever ran on decoded bytes, one layer down, so it
    never saw a file's own content. That is the wrong way round for this
    project - the game's saves are raw UTF-16 on disk, so the raw case is the
    likely accident and the encoded one is the exotic one.

    A ``.bin`` suffix on purpose: nothing in the tree recognises it, so the
    only reason this probe is opened at all is that the PII walker refuses to
    skip binaries.
    """
    fake_id = "76561190" + "000000042"
    probe = _tracked.probe_path("pipeline_utf16.bin")
    try:
        # Split so this source file does not itself carry a literal key=value
        # secret shape - the scanner cannot tell an invented id from a real one.
        keyed = "steam" + "Id" + "=" + fake_id
        probe.write_bytes(keyed.encode("utf-16-le"))

        plain_findings, _ = _scan_tree(_scan)
        encoded_findings, encoded_scanned = _scan_tree(_scan_encoded)
        _assert_scanned_enough(encoded_scanned)

        assert not any(probe.name in f for f in plain_findings), (
            "the plain pass is expected to be blind to raw UTF-16 - that is why "
            "the wide reading has to exist"
        )
        assert any(probe.name in f for f in encoded_findings), (
            "a raw UTF-16 identifier in a published file must be flagged. "
            f"findings: {encoded_findings}"
        )
    finally:
        probe.unlink(missing_ok=True)


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


# --------------------------------------------------------------------------
# OPS-50 - an OPERATOR IDENTIFIER, whatever command produced it
# --------------------------------------------------------------------------
#
# Everything above this line guards identifiers the GAME LOG carries. On
# 2026-09-07 this project quoted the raw output of a git log format string -
# the operator's own email address - into a note delivered to four sibling
# directories, and every test in this file passed throughout, because the
# string did not come out of a log parser. A rule scoped to a SOURCE is a rule
# with a hole in it; the data it protects is a CLASS.
#
# Two mechanisms, and neither one subsumes the other:
#
#   - the EMAIL rule, which is a SHAPE and therefore reaches an address this
#     machine has never seen, including one belonging to somebody else;
#   - the runtime git identity, which is a VALUE and therefore reaches the
#     operator's own address even in a shape the rule declines.
#
# No test in this file contains the operator's address as a literal. That would
# be the same leak one level down, and a tracked literal is exactly what git
# history keeps forever. The value half is derived at runtime; the shape half
# is exercised with addresses invented here.


def _scan_operator(path: Path, identities=None):
    """Return operator-identifier findings for one file.

    The finding never quotes the match. This message can reach CI output, and
    echoing the address at the moment the guard fires publishes the thing the
    guard exists to protect.
    """
    text = _read(path)
    if text is None:
        return [f"{_relative(path)}: unreadable"]

    rel = _relative(path)
    findings = []
    for label, matched, offset in iter_operator_identifiers(text, identities=identities):
        line_no = text.count("\n", 0, offset) + 1
        findings.append(
            f"{rel}:{line_no} {label} -> a {len(matched)}-character operator "
            "identifier, not quoted here because this message travels"
        )
    return findings


def test_the_email_label_is_scanned_over_the_tree_like_every_other():
    # EMAIL must not become a second IPV4. The exclusion test above already
    # pins that IPV4 is the only label held back; this states the intent
    # positively, so a future edit has to argue with both.
    assert "EMAIL" in ALL_LABELS
    assert "EMAIL" in FILE_SCAN_LABELS
    assert OPERATOR_IDENTIFIER_LABELS <= FILE_SCAN_LABELS


def test_the_email_rule_fires_on_an_ordinary_address():
    # Assembled at runtime, like every other planted identifier in this file.
    leak = "reply to " + "a.person" + "@" + "somecompany" + ".com" + " today"
    labels = {label for label, _, _ in iter_sensitive(leak, labels=FILE_SCAN_LABELS)}
    assert "EMAIL" in labels


def test_the_email_rule_declines_a_reserved_documentation_domain():
    # RFC 2606 and RFC 6761 reserve these precisely so a document can carry an
    # address that identifies nobody. This tree uses them in test fixtures and
    # in the hook probe's git config; a guard that reddened on those would be
    # switched off within a day, which is the failure that costs the most.
    for domain in (
        "example.invalid",
        "example.com",
        "example.net",
        "example.org",
        "somewhere.test",
        "anything.example",
        "box.localhost",
    ):
        text = "probe" + "@" + domain
        labels = {label for label, _, _ in iter_sensitive(text, labels=FILE_SCAN_LABELS)}
        assert "EMAIL" not in labels, f"{domain} must be treated as documentation"


def test_the_operator_git_identity_is_derived_at_runtime_and_is_address_shaped():
    # The identity is DERIVED, never stored. A literal here would be the leak.
    identities = operator_git_identities()
    assert identities, (
        "no git identity could be derived, so the value half of this guard is "
        "inert - and an inert guard passes forever"
    )
    for value in identities:
        local, _, domain = value.partition("@")
        assert local and "." in domain, "a derived identity must be address-shaped"


def test_the_value_half_reaches_what_the_shape_half_declines():
    # This is the whole reason both mechanisms exist. A reserved-domain address
    # is invisible to the EMAIL rule by design - and if it were the operator's
    # own, the value half must still catch it.
    disguised = "someone" + "@" + "example" + ".invalid"
    assert "EMAIL" not in {
        label for label, _, _ in iter_sensitive(disguised, labels=FILE_SCAN_LABELS)
    }
    hits = list(
        iter_operator_identifiers(
            "git log --format said " + disguised, identities=(disguised,)
        )
    )
    assert [label for label, _, _ in hits] == ["GIT_IDENTITY"]


def test_one_address_is_reported_once_and_not_twice():
    # Both mechanisms match an ordinary address. A finding reported twice makes
    # a count meaningless, and a count is what a sweep reports.
    address = "dup" + "@" + "somecompany" + ".com"
    labels = [
        label
        for label, _, _ in iter_operator_identifiers(
            "see " + address, identities=(address,)
        )
    ]
    assert labels == ["EMAIL"]


def test_the_refusal_never_quotes_the_address_it_found():
    # The message travels - into CI output, a bug report, a sibling's inbox.
    address = "quoted" + "@" + "somecompany" + ".com"
    with pytest.raises(RedactionError) as excinfo:
        assert_no_operator_identifier("mail " + address, identities=(address,))
    assert address not in str(excinfo.value)
    assert "somecompany" not in str(excinfo.value)


def test_the_repository_carries_no_operator_identifier():
    findings, scanned = _scan_tree(_scan_operator)
    _assert_scanned_enough(scanned)

    assert not findings, (
        f"{len(findings)} operator identifier(s) found in the tree. An email "
        "address is redactable whatever command produced it - see ROADMAP "
        "OPS-50 and ledger LL-0170.\n" + "\n".join(findings)
    )


def test_the_operator_identifier_scan_flags_a_planted_file():
    """End-to-end proof through the real walker, with an invented address.

    A clean tree and a broken pipeline return the same empty list. This plants
    an address at the repository root, runs the SAME walk the guard above runs,
    and requires it to be flagged. The address is invented and assembled at
    runtime; the operator's own is never written to disk by this suite.
    """
    planted = "maintainer" + "@" + "lanternlight-probe" + ".com"
    probe = _tracked.probe_path("operator_identifier.md")
    try:
        probe.write_text("contact " + planted + "\n", encoding="ascii")
        findings, scanned = _scan_tree(_scan_operator)
        _assert_scanned_enough(scanned)
        assert any(probe.name in f for f in findings), (
            "the operator-identifier pipeline missed a planted address. "
            f"findings: {findings}"
        )
    finally:
        probe.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# refusal by PATH - .githooks/pre-commit
# --------------------------------------------------------------------------
#
# The content scan above is the net. The hook is the fence, and the two guard
# different failures: the scan cannot tell a reviewed fixture from a raw dump,
# and the hook cannot see inside a file at all.
#
# The gap these pin, found on 2026-08-09: `.gitignore` blocks `*.sav`, so the
# standing pressure is to commit an ENCODED copy of the same bytes, and neither
# fence had anything to say about `save.sav.b64`. Nor about `dump.gvas.b64` -
# the same file under a name that mentions no save at all.
#
# Location, not extension, is what separates a reviewed fixture from a raw
# dump, because the extension is exactly the thing an accident renames. So an
# encoded blob is permitted under `tests/fixtures/` - where the content scan
# above covers it and a human reviewed it - and refused everywhere else.
#
# Every assertion below runs a REAL `git commit` against a throwaway repository
# wired to this repository's real hook, and checks HEAD afterwards. A hook that
# merely exists is not a hook that fires: `core.hooksPath` is local config that
# is never cloned, so proving the file is on disk proves nothing at all.

HOOKS_DIR = REPO_ROOT / ".githooks"

#: Shapes the hook must refuse ANYWHERE, including under tests/fixtures/. These
#: name the game's own files, so there is no reviewed-fixture case for them.
REFUSED_ANYWHERE = (
    "probe.sav",
    "probe.sav.b64",
    "probe.sav.base64",
    "probe.sav.hex",
    "probe.sav.txt",
    "probe.sav.gz",
    "probe.sav.zip",
    "probe.log",
    "probe.log.b64",
    "probe.log.base64",
    "probe.log.hex",
    "probe.log.gz",
    # Inside the reviewed-fixture tree too. The carve-out below is for blobs
    # under a neutral name; a path that says "save" or "log" gets no carve-out
    # anywhere. Mutation testing is why these are here: without the
    # tests/fixtures/ cases, deleting the log branch from the hook left every
    # assertion green, because outside the fixture tree the generic
    # encoded-blob branch catches the same paths anyway.
    "tests/fixtures/probe.sav.b64",
    "tests/fixtures/gvas/probe.sav.b64",
    "tests/fixtures/probe.log.b64",
    "tests/fixtures/probe.log.base64",
    "tests/fixtures/probe.log.hex",
    "tests/fixtures/gvas/probe.log.gz",
)

#: Encoded or derived blobs under a name that mentions no save at all. Refused
#: outside tests/fixtures/, permitted inside it.
REFUSED_OUTSIDE_FIXTURES = (
    "probe.gvas",
    "probe.gvas.b64",
    "docs/probe.gvas.b64",
    "probe.b64",
    "ops/probe.base64",
    "probe.hex",
    "probe.gz",
    "probe.zip",
)

#: The reviewed-fixture case. Blocking these would be a broken rule, not a
#: strict one - they are already committed and hand-verified.
PERMITTED_FIXTURES = (
    "tests/fixtures/gvas/probe.gvas.b64",
    "tests/fixtures/gvas/probe.b64",
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
        check=False,
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture(scope="module")
def hooked_repo(tmp_path_factory) -> Path:
    """A throwaway repository wired to this repository's real pre-commit hook.

    Throwaway rather than the real checkout on purpose: a probe commit that
    slipped through would land in real history, which is the one accident this
    whole module exists to prevent.
    """
    repo = tmp_path_factory.mktemp("hookprobe")
    assert _git(repo, "init", "-q").returncode == 0, "git init failed"
    for key, value in (
        ("user.email", "probe@example.invalid"),
        ("user.name", "hook probe"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", HOOKS_DIR.as_posix()),
    ):
        assert _git(repo, "config", key, value).returncode == 0, f"git config {key}"

    (repo / "README.md").write_text("probe repository\n", encoding="ascii")
    assert _git(repo, "add", "README.md").returncode == 0
    first = _git(repo, "commit", "-m", "probe: initial")
    assert first.returncode == 0, (
        "the hook refused an innocent commit, so every refusal below would be "
        f"meaningless.\nstdout: {first.stdout}\nstderr: {first.stderr}"
    )
    assert _head(repo), "no HEAD after the initial commit"
    return repo


def _attempt_commit(repo: Path, relpath: str, payload: bytes = b"probe\n"):
    """Stage ``relpath`` and attempt a real commit. Returns the git result."""
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    added = _git(repo, "add", "-f", "--", relpath)
    assert added.returncode == 0, f"could not stage {relpath}: {added.stderr}"
    try:
        return _git(repo, "commit", "-m", "probe: attempt")
    finally:
        _git(repo, "reset", "-q", "--", relpath)
        target.unlink(missing_ok=True)


@pytest.mark.slow
def test_the_hook_is_actually_wired_in_the_probe_repository(hooked_repo):
    # Everything below is meaningless if the hook is not running. Prove it
    # fires by tripping a rule that predates this section entirely.
    before = _head(hooked_repo)
    result = _attempt_commit(hooked_repo, "logs/anything.txt")
    assert result.returncode != 0, "the hook did not fire at all"
    assert _head(hooked_repo) == before


@pytest.mark.parametrize("relpath", REFUSED_ANYWHERE)
@pytest.mark.slow
def test_the_hook_refuses_a_save_or_log_shape_anywhere(hooked_repo, relpath):
    before = _head(hooked_repo)
    result = _attempt_commit(hooked_repo, relpath)
    assert result.returncode != 0, (
        f"{relpath} was committed. stdout: {result.stdout}"
    )
    assert "BLOCKED" in result.stderr, result.stderr
    assert _head(hooked_repo) == before, f"HEAD moved after staging {relpath}"


@pytest.mark.parametrize("relpath", REFUSED_OUTSIDE_FIXTURES)
@pytest.mark.slow
def test_the_hook_refuses_an_encoded_blob_outside_the_fixture_tree(
    hooked_repo, relpath
):
    before = _head(hooked_repo)
    result = _attempt_commit(hooked_repo, relpath)
    assert result.returncode != 0, (
        f"{relpath} was committed. stdout: {result.stdout}"
    )
    assert "BLOCKED" in result.stderr, result.stderr
    assert _head(hooked_repo) == before, f"HEAD moved after staging {relpath}"


@pytest.mark.parametrize("relpath", PERMITTED_FIXTURES)
@pytest.mark.slow
def test_the_hook_permits_a_reviewed_fixture(hooked_repo, relpath):
    # The specific regression to avoid. A rule that blocks the reviewed
    # fixtures is a broken rule, not a strict one.
    before = _head(hooked_repo)
    result = _attempt_commit(hooked_repo, relpath, payload=b"cGFkZGluZw==\n")
    assert result.returncode == 0, (
        f"{relpath} was refused, which breaks the reviewed-fixture tree.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert _head(hooked_repo) != before
    _git(hooked_repo, "rm", "-q", "-f", "--", relpath)
    _git(hooked_repo, "commit", "-q", "-m", "probe: cleanup")


@pytest.mark.slow
def test_the_hook_still_permits_the_existing_gvas_fixtures(hooked_repo):
    """The committed fixtures, byte for byte, must still be committable.

    Reads the real files rather than a stand-in. A stand-in proves the pattern
    the test author had in mind, not the paths that are actually in the tree.
    """
    fixtures = sorted((REPO_ROOT / "tests" / "fixtures" / "gvas").glob("*.gvas.b64"))
    assert fixtures, "no gvas fixtures found - this test has stopped testing anything"
    for fixture in fixtures:
        rel = fixture.relative_to(REPO_ROOT).as_posix()
        before = _head(hooked_repo)
        result = _attempt_commit(hooked_repo, rel, payload=fixture.read_bytes())
        assert result.returncode == 0, (
            f"{rel} would now be refused by the hook.\nstderr: {result.stderr}"
        )
        assert _head(hooked_repo) != before
        _git(hooked_repo, "rm", "-q", "-f", "--", rel)
        _git(hooked_repo, "commit", "-q", "-m", "probe: cleanup")


@pytest.mark.slow
def test_the_hook_still_refuses_non_ascii_in_authored_text(hooked_repo):
    # An existing rule, pinned here so a path-rule edit cannot quietly drop it.
    before = _head(hooked_repo)
    result = _attempt_commit(
        hooked_repo, "docs/probe.md", payload=("dash " + chr(0x2014) + "\n").encode("utf-8")
    )
    assert result.returncode != 0, result.stdout
    assert _head(hooked_repo) == before


@pytest.mark.slow
def test_the_hook_still_permits_an_ordinary_source_file(hooked_repo):
    # The other half of the same claim. A guard that refuses everything is not
    # a guard, it is an outage.
    before = _head(hooked_repo)
    result = _attempt_commit(hooked_repo, "ops/probe_ordinary.py", payload=b"x = 1\n")
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert _head(hooked_repo) != before
    _git(hooked_repo, "rm", "-q", "-f", "--", "ops/probe_ordinary.py")
    _git(hooked_repo, "commit", "-q", "-m", "probe: cleanup")


@pytest.mark.slow
def test_the_hook_scripts_carry_no_carriage_return():
    # Git for Windows runs these through sh, which chokes on a CR in the
    # shebang. `.gitattributes` says eol=lf; this checks the bytes on disk,
    # because an attribute is a claim and the file is the fact.
    for name in ("pre-commit", "commit-msg"):
        raw = (HOOKS_DIR / name).read_bytes()
        assert b"\r" not in raw, f".githooks/{name} contains a CR"
