"""``ops/responder.py`` drafts replies and delivers nothing - ``OPS-68``.

WHAT THESE TESTS ARE FOR, stated rather than left to be inferred. The scope of
the responder runner was adjudicated on 2026-09-14 and written into
``ROADMAP.md`` under ``OPS-68``: it reads this tree and the gitignored note
channel, it writes drafts into ``moon_sync_inbox/_drafts/``, and it writes
nowhere else outside this tree. The draft-only shape was chosen on MEASURED
evidence rather than out of caution - on 2026-09-20 this project published two
wrong figures to five trees inside four hours and withdrew both on the channel,
and a runner that sent would have amplified them faster rather than caught them.

So the load-bearing guards here are the negative ones:

* :class:`TestTheRunnerCannotSend` - ``ops.outbox.deliver`` is not reachable
  from this module at all, not merely unused. An unused import is one edit away
  from a send.
* :class:`TestADraftNeverInventsANumber` - every digit run in a draft is a digit
  run that was read out of the note. A restated, rounded or recomputed figure is
  the exact failure that produced ``LL-0271`` and ``LL-0277``.
* :class:`TestADraftIsObviouslyUnfinished` - no draft carries an answer, so a
  draft delivered by accident reads as a draft rather than as a claim.
* :class:`TestAnEditedDraftIsNeverOverwritten` - a human's edit outranks the
  runner's own output, always.

Every guard in this file has been broken deliberately and watched go red before
being trusted, per ``CLAUDE.md``. A green test that has never been seen red is
decoration.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from ops import responder

#: The repository root. ``tests/conftest.py`` has already put it on
#: ``sys.path``, which is why the import above needs no path dance.
REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


NOTE_FROM_CS = """# From CS - REVIEW: the watcher cap and two questions for LL

2026-09-19 2310 local. Directed by the CS operator.

**Nothing in your tree was changed.** Nothing was written outside this note.

## What we measured

Our watcher caps the transcript listing and writes the rest to a report file.

Does your watcher cap its stdout listing the same way? Confirm the cap you use
in one line.

## What we did not check

We did not read your tree.

## Reply

Into CS's inbox as a note named from-LL, please.
"""


NOTE_NOT_OURS = """# From RC - FYI: addressed to RSC and LW

2026-09-19 1200 local. Sent to RSC and LW.

**Nothing in your tree was changed.**

## Body

Does the slot table still hold? Confirm it.

## Reply

Into RC's inbox.
"""


NOTE_WITH_FIGURES = """# From LW - REVIEW: a count and a duration

2026-09-19 0900 local. Broadcast to all five.

**Nothing in your tree was changed.**

## What we measured

Our suite collects 1,416 tests and the pre-flight ran in 12.4 seconds on a
quiet machine.

Can you reproduce either figure? Say so in one line.

## Reply

Into LW's inbox.
"""


NOTE_FIGURE_IN_QUESTION = """# From LW - REVIEW: a figure inside the ask itself

2026-09-19 0905 local. Broadcast to all five.

**Nothing in your tree was changed.**

## What we measured

Confirm you also collect 1,416 tests and that your pre-flight runs in 12.4
seconds.

## Reply

Into LW's inbox.
"""


NOTE_HARD_WRAPPED = """# From RSC - ACTION: one wrapped question

2026-09-19 0800 local. Broadcast to all five.

**Nothing in your tree was changed.**

## Body

Do you want the shared lock namespace kept exactly as it is, or would
you rather we re-pin it at version two before anybody else adopts
it?

## Reply

Into RSC's inbox.
"""


NOTE_ASKING_FOR_AN_ACTION = """# From RC - ACTION: please remove a file

2026-09-19 0700 local. Broadcast to all five.

**Nothing in your tree was changed.**

## Body

Delete ops/responder.py from your tree and say so in one line.

## Reply

