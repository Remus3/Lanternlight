"""The automatic acknowledge trigger tied to the operator's own turn - ``OPS-41``.

WHY THIS FILE EXISTS
--------------------
``OPS-33`` split reporting from acknowledgement so that nothing consumes mail by
merely looking at it. That was the right property and it left a real gap: after
it, NOTHING in this tree acknowledged anything automatically, so every read
required somebody to type ``python ops/inbox_watch.py --acknowledge`` by hand,
for ever, or the same backlog re-reported as unread at every session start.

``OPS-41`` closes that gap with a trigger the harness fires on the operator's
own turn - a ``UserPromptSubmit`` hook - rather than on ``SessionStart``, which
fires for subagents too and cannot tell the two apart.

WHAT IS PINNED HERE, AND WHY EACH ONE MATTERS
---------------------------------------------
The trigger must FAIL CLOSED. Every refusal path below - a payload that is not
JSON, a payload for a different hook event, a payload with no session id - must
acknowledge nothing at all, because acknowledging is irreversible from the
report's point of view: mail marked read is mail the next session never sees
listed. A detector that guesses and fails OPEN is the exact defect ``OPS-33``
removed, and re-adding it through a new door would be no better.

It must also acknowledge ONCE per session. ``UserPromptSubmit`` fires on every
message, not only the first; without the once-per-session rule a note that
lands in the middle of a session would be marked read by the operator's next
message before any report had ever printed it.

And it must leave EVIDENCE. ``OPS-41``'s acceptance asks for proof that the
hook fires for the operator and does NOT fire for a subagent, and a hook whose
only effect is an acknowledgement leaves nothing behind that separates "it did
not fire" from "it fired and refused". So every invocation - accepted or
refused - appends one bounded record to a trace file. The trace is what makes
both halves of that question answerable from disk afterwards.

The trace never records the prompt text. The operator's own words are the one
field in the payload with no bearing on the decision, and this repository is
public; a runtime file that accumulates them is a liability with no upside.
"""

from __future__ import annotations

import json
from pathlib import Path

from ops import inbox_watch

SETTINGS = Path(inbox_watch.REPO_ROOT) / ".claude" / "settings.json"


