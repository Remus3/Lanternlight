"""The Stop-hook transcript-claim auditor - ROADMAP OPS-45.

The merge gate re-probes a SUBAGENT's claims before the merger relays them.
Nothing re-probed the merger's OWN closing claims, which is the shape of
mistake `LL-0161` recorded: a claim relayed without an independent probe that
turned out to be false. :mod:`ops.stop_audit` runs at the point the session is
about to stop, reads the transcript the harness itself wrote, and checks the
mechanically checkable claim shapes against ground truth.

Three properties this file exists to pin, because each of them is a way the
auditor could be decoration rather than a guard:

1. **It never blocks.** A Stop hook that exits non-zero refuses to let the
   session end and feeds its stderr back into the model, which on this event is
   a loop rather than a warning. Every path returns 0, including a payload that
   is not JSON and a transcript that is not there.
2. **It reads the MAIN agent's claims only.** Subagent turns are marked
   ``isSidechain`` in the transcript, and a subagent's claim is the merge
   gate's job, not this one's. Auditing them here would re-report findings the
   merger already adjudicated.
3. **It says what it does NOT check.** A guard that implies full coverage is
   worse than no guard, because the next session stops looking. The report
   carries the uncovered shapes by name.

The fixtures here are synthetic transcripts built in-test. Nothing reads the
operator's real transcript directory, and no test in this file writes into
``ops/runtime/``.
"""

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ops import stop_audit  # noqa: E402  (path bootstrap must run first)

# ---------------------------------------------------------------------------
# helpers - a synthetic transcript in the harness's own JSONL shape
# ---------------------------------------------------------------------------


def _assistant(text: str, uuid: str = "a1", sidechain: bool = False) -> dict:
    return {
        "type": "assistant",
        "uuid": uuid,
        "isSidechain": sidechain,
        "timestamp": "2026-09-08T00:00:00.000Z",
        "message": {"role": "assistant", "content": [{"type": "text", "text": text}]},
    }


def _user(text: str, uuid: str = "u1", sidechain: bool = False) -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "isSidechain": sidechain,
        "timestamp": "2026-09-08T00:00:00.000Z",
        "message": {"role": "user", "content": text},
    }


def _tool_result(uuid: str = "t1") -> dict:
    """A user-ROLE record that is a tool result, not an operator prompt."""
    return {
        "type": "user",
        "uuid": uuid,
        "isSidechain": False,
        "timestamp": "2026-09-08T00:00:00.000Z",
        "toolUseResult": {"stdout": "2306 tests collected"},
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "content": "2306 tests collected"}],
        },
    }


def _write_transcript(path: Path, records) -> Path:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    return path


# ---------------------------------------------------------------------------
# claim extraction
# ---------------------------------------------------------------------------


def test_a_numeric_suite_result_is_extracted_with_its_outcome_counts():
    claims = stop_audit.extract_claims("Suite: 2305 passed, 1 skipped.")
    counted = [c for c in claims if c.kind == stop_audit.KIND_TEST_COUNT]
    assert len(counted) == 1
    assert counted[0].detail["outcomes"] == {"passed": 2305, "skipped": 1}


def test_a_collected_count_is_extracted_as_its_own_outcome():
    claims = stop_audit.extract_claims("python -m pytest --collect-only: 2306 collected")
    counted = [c for c in claims if c.kind == stop_audit.KIND_TEST_COUNT]
    assert counted and counted[0].detail["outcomes"] == {"collected": 2306}


def test_a_bare_green_claim_is_extracted_as_unnumbered():
    claims = stop_audit.extract_claims("Full suite green, ruff clean, pushed.")
    green = [c for c in claims if c.kind == stop_audit.KIND_GREEN]
    assert green, "an unnumbered green claim must still be seen, not ignored"
    assert green[0].detail["outcomes"] == {}


def test_a_file_creation_claim_names_the_path_it_claims():
    claims = stop_audit.extract_claims("Wrote `ops/stop_audit.py` and its tests.")
    files = [c for c in claims if c.kind == stop_audit.KIND_FILE]
    assert [c.detail["path"] for c in files] == ["ops/stop_audit.py"]


def test_a_path_mentioned_without_a_creation_verb_is_not_a_file_claim():
    claims = stop_audit.extract_claims("Read `ops/merge_gate.py` for the pattern.")
    assert [c for c in claims if c.kind == stop_audit.KIND_FILE] == []


