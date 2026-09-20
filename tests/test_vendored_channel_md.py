"""Guard the vendored copy of Amberstone's ``docs/CHANNEL.md``.

``OPS-91``. This repository refused an unlicensed drop of this file, asked the
owning project to name a license and a repository, and Amberstone answered:
``Remus3/Amberstone``, PUBLIC, Apache-2.0, authored documentation inside the
grant. The operator then ruled VENDOR on 2026-09-20. ``CLAUDE.md``'s SECOND
EXCEPTION permits exactly that, and says in its own words that the gate "was
satisfied, not waived".

The same exception also says a vendored file is NOT edited. This module is what
makes that enforceable: it fails the moment the bytes change, and the honest
response to that red is to declare the change in the NOTICE, never to update
the constant here.

**Why this one records ONE digest and ``lw_write_tracer`` records two.** That
file arrived with CRLF on every line and ``.gitattributes`` pins the checkout to
LF, so its working-file hash and its git blob hash are different facts. This
file was fetched LF and is stored LF, measured 2026-09-20: zero CRLF pairs, so
the two hashes coincide and recording one is not a choice between them.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / "third_party" / "rc_channel"
VENDORED = VENDOR_DIR / "docs" / "CHANNEL.md"
NOTICE = VENDOR_DIR / "NOTICE.md"

#: The ``sha256`` Amberstone published for the LF form of this file, in its note
#: ``2026-09-15-1858-from-RC-FYI-899f6eb957cc-channel-md-v1-conventions-and-
#: charter-v4-is-current.md``, alongside the commit ``6e3c1c752`` it is
#: committed at. Verified against the bytes served by the public remote at that
#: commit BEFORE a byte was copied into this tree.
PUBLISHED_SHA256 = "fc22e86eebe93bb247a91f44835257a3fe717a287c4a3184a8e7a7b9a463fb9c"

#: Byte length of the same form, measured on the fetched bytes 2026-09-20.
PUBLISHED_BYTES = 25425

#: The upstream commit the copy was taken at, as Amberstone published it.
UPSTREAM_COMMIT = "6ad1531e2"


def _vendored_bytes() -> bytes:
    if not VENDORED.is_file():
        pytest.fail(
            f"{VENDORED.relative_to(REPO_ROOT).as_posix()} is missing. A "
            "vendored file that is not on disk cannot be attributed, and "
            "Apache-2.0 section 4(b) attaches to the copy, not to the intent."
        )
    return VENDORED.read_bytes()


def test_vendored_file_is_byte_identical_to_what_was_licensed() -> None:
    """The copy hashes to the digest its owner published.

    This is the whole value of a vendor over a paraphrase: every tree that
    holds this file can pin one digest and prove it holds the same text.
    """
    raw = _vendored_bytes()
    assert hashlib.sha256(raw).hexdigest() == PUBLISHED_SHA256, (
        "the vendored CHANNEL.md no longer hashes to the digest Amberstone "
        "published. Do NOT update the constant - declare the change in "
        f"{NOTICE.relative_to(REPO_ROOT).as_posix()}, or restore the bytes."
    )
    assert len(raw) == PUBLISHED_BYTES


def test_vendored_file_is_lf_and_ascii() -> None:
    """A text-mode copy on Windows would rewrite the line endings.

    ``Path.write_text`` turns LF into CRLF here and ``read_text`` hides it, so
    a byte count is the only honest witness. Asserting this separately means a
    line-ending rewrite reports as what it is rather than as an unexplained
    digest mismatch.
    """
    raw = _vendored_bytes()
    assert raw.count(b"\r\n") == 0, "CRLF found - this file was copied in text mode"
    assert raw.count(b"\r") == 0
    assert all(byte < 128 for byte in raw), "non-ASCII byte in a vendored file"


def test_notice_exists_and_carries_every_field_section_4b_requires() -> None:
    """Apache-2.0 4(b) wants attribution AND a statement of changes."""
    assert NOTICE.is_file(), (
        f"{NOTICE.relative_to(REPO_ROOT).as_posix()} is missing. A vendored "
        "Apache-2.0 file without a NOTICE is a license violation, not an "
        "untidy directory."
    )
    body = NOTICE.read_text(encoding="utf-8")
    collapsed = re.sub(r"\s+", " ", body)
    for needed in (
        "Remus3/Amberstone",
        "Apache-2.0",
        PUBLISHED_SHA256,
        UPSTREAM_COMMIT,
    ):
        assert needed in collapsed, f"the NOTICE does not record {needed!r}"
    assert "CHANGES MADE TO THE WORK" in collapsed.upper(), (
        "the NOTICE has no statement of changes; section 4(b) requires one "
        "even when the answer is that nothing was changed"
    )


#: Heading of the NOTICE section that may carry RETIRED digests. Everything
#: outside it must name only the current pin.
SUPERSEDED_HEADING = "## Superseded pins"


def test_notice_digest_cannot_drift_from_the_guard() -> None:
    """The NOTICE and this module must name the SAME digest.

    A NOTICE quoting one hash while the guard pins another is worse than no
    NOTICE: it reads as corroboration by two independent records when it is
    one record contradicting itself.

    **One place is exempt, and the exemption is what makes a re-pin legible.**
    The channel document is re-pinned JOINTLY by every carrier when its author
    cuts a new version, so a retired digest is a fact worth keeping: a reader
    meeting the old value in a sibling's note or in this repository's own
    ledger has to be able to resolve it. Retired digests live under a single
    named heading and ONLY there. A stray retired digest anywhere else in the
    prose would read as a second live claim about what this directory holds,
    which is the exact confusion this arm exists to prevent.
    """
    body = NOTICE.read_text(encoding="utf-8")
    assert SUPERSEDED_HEADING in body, (
        f"the NOTICE has no {SUPERSEDED_HEADING!r} section. The heading stays "
        "even at one pin, because its absence and an unrecorded re-pin look "
        "identical from here."
    )
    live, _, retired = body.partition(SUPERSEDED_HEADING)
    next_section = retired.find("\n## ")
    if next_section >= 0:
        retired = retired[:next_section]

    in_live = set(re.findall(r"\b[0-9a-f]{64}\b", live))
    assert in_live == {PUBLISHED_SHA256}, (
        "outside the superseded section the NOTICE must name the CURRENT pin "
        f"and nothing else: {sorted(in_live)}"
    )

    in_retired = set(re.findall(r"\b[0-9a-f]{64}\b", retired))
    assert PUBLISHED_SHA256 not in in_retired, (
        "the current pin is listed as SUPERSEDED, which is a record saying the "
        "bytes on disk are retired while the guard says they are live"
    )
