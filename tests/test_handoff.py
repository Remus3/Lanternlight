"""The hand-off writer - ROADMAP OPS-32.

`LL-NEXT-SESSION.txt` is the highest-variance artifact in this tree: rewritten
every session, never reviewed before it is written, quoting freely from whatever
that session happened to touch. It is also TRACKED, and this repository is
public, so the distance between "hand-off written" and "hand-off world-readable"
is one push.

Until this module existed the file was written by a session following a
document. The guarantee was "the ritual says to, and a test says the ritual says
to" - a real guarantee about the DOCUMENT and none at all about the FILE.

What this file pins:

1. **The refusal happens BEFORE anything is written.** That is the load-bearing
   half. A refusal that leaves a partial file, or a truncated one, has not
   refused - so these tests assert the target is ABSENT or BYTE-UNCHANGED after
   a refusal, never merely that an exception was raised.
2. **One engine.** The refusal runs `lanternlight.redact`'s own detectors -
   the plain pass, the encoded pass and the literal-joined operator pass - not a
   second private notion of what counts as an identifier. A rule added to the
   scrubber must start guarding the hand-off automatically.
3. **No exemption list.** If a legitimate hand-off is refused, the hand-off is
   what changes. There is deliberately no way to force a write past a finding.

Every identifier in this file is SYNTHETIC and assembled at runtime from parts
that are not themselves identifiers, per `LL-0175`: writing the real value into
the test that guards it is the exact failure this project made three times in
three days.
"""

import base64
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight.redact import RedactionError  # noqa: E402
from ops import handoff  # noqa: E402

CLEAN = """LANTERNLIGHT - NEXT SESSION PROMPT

Resume from disk. Read CLAUDE.md, then ROADMAP.md and docs/LEDGER.md.
Suite and collected counts are in the wrap commit's message; re-run rather
than quoting them.
"""


def _synthetic_steamid() -> str:
    """A SteamID64-shaped value that is nobody's."""
    return "7656119" + "8" + "012345678"


def _synthetic_userid() -> str:
    """A GSDK-shaped userId that is nobody's.

    The KEY is assembled from parts rather than written whole, because the
    tree-wide guard scans this file's BYTES and would otherwise report this
    fixture as a finding. That is the practice `lanternlight.redact` asks for
    with synthetic values, and it is safe here for the reason it is never safe
    with a real one: there is no value to protect.
    """
    return "user" + "Id: " + ("ab12cd34" * 4)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# the happy path - a writer exists at all
# ---------------------------------------------------------------------------


def test_a_clean_handoff_is_written_and_the_path_is_returned(tmp_path):
    target = tmp_path / "LL-NEXT-SESSION.txt"
    written = handoff.write_handoff(CLEAN, target)
    assert written == target
    assert target.read_text(encoding="utf-8") == CLEAN


def test_the_write_goes_through_a_temporary_file_and_leaves_none_behind(tmp_path):
    target = tmp_path / "LL-NEXT-SESSION.txt"
    handoff.write_handoff(CLEAN, target)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["LL-NEXT-SESSION.txt"]


def test_an_existing_handoff_is_replaced_rather_than_appended(tmp_path):
    target = tmp_path / "LL-NEXT-SESSION.txt"
    target.write_text("an older hand-off\n", encoding="utf-8")
    handoff.write_handoff(CLEAN, target)
    assert target.read_text(encoding="utf-8") == CLEAN


# ---------------------------------------------------------------------------
# the refusal - the half that matters
# ---------------------------------------------------------------------------


def test_an_identifier_refuses_the_write_and_leaves_NO_FILE_AT_ALL(tmp_path):
    target = tmp_path / "LL-NEXT-SESSION.txt"
    text = CLEAN + f"\nThe account was {_synthetic_steamid()}.\n"
    with pytest.raises(RedactionError):
        handoff.write_handoff(text, target)
    assert not target.exists(), "a refusal that creates the file has not refused"
    assert list(tmp_path.iterdir()) == [], "a refusal must leave no temporary behind"


