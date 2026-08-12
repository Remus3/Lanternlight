"""The guard that keeps a GVAS fixture an authored artifact, not a raw dump.

Why this file exists
--------------------

Three of the fixtures under ``tests/fixtures/gvas/`` were, for one commit,
**byte-identical to the operator's live save files** - confirmed by sha256. They
were scanned and were clean, and that is exactly the trap: "clean today" is a
statement about the shapes ``lanternlight.redact`` currently knows, not about
the bytes. A raw dump of a live save publishes every field the game writes,
including the ones nobody has decoded yet, on the assumption that the decoded
ones are the only ones that matter. A fixture exists to pin a **format**, so
every value in it should be one this repository chose.

So the rule is mechanical rather than judgemental: no committed fixture may be
byte-identical to any file the game currently has in its save directory. That
catches a re-copied fixture on the machine that has the game, which is the only
machine where the mistake can be made.

What this file must never do
----------------------------

**Never write a live save's hash into the repository.** A committed sha256 of
the operator's ``UserSettings_v1.sav`` is a fingerprint of their machine that
survives deletion in git history, and it would go stale the first time they
changed a graphics setting - so it would be a stale fingerprint. Every hash here
is computed at runtime and thrown away.

Enumerate, never assume
-----------------------

``Deck.sav`` did not exist when the reader was written; it appeared mid-session
and made a five-file save set into a six-file one. Both sides of every check
below therefore walk a directory: the fixture set is whatever is on disk under
``tests/fixtures/gvas/``, and the live set is whatever is in the game's save
directory. A test that hard-codes either list stops covering the surface the
moment the game writes something new, and it does so silently.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402  (path bootstrap must run first)

from lanternlight import paths  # noqa: E402
from lanternlight.gvas import parse  # noqa: E402
from lanternlight.redact import ALL_LABELS, iter_sensitive  # noqa: E402

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "gvas"

#: The suffix every committed fixture carries. Base64 rather than raw bytes so
#: the ASCII and PII guards can walk it as text; see ``tests/test_gvas.py``.
FIXTURE_SUFFIX = ".gvas.b64"


def fixture_files() -> list[Path]:
    """Every committed fixture, enumerated from disk rather than listed.

    Sorted so parametrisation ids are stable, and non-empty by construction:
    an empty fixture directory would make every check below vacuously true, so
    it is a failure rather than a quiet pass.
    """
    found = sorted(p for p in FIXTURE_DIR.iterdir() if p.is_file())
    assert found, f"no fixtures under {FIXTURE_DIR}, so every check here is vacuous"
    return found


def fixture_base64(path: Path) -> str:
    """Return one fixture's base64 with its line wrapping removed.

    The files are wrapped at 76 columns, so the newlines have to come out
    before ``validate=True`` will look at the payload - and ``validate=True``
    is the point: without it ``b64decode`` silently discards anything that is
    not base64, and a fixture that quietly loses bytes on decode pins a format
    nobody has.
    """
    return "".join(path.read_text(encoding="ascii").split())


def fixture_bytes(path: Path) -> bytes:
    """Decode one fixture back into the bytes the engine would have written."""
    return base64.b64decode(fixture_base64(path), validate=True)


def _live_save_hashes() -> dict[str, str]:
    """Map sha256 to filename for every file in the game's save directory.

    Computed at runtime and never persisted - see the module docstring.

    Skips rather than passes when there is nothing to compare against, because
    "this machine has no game installed" is a different fact from "the fixtures
    are not copies". The skip is deliberately narrow: it fires only when the
    directory is absent or empty, so a machine that *does* have the game runs
    the real comparison and cannot be quietened by it.
    """
    directory = paths.save_games_dir()
    if not directory.is_dir():
        pytest.skip(f"no save directory at {directory}; nothing to compare against")
    files = [p for p in sorted(directory.iterdir()) if p.is_file()]
    if not files:
        pytest.skip(f"{directory} holds no save files; nothing to compare against")
    return {hashlib.sha256(p.read_bytes()).hexdigest(): p.name for p in files}


def _collides(fixtures: list[Path], live: dict[str, str]) -> list[str]:
    """Return the name of each fixture that is a byte-for-byte live save.

    The live file's own name is deliberately **not** in the message. The game
    names one save ``CampData_<19-digit userId>.sav``, this repository is
    public, and a pasted pytest failure is a plausible way for that id to get
    out. The fixture name is what the reader has to act on anyway.
    """
    return [
        fixture.name
        for fixture in fixtures
        if hashlib.sha256(fixture_bytes(fixture)).hexdigest() in live
    ]


# --------------------------------------------------------------------------
# the rule
# --------------------------------------------------------------------------


def test_no_fixture_is_a_copy_of_a_live_save():
    # One test over the whole set rather than one per fixture, because the live
    # side is enumerated too: a new .sav appearing has to be compared against
    # every fixture, not only against the one somebody remembered to register.
    collisions = _collides(fixture_files(), _live_save_hashes())
    assert not collisions, (
        "these fixtures are raw dumps of a file in the game's save directory: "
        + ", ".join(collisions)
        + ". Splice authored values over the machine-specific ones and patch the "
        "enclosing Size, as tests/test_gvas.py documents. Deleting the file later "
        "will not remove those bytes from git history."
    )


def test_the_copy_check_would_catch_a_copy(tmp_path: Path):
    # A guard that cannot fail is decoration. Build the mistake this file
    # exists to prevent - a fixture encoded straight from a live save - in a
    # temporary directory, and prove the same helper reports it. Nothing is
    # written into the repository and no hash outlives the test.
    live = _live_save_hashes()
    directory = paths.save_games_dir()
    source = next(p for p in sorted(directory.iterdir()) if p.is_file())

    planted = tmp_path / f"planted{FIXTURE_SUFFIX}"
    planted.write_bytes(base64.encodebytes(source.read_bytes()))

    assert _collides([planted], live) == [f"planted{FIXTURE_SUFFIX}"]


def test_a_sanitised_fixture_is_not_reported_as_a_copy(tmp_path: Path):
    # The other half of the same proof: the check has to distinguish, not just
    # fire. One flipped byte in the value region is enough to change the digest.
    live = _live_save_hashes()
    directory = paths.save_games_dir()
    source = next(p for p in sorted(directory.iterdir()) if p.is_file())

    mutated = bytearray(source.read_bytes())
    mutated[-1] ^= 0xFF
    planted = tmp_path / f"planted{FIXTURE_SUFFIX}"
    planted.write_bytes(base64.encodebytes(bytes(mutated)))

    assert _collides([planted], live) == []


def test_no_fixture_filename_carries_an_identifier_a_live_filename_carries():
    # The game names one save CampData_<19-digit userId>.sav, so content
    # sanitisation alone would still have published that id in the directory
    # listing. Both sides are enumerated: whatever identifier the game puts in
    # a filename today is what the fixture names are checked against, rather
    # than the one shape somebody remembered to hard-code.
    # Proven live first. If no save on this machine happened to carry an
    # identifier in its name, the loop below would range over nothing and pass
    # without testing anything - so assert the detector fires on the shape the
    # game is known to write. Assembled at runtime so this file never contains
    # a 19-digit id of its own.
    probe = "CampData_" + "1" * 19 + ".sav"
    assert [label for label, _, _ in iter_sensitive(probe, labels=ALL_LABELS)], (
        "no detector fires on a save filename carrying a 19-digit id, so the "
        "check below cannot catch the one leak it exists for"
    )

    leaked = []
    for live_name in _live_save_hashes().values():
        for label, matched, _offset in iter_sensitive(live_name, labels=ALL_LABELS):
            for fixture in fixture_files():
                if matched in fixture.name:
                    # The identifier itself is not repeated into the message.
                    leaked.append(f"{fixture.name} carries a {label} from a live filename")
    assert not leaked, "; ".join(leaked)


# --------------------------------------------------------------------------
# every fixture is still a fixture: it parses, and it parses whole
# --------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", fixture_files(), ids=lambda p: p.name)
def test_every_fixture_parses_with_nothing_left_over(fixture: Path):
    # Sanitising is a byte splice, and a splice that forgets to patch the
    # enclosing Size desynchronises the reader. Strict mode raises on an
    # unmeasured type; these three assertions catch the quieter failure where
    # the file still parses but no longer accounts for all of itself.
    save = parse(fixture_bytes(fixture))
    assert save.unknown_properties == ()
    assert save.is_complete
    assert save.undecoded_trailing == b""
    assert save.properties, f"{fixture.name} decodes to no properties at all"
    for profile in save.key_profiles:
        assert profile.unknown_properties == ()
        assert profile.is_complete


@pytest.mark.parametrize("fixture", fixture_files(), ids=lambda p: p.name)
def test_every_fixture_is_pure_ascii(fixture: Path):
    raw = fixture.read_bytes()
    assert b"\r" not in raw, f"{fixture.name} carries CRLF; the fixtures are LF"
    try:
        raw.decode("ascii")
    except UnicodeDecodeError as exc:  # pragma: no cover - the assert is the report
        pytest.fail(f"{fixture.name} is not 7-bit ASCII: {exc}")


@pytest.mark.parametrize("fixture", fixture_files(), ids=lambda p: p.name)
def test_every_fixture_is_valid_base64(fixture: Path):
    # validate=True, so a stray character is an error rather than being
    # silently discarded - a fixture that quietly loses bytes on decode would
    # pin a format nobody has.
    payload = fixture_base64(fixture)
    try:
        decoded = base64.b64decode(payload, validate=True)
    except binascii.Error as exc:  # pragma: no cover - the fail is the report
        pytest.fail(f"{fixture.name} is not valid base64: {exc}")
    assert decoded
    # Round-trips exactly, so the file carries no padding slop and no dropped
    # character that a lenient decode would have hidden.
    assert base64.b64encode(decoded).decode("ascii") == payload


#: How many consecutive zero bytes it takes to encode to a 32-character run of
#: ``A``. Base64 spends 4 characters on every 3 bytes, so 24 zero bytes become
#: 32 zero sextets, and the character for a zero sextet is ``A``.
_ZEROS_PER_HEX32_RUN = 24


@pytest.mark.parametrize("fixture", fixture_files(), ids=lambda p: p.name)
def test_no_fixture_encodes_a_long_run_of_zero_bytes(fixture: Path):
    """A trap that belongs to base64 rather than to any save.

    ``A`` is a hexadecimal digit, so 24 consecutive zero bytes encode to a
    32-character hex run - which is exactly the shape ``PRODUCTUSERID`` is, and
    the repository's plain scan reads a committed fixture as TEXT before it
    reads it as an encoding. The result is a red tree scan pointing at a file
    whose decoded bytes are provably clean, with nothing in the message to
    suggest that the finding is an artifact of the encoding.

    Measured while building ``standalone_slot.gvas.b64``: three native
    ``Vector`` payloads in the game's transient save are entirely zero, and the
    builder authors them for this reason and no other. This check states the
    constraint for the next fixture rather than leaving it to be rediscovered
    from a confusing failure.

    Stated rather than hidden: whether a given run actually MATCHES also depends
    on its alignment and on the characters either side, so a fixture can carry
    such a run and still pass the tree scan today. That makes this check
    stricter than the scan on purpose - the alignment is luck, and a fixture
    that depends on luck is a fixture that breaks when something before it
    changes length.
    """
    raw = fixture_bytes(fixture)
    run = b"\x00" * _ZEROS_PER_HEX32_RUN
    assert run not in raw, (
        f"{fixture.name} decodes to {_ZEROS_PER_HEX32_RUN} or more consecutive "
        "zero bytes, which base64 turns into a 32-character run of 'A' - a hex "
        "run, and therefore a PRODUCTUSERID finding on the committed text. "
        "Author the zero payload where the fixture is built."
    )


@pytest.mark.parametrize("fixture", fixture_files(), ids=lambda p: p.name)
def test_every_fixture_carries_the_expected_suffix(fixture: Path):
    # The enumeration above is what makes a new fixture covered automatically,
    # and it only works if a new fixture is named like the others.
    assert fixture.name.endswith(FIXTURE_SUFFIX)
