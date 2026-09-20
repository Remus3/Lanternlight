"""Every write into a sibling inbox goes through ``ops.outbox.deliver``.

WHY THIS EXISTS
---------------
``CLAUDE.md`` names :func:`ops.outbox.deliver` "the choke point for anything
going out on the note channel", and ``ops/outbox.py`` earns that name at run
time: it refuses an operator identifier before a byte is written, and it keeps
a local copy plus a manifest row BEFORE it attempts a single sibling write
(``OPS-43``). ``tests/test_outbox.py`` tests all of that thoroughly.

What nothing tested is the word EVERY. ``tests/test_outbox.py`` asks whether
the choke point behaves when it is used; it asks nothing about code that walks
around it. A static-guard census on 2026-09-20 recorded that gap as an
UNGUARDED PROPERTY rather than a weak guard, and it is ``LL-0170``'s exact
failure: a session quoted raw ``git log`` output into four sibling directories,
the redactor was never consulted because the string came from ``git`` rather
than from a log parser, and no commit-time guard fired because
``moon_sync_inbox/`` is gitignored and nothing was being committed. Every
control this repository owns was silent, and silent BY CONSTRUCTION.

THE TWO ARMS, AND WHY NEITHER IS SUFFICIENT ALONE
-------------------------------------------------
:class:`TestNoModuleNamesASiblingInboxExceptTheChokePoint` is the STATIC arm -
the obvious form, and exactly the shape a census exists to distrust. It is
written anyway because it is cheap and it catches the honest case, and its
blindness is enumerated in its own docstring rather than left for a reader to
discover.

:class:`TestTheChokePointIsObservedAtRUNTIME` is the load-bearing arm. It runs
:func:`ops.outbox.deliver` in a subprocess under :func:`sys.addaudithook` and
reads the real file events, the same architecture
``tests/test_responder.py::TestTheRunnerCannotSendAtRUNTIME`` and
``tests/conftest.py``'s doc-open recorder already use here. An audit hook sits
BELOW name resolution, so it sees a write however the path was spelled -
assembled at run time, resolved through ``getattr``, or arrived at by an idiom
nobody enumerated.

The runtime arm carries its own NEGATIVE CONTROL. A probe that reports "no
bypass detected" is indistinguishable from a probe that detects nothing at all,
so one mode of the subprocess performs a real bypass - two lines writing
straight into a fake sibling inbox with the choke point never consulted - and
:func:`choke_point_violations` is required to report it. That is what makes the
detector's silence in the other modes mean something.

NOTHING HERE TOUCHES A REAL SIBLING INBOX
-----------------------------------------
Every write in this module lands under ``tmp_path``. :func:`ops.outbox.deliver`
takes an ``inboxes`` parameter for exactly this, and ``root`` is redirected too
so this repository's own outbox and manifest are never opened. The real
``SIBLING_INBOXES`` map is READ by the static arm - to count how many modules
reference it - and no path from it is ever opened, for reading or for writing.

WHAT THIS MODULE STILL CANNOT SEE, stated here because a caveat that lives only
in a chat message is a lie in the artifact:

* The runtime arm is a claim about the runs it makes. It proves the detector
  works and that ``deliver`` satisfies it; it does NOT watch the whole suite,
  so a module that writes into a sibling inbox during some other test is not
  observed. Wiring :func:`choke_point_violations` into ``tests/conftest.py``'s
  existing session-wide audit hook would close that, and ``tests/conftest.py``
  is not this slice's file to edit. Recorded for the merger.
* Neither arm sees a write performed OUTSIDE this repository's Python - a shell
  redirect, a copy command, an editor, or an agent writing the file directly.
  ``LL-0170`` itself was of that kind. The honest claim is that this module
  guards the code path, and ``CLAUDE.md``'s standing rule guards the rest.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import _tracked
import pytest

from ops import outbox

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A drive-rooted path to a sibling's note channel, in the spellings this
#: repository could plausibly commit.
#:
#: ASSEMBLED FROM PARTS, and the channel directory's name is split across two
#: string literals. This module is itself inside the corpus the static arm
#: scans, so a pattern typed as one literal would match its own source and turn
#: the guard into a report about itself. The same lesson ``tests/test_no_pii.py``
#: and ``tests/test_no_hardcoded_home_path.py`` both record: prose describing a
#: needle is indistinguishable from the needle.
#:
#: :func:`test_the_literal_pattern_is_armed` proves it still fires on a real
#: example, and :func:`test_the_literal_pattern_does_not_match_its_own_source`
#: proves the splitting worked.
_DRIVE = "[A-Za-z]:"
_SEP = r"[\\/]{1,2}"
SIBLING_INBOX_LITERAL = re.compile(
    _DRIVE + _SEP + r"[A-Za-z][A-Za-z0-9 ._-]*" + _SEP + "moon" + "_sync_inbox"
)

#: The only tracked Python files permitted to name a sibling inbox directory.
#:
#: ``ops/outbox.py`` is the choke point and carries the map itself.
#: ``tests/test_outbox.py`` carries ONE constant, and it is a read-only
#: assertion that Substrate's row says what ``docs/REPLY_PATHS.md`` says -
#: re-measured 2026-09-20 rather than assumed, by reading the line.
#:
#: This is an ALLOWLIST on purpose. A new entrant is a human decision, and the
#: failure direction of a forgotten entry is a red suite rather than a silent
#: bypass.
MAY_NAME_A_SIBLING_INBOX = frozenset(
    {
        "ops/outbox.py",
        "tests/test_outbox.py",
    }
)

#: The only tracked Python files permitted to reference the map by NAME.
#:
#: Wider than the set above because naming the constant is not the same act as
#: naming a path: ``tests/test_source_register.py`` mentions it in a register
#: entry, and this module reads it to count referents. Pinned rather than
#: forbidden - a rise is a human decision, exactly as above.
MAY_REFERENCE_THE_MAP = frozenset(
    {
        "ops/outbox.py",
        "tests/test_outbox.py",
        "tests/test_sibling_inbox_choke_point.py",
        "tests/test_source_register.py",
    }
)


def tracked_python_files() -> list[str]:
    """Every published ``.py`` file, through the repository's own walker.

    ``_tracked.iter_authored_files`` rather than a private listing, for the
    reason ``tests/test_no_hardcoded_home_path.py`` records at length: this
    repository has exactly one answer to "what would be published from here",
    and a second implementation is a second thing to keep in step. That walker
    is itself guarded behaviourally - see
    ``TestTheCorpusCoversProseNotJustCode`` in that module - so a corpus that
    silently narrowed under this arm would redden there.
    """
    return sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in _tracked.iter_authored_files(REPO_ROOT)
        if path.suffix == ".py"
    )


# ---------------------------------------------------------------------------
# the predicate the runtime arm is built on
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """One spelling for a Windows path, for prefix comparison only."""
    return str(text).replace("\\", "/").lower().rstrip("/")


def _first_under(
    writes: Sequence[Sequence[str]], directories: Sequence[str]
) -> int | None:
    """Index of the first recorded write landing under any of ``directories``."""
    prefixes = [_normalise(d) + "/" for d in directories]
    for index, row in enumerate(writes):
        target = _normalise(row[1])
        if any(target.startswith(prefix) for prefix in prefixes):
            return index
    return None


def choke_point_violations(
    writes: Sequence[Sequence[str]],
    outbox_dir: str,
    inbox_dirs: Sequence[str],
) -> list[str]:
    """Reasons an observed write sequence did NOT go through the choke point.

    ``writes`` is an ordered list of ``[event, path]`` rows as the audit probe
    records them. Returns an empty list when the sequence is consistent with
    :func:`ops.outbox.deliver` having produced it.

    THE DISCRIMINATOR, and it is a property of ORDER rather than of names.
    ``OPS-43`` requires the local copy and the manifest row to land BEFORE any
    sibling write is attempted, so that a delivery which fails half way still
    leaves the evidence that it was tried. A bypass cannot reproduce that: it
    writes the sibling file and nothing else. So a sibling write with no
    earlier outbox write, or with the outbox write after it, is a bypass -
    whatever the calling code is spelled like, and whatever it imported.

    A run that wrote no sibling file at all has nothing to answer for and
    returns no violations. That is deliberate: this function judges sends, and
    the ANCHOR that a send happened at all belongs to the caller. A version
    that reported "no send" as a violation would be red on every run of the
    suite that sends nothing, which is almost all of them.

    Kept pure, and separate from the subprocess, so it can be exercised in both
    directions against constructed event lists. A predicate only ever fed real
    input that satisfies it is a predicate nobody has watched say no.
    """
    first_sibling = _first_under(writes, inbox_dirs)
    if first_sibling is None:
        return []
    problems: list[str] = []
    first_outbox = _first_under(writes, [outbox_dir])
    if first_outbox is None:
        problems.append(
            "a sibling inbox was written and NO local outbox copy was written "
            "at all - the note left this machine with no record here that it "
            "was ever sent, which is LL-0170's shape"
        )
    elif first_outbox > first_sibling:
        problems.append(
            "the local outbox copy was written AFTER the sibling write - "
            "OPS-43 requires the record first, so a delivery that dies half "
            "way still leaves the evidence that it was tried"
        )
    manifest_writes = [
        row
        for row in writes
        if "deliveries" in _normalise(row[1]).rsplit("/", 1)[-1]
        and _normalise(row[1]).startswith(_normalise(outbox_dir) + "/")
    ]
    if not manifest_writes:
        problems.append(
            "a sibling inbox was written and no manifest row was recorded, so "
            "ops.outbox.replies_to cannot account for the note"
        )
    return problems


# ---------------------------------------------------------------------------
# the runtime probe
# ---------------------------------------------------------------------------

#: Run in a bare subprocess under an audit hook. See the module docstring.
#:
#: ``-B`` is passed so importing ``ops.outbox`` writes no ``.pyc``, which keeps
#: the recorded write list down to writes this probe chose to make.
#:
#: Only writes under the throwaway base directory are kept. Keeping every
#: audited event would be tens of thousands of stdlib opens, and the filter is
#: a substring test on a path the caller controls, so nothing real can be
#: dragged in by it.
AUDIT_PROBE = r'''
import json
import os
import sys

REPO, ROOT, BASE, MODE = sys.argv[1:5]

WRITES = []
RECORDING = [True]
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC


def _arg(args, index):
    try:
        return args[index]
    except Exception:
        return None


def _is_write(mode, flags):
    if isinstance(mode, str) and any(char in mode for char in "wxa+"):
        return True
    if isinstance(flags, int) and flags > 0 and (flags & WRITE_FLAGS):
        return True
    return False


def _hook(event, args):
    # An exception inside an audit hook aborts the operation that raised it,
    # so this body swallows everything - the rule tests/conftest.py records.
    if not RECORDING[0]:
        return
    try:
        if event == "open":
            target = _arg(args, 0)
            # os.fdopen re-opens a descriptor and carries no path. Dropped
            # rather than labelled: the os.open that produced the descriptor
            # was itself audited WITH its path, so no evidence is lost.
            if isinstance(target, int):
                return
            if not _is_write(_arg(args, 1), _arg(args, 2)):
                return
        elif event == "os.rename":
            target = _arg(args, 1)
        else:
            return
        text = str(target)
        if BASE.lower() not in text.lower():
            return
        # RECORDED RELATIVE TO THE THROWAWAY BASE - ADR-004. A pytest tmp
        # directory sits under the operator's home, so an absolute path here
        # would put an operator identifier into this test's own failure
        # message, where CI and any pasted transcript would carry it. The
        # relative path answers every question the predicate asks.
        WRITES.append([event, os.path.relpath(text, BASE)])
    except Exception:
        pass


sys.addaudithook(_hook)
sys.path.insert(0, REPO)

from ops import outbox  # noqa: E402

INBOXES = {
    "AA": os.path.join(BASE, "siblings", "AA"),
    "BB": os.path.join(BASE, "siblings", "BB"),
}
for directory in INBOXES.values():
    os.makedirs(directory, exist_ok=True)

NAME = "2026-09-20-0000-from-LL-probe.md"
CLEAN = "# to AA\n\nnothing sensitive in this note\n"
# Assembled at run time, at an invented host that is not reserved for
# documentation, so the SHAPE half of the redactor is what catches it. The
# same construction tests/test_outbox.py uses, for the same reason.
DIRTY = "# to AA\n\nmail " + "someone" + "@" + "a-real-looking-host" + ".com" + "\n"

outcome = {"mode": MODE, "raised": None}

if MODE == "clean":
    outbox.deliver(NAME, CLEAN, ["AA", "BB"], root=ROOT, inboxes=INBOXES)
elif MODE == "refused":
    try:
        outbox.deliver(NAME, DIRTY, ["AA", "BB"], root=ROOT, inboxes=INBOXES)
    except Exception as exc:
        outcome["raised"] = type(exc).__name__
elif MODE == "bypass":
    # THE NEGATIVE CONTROL. A note written straight into a sibling inbox with
    # the choke point never consulted - LL-0170 reduced to two lines. If the
    # detector cannot see this, its silence elsewhere means nothing.
    with open(os.path.join(INBOXES["AA"], NAME), "w", encoding="ascii") as handle:
        handle.write(CLEAN)
else:
    raise SystemExit("unknown probe mode: " + MODE)

RECORDING[0] = False
outcome["writes"] = WRITES
# Relative to BASE for the same reason the write rows are - see the hook.
outcome["inbox_dirs"] = sorted(
    os.path.relpath(directory, BASE) for directory in INBOXES.values()
)
outcome["outbox_dir"] = os.path.relpath(
    os.path.join(ROOT, "moon_sync_inbox", "_outbox"), BASE
)
print(json.dumps(outcome))
'''


def _run_probe(tmp_path: Path, mode: str) -> dict:
    """Run one probe mode in a subprocess; return its JSON.

    Nothing outside ``tmp_path`` is written. ``root`` and ``inboxes`` are both
    redirected, so neither this repository's own outbox nor any real sibling
    directory is opened.
    """
    base = tmp_path / mode
    (base / "repo").mkdir(parents=True)
    script = tmp_path / f"audit_probe_{mode}.py"
    script.write_text(AUDIT_PROBE, encoding="ascii", newline="\n")
    proc = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            str(REPO_ROOT),
            str(base / "repo"),
            str(base),
            mode,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------------------
# the static arm
# ---------------------------------------------------------------------------


class TestNoModuleNamesASiblingInboxExceptTheChokePoint:
    """The obvious form, written with its blindness enumerated.

    WHAT IT CAN SEE: a drive-rooted sibling inbox path typed as a literal into
    a tracked Python file, and a reference to :data:`ops.outbox.SIBLING_INBOXES`
    by name. Those are the cheap, honest spellings and they are the ones a
    hurried session actually writes.

    WHAT IT CANNOT SEE, and this list is the point of the class existing at
    all:

    * A path assembled at run time, from parts, from an environment variable,
      or read out of a JSON or Markdown file. ``docs/REPLY_PATHS.md`` carries
      every sibling path in prose and is not Python, so a module that parsed it
      would name no literal here.
    * A path reached by walking - a glob over the drive root, or
      ``parent.parent / "moon" "_sync_inbox"``.
    * A write performed by a subprocess, a shell redirect, an editor, or an
      agent typing the file directly. ``LL-0170`` was of that last kind, so the
      incident that motivated this module is one the static arm would have
      missed entirely. The runtime arm below is the answer to that, and
      ``CLAUDE.md``'s standing rule is the answer to the rest.
    * An UNTRACKED script. The corpus is what would be published, which is
      correct for a publication guard and wrong for this one.

    It is therefore a check on tidiness with a useful side effect, not a proof.
    Saying so here is cheaper than a future session mistaking it for one.
    """

    def test_the_literal_pattern_is_armed(self):
        """A clean result and a broken regex are the same output."""
        planted = [
            "C:" + "\\" + "Somewhere" + "\\" + "moon" + "_sync_inbox",
            "D:" + "/" + "Some Project" + "/" + "moon" + "_sync_inbox" + "/note.md",
            "C:" + "\\" + "With-Dashes_1" + "\\" + "moon" + "_sync_inbox",
        ]
        for text in planted:
            assert SIBLING_INBOX_LITERAL.search(text), (
                f"the pattern failed to fire on {text!r}, so a clean sweep "
                "below would be a claim about the pattern rather than about "
                "the tree"
            )

    def test_the_literal_pattern_does_not_match_its_own_source(self):
        """The needle is split across literals; prove the split held.

        If this module's own text matched, the sweep would report this file and
        a session would add it to the allowlist, which is how a guard quietly
        stops guarding.
        """
        own = Path(__file__).read_text(encoding="utf-8")
        hits = SIBLING_INBOX_LITERAL.findall(own)
        assert not hits, (
            f"this module's own source carries a sibling inbox literal: {hits}"
        )

    def test_only_the_choke_point_names_a_sibling_inbox_path(self):
        offenders = []
        for rel in tracked_python_files():
            if rel in MAY_NAME_A_SIBLING_INBOX:
                continue
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for match in SIBLING_INBOX_LITERAL.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                offenders.append(f"{rel}:{line}")
        assert not offenders, (
            "a tracked Python file names a sibling inbox directory and is not "
            "the choke point. Every note leaving this tree goes through "
            "ops.outbox.deliver, which keeps a local copy and refuses an "
            "operator identifier - see CLAUDE.md, OPS-43 and LL-0170:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_sweep_actually_reaches_the_choke_point_itself(self):
        """ANCHOR. An empty sweep is a claim about the pattern, not the tree.

        ``ops/outbox.py`` genuinely carries five sibling paths. If the sweep
        does not find them there, it is finding nothing anywhere and the clean
        result above is decoration.
        """
        corpus = tracked_python_files()
        assert "ops/outbox.py" in corpus, (
            "the choke point is not in the scanned corpus at all, so the sweep "
            "above covered a tree that does not include it"
        )
        text = (REPO_ROOT / "ops" / "outbox.py").read_text(encoding="utf-8")
        found = SIBLING_INBOX_LITERAL.findall(text)
        assert len(found) >= 2, (
            "the pattern found fewer than two sibling paths in ops/outbox.py, "
            f"which carries one per sibling: {found}"
        )
        assert len(found) == len(outbox.SIBLING_INBOXES), (
            f"the pattern found {len(found)} literal paths in ops/outbox.py "
            f"but the live map has {len(outbox.SIBLING_INBOXES)} entries - one "
            "of the two is being derived some other way and the sweep is no "
            "longer a complete account of the map"
        )

    def test_the_set_of_modules_referencing_the_map_is_pinned(self):
        referents = []
        for rel in tracked_python_files():
            text = (REPO_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            if "SIBLING" + "_INBOXES" in text:
                referents.append(rel)
        assert set(referents) == set(MAY_REFERENCE_THE_MAP), (
            "the set of tracked Python modules referencing the sibling inbox "
            "map changed. Adding one is a human decision, not a drift: a new "
            "referent is a new place a note can leave this tree without "
            f"passing the redactor.\n  found: {sorted(referents)}\n  pinned: "
            f"{sorted(MAY_REFERENCE_THE_MAP)}"
        )

    def test_every_pinned_name_is_a_file_that_exists(self):
        """A pin naming a deleted file is a pin that guards nothing."""
        named = set(MAY_NAME_A_SIBLING_INBOX) | set(MAY_REFERENCE_THE_MAP)
        missing = [rel for rel in sorted(named) if not (REPO_ROOT / rel).is_file()]
        assert not missing, f"pinned set names files that do not exist: {missing}"


# ---------------------------------------------------------------------------
# the predicate, in both directions
# ---------------------------------------------------------------------------


class TestThePredicateSaysNoAsWellAsYes:
    """A predicate only ever shown satisfying input has not been watched work.

    These exercise :func:`choke_point_violations` against CONSTRUCTED event
    lists, so its two failure directions are proved without editing
    ``ops/outbox.py`` - which is not this slice's file - and without needing a
    mutant that survives long enough to be observed.
    """

    OUTBOX = "C:/tree/channel/_outbox"
    INBOXES = ("C:/elsewhere/AA", "C:/elsewhere/BB")

    def _good(self) -> list[list[str]]:
        return [
            ["open", self.OUTBOX + "/.note.md.1.tmp"],
            ["os.rename", self.OUTBOX + "/note.md"],
            ["open", self.OUTBOX + "/.DELIVERIES.json.1.tmp"],
            ["os.rename", self.OUTBOX + "/DELIVERIES.json"],
            ["open", self.INBOXES[0] + "/.note.md.1.tmp"],
            ["os.rename", self.INBOXES[0] + "/note.md"],
        ]

    def test_a_delivery_shaped_sequence_is_accepted(self):
        assert choke_point_violations(self._good(), self.OUTBOX, self.INBOXES) == []

    def test_a_sequence_with_no_sibling_write_has_nothing_to_answer_for(self):
        local_only = self._good()[:4]
        assert choke_point_violations(local_only, self.OUTBOX, self.INBOXES) == []

    def test_a_bare_sibling_write_is_reported(self):
        bypass = [["open", self.INBOXES[0] + "/note.md"]]
        problems = choke_point_violations(bypass, self.OUTBOX, self.INBOXES)
        assert problems, "a write straight into a sibling inbox was accepted"
        assert any("NO local outbox copy" in problem for problem in problems)

    def test_an_outbox_copy_written_AFTER_the_sibling_is_reported(self):
        """The OPS-43 ordering, which is the half a tidy bypass could fake."""
        late = self._good()[4:] + self._good()[:4]
        problems = choke_point_violations(late, self.OUTBOX, self.INBOXES)
        assert problems, "a copy written after the sibling write was accepted"
        assert any("AFTER the sibling" in problem for problem in problems)

    def test_a_missing_manifest_row_is_reported(self):
        no_manifest = [row for row in self._good() if "DELIVERIES" not in row[1]]
        problems = choke_point_violations(no_manifest, self.OUTBOX, self.INBOXES)
        assert any("no manifest row" in problem for problem in problems)


# ---------------------------------------------------------------------------
# the runtime arm
# ---------------------------------------------------------------------------


class TestTheChokePointIsObservedAtRUNTIME:
    """Measured on the RUN, below name resolution - see the module docstring.

    WHAT THIS CAN SEE: every file the interpreter opened for writing or renamed
    during the probe run, however the path was spelled. A name assembled at run
    time, resolved through ``getattr``, or imported by a concatenated module
    name is invisible to a source scan and plainly visible here, because an
    audit hook is raised by the file operation itself.

    WHAT IT CANNOT SEE: a path this particular run did not take, and any part
    of the suite it does not execute. It is three runs of one function, not a
    session-wide watch. Making it session-wide is a change to
    ``tests/conftest.py``, which already installs an audit hook for the doc
    recorder and is out of this slice.
    """

    @pytest.fixture(scope="class")
    def clean(self, tmp_path_factory) -> dict:
        return _run_probe(tmp_path_factory.mktemp("choke"), "clean")

    def test_the_probe_sees_the_sibling_writes_at_all(self, clean: dict):
        """ANCHOR. A detector that records nothing reports no bypass either."""
        assert clean["writes"], "the audit probe recorded no writes whatsoever"
        landed = _first_under(clean["writes"], clean["inbox_dirs"])
        assert landed is not None, (
            "the probe recorded writes but none of them landed in a sibling "
            "inbox, so every absence asserted below would be vacuous"
        )

    def test_a_real_delivery_satisfies_the_choke_point_predicate(self, clean: dict):
        problems = choke_point_violations(
            clean["writes"], clean["outbox_dir"], clean["inbox_dirs"]
        )
        assert problems == [], (
            "ops.outbox.deliver itself failed the predicate that defines going "
            f"through the choke point: {problems}"
        )

    def test_the_local_copy_and_manifest_really_precede_the_sibling_write(
        self, clean: dict
    ):
        """``OPS-43``'s ordering claim, read off the event stream.

        ``tests/test_outbox.py`` asserts the local copy EXISTS after a
        delivery. Existence afterwards is not order: a copy written last would
        satisfy it just as well. This reads the sequence.
        """
        writes = clean["writes"]
        first_outbox = _first_under(writes, [clean["outbox_dir"]])
        first_sibling = _first_under(writes, clean["inbox_dirs"])
        assert first_outbox is not None and first_sibling is not None
        assert first_outbox < first_sibling, (
            "the first sibling write came before the first local write, so a "
            "delivery that died half way would leave a note in a sibling tree "
            "and no record of it here"
        )
        manifest_before = [
            index
            for index, row in enumerate(writes)
            if "deliveries" in row[1].lower() and index < first_sibling
        ]
        assert manifest_before, (
            "no manifest write was observed before the first sibling write"
        )

    def test_the_bypass_negative_control_is_detected(self, tmp_path: Path):
        """The detector is shown saying NO on a real, executed bypass.

        Without this, "no violations" from the clean run would be consistent
        with a predicate that can never report anything.
        """
        result = _run_probe(tmp_path, "bypass")
        assert result["writes"], "the bypass probe recorded no writes at all"
        problems = choke_point_violations(
            result["writes"], result["outbox_dir"], result["inbox_dirs"]
        )
        assert problems, (
            "a note was written straight into a sibling inbox with the choke "
            "point never consulted and the detector reported nothing - which "
            "is LL-0170 happening again with a guard watching"
        )
        assert any("NO local outbox copy" in problem for problem in problems)

    def test_a_refused_note_produces_NO_write_anywhere(self, tmp_path: Path):
        """``OPS-50`` at the syscall level rather than through ``exists()``.

        ``tests/test_outbox.py`` asserts no file is PRESENT after a refusal.
        That is the right property and it is checked one layer above the act: a
        write followed by an unlink satisfies it, and would have left the
        operator identifier on disk in between - inside the watched channel,
        which is where the next session reads. This asserts the write never
        happened.

        The clean run above is this test's own non-vacuity control: the same
        probe, the same filter, produced writes there. Zero here is therefore
        a fact about the refusal rather than about the recorder.
        """
        result = _run_probe(tmp_path, "refused")
        assert result["raised"] == "RedactionError", (
            f"the gate did not refuse the note; it raised {result['raised']!r}"
        )
        assert result["writes"] == [], (
            "a note carrying an operator identifier was refused, and writes "
            f"happened anyway: {result['writes']}"
        )