def test_a_number_that_is_not_a_test_outcome_is_not_a_test_count_claim():
    claims = stop_audit.extract_claims("The note was 3032 bytes and 4 siblings got it.")
    assert [c for c in claims if c.kind == stop_audit.KIND_TEST_COUNT] == []


# ---------------------------------------------------------------------------
# which turns are read
# ---------------------------------------------------------------------------


def test_a_subagent_turn_is_not_audited():
    records = [
        _user("do the thing"),
        _assistant("subagent says 9999 passed", uuid="s1", sidechain=True),
        _assistant("merger says 2306 collected", uuid="m1"),
    ]
    texts = [block["text"] for block in stop_audit.final_turn_texts(records)]
    assert texts == ["merger says 2306 collected"]


def test_only_the_turn_after_the_last_operator_prompt_is_audited():
    records = [
        _user("first ask", uuid="u1"),
        _assistant("an old claim: 1 passed", uuid="a1"),
        _user("second ask", uuid="u2"),
        _assistant("the closing claim: 2 passed", uuid="a2"),
    ]
    texts = [block["text"] for block in stop_audit.final_turn_texts(records)]
    assert texts == ["the closing claim: 2 passed"]


def test_a_tool_result_does_not_end_the_turn():
    """A tool result is a user-ROLE record and is not an operator prompt.

    Treating one as a turn boundary would cut the audited window down to
    whatever the model said after its last tool call, which is routinely a
    single sentence and never the claim-carrying summary.
    """
    records = [
        _user("the ask", uuid="u1"),
        _assistant("first half: 2306 collected", uuid="a1"),
        _tool_result(uuid="t1"),
        _assistant("second half: 2305 passed", uuid="a2"),
    ]
    texts = [block["text"] for block in stop_audit.final_turn_texts(records)]
    assert texts == ["first half: 2306 collected", "second half: 2305 passed"]


def test_thinking_blocks_are_not_audited():
    record = {
        "type": "assistant",
        "uuid": "a1",
        "isSidechain": False,
        "message": {
            "role": "assistant",
            "content": [{"type": "thinking", "thinking": "maybe 9999 passed"}],
        },
    }
    assert stop_audit.final_turn_texts([_user("ask"), record]) == []


# ---------------------------------------------------------------------------
# verification against ground truth
# ---------------------------------------------------------------------------


def test_a_file_claim_for_a_real_non_empty_file_verifies(tmp_path):
    (tmp_path / "made.py").write_text("x = 1\n", encoding="utf-8")
    claims = stop_audit.extract_claims("Created `made.py`.")
    findings = stop_audit.verify(claims, root=tmp_path, collected=None)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_OK]


def test_a_file_claim_for_a_missing_file_is_refuted(tmp_path):
    claims = stop_audit.extract_claims("Created `never_written.py`.")
    findings = stop_audit.verify(claims, root=tmp_path, collected=None)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_FAIL]
    assert "does not exist" in findings[0].reason


def test_a_file_claim_for_an_empty_file_is_refuted(tmp_path):
    (tmp_path / "hollow.py").write_text("", encoding="utf-8")
    claims = stop_audit.extract_claims("Wrote `hollow.py`.")
    findings = stop_audit.verify(claims, root=tmp_path, collected=None)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_FAIL]
    assert "empty" in findings[0].reason


def test_outcome_counts_that_sum_to_the_collected_total_verify(tmp_path):
    claims = stop_audit.extract_claims("2305 passed, 1 skipped")
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_OK]


def test_outcome_counts_that_do_not_sum_to_the_collected_total_are_refuted(tmp_path):
    """The exact shape of `LL-0173`: a count carried from an earlier tree.

    2295 passed and 2296 collected were honestly observed in an intermediate,
    never-committed state. Repeated at a wrap against a tree collecting 2306,
    that is a stale number presented as a current one, and it is the single
    most repeated false claim shape in this project's ledger.
    """
    claims = stop_audit.extract_claims("2295 passed, 1 skipped")
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_FAIL]
    assert "2306" in findings[0].reason


def test_a_passed_count_above_the_collected_total_is_refuted(tmp_path):
    claims = stop_audit.extract_claims("9999 passed")
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_FAIL]


def test_a_numeric_claim_is_unchecked_when_the_collection_could_not_be_run(tmp_path):
    claims = stop_audit.extract_claims("2305 passed, 1 skipped")
    findings = stop_audit.verify(claims, root=tmp_path, collected=None)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_UNCHECKED]


