"""Reporting the inbox must never acknowledge it - ``ops/inbox_watch.py``.

WHY THIS FILE EXISTS
--------------------
``scan()`` used to write the seen set on its own last step, so LOOKING was
acknowledging. Everything that looks then consumes mail: the ``SessionStart``
hook, the manual ``python ops/inbox_watch.py`` that ``CLAUDE.md`` prescribes
when no report appeared, a probe, a one-off check. Whichever of them ran second
was told "nothing new" about mail the first run had only PRINTED - possibly
into a transcript nobody kept, possibly into a subagent that exited a second
later. On a channel whose entire premise is that continuity lives on disk, that
is the module's own failure mode wearing its own report's voice.

The split is: a plain run REPORTS; :func:`ops.inbox_watch.acknowledge_inbox`
and ``--acknowledge`` are the only things that move the watermark.

DETECTION IS THE WRONG SHAPE, AND THAT IS PINNED HERE TOO
---------------------------------------------------------
The tempting alternative is to work out what kind of caller this is - a real
session, a subagent, a probe - and acknowledge only for the "real" one. A
sibling warned against it and the warning holds on its own merits: every such
detector is a guess about the runtime, and it fails OPEN. Failing open here
means silently eating mail, which is the exact defect being fixed. An explicit
argument cannot be wrong about what it was asked to do.

So one test below reads the module's own source and asserts it consults no
environment at all. That is a coarse instrument on purpose: it is not trying to
prove the current logic is right, it is trying to make the wrong shape hard to
add back without noticing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ops import inbox_watch

MODULE_SOURCE = Path(inbox_watch.__file__).read_text(encoding="utf-8")


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    inbox = tmp_path / "moon_sync_inbox"
    inbox.mkdir()
    return inbox, tmp_path / "runtime" / "inbox_seen.json"


def _write(inbox: Path, name: str, body: str) -> Path:
    target = inbox / name
    target.write_text(body, encoding="utf-8", newline="\n")
    return target


def _new_names(result) -> set[str]:
    out: set[str] = set()
    for group in result.groups:
        if group.is_new:
            out.update(group.names)
    return out


class TestAPlainRunReportsAndChangesNothing:
    def test_the_seen_set_is_not_written_at_all(self, tmp_path: Path) -> None:
        inbox, state = _tree(tmp_path)
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")

        result = inbox_watch.scan(inbox=inbox, state=state)

        assert result.acknowledged is False
        assert not state.exists(), (
            "a report-only run wrote the acknowledged set, so looking at the "
            "inbox is still the same act as marking it read"
        )

    def test_the_same_mail_is_reported_again_on_every_plain_run(self, tmp_path: Path) -> None:
        inbox, state = _tree(tmp_path)
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")

        first = inbox_watch.scan(inbox=inbox, state=state)
        second = inbox_watch.scan(inbox=inbox, state=state)
        third = inbox_watch.scan(inbox=inbox, state=state)

        assert _new_names(first) == {"note.md"}
        assert _new_names(second) == {"note.md"}, (
            "the second look was handed 'nothing new' over mail that had only "
            "been printed - this is the defect, stated as a test"
        )
        assert _new_names(third) == {"note.md"}

    def test_the_report_says_out_loud_that_it_acknowledged_nothing(self, tmp_path: Path) -> None:
        inbox, state = _tree(tmp_path)
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")

        rendered = inbox_watch.render(inbox_watch.scan(inbox=inbox, state=state))

        assert "REPORTED only" in rendered
        assert "--acknowledge" in rendered, (
            "the reader is told the mail is still unread but not how to clear it"
        )


class TestAcknowledgementIsExplicit:
    def test_the_callable_marks_what_it_read_as_read(self, tmp_path: Path) -> None:
        inbox, state = _tree(tmp_path)
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")

        acked = inbox_watch.acknowledge_inbox(inbox=inbox, state=state)
        after = inbox_watch.scan(inbox=inbox, state=state)

        assert acked.acknowledged is True
        assert _new_names(acked) == {"note.md"}, "the acknowledging run still reports"
        assert state.is_file(), "the acknowledged set was never written"
        assert _new_names(after) == set()

    def test_the_acknowledging_report_says_so(self, tmp_path: Path) -> None:
        inbox, state = _tree(tmp_path)
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")

        rendered = inbox_watch.render(
            inbox_watch.acknowledge_inbox(inbox=inbox, state=state)
        )

        assert "ACKNOWLEDGED" in rendered
        assert "REPORTED only" not in rendered

    def test_the_flag_is_what_switches_the_command_line(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        inbox, state = _tree(tmp_path)
        reported = tmp_path / "runtime" / "inbox_reported.json"
        _write(inbox, "note.md", "# From RC - hello\n\nsent to LL.\n")
        argv = ["--inbox", str(inbox), "--state", str(state), "--reported", str(reported)]

        assert inbox_watch.main(argv) == 0
        capsys.readouterr()
        assert not state.exists(), "the bare command acknowledged"

        assert inbox_watch.main(argv) == 0
        assert "note.md" in capsys.readouterr().out, "the second bare run hid the note"

        assert inbox_watch.main([*argv, "--acknowledge"]) == 0
        capsys.readouterr()
        assert state.is_file()

        assert inbox_watch.main(argv) == 0
        assert "nothing new" in capsys.readouterr().out.lower()


class TestTheDecisionIsNeverInferredFromTheRuntime:
    def test_the_module_consults_no_environment_to_decide(self) -> None:
        """No detector, by construction rather than by review.

        A detector for "is this a real session" fails open, and failing open
        here means eating mail. This does not prove the logic is right; it
        makes the wrong shape hard to reintroduce quietly.
        """
        for token in ("os.environ", "os.getenv", "getenv(", "CLAUDECODE"):
            assert token not in MODULE_SOURCE, (
                f"{token!r} appears in ops/inbox_watch.py - acknowledgement must be "
                "asked for explicitly, never guessed from the runtime"
            )

    def test_acknowledgement_defaults_to_off_in_the_signature(self) -> None:
        import inspect

        default = inspect.signature(inbox_watch.scan).parameters["acknowledge"].default
        assert default is False, (
            "a default of True would make every hook, probe and test an "
            "acknowledgement again"
        )