def test_an_identifier_leaves_an_EXISTING_handoff_byte_unchanged(tmp_path):
    target = tmp_path / "LL-NEXT-SESSION.txt"
    target.write_text("the previous session's hand-off, still good\n", encoding="utf-8")
    before = _digest(target)
    with pytest.raises(RedactionError):
        handoff.write_handoff(CLEAN + f"\n{_synthetic_userid()}\n", target)
    assert _digest(target) == before


def test_an_ENCODED_identifier_is_refused_too(tmp_path):
    """Encoding is not redaction. The tracked-file guard decodes; so does this."""
    target = tmp_path / "LL-NEXT-SESSION.txt"
    blob = base64.b64encode(_synthetic_steamid().encode("ascii")).decode("ascii")
    with pytest.raises(RedactionError):
        handoff.write_handoff(CLEAN + f"\nstate blob: {blob}\n", target)
    assert not target.exists()


def test_an_operator_git_identity_is_refused(tmp_path):
    """Derived at runtime, never written down - `LL-0175`.

    The identity is asked for from the redactor rather than typed here, so this
    test cannot become the place the value gets published. If this machine has
    no git identity to derive, the test says so rather than passing vacuously.
    """
    identities = handoff.operator_identities()
    if not identities:
        pytest.skip("no git identity derivable here; nothing to plant")
    target = tmp_path / "LL-NEXT-SESSION.txt"
    with pytest.raises(RedactionError):
        handoff.write_handoff(CLEAN + f"\nauthored by {identities[0]}\n", target)
    assert not target.exists()


def test_the_operator_VALUE_pass_fires_on_a_shape_the_email_rule_declines():
    """The value half, proven with a SYNTHETIC identity injected at the call.

    This test exists because a mutation SURVIVED without it: deleting the
    operator pass entirely left every test in this file green, since the
    address planted by the test above is already caught by the plain EMAIL
    rule. A pass whose deletion changes nothing is not covered, whatever the
    count says. The value below sits at an RFC 2606 reserved domain, which the
    EMAIL shape rule declines by design - so only the value half can reach it.
    """
    token = "ll-handoff-probe@" + "example.com"
    findings = handoff.check(f"handed over by {token}\n", identities=(token,))
    assert findings
    # The plain operator pass is what reports an OFFSET and calls a contiguous
    # value what it is. Without this, deleting that pass leaves the suite green:
    # the literal-joined pass runs the same value half over joined text, which
    # for a contiguous value is the same text, so it silently covers for it -
    # and mislabels the finding as split across literals. Measured by mutation;
    # the pass SURVIVED twice before this assertion existed.
    assert any("an operator identifier" in f and "at offset" in f for f in findings)
    assert handoff.check(f"handed over by {token}\n") == [], (
        "a reserved domain is declined by the SHAPE rule, which is exactly "
        "what makes this value able to exercise the VALUE half alone"
    )


def test_the_literal_joined_pass_fires_on_a_value_split_across_literals():
    """`LL-0175`: any sweep for a value is a claim about that value's contiguity."""
    token = "ll-handoff-split@" + "example.com"
    # The '+' matters: the folder joins literals the way PYTHON does, so
    # implicit adjacency alone is not what it looks for. Measured here rather
    # than assumed - the first version of this test used adjacency and passed
    # for the wrong reason, by finding nothing.
    split = '"ll-handoff-split@exam" + "ple.com"'
    assert handoff.check(f"handed over by {split}\n", identities=(token,))
    assert handoff.check(f"handed over by {split}\n") == []


def test_a_non_ascii_character_is_refused_before_the_write(tmp_path):
    """The hand-off is tracked, and this repository is 7-bit ASCII everywhere.

    Refusing here turns a commit-time failure into a write-time one, at the
    moment the session still has the context to fix it.
    """
    target = tmp_path / "LL-NEXT-SESSION.txt"
    with pytest.raises(handoff.HandoffRefused):
        # Built with chr() rather than typed: this repository's own ASCII guard
        # scans this file, so a literal em dash here would be a test that
        # cannot live in the tree it tests.
        handoff.write_handoff(CLEAN + "\nan em dash " + chr(0x2014) + " here\n", target)
    assert not target.exists()