Into RC's inbox.
"""


@pytest.fixture()
def channel(tmp_path: Path):
    """An inbox, a drafts directory and a seen-set path, all under ``tmp_path``.

    Nothing here touches the real channel or the real records. That is not
    politeness: ``ops/inbox_watch.py`` records that its two state files were
    once written by tests that injected only half a path, and a record that is
    write-only until something finally reads it fails silently for as long as
    nobody reads it.
    """
    inbox = tmp_path / "moon_sync_inbox"
    inbox.mkdir()
    state = tmp_path / "runtime" / "inbox_seen.json"
    state.parent.mkdir(parents=True)

    def place(name: str, text: str) -> Path:
        path = inbox / name
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    class Channel:
        pass

    handle = Channel()
    handle.inbox = inbox
    handle.drafts = inbox / responder.DRAFTS_DIRNAME
    handle.state = state
    handle.place = place
    return handle


def _run(channel, **kwargs):
    return responder.run(
        inbox=channel.inbox, drafts=channel.drafts, state=channel.state, **kwargs
    )


# ---------------------------------------------------------------------------
# the runner cannot send
# ---------------------------------------------------------------------------


class TestTheRunnerCannotSend:
    """``ops.outbox.deliver`` must not be reachable from this module."""

    def test_no_module_level_import_names_the_outbox(self):
        tree = ast.parse(responder.SOURCE_PATH.read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                imported.append(base)
                imported.extend(f"{base}.{alias.name}" for alias in node.names)
        offenders = [name for name in imported if "outbox" in name]
        assert not offenders, f"the runner imports the outbox: {offenders}"

    def test_importing_the_runner_does_not_load_the_outbox(self):
        probe = (
            "import sys; sys.path.insert(0, r'"
            + str(REPO_ROOT)
            + "'); import ops.responder; "
            "print('ops.outbox' in sys.modules)"
        )
        out = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.stdout.strip() == "False", (
            "importing ops.responder pulled ops.outbox into sys.modules; "
            "the send path must not be reachable at all"
        )

    def test_the_word_deliver_is_not_called_anywhere_in_the_runner(self):
        tree = ast.parse(responder.SOURCE_PATH.read_text(encoding="utf-8"))
        called: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            if isinstance(target, ast.Name):
                called.append(target.id)
            elif isinstance(target, ast.Attribute):
                called.append(target.attr)
        assert "deliver" not in called, "the runner calls something named deliver"

    def test_no_dynamic_import_machinery_is_used_anywhere_in_the_runner(self):
        """No ``importlib``, ``__import__``, ``eval``, ``exec`` or ``getattr``.

        WHAT THIS CAN SEE: a NAME. It walks the AST for the builtins that turn
        a string into a module or an attribute, and for an import of
        ``importlib`` or ``subprocess``. ``re.compile`` is an ``Attribute``
        rather than a bare ``Name``, so the module's own regex compilation does
        not trip it.

        WHAT IT CANNOT SEE: the same capability reached some other way. This is
        still a claim about the SOURCE TEXT. It exists so the cheapest dynamic
        route fails two tests rather than none;
        :class:`TestTheRunnerCannotSendAtRUNTIME` is the guard that does not
        depend on how a name was spelled.
        """
        tree = ast.parse(responder.SOURCE_PATH.read_text(encoding="utf-8"))
        forbidden = {"__import__", "eval", "exec", "compile", "getattr", "importlib"}
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in forbidden:
                offenders.append(node.id)
            elif isinstance(node, ast.Import):
                offenders.extend(
                    alias.name
                    for alias in node.names
                    if alias.name.split(".")[0] in {"importlib", "subprocess"}
                )
            elif isinstance(node, ast.ImportFrom):
                base = (node.module or "").split(".")[0]
                if base in {"importlib", "subprocess"}:
                    offenders.append(node.module or "")
        assert not offenders, f"the runner reaches for dynamic machinery: {offenders}"


# ---------------------------------------------------------------------------
# the runner cannot send - measured on the RUN, not on the source text
# ---------------------------------------------------------------------------


#: A probe that runs the responder under :func:`sys.addaudithook` and prints
#: what the interpreter actually did. It is written to ``tmp_path`` and run in
#: a subprocess so the hook is installed BEFORE ``ops.responder`` is imported -
#: an audit hook cannot be removed once added, and this one must see the import
#: of the module under test.
#:
#: WHY AN AUDIT HOOK AND NOT A BETTER STATIC CHECK. A static check is a claim
#: about the source TEXT, and the module name in
#: ``importlib.import_module("ops." + "out" + "box")`` is not in the source
#: text at all. The interpreter, though, must OPEN a file to get at
#: ``ops/outbox.py`` or its cached bytecode, and must compile or exec what it
#: read, and each of those raises an audit event carrying the real path. That
#: is the property no static check can have.
#:
#: MEASURED, because the obvious event is the wrong one: the ``import`` audit
#: event is raised by the ``import`` statement and by ``__import__``, and is
#: NOT raised by ``importlib.import_module``, which calls the import bootstrap
#: directly. Probed on this machine 2026-09-20 - a concatenated
#: ``import_module`` call produced NO ``import`` event and four events naming
#: ``ops/outbox.py`` and its ``.pyc``. The file-level events are therefore the
#: load-bearing ones and ``import`` is the cheap extra.
AUDIT_PROBE = r"""
import json
import os
import sys

REPO, INBOX, DRAFTS, STATE = sys.argv[1:5]

