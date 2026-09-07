"""Every port this project names must sit inside its allocated block.

The machine-wide registry lives in `CLAUDE.md`: this project owns **8810-8819**
and sibling projects own blocks around it. The number of siblings is not stated
here on purpose - it was "five" until a seventh project reserved a block on
2026-09-06, and a count written into a guard is a lie waiting for the next
allocation. Allocating outside the block is how two local projects end up
fighting over a socket, and the failure surfaces as one of them mysteriously
not starting - a long way from the line that chose the number.

Nothing in this repository binds a port today, so this guard protects an
allocation rather than a running service. That is deliberate: the moment a
service IS built is the moment a stray constant becomes expensive, and a guard
added then would be added after the mistake.

Three things are checked, and they fail for different reasons:

- a port CONSTANT in the source that sits outside the block
- the `CLAUDE.md` table drifting away from the block it declares
- the machine-wide registry claiming the same port twice, this project's own
  block included

The registry of sibling blocks is still deliberately NOT restated here.
`CLAUDE.md` is the authority; a second copy is a second thing to go stale, which
is the exact defect that put a contradiction about port 8812 between `CLAUDE.md`
and `docs/ARCHITECTURE.md` for weeks. `TestTheMachineWideRegistry` reads that
table out of the document and checks the rows against each other, so it gains no
copy to go stale and covers a block added long after it was written. See its
docstring for what was previously unguarded and what a sibling merely REPORTED
rather than something measured here.
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

#: The two table headers inside the `## Ports` section. The first opens the
#: machine-wide registry of sibling blocks; the second opens this project's own
#: per-port table.
_REGISTRY_HEADER = "| Block | Project |"
_OWN_TABLE_HEADER = "| Port | Service | State |"

#: One span inside a registry row's first cell: `8770-8789`, or a bare `2999`.
#: The range arm is tried first at each run of digits, so `8888-8895` parses as
#: one span rather than two singles - the shape that a naive parser silently
#: mangles, which is why there is a positive control for exactly that row.
_SPAN = re.compile(r"(\d{4})(?:\s*-\s*(\d{4}))?")


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


def _ports_section():
    """The whole `## Ports` section of `CLAUDE.md`, verbatim."""
    text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    start = text.index("## Ports")
    end = text.index("## Paths", start)
    return text[start:end]


def _registry_rows():
    """Yield `(project, [(low, high), ...])` for each machine-wide registry row.

    Derived entirely from the rows that are present. Nothing here enumerates
    the sibling projects, so a block added to the table after this was written
    is checked by this same code with no edit to it.
    """
    section = _ports_section()
    assert _REGISTRY_HEADER in section, "the CLAUDE.md registry table changed shape"
    assert _OWN_TABLE_HEADER in section, "the CLAUDE.md port table changed shape"
    registry = section[
        section.index(_REGISTRY_HEADER) + len(_REGISTRY_HEADER) : section.index(_OWN_TABLE_HEADER)
    ]
    rows = []
    for line in registry.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 2:
            continue
        spans = [
            (int(m.group(1)), int(m.group(2) or m.group(1))) for m in _SPAN.finditer(cells[0])
        ]
        rows.append((cells[1].replace("*", "").strip(), spans))
    return rows


def _expand(spans):
    """Every individual port covered by a row's spans."""
    ports = set()
    for low, high in spans:
        ports.update(range(low, high + 1))
    return ports


def _claude_md_ports():
    """Every port named in the `CLAUDE.md` port table, ranges expanded."""
    section = _ports_section()
    # The section carries TWO tables - the sibling registry and this project's
    # ports. Only rows after the second header belong to this project.
    marker = _OWN_TABLE_HEADER
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
            "CLAUDE.md carries the machine-wide registry; sibling projects own the "
            "blocks around this one, and allocating into theirs is how two local "
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