def test_an_exotic_line_separator_is_still_scanned_for_non_ascii(tmp_path):
    """`str.splitlines()` CONSUMES U+0085, U+2028 and U+2029 as line breaks.

    Found by this item's adversarial pass: an ASCII scan built on splitlines
    never inspects the separator itself, so those three characters walked
    straight onto disk while the check reported clean. The tree-wide guard
    scans BYTES and catches them, so this module was LOOSER than the guard it
    claims to stand in front of - which is the worst shape for a gate to have,
    since it teaches the reader that passing here means passing there.
    """
    target = tmp_path / "LL-NEXT-SESSION.txt"
    for code_point in (0x85, 0x2028, 0x2029):
        text = "ok\ntail" + chr(code_point) + "more\n"
        assert handoff.check(text), f"U+{code_point:04X} was not seen"
        with pytest.raises(handoff.HandoffRefused):
            handoff.write_handoff(text, target)
        assert not target.exists()


def test_the_reported_line_counts_newlines_and_nothing_else(tmp_path):
    """A form feed is not a line break for this purpose, and said so wrongly.

    Any character the scanner treats as a line break shifts every position
    after it, and a finding that sends the reader to the wrong line is worse
    than one that sends them only to the file.
    """
    findings = handoff.check("first\x0csecond " + chr(0x2014) + "\n")
    assert findings
    assert "line 1" in findings[0]


def test_a_write_into_a_directory_that_does_not_exist_yet_succeeds(tmp_path):
    target = tmp_path / "nested" / "deeper" / "LL-NEXT-SESSION.txt"
    handoff.write_handoff(CLEAN, target)
    assert target.read_text(encoding="utf-8") == CLEAN


def test_a_failing_write_leaves_no_temporary_behind(tmp_path):
    """The refusal path was clean; the OS-ERROR path was not.

    Found by the adversarial pass: a target that is a directory raises after
    the temporary exists, so a `.tmp` was left in the repository root - an
    untracked orphan that this project's own lane guard then fails on, from a
    write that never landed.
    """
    target = tmp_path / "LL-NEXT-SESSION.txt"
    target.mkdir()
    with pytest.raises(OSError):
        handoff.write_handoff(CLEAN, target)
    assert [p.name for p in tmp_path.iterdir()] == ["LL-NEXT-SESSION.txt"]


def test_the_refusal_message_says_how_many_findings_it_did_not_list(tmp_path):
    text = CLEAN + "".join(f"\nline {n} {_synthetic_steamid()}" for n in range(12))
    with pytest.raises(handoff.HandoffRefused) as caught:
        handoff.write_handoff(text, tmp_path / "LL-NEXT-SESSION.txt")
    message = str(caught.value)
    assert "more" in message
    # And it must LIST some of them. Asserting only the tail count left a
    # mutation alive that listed nothing at all: a refusal saying "and 14 more"
    # with no first fourteen is a refusal the reader cannot act on.
    assert "at offset" in message
    assert message.count(";") >= 4


def test_the_findings_name_the_label_and_the_line(tmp_path):
    findings = handoff.check(CLEAN + f"\nThe account was {_synthetic_steamid()}.\n")
    assert findings
    assert any("LONG_ID" in f or "STEAMID64" in f for f in findings)


def test_a_clean_string_produces_no_findings():
    assert handoff.check(CLEAN) == []


def test_there_is_no_way_to_force_a_write_past_a_finding():
    """Criterion 5: no exemption list, and no override argument either.

    An exemption list is a gate disarmed one word at a time. A `force=True`
    is the same thing in one word.
    """
    import inspect

    signature = inspect.signature(handoff.write_handoff)
    banned = {"force", "allow", "skip_checks", "exempt", "ignore"}
    assert not banned & set(signature.parameters)
    source = Path(handoff.__file__).read_text(encoding="utf-8")
    assert "EXEMPT" not in source.upper().replace("EXEMPTION", "")