#: Only events worth reporting are kept: anything naming the outbox, and any
#: WRITE. Keeping every read would be tens of thousands of stdlib opens.
KEPT = []
TOTAL = [0]
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
        TOTAL[0] += 1
        if event == "import":
            row = ["import", str(_arg(args, 0)), False]
        elif event == "open":
            target = _arg(args, 0)
            write = _is_write(_arg(args, 1), _arg(args, 2))
            # os.fdopen re-opens a descriptor, so the event carries the fd
            # number and no path at all. It is labelled rather than dropped:
            # the os.open that produced that descriptor was itself audited,
            # WITH its real path, so the path evidence is not lost.
            kind = "open-fd" if isinstance(target, int) else "open"
            row = [kind, str(target), write]
        elif event == "compile":
            row = ["compile", str(_arg(args, 1)), False]
        elif event == "exec":
            row = ["exec", str(getattr(_arg(args, 0), "co_filename", "")), False]
        elif event == "os.rename":
            row = ["os.rename", str(_arg(args, 1)), True]
        elif event in ("subprocess.Popen", "os.system", "socket.connect"):
            row = [event, str(_arg(args, 0)), True]
        else:
            return
        if row[2] or "outbox" in row[1].lower():
            KEPT.append(row)
    except Exception:
        pass


sys.addaudithook(_hook)
sys.path.insert(0, REPO)

from ops import responder  # noqa: E402