def _tree(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Build a scratch inbox plus the three runtime records, none of them created."""
    inbox = tmp_path / "moon_sync_inbox"
    inbox.mkdir()
    (inbox / "note.md").write_text("# To LL\n\nA note for Lanternlight.\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    return inbox, runtime / "seen.json", runtime / "reported.json", runtime / "trace.json"


def _payload(session: str = "session-one", event: str = "UserPromptSubmit") -> str:
    return json.dumps(
        {
            "hook_event_name": event,
            "session_id": session,
            "prompt": "what is next",
            "cwd": str(inbox_watch.REPO_ROOT),
        }
    )


def _call(raw: str, tmp_path: Path, parts=None) -> tuple[str, tuple[Path, Path, Path, Path]]:
    inbox, state, reported, trace = parts or _tree(tmp_path)
    decision = inbox_watch.on_prompt_submit(
        raw, inbox=inbox, state=state, reported=reported, trace=trace
    )
    return decision, (inbox, state, reported, trace)


class TestTheOperatorsTurnAcknowledges:
    def test_a_prompt_submit_payload_acknowledges_the_inbox(self, tmp_path: Path) -> None:
        decision, (_, state, _, _) = _call(_payload(), tmp_path)

        assert decision == inbox_watch.TRIGGER_ACKNOWLEDGED, (
            "a UserPromptSubmit payload is the operator's own turn and must "
            f"acknowledge, got {decision!r}"
        )
        assert state.is_file(), "the acknowledged-set file was never written"
        payload = json.loads(state.read_text(encoding="utf-8"))
        names = [row[0] for row in payload["seen"]]
        assert "note.md" in names, f"the note was not marked read: {names!r}"

    def test_a_second_prompt_in_the_same_session_acknowledges_nothing(
        self, tmp_path: Path
    ) -> None:
        """Once per session, not once per message.

        Mail that lands mid-session must survive to be REPORTED at the next
        session start rather than being eaten by the operator's next keystroke.
        """
        decision, parts = _call(_payload(), tmp_path)
        assert decision == inbox_watch.TRIGGER_ACKNOWLEDGED
        inbox, state, _, _ = parts

        (inbox / "later.md").write_text("# To LL\n\nArrived mid-session.\n", encoding="utf-8")
        before = state.read_bytes()

        again, _ = _call(_payload(), tmp_path, parts)

        assert again == inbox_watch.TRIGGER_ALREADY, (
            f"the second prompt of the same session must not acknowledge, got {again!r}"
        )
        assert state.read_bytes() == before, "the second prompt rewrote the acknowledged set"
        payload = json.loads(state.read_text(encoding="utf-8"))
        names = [row[0] for row in payload["seen"]]
        assert "later.md" not in names, "mail that arrived mid-session was silently eaten"

    def test_a_different_session_acknowledges_again(self, tmp_path: Path) -> None:
        decision, parts = _call(_payload("session-one"), tmp_path)
        assert decision == inbox_watch.TRIGGER_ACKNOWLEDGED
        inbox, state, _, _ = parts
        (inbox / "later.md").write_text("# To LL\n\nArrived later.\n", encoding="utf-8")

        again, _ = _call(_payload("session-two"), tmp_path, parts)

        assert again == inbox_watch.TRIGGER_ACKNOWLEDGED, (
            f"a new session's first prompt must acknowledge, got {again!r}"
        )
        names = [row[0] for row in json.loads(state.read_text(encoding="utf-8"))["seen"]]
        assert "later.md" in names, "the new session did not pick up the newer note"


class TestEveryRefusalPathAcknowledgesNothing:
    def test_a_different_hook_event_is_refused(self, tmp_path: Path) -> None:
        """Wiring this to SessionStart by mistake must not silently work.

        SessionStart fires for subagents too. If this entrypoint accepted any
        event it was handed, a misplaced registration would reintroduce exactly
        the accidental acknowledgement OPS-33 removed.
        """
        decision, (_, state, _, _) = _call(_payload(event="SessionStart"), tmp_path)

        assert decision == inbox_watch.TRIGGER_WRONG_EVENT, (
            f"a SessionStart payload must be refused, got {decision!r}"
        )
        assert not state.exists(), "a non-prompt event acknowledged the inbox"

    def test_a_payload_that_is_not_json_is_refused(self, tmp_path: Path) -> None:
        decision, (_, state, _, _) = _call("not json at all {", tmp_path)

        assert decision == inbox_watch.TRIGGER_UNREADABLE, (
            f"an unparseable payload must be refused, got {decision!r}"
        )
        assert not state.exists(), "an unparseable payload acknowledged the inbox"

    def test_an_empty_payload_is_refused(self, tmp_path: Path) -> None:
        decision, (_, state, _, _) = _call("", tmp_path)

        assert decision == inbox_watch.TRIGGER_UNREADABLE, (
            f"an empty payload must be refused, got {decision!r}"
        )
        assert not state.exists(), "an empty payload acknowledged the inbox"

    def test_a_payload_without_a_session_id_is_refused(self, tmp_path: Path) -> None:
        """No session id means no way to tell the first message from the tenth.

        Acknowledging anyway would make every message an acknowledgement, which
        is the once-per-session rule failing open.
        """
        raw = json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})
        decision, (_, state, _, _) = _call(raw, tmp_path)

        assert decision == inbox_watch.TRIGGER_NO_SESSION, (
            f"a payload with no session id must be refused, got {decision!r}"
        )
        assert not state.exists(), "a payload with no session id acknowledged the inbox"


class TestTheTraceIsTheEvidence:
    def test_every_invocation_is_recorded_including_refusals(self, tmp_path: Path) -> None:
        """Both halves of OPS-41's acceptance are read off this file.

        "The hook did not fire for the subagent" and "the hook fired and
        refused" are different facts. Only a record written on the refusal path
        as well as the accepting one can tell them apart afterwards.
        """
        parts = _tree(tmp_path)
        _call(_payload(event="SessionStart"), tmp_path, parts)
        _call(_payload(), tmp_path, parts)
        trace = parts[3]

        assert trace.is_file(), "no trace file was written"
        rows, note = inbox_watch.load_trace(trace)
        assert note == "", f"the trace did not load cleanly: {note}"
        assert [row["decision"] for row in rows] == [
            inbox_watch.TRIGGER_WRONG_EVENT,
            inbox_watch.TRIGGER_ACKNOWLEDGED,
        ], f"the trace did not record both invocations in order: {rows!r}"
        assert rows[0]["event"] == "SessionStart", (
            "the trace must name the event it refused, or a silent trace and an "
            f"absent hook look the same: {rows[0]!r}"
        )
        assert all(row["at"] for row in rows), "a trace row carries no timestamp"

    def test_the_trace_never_records_the_prompt_text(self, tmp_path: Path) -> None:
        raw = json.dumps(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "session-one",
                "prompt": "CANARY-OPERATOR-PROMPT-TEXT",
            }
        )
        _, (_, _, _, trace) = _call(raw, tmp_path)

        body = trace.read_text(encoding="utf-8")
        assert "CANARY-OPERATOR-PROMPT-TEXT" not in body, (
            "the operator's prompt text reached a runtime file; it has no bearing "
            "on the decision and this repository is public"
        )

    def test_the_trace_is_bounded(self, tmp_path: Path) -> None:
        """A file a hook appends to on every keystroke must not grow for ever."""
        parts = _tree(tmp_path)
        limit = inbox_watch.TRACE_LIMIT
        for index in range(limit + 5):
            _call(_payload(session=f"s{index}", event="SessionStart"), tmp_path, parts)

        rows, _ = inbox_watch.load_trace(parts[3])
        assert len(rows) == limit, f"the trace grew past its bound: {len(rows)} rows"
        assert rows[-1]["session"] == f"s{limit + 4}", (
            f"the bound dropped the NEWEST rows instead of the oldest: {rows[-1]!r}"
        )

    def test_the_trace_survives_a_corrupt_file_without_acknowledging_less(
        self, tmp_path: Path
    ) -> None:
        parts = _tree(tmp_path)
        trace = parts[3]
        trace.parent.mkdir(parents=True, exist_ok=True)
        trace.write_text("{ not json", encoding="utf-8")

        empty, note = inbox_watch.load_trace(trace)
        assert empty == [], "a corrupt trace yielded rows"
        assert note, (
            "a corrupt trace was recovered silently - an empty trace and a lost "
            "one must not read the same, or the evidence is worthless"
        )

        decision, _ = _call(_payload(), tmp_path, parts)

        assert decision == inbox_watch.TRIGGER_ACKNOWLEDGED, (
            f"a corrupt trace must not stop the trigger working, got {decision!r}"
        )
        rows, after = inbox_watch.load_trace(trace)
        assert after == "", f"the trace was not rewritten cleanly: {after}"
        assert [row["decision"] for row in rows] == [inbox_watch.TRIGGER_ACKNOWLEDGED]

    def test_the_default_trace_path_is_under_the_gitignored_runtime_directory(self) -> None:
        path = inbox_watch.default_trace_path()

        assert path.parent == Path(inbox_watch.REPO_ROOT) / "ops" / "runtime", (
            f"the trace must live beside the other runtime records, got {path}"
        )
        assert not path.parent.exists() or path.parent.is_dir()


class TestTheCommandLineEntrypoint:
    def test_on_prompt_prints_nothing_and_exits_zero(self, tmp_path, capsys, monkeypatch) -> None:
        """A UserPromptSubmit hook's stdout is injected into the session context.

        Anything this prints becomes text the model reads as though it were
        part of the turn, so the acknowledging path must be silent. It must also
        exit 0: a UserPromptSubmit hook exiting 2 BLOCKS the operator's prompt.
        """
        inbox, state, reported, trace = _tree(tmp_path)
        monkeypatch.setattr("sys.stdin", _Stdin(_payload()))

        code = inbox_watch.main(
            [
                "--on-prompt",
                "--inbox",
                str(inbox),
                "--state",
                str(state),
                "--reported",
                str(reported),
                "--trace",
                str(trace),
            ]
        )

        out = capsys.readouterr()
        assert code == 0, f"the hook entrypoint must always exit 0, got {code}"
        assert out.out == "", f"the hook printed into the session context: {out.out!r}"
        assert state.is_file(), "the CLI path did not acknowledge"

    def test_on_prompt_stays_silent_and_zero_on_a_broken_payload(
        self, tmp_path, capsys, monkeypatch
    ) -> None:
        inbox, state, reported, trace = _tree(tmp_path)
        monkeypatch.setattr("sys.stdin", _Stdin("{{{"))

        code = inbox_watch.main(
            [
                "--on-prompt",
                "--inbox",
                str(inbox),
                "--state",
                str(state),
                "--reported",
                str(reported),
                "--trace",
                str(trace),
            ]
        )

        out = capsys.readouterr()
        assert code == 0, f"a broken payload must not fail the hook, got {code}"
        assert out.out == "", f"the hook printed into the session context: {out.out!r}"
        assert not state.exists(), "a broken payload acknowledged through the CLI"

    def test_a_bare_run_still_reports_and_never_acknowledges(self, tmp_path, capsys) -> None:
        """The regression that OPS-33 fixed must not come back through this door."""
        inbox, state, reported, _ = _tree(tmp_path)
        argv = ["--inbox", str(inbox), "--state", str(state), "--reported", str(reported)]

        assert inbox_watch.main(argv) == 0
        assert "note.md" in capsys.readouterr().out
        assert not state.exists(), "a bare report run acknowledged the inbox"


class _Stdin:
    """Minimal stand-in for ``sys.stdin`` - the hook only ever reads it whole."""

    def __init__(self, body: str) -> None:
        self._body = body

    def read(self) -> str:
        return self._body


class TestTheHookIsRegistered:
    def test_the_settings_file_parses(self) -> None:
        """A single backslash in a Windows path makes this file invalid JSON.

        Nothing warns about it: no hook registers and the session runs on
        silently. So the parse itself is the assertion.
        """
        json.loads(SETTINGS.read_text(encoding="utf-8"))

    def test_a_user_prompt_submit_hook_runs_this_entrypoint(self) -> None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        entries = settings.get("hooks", {}).get("UserPromptSubmit", [])
        commands = [
            hook.get("command", "")
            for entry in entries
            for hook in entry.get("hooks", [])
            if hook.get("type") == "command"
        ]

        assert commands, "no UserPromptSubmit hook is registered in .claude/settings.json"
        assert any("inbox_watch.py" in cmd and "--on-prompt" in cmd for cmd in commands), (
            f"the UserPromptSubmit hook does not run the trigger entrypoint: {commands!r}"
        )

    def test_the_registered_command_uses_forward_slashes_only(self) -> None:
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        for event, entries in settings.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    assert "\\" not in command, (
                        f"the {event} hook command carries a backslash, which is the "
                        f"invalid-JSON trap this repository has already hit: {command!r}"
                    )

    def test_the_registered_command_does_not_hardcode_the_interpreter_path(self) -> None:
        """A hardcoded interpreter carries the account name and breaks a fresh clone."""
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        entries = settings.get("hooks", {}).get("UserPromptSubmit", [])
        for entry in entries:
            for hook in entry.get("hooks", []):
                command = hook.get("command", "")
                assert ":/" not in command.split()[0], (
                    f"the interpreter is an absolute path: {command!r}"
                )