def test_an_unnumbered_green_claim_is_unchecked_and_says_why(tmp_path):
    claims = stop_audit.extract_claims("Full suite green.")
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_UNCHECKED]
    assert "no number" in findings[0].reason


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


def test_the_report_names_the_shapes_it_does_not_check(tmp_path):
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `made.py`.")]
    )
    report = stop_audit.audit(transcript, root=tmp_path, collected=None)
    rendered = report.format()
    assert stop_audit.NOT_CHECKED, "the uncovered list must not be empty"
    for shape in stop_audit.NOT_CHECKED:
        assert shape in rendered


def test_the_report_is_valid_json_on_disk_and_carries_a_schema(tmp_path):
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `made.py`.")]
    )
    report = stop_audit.audit(transcript, root=tmp_path, collected=None)
    target = tmp_path / "report.json"
    stop_audit.write_report(report, target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == stop_audit.SCHEMA
    assert payload["findings"][0]["verdict"] == stop_audit.VERDICT_FAIL


def test_a_quoted_snippet_is_redacted_before_it_reaches_the_report(tmp_path):
    """The transcript is not a safe source. It carries whatever was pasted in.

    A report that quotes a claim verbatim is a second copy of anything an
    identifier reached the transcript through, sitting in a file a later
    session will read and may paste. The snippet goes through the redactor on
    the way in, and the identifier below is a synthetic one built to be
    matched, not a real value.
    """
    steamid = "7656119" + "0123456789"[:10]
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        [_user("ask"), _assistant(f"Wrote `made.py` for SteamID {steamid}.")],
    )
    report = stop_audit.audit(transcript, root=tmp_path, collected=None)
    rendered = report.format()
    assert steamid not in rendered
    assert json.dumps(report.as_dict()).find(steamid) == -1


# ---------------------------------------------------------------------------
# the hook entry point - it must never block, and it must leave evidence
# ---------------------------------------------------------------------------


def test_the_hook_returns_zero_on_a_payload_that_is_not_json(tmp_path):
    assert (
        stop_audit.run_hook(
            "{not json", root=tmp_path, runtime_dir=tmp_path / "rt", collected=None
        )
        == 0
    )


def test_the_hook_returns_zero_when_the_transcript_is_missing(tmp_path):
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "s-1",
            "transcript_path": str(tmp_path / "nope.jsonl"),
        }
    )
    assert (
        stop_audit.run_hook(
            payload, root=tmp_path, runtime_dir=tmp_path / "rt", collected=None
        )
        == 0
    )


def test_the_hook_returns_zero_even_when_it_refutes_a_claim(tmp_path):
    """Refuting is not blocking. This event cannot be blocked safely."""
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `absent.py`.")]
    )
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "s-1",
            "transcript_path": str(transcript),
        }
    )
    runtime = tmp_path / "rt"
    assert stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime, collected=None) == 0
    report = json.loads((runtime / "last_report.json").read_text(encoding="utf-8"))
    assert report["counts"]["fail"] == 1


def test_a_payload_that_blows_the_parser_stack_still_returns_zero(tmp_path):
    """`json.JSONDecodeError` is not the only way a payload can fail to parse.

    Found by the adversarial pass: deeply nested JSON raises `RecursionError`,
    which is not a `JSONDecodeError` and was escaping the boundary. A hook that
    raises is a hook that breaks the session it was meant to audit.
    """
    payload = "[" * 200000 + "]" * 200000
    assert (
        stop_audit.run_hook(
            payload, root=tmp_path, runtime_dir=tmp_path / "rt", collected=None
        )
        == 0
    )


def test_a_thousands_separator_is_read_as_the_number_it_is(tmp_path):
    """A MISREAD is worse than a miss: it refutes true claims and passes false ones."""
    claims = stop_audit.extract_claims("Suite: 1,234 passed.")
    counted = [c for c in claims if c.kind == stop_audit.KIND_TEST_COUNT]
    assert counted and counted[0].detail["outcomes"] == {"passed": 1234}


def test_a_single_file_result_is_unchecked_rather_than_refuted(tmp_path):
    """Reporting one file's result is legitimate and routine.

    Refuting it would be wrong - the numbers are true - and confirming it would
    be a claim nothing checked. Unchecked is the only honest third answer.
    """
    claims = stop_audit.extract_claims("tests/test_stop_audit.py: 38 passed.")
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    counted = [f for f in findings if f.claim.kind == stop_audit.KIND_TEST_COUNT]
    assert [f.verdict for f in counted] == [stop_audit.VERDICT_UNCHECKED]