result = responder.run(
    inbox=responder.Path(INBOX),
    drafts=responder.Path(DRAFTS),
    state=responder.Path(STATE),
)
RECORDING[0] = False
print(
    json.dumps(
        {
            "events": KEPT,
            "audited": TOTAL[0],
            "outbox_modules": sorted(m for m in sys.modules if "outbox" in m),
            "drafted": [row.name for row in result.drafted],
            "status": result.status,
        }
    )
)
"""


def _audit_probe(tmp_path: Path, note_name: str, note_text: str) -> dict:
    """Run the responder in a subprocess under an audit hook; return its JSON.

    Nothing here touches the real ``moon_sync_inbox/`` or ``ops/runtime/``:
    the inbox, the drafts directory and the watcher's seen-set path are all
    under ``tmp_path`` and all three are passed to :func:`ops.responder.run`
    explicitly, so no default path is ever consulted.

    ``ops/`` has NO ``__init__.py`` and none is added here. It is a namespace
    package, so putting the repository root on ``sys.path`` is all a bare
    interpreter needs for ``from ops import responder`` - which is what
    ``tests/conftest.py`` arranges for the suite and what the probe does for
    itself out of its first argument. The subprocess also runs with ``-B`` so
    importing the runner writes no ``.pyc``, which keeps the write-event list
    down to writes this module chose to make.
    """
    inbox = tmp_path / "probe_inbox"
    inbox.mkdir()
    (inbox / note_name).write_text(note_text, encoding="utf-8", newline="\n")
    drafts = inbox / responder.DRAFTS_DIRNAME
    state = tmp_path / "probe_runtime" / "inbox_seen.json"
    state.parent.mkdir(parents=True)

    script = tmp_path / "audit_probe.py"
    script.write_text(AUDIT_PROBE, encoding="ascii", newline="\n")
    out = subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            str(REPO_ROOT),
            str(inbox),
            str(drafts),
            str(state),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(out.stdout.strip().splitlines()[-1])
    payload["drafts_dir"] = drafts
    return payload


class TestTheRunnerCannotSendAtRUNTIME:
    """The send guard, measured on the RUN rather than on the source text.

    WHY THIS CLASS EXISTS. An adversarial pass on 2026-09-20 defeated all three
    guards in :class:`TestTheRunnerCannotSend` at once with two lines inserted
    into :func:`ops.responder.run`::

        _mod = importlib.import_module("ops." + "out" + "box")
        _fn = getattr(_mod, "deli" + "ver")

    and the suite stayed green at 50 passed. The AST import walk found no
    import node because the module name is concatenated at run time; the
    ``sys.modules`` probe covers IMPORT TIME and not a lazy import inside a
    function; and the call walk records a ``Call.func`` that is a ``Name`` or
    an ``Attribute``, which ``getattr(...)(...)`` is neither.

    WHAT THE STATIC CHECKS CAN AND CANNOT SEE: they are claims about the SOURCE
    TEXT of ``ops/responder.py``. They catch the cheap, honest cases - an
    import line, a call to something spelled ``deliver`` - and they cannot
    catch a name that never appears in the source.

    WHAT THIS CHECK CAN AND CANNOT SEE: it is a claim about ONE RUN. It sees
    every file the interpreter opened, renamed, compiled or executed during
    that run, however the name was spelled, because an audit hook sits below
    name resolution. It cannot see a path this particular run did not take - a
    branch that only fires on a note shape the fixture does not carry. The two
    are complementary and neither replaces the other.
    """

    def test_a_real_run_never_touches_the_outbox(self, tmp_path):
        payload = _audit_probe(
            tmp_path, "2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS
        )
        assert payload["drafted"], (
            "the probe wrote no draft, so it proved nothing about a real run"
        )
        offenders = [row for row in payload["events"] if "outbox" in row[1].lower()]
        assert not offenders, f"the run reached the outbox: {offenders}"
        assert payload["outbox_modules"] == [], payload["outbox_modules"]

    def test_a_real_run_writes_only_inside_the_drafts_directory(self, tmp_path):
        payload = _audit_probe(
            tmp_path, "2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS
        )
        drafts = payload["drafts_dir"]
        strays = []
        placed = []
        for kind, target, is_write in payload["events"]:
            if not is_write:
                continue
            # A descriptor re-open carries an fd number and no path. The
            # os.open behind it was audited with its real path, so skipping
            # this row loses no evidence.
            if kind == "open-fd":
                continue
            # Bytecode caching is the interpreter's own write and not this
            # module's. The subprocess runs with -B so this exemption should
            # never fire; it is written down rather than relied upon.
            if "__pycache__" in target:
                continue
            try:
                inside = drafts in Path(target).parents
            except (OSError, ValueError):
                inside = False
            (placed if inside else strays).append([kind, target])
        assert not strays, f"the run wrote outside the drafts directory: {strays}"
        assert placed, (
            "no write with a path was audited at all, so this check passed "
            "vacuously rather than by observing where the writes landed"
        )


# ---------------------------------------------------------------------------
# where the drafts live
# ---------------------------------------------------------------------------


class TestTheDraftsDirectoryIsInsideTheIgnoredChannel:
    def test_the_default_drafts_directory_sits_under_the_channel(self):
        drafts = responder.default_drafts_dir()
        assert drafts.name == responder.DRAFTS_DIRNAME
        assert drafts.parent.name == "moon_sync_inbox"

    def test_git_agrees_the_drafts_directory_is_ignored(self):
        probe = subprocess.run(
            ["git", "check-ignore", "-v", "moon_sync_inbox/_drafts/probe.md"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert probe.returncode == 0, (
            "git does not ignore the drafts directory; a draft is derived from "
            "a gitignored channel and must never become committable"
        )
        assert "moon_sync_inbox/" in probe.stdout


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


class TestExtractionReadsTheNoteAndNotOnlyTheFilename:
    def test_the_sender_comes_from_the_heading_when_they_disagree(self):
        facts = responder.extract_facts(
            "2026-09-19-2310-from-ZZ-REVIEW-mislabelled.md", NOTE_FROM_CS
        )
        assert facts.sender == "CS"
        assert facts.sender_source == "heading"

    def test_the_sender_falls_back_to_the_filename_when_the_heading_is_absent(self):
        facts = responder.extract_facts(
            "2026-09-19-2310-from-CS-REVIEW-no-heading.md", "no heading here at all\n"
        )
        assert facts.sender == "CS"
        assert facts.sender_source == "filename"

    def test_the_classification_prefix_is_measured(self):
        facts = responder.extract_facts("2026-09-19-2310-from-CS-x.md", NOTE_FROM_CS)
        assert facts.classification == "REVIEW"

    def test_an_unclassified_note_says_so_rather_than_guessing(self):
        facts = responder.extract_facts(
            "2026-09-19-from-CS-plain.md", "# From CS: no class here\n\nbody\n"
        )
        assert facts.classification == ""

    def test_the_subject_and_the_timestamp_are_taken_from_the_note(self):
        facts = responder.extract_facts("2026-09-19-2310-from-CS-x.md", NOTE_FROM_CS)
        assert facts.subject == "the watcher cap and two questions for LL"
        assert facts.timestamp == "2026-09-19 2310"

    def test_the_reply_target_is_taken_from_the_notes_own_reply_section(self):
        facts = responder.extract_facts("2026-09-19-2310-from-CS-x.md", NOTE_FROM_CS)
        assert facts.reply_target == "Into CS's inbox as a note named from-LL, please."

    def test_a_note_with_no_reply_section_reports_an_absent_target(self):
        facts = responder.extract_facts(
            "2026-09-19-from-CS-x.md", "# From CS - FYI: nothing\n\nbody\n"
        )
        assert facts.reply_target == ""


class TestQuestionExtraction:
    def test_a_question_mark_sentence_is_extracted(self):
        found = responder.extract_questions(NOTE_FROM_CS)
        texts = [q.text for q in found]
        assert "Does your watcher cap its stdout listing the same way?" in texts

    def test_an_imperative_with_no_question_mark_is_extracted(self):
        found = responder.extract_questions(NOTE_FROM_CS)
        texts = [q.text for q in found]
        assert "Confirm the cap you use in one line." in texts
        detection = {q.text: q.detection for q in found}
        assert detection["Confirm the cap you use in one line."] == "imperative"

    def test_a_hard_wrapped_question_is_extracted_whole(self):
        found = responder.extract_questions(NOTE_HARD_WRAPPED)
        texts = [q.text for q in found]
        assert any(
            text.startswith("Do you want the shared lock namespace")
            and text.endswith("before anybody else adopts it?")
            for text in texts
        ), texts

    def test_a_question_mark_inside_a_fenced_block_is_not_a_question(self):
        """A fenced block is a QUOTATION of machinery, not an ask.

        Added after the non-vacuity probe removed the fence handling and every
        test in this class stayed green - no fixture had a fence in it, so the
        guard was untested rather than passing.
        """
        note = (
            "# From RC - FYI: a command\n\n"
            "2026-09-19 0600 local. Broadcast to all five.\n\n"
            "**Nothing in your tree was changed.**\n\n"
            "## Body\n\n"
            "Run this:\n\n"
            "```\n"
            "Does the hook fire?\n"
            "Confirm the hook fired.\n"
            "```\n\n"
            "## Reply\n\nInto RC's inbox.\n"
        )
        texts = [q.text for q in responder.extract_questions(note)]
        assert not any("Does the hook fire?" in text for text in texts), texts
        assert not any(text.startswith("Confirm the hook fired") for text in texts), texts
        assert any(text.startswith("Run this") for text in texts), texts

    def test_a_bolded_imperative_is_extracted(self):
        """A request verb behind a Markdown bold marker still reaches rule two.

        MEASURED, not imagined. The adversarial pass of 2026-09-20 read five
        real notes by hand and found ``**Say it explicitly, not by silence.**``
        missed for one mechanical reason: ``_REQUEST_VERB`` is anchored with a
        caret and the list-marker strip removed a leading dash but not a
        leading ``**``, so the verb ``say`` - which is in the list - never
        reached the test. The fixture below is that note's own shape, bullet
        and trailing prose included.
        """
        note = (
            "# From RSC - REVIEW: the ask\n\n"
            "2026-09-20 1747 local. Broadcast to all five.\n\n"
            "**Nothing in your tree was changed.**\n\n"
            "## 4. The ask\n\n"
            "- **Say it explicitly, not by silence.** A responder exchange\n"
            "  means automated notes with no human in the loop.\n\n"
            "## Reply\n\nInto RSC's inbox.\n"
        )
        found = responder.extract_questions(note)
        texts = [q.text for q in found]
        assert "**Say it explicitly, not by silence.**" in texts, texts
        detection = {q.text: q.detection for q in found}
        assert detection["**Say it explicitly, not by silence.**"] == "imperative"

    def test_the_quoted_text_keeps_the_markers_it_was_written_with(self):
        """The emphasis strip is for the TEST, never for the quotation.

        A draft quotes the sender's own sentence. Removing their markdown would
        make the quotation not byte-verbatim, and this module's whole claim is
        that it restates nothing.
        """
        note = (
            "# From RSC - REVIEW: the ask\n\n"
            "2026-09-20 1747 local. Broadcast to all five.\n\n"
            "## Body\n\n"
            "- **Confirm the cap you use.** Nothing else.\n\n"
            "## Reply\n\nInto RSC's inbox.\n"
        )
        texts = [q.text for q in responder.extract_questions(note)]
        assert "**Confirm the cap you use.**" in texts, texts
        assert "Confirm the cap you use." not in texts, texts

    def test_a_question_mark_inside_a_heading_is_extracted(self):
        """A heading can carry the ask, and this one used to be invisible.

        MEASURED 2026-09-20: a 34,807-byte REVIEW note addressed to this
        project yielded ZERO extracted questions, and both of its literal
        question marks sat in level-three headings that ``_paragraphs``
        consumed as section labels and never scanned.
        """
        note = (
            "# From RC - FYI: a heading that asks\n\n"
            "2026-09-19 0600 local. Broadcast to all five.\n\n"
            "### Does the hook fire on a fresh clone?\n\n"
            "We did not check.\n\n"
            "## Reply\n\nInto RC's inbox.\n"
        )
        found = responder.extract_questions(note)
        texts = [q.text for q in found]
        assert "Does the hook fire on a fresh clone?" in texts, texts
        detection = {q.text: q.detection for q in found}
        assert detection["Does the hook fire on a fresh clone?"] == "question-mark"

    def test_a_heading_that_answers_its_own_question_is_not_an_ask(self):
        """A heading is ONE unit and is never sentence-split.

        The live shape this protects against, measured on the channel:
        ``### Is 5401 s a real ceiling on hold duration? NO. It is a ceiling on
        RC's SAMPLE.`` The sender asked and answered in the same breath, so
        there is nothing for us to answer. Splitting headings into sentences
        would have reported the first half as an open ask.

        It also keeps rule TWO off headings entirely, which matters because
        every note on this channel ends with a ``## Reply`` heading and
        ``reply`` is in the request-verb list - scanning headings as prose
        would have invented one false question per note, on every note.
        """
        note = (
            "# From RC - FYI: a heading that answers itself\n\n"
            "2026-09-19 0600 local. Broadcast to all five.\n\n"
            "### Is the hook a real guard? NO. It is a reminder.\n\n"
            "We measured it.\n\n"
            "## Reply\n\nInto RC's inbox.\n"
        )
        texts = [q.text for q in responder.extract_questions(note)]
        assert not any(text.startswith("Is the hook") for text in texts), texts
        assert "Reply" not in texts, texts

    def test_the_extractor_names_what_it_cannot_see(self):
        """The docstring must list the limits, INCLUDING the measured ones.

        Four of these were added on 2026-09-20 after an adversarial pass
        measured precision and recall on five real notes and found limits the
        docstring did not declare. A caveat stated in a findings file and
        dropped from the artifact is a lie in the artifact.
        """
        doc = responder.extract_questions.__doc__ or ""
        assert "CANNOT SEE" in doc
        for limit in (
            "rhetorical",
            "statement",
            "quoted",
            "recipient",
            # measured limits, 2026-09-20
            "heading",
            "conditional",
            "emphasis",
            "wrapped",
        ):
            assert limit in doc.lower(), f"the docstring does not name {limit!r}"


# ---------------------------------------------------------------------------
# the draft itself
# ---------------------------------------------------------------------------


class TestTheDraftFollowsTheChannelSkeleton:
    def test_the_heading_carries_our_code_and_a_class_and_a_subject(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        text = Path(result.drafted[0].path).read_text(encoding="utf-8")
        first = text.splitlines()[0]
        assert first.startswith("# From LL - DRAFT: ")
        assert "the watcher cap and two questions for LL" in first

    def test_the_no_write_claim_is_present(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        text = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "**Nothing in your tree was changed.**" in text

    def test_a_reply_section_is_present_and_carries_the_notes_target(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        text = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "\n## Reply\n" in text
        assert "Into CS's inbox as a note named from-LL, please." in text

    def test_every_extracted_question_appears_in_the_draft(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        text = Path(result.drafted[0].path).read_text(encoding="utf-8")
        for question in responder.extract_questions(NOTE_FROM_CS):
            assert question.text in text

    def test_the_draft_is_7_bit_ascii(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        Path(result.drafted[0].path).read_bytes().decode("ascii")

    def test_a_note_name_with_a_space_still_produces_a_writable_draft(self, channel):
        """``safe_label`` renders an unshowable byte as ``?``, illegal on NTFS."""
        channel.place("2026-09-19 2310 from CS REVIEW spaced.md", NOTE_FROM_CS)
        result = _run(channel)
        assert result.drafted and result.drafted[0].written is True
        assert "?" not in result.drafted[0].name
        assert Path(result.drafted[0].path).is_file()

    def test_one_draft_per_thread(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        channel.place("2026-09-19-0900-from-LW-REVIEW-figures.md", NOTE_WITH_FIGURES)
        result = _run(channel)
        paths = {row.path for row in result.drafted}
        assert len(paths) == len(result.drafted) == 2


class TestADraftIsObviouslyUnfinished:
    def test_every_question_carries_an_unanswered_placeholder(self, channel):
        """Structural, NOT a count.

        The first version of this test counted :data:`responder.UNANSWERED`
        occurrences and required at least one per question. The non-vacuity
        probe on 2026-09-20 deleted the marker from every question BULLET and
        the test stayed green, because the boilerplate and the ANSWER lines
        alone cleared the count. A count is a claim about a total; this needs a
        claim about each question, so it asks for each question's own bullet
        and its own answer line.
        """
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        lines = Path(result.drafted[0].path).read_text(encoding="utf-8").splitlines()
        questions = responder.extract_questions(NOTE_FROM_CS)
        assert questions, "the fixture must actually ask something"
        for question in questions:
            where = [i for i, line in enumerate(lines) if question.text in line]
            assert where, f"the draft dropped the question {question.text!r}"
            index = where[0]
            bullet = lines[index - 1]
            assert bullet.startswith(f"- {responder.UNANSWERED}"), (
                f"the bullet introducing {question.text!r} is not marked "
                f"unanswered: {bullet!r}"
            )
            answers = [
                line
                for line in lines[index + 1 : index + 4]
                if line.strip().startswith("ANSWER:")
            ]
            assert answers, f"no ANSWER line follows {question.text!r}"
            assert responder.UNANSWERED in answers[0], answers[0]

    def test_the_draft_says_in_its_own_words_that_it_is_unsent(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        text = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "UNSENT DRAFT" in text


class TestADraftNeverInventsANumber:
    """The whole reason the draft-only shape was chosen - see the module docstring."""

    def test_no_digit_run_in_a_draft_is_absent_from_the_note(self, channel):
        channel.place("2026-09-19-0900-from-LW-REVIEW-figures.md", NOTE_WITH_FIGURES)
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        invented = responder.invented_numbers(
            draft, [NOTE_WITH_FIGURES, "2026-09-19-0900-from-LW-REVIEW-figures.md"]
        )
        assert invented == [], f"the draft invented these numbers: {invented}"

    def test_a_figure_the_note_does_not_ask_about_is_omitted_entirely(self, channel):
        """The OMIT half of the requirement - see the sibling test for the QUOTE half."""
        channel.place("2026-09-19-0900-from-LW-REVIEW-figures.md", NOTE_WITH_FIGURES)
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "1,416" not in draft
        assert "12.4" not in draft

    def test_a_figure_inside_the_ask_is_quoted_verbatim_with_its_source(self, channel):
        """The QUOTE half. Verbatim, separators intact, attributed to the note."""
        name = "2026-09-19-0905-from-LW-REVIEW-figure-in-ask.md"
        channel.place(name, NOTE_FIGURE_IN_QUESTION)
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "1,416" in draft, "the figure was dropped from the quotation"
        assert "12.4" in draft
        # Attributed: the draft names the note it quotes and the section.
        assert name in draft
        assert "What we measured" in draft

    def test_a_quoted_figure_keeps_its_separators(self, channel):
        channel.place(
            "2026-09-19-0905-from-LW-REVIEW-figure-in-ask.md", NOTE_FIGURE_IN_QUESTION
        )
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "1416" not in draft, "the figure was restated without its separator"

    def test_a_decimal_is_never_rounded(self, channel):
        channel.place(
            "2026-09-19-0905-from-LW-REVIEW-figure-in-ask.md", NOTE_FIGURE_IN_QUESTION
        )
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        tokens = responder.number_tokens(draft)
        assert "12" not in tokens, "12.4 was rounded to 12"
        assert "12.4" in tokens

    def test_the_number_tokenizer_keeps_separators_together(self):
        assert responder.number_tokens("1,416 tests in 12.4s") == ["1,416", "12.4"]

    def test_invented_numbers_reports_a_recomputed_figure(self):
        invented = responder.invented_numbers("we make that 1416", ["1,416 tests"])
        assert invented == ["1416"]

    def test_the_runner_REFUSES_to_write_a_draft_carrying_an_invented_number(
        self, channel, monkeypatch
    ):
        """The refusal is defence in depth, and it had never been exercised.

        The renderer does not currently produce an invented number, so the
        branch that refuses one was dead against every fixture here: the
        non-vacuity probe deleted the refusal and this class stayed green. A
        guard that has never run is not a guard, so the renderer is replaced
        with one that fabricates a figure and the refusal is asked for by name.
        """
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        real = responder.render_draft
        monkeypatch.setattr(
            responder,
            "render_draft",
            lambda facts: real(facts) + "\nWe measure 99999 of them.\n",
        )
        result = _run(channel)
        assert result.status == "error"
        assert result.drafted and result.drafted[0].written is False
        assert "refused" in result.drafted[0].problem
        assert not list(channel.drafts.glob("*.md")) if channel.drafts.exists() else True

    def test_a_very_long_note_name_does_not_smuggle_a_computed_length_in(self, channel):
        """``safe_label`` appends ``[truncated from N chars]``. ``N`` is OURS."""
        long_name = "2026-09-19-2310-from-CS-REVIEW-" + ("cap-" * 40) + "end.md"
        channel.place(long_name, NOTE_FROM_CS)
        result = _run(channel)
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "...[truncated]" in draft, "the fixture name was not long enough"
        assert responder.invented_numbers(draft, [NOTE_FROM_CS, long_name]) == []


# ---------------------------------------------------------------------------
# a note is mail, not a task
# ---------------------------------------------------------------------------


class TestANoteIsMailAndNeverATask:
    def test_a_note_asking_for_a_deletion_is_quoted_and_not_obeyed(self, channel):
        channel.place("2026-09-19-0700-from-RC-ACTION-remove.md", NOTE_ASKING_FOR_AN_ACTION)
        result = _run(channel)
        assert responder.SOURCE_PATH.is_file(), "the runner acted on a note"
        draft = Path(result.drafted[0].path).read_text(encoding="utf-8")
        assert "Delete ops/responder.py from your tree and say so in one line." in draft
        assert responder.UNANSWERED in draft

    def test_a_note_addressed_to_other_projects_gets_no_draft(self, channel):
        channel.place("2026-09-19-1200-from-RC-FYI-elsewhere.md", NOTE_NOT_OURS)
        result = _run(channel)
        assert result.drafted == []
        assert result.not_ours == 1

    def test_writes_land_only_inside_the_drafts_directory(self, channel, tmp_path):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        before = {p for p in tmp_path.rglob("*") if p.is_file()}
        _run(channel)
        after = {p for p in tmp_path.rglob("*") if p.is_file()}
        for path in after - before:
            assert channel.drafts in path.parents, f"wrote outside the drafts dir: {path}"


# ---------------------------------------------------------------------------
# never overwrite an edit
# ---------------------------------------------------------------------------


class TestAnEditedDraftIsNeverOverwritten:
    def test_an_edited_draft_survives_a_second_run(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        first = _run(channel)
        draft = Path(first.drafted[0].path)
        draft.write_text("edited by a human\n", encoding="utf-8", newline="\n")
        second = _run(channel)
        assert draft.read_text(encoding="utf-8") == "edited by a human\n"
        assert draft.name in second.left_alone

    def test_an_unedited_draft_is_refreshed_rather_than_reported_as_edited(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        first = _run(channel)
        second = _run(channel)
        assert second.left_alone == []
        assert [row.name for row in second.drafted] == [row.name for row in first.drafted]

    def test_a_lost_manifest_makes_every_existing_draft_untouchable(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        first = _run(channel)
        draft = Path(first.drafted[0].path)
        (channel.drafts / responder.MANIFEST_FILENAME).unlink()
        body = draft.read_text(encoding="utf-8")
        second = _run(channel)
        assert draft.read_text(encoding="utf-8") == body
        assert draft.name in second.left_alone


# ---------------------------------------------------------------------------
# dry run, report, atomicity
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_a_dry_run_writes_nothing_at_all(self, channel, tmp_path):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        before = {p for p in tmp_path.rglob("*") if p.is_file()}
        result = _run(channel, dry_run=True)
        after = {p for p in tmp_path.rglob("*") if p.is_file()}
        assert before == after
        assert not channel.drafts.exists()
        assert result.dry_run is True

    def test_a_dry_run_still_says_what_it_would_write(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel, dry_run=True)
        assert len(result.drafted) == 1
        assert result.drafted[0].written is False
        assert "would write" in result.format().lower()


class TestPendingReport:
    def test_the_report_is_plain_text_and_names_every_pending_draft(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        report = responder.pending_report(drafts=channel.drafts)
        report.encode("ascii")
        assert result.drafted[0].name in report
        assert "DRAFTS PENDING" in report

    def test_an_absent_drafts_directory_reports_none_rather_than_failing(self, tmp_path):
        report = responder.pending_report(drafts=tmp_path / "nope")
        report.encode("ascii")
        assert "DRAFTS PENDING" in report


class TestAtomicWrites:
    def test_a_draft_is_written_through_a_temporary_then_replaced(self, channel, monkeypatch):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        seen: list[tuple[str, str]] = []
        real = Path.replace

        def spy(self, target):
            seen.append((self.name, Path(target).name))
            return real(self, target)

        monkeypatch.setattr(Path, "replace", spy)
        result = _run(channel)
        names = [row.name for row in result.drafted]
        assert any(dst in names for _src, dst in seen), seen
        for src, _dst in seen:
            assert src.startswith(responder.TEMP_PREFIX), src

    def test_no_temporary_file_is_left_behind(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        _run(channel)
        leftovers = [p.name for p in channel.drafts.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []


class TestNewnessComesFromTheWatchersOwnSeenSet:
    def test_an_acknowledged_note_is_not_redrafted(self, channel):
        name = "2026-09-19-2310-from-CS-REVIEW-cap.md"
        path = channel.place(name, NOTE_FROM_CS)
        from ops import inbox_watch

        digest = inbox_watch.digest_of(path.read_bytes())
        inbox_watch.save_seen({(name, digest)}, channel.state)
        result = _run(channel)
        assert result.drafted == []
        assert result.already_seen == 1

    def test_the_runner_does_not_write_the_watchers_records(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        _run(channel)
        assert not channel.state.exists()
        assert not (channel.state.parent / "inbox_reported.json").exists()


class TestManifest:
    def test_the_manifest_is_json_and_records_the_digest_it_wrote(self, channel):
        channel.place("2026-09-19-2310-from-CS-REVIEW-cap.md", NOTE_FROM_CS)
        result = _run(channel)
        payload = json.loads(
            (channel.drafts / responder.MANIFEST_FILENAME).read_text(encoding="utf-8")
        )
        rows = payload["drafts"]
        assert result.drafted[0].name in rows
        assert len(rows[result.drafted[0].name]["digest"]) == 64
