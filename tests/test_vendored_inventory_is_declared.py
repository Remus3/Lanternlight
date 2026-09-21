"""Every vendored directory on disk must be NAMED in ``CLAUDE.md``.

WHY, and this is a failure that actually happened rather than one imagined.

``CLAUDE.md`` records the second vendoring exception and then names the
instances it covers. When ``third_party/rc_channel/`` was vendored on
2026-09-20 under the operator's ruling, that sentence was not updated, so
``CLAUDE.md`` went on saying ``third_party/lw_write_tracer/`` was "the one
instance" while a second one sat beside it in the same tree.

**A cold reader then reached the wrong conclusion from it, which is the whole
point.** On 2026-09-20 an analysis pass over the note channel read that
sentence, saw four sibling projects reporting a vendored ``CHANNEL.md`` in this
repository, and concluded the siblings were wrong - that the reports were "a
fabrication, or a hallucination propagating across sibling notes". They were
not. The file was on disk, committed, with a ``NOTICE.md`` and a pin test. The
document was stale and the world was right, and the reader trusted the document
because trusting the document is what this repository tells it to do.

That is the exact failure the continuity design exists to prevent, so it is
guarded rather than merely corrected: ``CLAUDE.md`` is what a session with no
other context believes, and a stale inventory there is not a tidiness problem,
it is a confident lie aimed at the one reader least able to check it.

**This guard asks the FILESYSTEM and compares.** It does not store a count and
it does not store a list of names beyond what the document itself carries -
``tests/test_source_register.py`` gives the reason one level down: a committed
list of filenames goes stale on the first rename.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
THIRD_PARTY = REPO_ROOT / "third_party"


def vendored_directories(root: Path = THIRD_PARTY) -> set[str]:
    """Directory names directly under ``third_party/``.

    One directory is one vendored work. ``CLAUDE.md`` requires a ``NOTICE``
    per vendored work, so the directory is the unit the document names.
    """
    if not root.is_dir():
        return set()
    return {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")}


def declared_directories(text: str) -> set[str]:
    """Every ``third_party/<name>/`` path the document mentions.

    Read out of the prose rather than out of a list, because the document is
    prose and a session reads the prose. The trailing slash is required: it is
    what distinguishes naming an INSTANCE from naming the parent directory in a
    sentence about the rule.
    """
    return set(re.findall(r"third_party/([A-Za-z0-9_.\-]+)/", text))


def test_every_vendored_directory_is_named_in_claude_md():
    on_disk = vendored_directories()
    declared = declared_directories(CLAUDE_MD.read_text(encoding="utf-8"))

    missing = sorted(on_disk - declared)
    assert not missing, (
        "these vendored works exist on disk and CLAUDE.md does not name them: "
        + ", ".join(f"third_party/{name}/" for name in missing)
        + ". A cold session believes CLAUDE.md over the tree, and on 2026-09-20 "
        "one did exactly that and called a real vendored file a fabrication."
    )


def test_claude_md_names_no_vendored_directory_that_is_gone():
    """The other direction. A named instance that was removed is also a lie."""
    on_disk = vendored_directories()
    declared = declared_directories(CLAUDE_MD.read_text(encoding="utf-8"))

    stale = sorted(declared - on_disk)
    assert not stale, (
        "CLAUDE.md names these vendored works and they are not on disk: "
        + ", ".join(f"third_party/{name}/" for name in stale)
    )


def test_the_population_is_not_empty():
    """A scan that reached nothing is not a pass.

    Without this, deleting ``third_party/`` outright would make both arms above
    vacuously green - which is the shape of a guard that stopped guarding.
    """
    assert vendored_directories(), (
        "third_party/ holds no vendored work, so both arms above are vacuous"
    )


def test_the_declaration_reader_is_not_vacuous():
    """Prove the parser finds a name, and does not find one that is absent."""
    sample = "we vendor `third_party/example_pkg/` and nothing else"
    assert declared_directories(sample) == {"example_pkg"}
    assert declared_directories("we vendor nothing under third_party at all") == set()
    # Naming the parent without an instance must NOT read as a declaration.
    assert declared_directories("`ruff.toml` excludes `third_party/`") == set()