# ---------------------------------------------------------------------------
# the ritual has to CALL it, not describe it
# ---------------------------------------------------------------------------


def test_the_wrap_command_names_the_writer():
    text = (REPO_ROOT / ".claude" / "commands" / "done.md").read_text(encoding="utf-8")
    assert "ops/handoff.py" in text or "ops.handoff" in text


def test_the_cli_writes_from_a_file_and_reports_the_target(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text(CLEAN, encoding="utf-8")
    target = tmp_path / "LL-NEXT-SESSION.txt"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ops" / "handoff.py"),
            "--from-file",
            str(source),
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert target.read_text(encoding="utf-8") == CLEAN


def test_the_cli_exits_non_zero_and_writes_nothing_on_a_refusal(tmp_path):
    """A CLI that refused but exited 0 would be a ritual step nobody notices."""
    source = tmp_path / "draft.txt"
    source.write_text(CLEAN + f"\n{_synthetic_steamid()}\n", encoding="utf-8")
    target = tmp_path / "LL-NEXT-SESSION.txt"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ops" / "handoff.py"),
            "--from-file",
            str(source),
            "--target",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert not target.exists()
    output = completed.stdout + completed.stderr
    # Each of these was untested until the adversarial pass neutered the whole
    # reporting block and the suite stayed green: an uncaught traceback also
    # exits non-zero and also contains the word REFUSED, so the original
    # assertion passed off the exception rather than off the handler.
    assert "Traceback" not in output, "a refusal must be reported, not raised"
    assert completed.returncode == 1
    assert "hand-off REFUSED, nothing written:" in output
    assert "LONG_ID" in output or "STEAMID64" in output
    assert "no exemption list" in output


def test_the_cli_can_check_without_writing(tmp_path):
    source = tmp_path / "draft.txt"
    source.write_text(CLEAN, encoding="utf-8")
    target = tmp_path / "LL-NEXT-SESSION.txt"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "ops" / "handoff.py"),
            "--from-file",
            str(source),
            "--target",
            str(target),
            "--check-only",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert not target.exists(), "--check-only must not write"


# ---------------------------------------------------------------------------
# the live file, which is the one that actually gets pushed
# ---------------------------------------------------------------------------


def test_the_handoff_currently_on_disk_would_be_accepted_by_this_writer():
    """A guard nobody has pointed at the real artifact is a guard about fixtures.

    If this goes red, the hand-off is what changes - never this test, and never
    the detectors. That is criterion 5.
    """
    live = REPO_ROOT / "LL-NEXT-SESSION.txt"
    if not live.exists():
        pytest.skip("no hand-off on disk yet")
    assert handoff.check(live.read_text(encoding="utf-8")) == []


def test_the_default_target_is_the_repo_root_handoff():
    assert handoff.DEFAULT_TARGET == REPO_ROOT / "LL-NEXT-SESSION.txt"


def test_the_module_is_not_importing_a_second_pii_engine():
    """One engine, not two - acceptance criterion 2.

    A private copy of the patterns is how a guard drifts behind the thing it
    guards. The module may only get its detectors from `lanternlight.redact`.
    """
    source = Path(handoff.__file__).read_text(encoding="utf-8")
    assert "lanternlight.redact" in source
    for smell in ("7656119", "re.compile(r\"[0-9]{17}", "SteamID64 = "):
        assert smell not in source


def test_json_payloads_are_not_special_cased(tmp_path):
    """A hand-off is prose. Nothing here parses it, so nothing can be fooled."""
    target = tmp_path / "LL-NEXT-SESSION.txt"
    payload = json.dumps({"note": _synthetic_steamid()})
    with pytest.raises(RedactionError):
        handoff.write_handoff(CLEAN + "\n" + payload + "\n", target)
    assert not target.exists()
