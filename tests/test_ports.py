"""Every port this project names must sit inside its allocated block.

The machine-wide registry lives in `CLAUDE.md`: this project owns **8810-8819**
and five sibling projects own blocks around it. Allocating outside the block is
how two local projects end up fighting over a socket, and the failure surfaces
as one of them mysteriously not starting - a long way from the line that chose
the number.

Nothing in this repository binds a port today, so this guard protects an
allocation rather than a running service. That is deliberate: the moment a
service IS built is the moment a stray constant becomes expensive, and a guard
added then would be added after the mistake.

Two things are checked, and they fail for different reasons:

- a port CONSTANT in the source that sits outside the block
- the `CLAUDE.md` table drifting away from the block it declares

The registry of sibling blocks is deliberately NOT restated here. `CLAUDE.md` is
the authority; a second copy is a second thing to go stale, which is the exact
defect that put a contradiction about port 8812 between `CLAUDE.md` and
`docs/ARCHITECTURE.md` for weeks.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "tests"))

import _tracked  # noqa: E402

#: This project's allocated block, from `CLAUDE.md`. Stated once, here, because
#: a test needs a literal to compare against - and pinned to the document by
#: `test_the_block_matches_what_claude_md_declares` so the two cannot drift.
BLOCK_LOW, BLOCK_HIGH = 8810, 8819

#: An assignment of a port-shaped name to a literal: `CONTROL_PORT = 8814`.
_PORT_CONSTANT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*PORT[A-Za-z0-9_]*)\s*=\s*(\d{2,5})\s*$")

#: A row of the `CLAUDE.md` port table: `| 8810 | Dashboard | not built |` and
#: the range form `| 8815-8819 | unallocated | free |`.
_TABLE_ROW = re.compile(r"^\|\s*(\d{4})(?:\s*-\s*(\d{4}))?\s*\|")


def _source_files():
    """Python sources that could name a port."""
    for path in _tracked.iter_authored_files(REPO_ROOT):
        if path.suffix == ".py":
            yield path


def _port_constants():
    """Yield (path, name, value) for every port constant in the source."""
    for path in _source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            match = _PORT_CONSTANT.match(line)
            if match:
                yield path, line_number, match.group(1), int(match.group(2))


def _claude_md_ports():
    """Every port named in the `CLAUDE.md` port table, ranges expanded."""
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index("## Ports")
    end = text.index("## Paths", start)
    section = text[start:end]
    # The section carries TWO tables - the sibling registry and this project's
    # ports. Only rows after the second header belong to this project.
    marker = "| Port | Service | State |"
    assert marker in section, "the CLAUDE.md port table changed shape"
    own = section[section.index(marker) :]
    ports = []
    for line in own.splitlines():
        match = _TABLE_ROW.match(line)
        if not match:
            continue
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        ports.extend(range(low, high + 1))
    return ports


class TestThePortConstantsInSource:
    def test_the_scan_finds_the_constant_that_is_actually_there(self):
        """A scanner that finds nothing agrees with any repository forever.

        `overlay/window.py` defines `CONTROL_PORT`, so the positive control has
        a real target. If this ever fails because that constant was removed,
        replace the control - do not delete it and leave the scan unproven.
        """
        found = {(name, value) for _p, _n, name, value in _port_constants()}
        assert ("CONTROL_PORT", 8814) in found, (
            f"the port-constant scan did not find overlay.window.CONTROL_PORT; found {found}"
        )

    def test_every_port_constant_is_inside_the_allocated_block(self):
        strays = [
            f"{path.relative_to(REPO_ROOT).as_posix()}:{line} {name} = {value}"
            for path, line, name, value in _port_constants()
            if not BLOCK_LOW <= value <= BLOCK_HIGH
        ]
        assert not strays, (
            f"port constant(s) outside this project's block {BLOCK_LOW}-{BLOCK_HIGH}. "
            "CLAUDE.md carries the machine-wide registry; five sibling projects own "
            "the blocks around this one, and allocating into theirs is how two local "
            "projects end up fighting over a socket:\n  " + "\n  ".join(strays)
        )


class TestTheDocumentAndTheBlockAgree:
    def test_the_table_lists_only_ports_inside_the_block(self):
        ports = _claude_md_ports()
        assert ports, "no port rows parsed out of CLAUDE.md - the table changed shape"
        outside = [p for p in ports if not BLOCK_LOW <= p <= BLOCK_HIGH]
        assert not outside, f"CLAUDE.md's own port table names ports outside its block: {outside}"

    def test_the_block_matches_what_claude_md_declares(self):
        """Pins the literal above to the document, so the two cannot drift.

        Without this the constants here could quietly disagree with the
        authority, and the guard would be enforcing a block nobody allocated.
        """
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert f"block is {BLOCK_LOW}-{BLOCK_HIGH}" in text, (
            f"CLAUDE.md no longer declares the block as {BLOCK_LOW}-{BLOCK_HIGH}; "
            "update BLOCK_LOW/BLOCK_HIGH here to match the authority"
        )

    def test_the_table_covers_the_whole_block(self):
        # Every port in the block should be accounted for - named or explicitly
        # free. A silent gap is how an allocation gets made twice.
        ports = set(_claude_md_ports())
        missing = [p for p in range(BLOCK_LOW, BLOCK_HIGH + 1) if p not in ports]
        assert not missing, (
            f"CLAUDE.md's port table does not account for {missing}. List them, or "
            "mark them free - an unlisted port is one nobody knows is available."
        )