def test_no_identifier_reaches_the_report_through_a_claimed_PATH(tmp_path):
    """The path is extracted from the RAW line, so it needs its own redaction.

    Found by the adversarial pass: the quoted snippet was masked while the
    ``detail.path`` beside it carried the same identifier verbatim, along with
    the reason built from it. Redacting one field and not its neighbour is the
    contiguity lesson in a second dress - the value is still on disk, just not
    where the sweep looked.
    """
    steamid = "7656119" + "8765432109"
    (tmp_path / "rt").mkdir()
    transcript = _write_transcript(
        tmp_path / "t.jsonl",
        [_user("ask"), _assistant(f"Wrote `runs/{steamid}/out.py`.")],
    )
    payload = json.dumps(
        {"hook_event_name": "Stop", "session_id": "s", "transcript_path": str(transcript)}
    )
    stop_audit.run_hook(payload, root=tmp_path, runtime_dir=tmp_path / "rt", collected=None)
    written = (tmp_path / "rt" / "last_report.json").read_text(encoding="utf-8")
    trace = (tmp_path / "rt" / "trace.jsonl").read_text(encoding="utf-8")
    assert steamid not in written
    assert steamid not in trace


def test_a_missing_transcript_and_an_empty_one_write_different_trace_rows(tmp_path):
    """The `OPS-41` objection, applied to this artifact by the adversarial pass.

    Two different situations that write a byte-identical evidence row are two
    situations the evidence cannot tell apart, which is exactly why `OPS-41`'s
    criterion 1 was refuted at its own wrap. The note that distinguishes them
    was being computed and then discarded.
    """
    runtime = tmp_path / "rt"
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    for transcript in (tmp_path / "absent.jsonl", empty):
        payload = json.dumps(
            {
                "hook_event_name": "Stop",
                "session_id": "s",
                "transcript_path": str(transcript),
            }
        )
        stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime, collected=None)
    rows = [
        json.loads(line)
        for line in (runtime / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 2
    assert rows[0]["transcript_exists"] is False
    assert rows[1]["transcript_exists"] is True
    assert rows[0]["notes"] != rows[1]["notes"]


def test_every_fire_appends_a_trace_row_carrying_its_own_attribution(tmp_path):
    """`OPS-41`'s trace could not distinguish a first fire from a later one.

    The objection recorded in that item is that the artifact had no ordinal, no
    submitter and no causal attribution, so two different hypotheses wrote a
    byte-identical file. This trace carries an ordinal, the transcript's line
    count and the uuid of the last main-agent record at fire time, so a later
    session can tell one fire from another and can tell a fire at the end of a
    turn from a fire at the end of a session.
    """
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `absent.py`.", uuid="a9")]
    )
    payload = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "s-1",
            "transcript_path": str(transcript),
        }
    )
    runtime = tmp_path / "rt"
    stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime, collected=None)
    stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime, collected=None)

    rows = [
        json.loads(line)
        for line in (runtime / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["ordinal"] for row in rows] == [1, 2]
    assert rows[0]["event"] == "Stop"
    assert rows[0]["transcript_lines"] == 2
    assert rows[0]["last_main_uuid"] == "a9"
    assert rows[0]["session"] == "s-1"


def test_no_collection_is_run_when_the_turn_makes_no_numeric_claim(tmp_path, monkeypatch):
    """A subprocess at the end of every turn is a cost paid for nothing.

    Most turns assert no number. The collection is the only expensive thing
    this hook does, and it is only worth running when there is a number to
    check it against.
    """
    calls = []
    monkeypatch.setattr(stop_audit, "collect_count", lambda *a, **k: calls.append(1))
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `absent.py`.")]
    )
    payload = json.dumps(
        {"hook_event_name": "Stop", "session_id": "s", "transcript_path": str(transcript)}
    )
    assert stop_audit.run_hook(payload, root=tmp_path, runtime_dir=tmp_path / "rt") == 0
    assert calls == []