class TestTheMachineWideRegistry:
    """The sibling registry table, checked as a table rather than as prose.

    WHY THIS CLASS WAS ADDED, 2026-09-06, when a seventh block was recorded.

    The two classes above check only that THIS project stays inside its own
    block, and that is deliberately staleness-proof: they hold no list of
    siblings, so a block added to the registry after they were written cannot
    make them wrong. Containment in one's own block is a stronger property than
    a hand-maintained disjointness list, and it needs no maintenance.

    What it left unguarded is the registry table itself. Nothing checked that
    two rows do not overlap, and - the sharp edge - nothing checked that a
    sibling row does not sit on top of this project's own block.
    `test_the_block_matches_what_claude_md_declares` greps for the sentence
    declaring 8810-8819 and never compares it to the table, so a row reading
    `| 8815-8830 | Somebody |` would have been green on every test in this file
    while claiming half of Lanternlight's ports.

    The checks below are DERIVED from whatever rows are present, never from a
    second copy of the registry. An eighth block added later is checked by this
    same code with no edit. That is the difference from the failure `ROADMAP.md`
    OPS-31 is about, where a list written into a file is silently green over
    everything added after it was written.
    """

    def test_the_registry_parser_finds_the_row_that_is_actually_there(self):
        """A parser that finds nothing agrees with any document forever.

        Amberstone's row is the positive control because its `8888-8895 and
        2999` shape is the one a naive parser mangles - splitting the range
        into two singles, or dropping the trailing `2999` so a collision there
        would be invisible. If this ever fails because that row changed,
        replace the control; do not delete it and leave the parser unproven.
        """
        rows = _registry_rows()
        assert rows, "no registry rows parsed out of CLAUDE.md - the table changed shape"
        by_project = dict(rows)
        amberstone = [spans for project, spans in rows if "Amberstone" in project]
        assert amberstone == [[(8888, 8895), (2999, 2999)]], (
            "the registry parser did not read Amberstone's two-span row as two spans; "
            f"parsed rows were {by_project}"
        )
        unparsed = [project for project, spans in rows if not spans]
        assert not unparsed, (
            "registry row(s) yielded no port span at all, so they are invisible to every "
            f"check below: {unparsed}"
        )

    def test_no_two_blocks_in_the_registry_overlap(self):
        rows = _registry_rows()
        collisions = []
        for i, (project_a, spans_a) in enumerate(rows):
            for project_b, spans_b in rows[i + 1 :]:
                shared = sorted(_expand(spans_a) & _expand(spans_b))
                if shared:
                    collisions.append(f"{project_a} and {project_b} both claim {shared}")
        assert not collisions, (
            "the machine-wide registry in CLAUDE.md claims the same port twice. Two local "
            "projects fighting over a socket surfaces a long way from the line that chose "
            "the number:\n  " + "\n  ".join(collisions)
        )

    def test_this_projects_block_appears_in_the_registry_as_declared(self):
        """Pins the declared block to the registry row, not just to the prose.

        Without this, the registry could omit Lanternlight entirely, or list it
        at a different span from the one the section declares and the constants
        above enforce, and nothing would notice.
        """
        rows = _registry_rows()
        ours = [spans for project, spans in rows if "Lanternlight" in project]
        assert ours == [[(BLOCK_LOW, BLOCK_HIGH)]], (
            f"the machine-wide registry does not carry exactly one Lanternlight row of "
            f"{BLOCK_LOW}-{BLOCK_HIGH}; it carries {ours}"
        )

    def test_the_registry_records_the_resincompute_reservation(self):
        """ResinCompute reserves 8790-8809, recorded 2026-09-06.

        THIS ONE IS A CHANGE-PINNING REGRESSION TEST, NOT A REGISTRY MIRROR,
        and the distinction matters. Unlike the disjointness check above it
        names a project, so it does NOT extend itself to an eighth block, and
        it goes stale the day RSC releases the block - retire it then rather
        than widening it into the hand-maintained list this class exists to
        avoid.

        WHAT WAS MEASURED HERE, and what was not. Sweeping THIS tree for
        `879[0-9]` and `880[0-9]` on 2026-09-06 turned up no port constant, no
        bind site and no registry claim in 8790-8809: the only hits were a
        coincidental substring of a Unix timestamp in `docs/CLASSES.md`, two
        hex redaction fixtures containing `8796`, and prose in `docs/LEDGER.md`
        recording the span as unallocated.

        RSC's supporting argument - that Amberstone's `core/ports.py` reads
        `RM_BLOCK = range(8770, 8790)`, whose end is exclusive, so Red Moon
        stops at 8789 and does not claim 8790 - is REPORTED BY RSC and is not
        verified here. Nobody read a sibling's tree to check it, because the
        standalone rule in `CLAUDE.md` says knowing a neighbour's block is not
        permission to go looking in it. A claim a sibling reported is not the
        same fact as one measured here, and it does not become one by being
        written down.
        """
        rows = _registry_rows()
        rsc = [spans for project, spans in rows if "ResinCompute" in project]
        assert rsc == [[(8790, 8809)]], (
            "the machine-wide registry in CLAUDE.md does not record ResinCompute's "
            f"reservation of 8790-8809; the rows for it are {rsc}"
        )

    def test_the_registry_is_not_an_invitation_to_connect(self):
        """The framing beside the table must survive an edit to the table.

        A registry of neighbours reads as a directory unless something says
        otherwise, and the sentences below are that something. They are checked
        WHITESPACE-COLLAPSED on purpose: this repo's prose is hard-wrapped near
        80 columns, so a re-wrap moves the line break and a line-oriented match
        would report a confident false absence.
        """
        flat = re.sub(r"\s+", " ", _ports_section())
        for sentence in (
            "Knowing a neighbour's block is not permission to talk to it.",
            "This table exists so an allocation avoids a collision, "
            "not so a service can find a sibling.",
        ):
            assert sentence in flat, (
                "the CLAUDE.md ports section no longer carries the sentence that stops the "
                f"registry reading as a directory of services to call: {sentence!r}"
            )