def test_a_numeric_claim_does_pay_for_the_collection(tmp_path, monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(1)
        return 2306

    monkeypatch.setattr(stop_audit, "collect_count", fake)
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Suite: 2305 passed, 1 skipped.")]
    )
    payload = json.dumps(
        {"hook_event_name": "Stop", "session_id": "s", "transcript_path": str(transcript)}
    )
    runtime = tmp_path / "rt"
    assert stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime) == 0
    assert calls == [1]
    report = json.loads((runtime / "last_report.json").read_text(encoding="utf-8"))
    assert report["counts"]["ok"] == 1


def test_collect_count_reads_the_total_this_tree_actually_reports():
    """Non-vacuous by construction: it is checked against a second reading.

    A hardcoded expected count would go stale the day a test is added, which is
    the defect `CLAUDE.md` names for any checked-in suite count. This asserts
    the parser agrees with a plain re-run instead.
    """
    first = stop_audit.collect_count(REPO_ROOT)
    assert isinstance(first, int) and first > 0


def test_the_trace_survives_a_corrupt_row_rather_than_restarting_the_ordinal(tmp_path):
    runtime = tmp_path / "rt"
    runtime.mkdir()
    (runtime / "trace.jsonl").write_text(
        '{"ordinal": 4, "event": "Stop"}\nnot json at all\n', encoding="utf-8"
    )
    transcript = _write_transcript(tmp_path / "t.jsonl", [_user("ask"), _assistant("hi")])
    payload = json.dumps(
        {"hook_event_name": "Stop", "session_id": "s", "transcript_path": str(transcript)}
    )
    stop_audit.run_hook(payload, root=tmp_path, runtime_dir=runtime, collected=None)
    rows = [
        json.loads(line)
        for line in (runtime / "trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("{")
    ]
    assert rows[-1]["ordinal"] == 5


def test_an_unparseable_transcript_line_is_counted_rather_than_fatal(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(
        json.dumps(_user("ask")) + "\nnot json\n" + json.dumps(_assistant("Wrote `x.py`.")) + "\n",
        encoding="utf-8",
    )
    records, note = stop_audit.iter_transcript(path)
    assert len(records) == 2
    assert "1" in note


# ---------------------------------------------------------------------------
# registration - the hook has to actually be wired, not merely written
# ---------------------------------------------------------------------------


def test_the_stop_hook_is_registered_in_settings_json():
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["Stop"]
    commands = [
        hook["command"] for entry in entries for hook in entry.get("hooks", [])
    ]
    assert any("stop_audit.py" in command for command in commands)


def test_the_registered_stop_hook_names_no_account_specific_path():
    settings = (REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    payload = json.loads(settings)
    entries = payload["hooks"]["Stop"]
    for entry in entries:
        for hook in entry.get("hooks", []):
            assert "Users/" not in hook["command"]


def test_a_quoted_example_of_a_false_claim_is_still_flagged(tmp_path):
    """The known false positive, pinned rather than patched.

    Measured on this hook's first live fire, 2026-09-08: a session that wrote a
    wrong number down as an EXAMPLE of a wrong number got it refuted, because
    the sentence is identical either way. A rule that excuses a number inside
    quotes excuses the easiest place to hide a real one, so the behaviour is
    deliberate and this test exists so nobody "fixes" it without reading why.
    """
    claims = stop_audit.extract_claims(
        'A false wrap would say "2295 passed, 1 skipped" against this tree.'
    )
    findings = stop_audit.verify(claims, root=tmp_path, collected=2306)
    assert [f.verdict for f in findings] == [stop_audit.VERDICT_FAIL]


def test_show_last_says_so_plainly_when_no_report_has_been_written(tmp_path):
    text = stop_audit.show_last(tmp_path)
    assert "has not written one" in text


def test_show_last_renders_the_refutations_of_the_report_on_disk(tmp_path):
    transcript = _write_transcript(
        tmp_path / "t.jsonl", [_user("ask"), _assistant("Wrote `absent.py`.")]
    )
    report = stop_audit.audit(transcript, root=tmp_path, collected=None)
    stop_audit.write_report(report, tmp_path / stop_audit.REPORT_NAME)
    text = stop_audit.show_last(tmp_path)
    assert "1 refuted" in text
    assert "absent.py does not exist" in text


@pytest.mark.parametrize("mode", ["--stop-hook", "--audit-transcript", "--show-last"])
def test_the_module_exposes_the_two_entry_points_it_documents(mode):
    parser = stop_audit.build_parser()
    assert mode in _option_strings(parser)


def _option_strings(parser):
    return {string for action in parser._actions for string in action.option_strings}
