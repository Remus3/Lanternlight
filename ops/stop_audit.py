"""Audit the claims a session made, at the moment it is about to stop.

ROADMAP `OPS-45`. This is the merge gate's missing sibling. `ops/merge_gate.py`
re-probes a SUBAGENT's "done" before the merger relays it; nothing re-probed the
merger's OWN closing claims, which is exactly the mistake `LL-0161` recorded - a
claim relayed without an independent probe that turned out to be false.

The harness writes every session's transcript as JSONL. At the ``Stop`` event it
hands this module the path to that file. We read the main agent's final turn,
pull out the claim shapes this project has actually been burned by, and check
them against ground truth: the filesystem for file claims, a live
``pytest --collect-only`` for numeric suite claims.

WHAT IT CHECKS
    - a numeric suite result ("2305 passed, 1 skipped", "2306 collected"),
      against the count pytest reports for the tree as it stands right now
    - a file creation claim ("wrote ``ops/stop_audit.py``"), against the
      filesystem

WHAT IT DOES NOT CHECK - see :data:`NOT_CHECKED`, which is printed in every
report. A guard that implies full coverage is worse than no guard, because the
next session stops looking.

THREE RULES THIS MODULE DOES NOT BEND

1. **It never blocks.** A ``Stop`` hook that exits non-zero refuses to let the
   session end and feeds its stderr back into the model. On this event that is
   a loop, not a warning. :func:`run_hook` returns 0 on every path, including a
   payload that is not JSON, a transcript that is not there, and its own
   unexpected exceptions.
2. **It reads the MAIN agent only.** Subagent records carry ``isSidechain``
   true. A subagent's claim belongs to the merge gate; re-reporting it here
   would duplicate an adjudication that already happened.
3. **Nothing it writes carries an identifier.** A transcript holds whatever was
   pasted into the session. Every string that reaches a written artifact goes
   through :func:`safe_text` - the quoted snippet, the claimed path, the reason
   built from it, and the transcript path in both the report and the trace -
   and anything still tripping
   :func:`lanternlight.redact.assert_no_operator_identifier` is dropped rather
   than written. The first version redacted the SNIPPET only, and this item's
   adversarial pass got a synthetic identifier onto disk through the claimed
   path standing beside it. Redacting one field and not its neighbour is this
   repository's contiguity lesson wearing different clothes.

WHAT THE EXTRACTOR MISSES, enumerated by this item's adversarial pass rather
than left for a reader to discover. A numeric claim is only seen when a digit
sits directly in front of an outcome word, so "2295 tests pass", "2295 passing",
"passed: 2295" and "the suite is at 2295" are all invisible. A file claim is
only seen when the path is in BACKTICKS after a creation verb, so a bare
``I created ops/foo.py``, a Markdown link, a bolded path and a quoted path are
all invisible, as is any path without one of :data:`_PATH_SUFFIXES`. These are
MISSES, not misreads - the auditor stays silent rather than saying something
false - and widening the patterns is the obvious next increment for anyone who
wants it. A thousands separator used to be a MISREAD, which is worse than a
miss, and that one was fixed rather than documented.

A LIMIT MEASURED ON ITS FIRST REAL FIRE, 2026-09-08. This module cannot tell a
claim from a QUOTATION of one. Its first live report refuted a number that the
session had written down as an EXAMPLE of a false claim - the outcomes summed to
2296 against a tree collecting 2343, exactly as they were meant to, and the
auditor called it refuted because the sentence looks identical either way. That
is left in rather than heuristically patched: a rule that excuses a number
inside quotes excuses the easiest place to hide a real false claim, and a false
positive that reads "check this number" costs a reader ten seconds while a false
negative costs the thing this item exists to prevent.

WHY THE ARTIFACT LOOKS LIKE THIS. `OPS-41`'s trace was refuted at its own wrap:
it had no ordinal, no submitter and no causal attribution, so two different
hypotheses about when the hook fired wrote a byte-identical file, and the file
was gitignored so no later session could re-derive anything. The trace here
carries an ordinal, the transcript's line count and the uuid of the last
main-agent record at fire time, which is enough to tell one fire from the next
and a per-turn fire from a per-session one. The runtime trace is still local and
still gitignored - that part is unavoidable, because it describes this machine's
sessions - but the AUDIT ITSELF is reproducible from the repository:
``--audit-transcript`` runs the whole pipeline over any transcript, and
``tests/test_stop_audit.py`` drives it over synthetic ones.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lanternlight.redact import (  # noqa: E402  (path bootstrap must run first)
    RedactionError,
    assert_no_operator_identifier,
    redact,
)

SCHEMA = 1

KIND_TEST_COUNT = "test-count"
KIND_GREEN = "green"
KIND_FILE = "file"

VERDICT_OK = "ok"
VERDICT_FAIL = "fail"
VERDICT_UNCHECKED = "unchecked"

#: Claim shapes this auditor does NOT check, named in every report.
#:
#: Each line is a shape this project's ledger records being wrong about at
#: least once. They are listed rather than silently omitted because the failure
#: this whole item guards against is a reader assuming a check happened.
NOT_CHECKED: tuple[str, ...] = (
    "whether a passing test actually tests the thing it names - vacuity is the "
    "single most repeated defect in this ledger and no count can see it",
    "an asserted ABSENCE - a clean bill is a claim about the pattern until a "
    "positive control has been shown to fire",
    "a universal written from a narrow measurement - 'ever', 'any', 'all'",
    "a stated MECHANISM - why something happened, as opposed to that it did",
    "a claim about TDD ordering, a mutation watched red, or a file restored",
    "a claim about what the GAME does - only re-measuring the log settles one",
    "a claim that a commit was pushed, or that a working tree is clean",
    "a claim that a note was delivered to a sibling project",
    "a claim about a subagent's work - that is the merge gate's job",
    "a claim made in an earlier turn of this session, not the final one",
    "a number that came from outside this tree",
)

#: The runtime home for the trace and the last report. Gitignored by design -
#: it describes this machine's sessions, and a tracked file rewritten at every
#: Stop event would make every commit a diff of session noise.
RUNTIME_DIR = REPO_ROOT / "ops" / "runtime" / "stop_audit"

TRACE_NAME = "trace.jsonl"
REPORT_NAME = "last_report.json"

#: Keep the trace bounded. It is evidence, not an archive, and an unbounded
#: append in a hook is a slow leak nobody notices until it is large.
TRACE_KEEP = 500

_AUTO = object()

_OUTCOME_WORDS = (
    "passed",
    "failed",
    "skipped",
    "xfailed",
    "xpassed",
    "deselected",
    "collected",
    "errors",
    "error",
)

_OUTCOME = re.compile(
    r"\b(\d{1,3}(?:,\d{3})+|\d{1,7})\s+(" + "|".join(_OUTCOME_WORDS) + r")\b",
    re.IGNORECASE,
)

_GREEN = re.compile(
    r"\b(?:suite|tests?|pytest)\b[^.\n]{0,60}\bgreen\b"
    r"|\bgreen\b[^.\n]{0,60}\b(?:suite|tests?|pytest)\b"
    r"|\ball\s+tests?\s+pass(?:ed|ing)?\b"
    r"|\bfull\s+suite\s+green\b",
    re.IGNORECASE,
)

_CREATION_VERB = re.compile(
    r"\b(?:wrote|writing|created|creating|added|adding|generated|shipped|landed)\b",
    re.IGNORECASE,
)

_BACKTICKED = re.compile(r"`([^`\n]{1,200})`")

_PATH_LIKE = re.compile(r"^[A-Za-z0-9_./\\:-]+$")

_PATH_SUFFIXES = (
    ".py",
    ".md",
    ".json",
    ".txt",
    ".ini",
    ".toml",
    ".cfg",
    ".ps1",
    ".sh",
    ".yml",
    ".yaml",
    ".jsonl",
)

_COLLECTED = re.compile(r"\b(\d{1,7})\s+tests?\s+collected\b")

#: A line that names a partial run - one file, or a selection flag. Its numbers
#: legitimately sum below the tree's collected total, so calling it refuted
#: would be wrong, and calling it confirmed would be a claim nothing checked.
#: It is reported UNCHECKED, which is the only honest third answer.
_PARTIAL_RUN = re.compile(
    r"(?:^|\s)-[km]\s"
    r"|\btests?/[A-Za-z0-9_./-]+\.py\b"
    r"|\bsingle file\b"
    r"|\bthat file alone\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# claims
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    """One assertion pulled out of the session's own words."""

    kind: str
    text: str
    detail: dict

    def as_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "detail": self.detail}


@dataclass(frozen=True)
class Finding:
    """A claim plus what ground truth said about it."""

    claim: Claim
    verdict: str
    reason: str

    def as_dict(self) -> dict:
        return {
            "kind": self.claim.kind,
            "verdict": self.verdict,
            "reason": self.reason,
            "claim": self.claim.text,
            "detail": {
                key: value for key, value in self.claim.detail.items() if key != "path"
            },
        }


def _safe_snippet(line: str) -> str:
    """Return a quotable form of ``line``, or a placeholder if it cannot be one.

    Two passes, not one. :func:`redact` masks the labelled identifier classes;
    :func:`assert_no_operator_identifier` is the backstop that refuses anything
    still carrying an operator identity after that. A snippet that fails the
    backstop is DROPPED - a report is worth less than a leak costs.
    """
    text = " ".join(line.split())[:240]
    try:
        text = redact(text)
    except Exception:  # pragma: no cover - redact is total, this is belt-and-braces
        return "[snippet withheld: redaction failed]"
    try:
        assert_no_operator_identifier(text)
    except RedactionError:
        return "[snippet withheld: operator identifier]"
    return text


def safe_text(value: str) -> str:
    """Redact any string on its way into a written artifact.

    :func:`_safe_snippet` covered the QUOTED line and nothing else, so a
    claimed path - which is pulled out of the RAW line - reached the report
    carrying whatever that line carried. That is this repository's contiguity
    lesson in a second dress: the value was still on disk, just not where the
    sweep was looking. Everything written now goes through here.
    """
    try:
        cleaned = redact(str(value))
    except Exception:
        return "[withheld: redaction failed]"
    try:
        assert_no_operator_identifier(cleaned)
    except RedactionError:
        return "[withheld: operator identifier]"
    return cleaned


def extract_claims(text: str) -> list[Claim]:
    """Pull the checkable claim shapes out of one block of the model's prose.

    Line by line, because a claim is a sentence-scale thing and because merging
    across lines would let a number from one statement verify a filename from
    another.
    """
    claims: list[Claim] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        snippet = _safe_snippet(line)

        outcomes: dict[str, int] = {}
        for count, word in _OUTCOME.findall(line):
            key = word.lower()
            if key == "errors":
                key = "error"
            outcomes[key] = outcomes.get(key, 0) + int(count.replace(",", ""))
        if outcomes:
            claims.append(
                Claim(
                    kind=KIND_TEST_COUNT,
                    text=snippet,
                    detail={
                        "outcomes": outcomes,
                        "partial_run": bool(_PARTIAL_RUN.search(line)),
                    },
                )
            )
        elif _GREEN.search(line):
            claims.append(Claim(kind=KIND_GREEN, text=snippet, detail={"outcomes": {}}))

        if _CREATION_VERB.search(line):
            for token in _BACKTICKED.findall(line):
                candidate = token.strip()
                if not _PATH_LIKE.match(candidate):
                    continue
                if not candidate.lower().endswith(_PATH_SUFFIXES):
                    continue
                claims.append(
                    Claim(
                        kind=KIND_FILE,
                        text=snippet,
                        detail={"path": candidate, "safe_path": safe_text(candidate)},
                    )
                )
    return claims


# ---------------------------------------------------------------------------
# transcript reading
# ---------------------------------------------------------------------------


def iter_transcript(path: Path | str) -> tuple[list[dict], str]:
    """Read a JSONL transcript, returning ``(records, note)`` and never raising.

    A line that will not parse is COUNTED rather than fatal. The harness appends
    to this file while the session runs, so the last line can genuinely be half
    written at the moment a hook reads it; refusing the whole file for that
    would mean the auditor is blind exactly when it is most needed.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return [], f"transcript {path} does not exist; nothing was audited"
    except OSError as exc:
        return [], f"transcript {path} could not be read ({exc.__class__.__name__})"

    records: list[dict] = []
    bad = 0
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(record, dict):
            records.append(record)
        else:
            bad += 1
    note = f"{bad} transcript line(s) did not parse and were skipped" if bad else ""
    return records, note


def _is_operator_prompt(record: dict) -> bool:
    """True for a record that is a prompt SUBMITTED INTO the session.

    A tool result is also a user-role record, and treating one as a turn
    boundary would shrink the audited window to whatever was said after the
    last tool call - routinely one sentence, and never the summary that carries
    the claims.
    """
    if record.get("type") != "user" or record.get("isSidechain"):
        return False
    if record.get("toolUseResult") is not None:
        return False
    content = record.get("message", {}).get("content")
    if isinstance(content, list):
        return not any(
            isinstance(block, dict) and block.get("type") == "tool_result"
            for block in content
        )
    return True


def _assistant_texts(record: dict) -> list[str]:
    if record.get("type") != "assistant" or record.get("isSidechain"):
        return []
    content = record.get("message", {}).get("content")
    if not isinstance(content, list):
        return []
    return [
        block["text"]
        for block in content
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]


def final_turn_texts(records: list[dict]) -> list[dict]:
    """Return the main agent's text blocks since the last operator prompt."""
    start = 0
    for index, record in enumerate(records):
        if _is_operator_prompt(record):
            start = index + 1
    blocks: list[dict] = []
    for record in records[start:]:
        for text in _assistant_texts(record):
            blocks.append(
                {
                    "uuid": record.get("uuid", ""),
                    "timestamp": record.get("timestamp", ""),
                    "text": text,
                }
            )
    return blocks


def _has_numeric_claim(records: list[dict]) -> bool:
    """True when the final main-agent turn asserts a number about the suite."""
    for block in final_turn_texts(records):
        for claim in extract_claims(block["text"]):
            if claim.kind == KIND_TEST_COUNT:
                return True
    return False


def last_main_uuid(records: list[dict]) -> str:
    for record in reversed(records):
        if (
            not record.get("isSidechain")
            and isinstance(record.get("uuid"), str)
            and record.get("type") in {"assistant", "user"}
        ):
            return record["uuid"]
    return ""


# ---------------------------------------------------------------------------
# verification
# ---------------------------------------------------------------------------


def collect_count(root: Path | str | None = None, timeout: float = 120.0) -> int | None:
    """Return what pytest collects for the tree right now, or ``None``.

    Bare ``--collect-only``, deliberately. ``pytest.ini`` already carries ``-q``
    in ``addopts``, so passing another one makes it ``-qq`` and the total line
    this function parses is never printed at all - the trap `CLAUDE.md` records
    for the suite summary, in its collection form.

    Measured 2026-09-08 on this tree: under one second. That is the whole reason
    the numeric check is affordable inside a hook, where a full run at over
    three minutes would not be.
    """
    root = Path(root) if root is not None else REPO_ROOT
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "--collect-only", "-p", "no:cacheprovider"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = _COLLECTED.search(completed.stdout or "")
    if not match:
        return None
    return int(match.group(1))


def _verify_file(claim: Claim, root: Path) -> Finding:
    raw = claim.detail.get("safe_path") or safe_text(claim.detail.get("path", ""))
    candidate = Path(claim.detail.get("path", ""))
    target = candidate if candidate.is_absolute() else root / candidate
    if not target.exists():
        return Finding(claim, VERDICT_FAIL, f"{raw} does not exist under {root}")
    if target.is_dir():
        return Finding(claim, VERDICT_OK, f"{raw} exists as a directory")
    try:
        size = target.stat().st_size
    except OSError as exc:
        return Finding(claim, VERDICT_UNCHECKED, f"{raw} could not be stat'd ({exc})")
    if size == 0:
        return Finding(claim, VERDICT_FAIL, f"{raw} exists but is empty")
    return Finding(claim, VERDICT_OK, f"{raw} exists, {size} bytes")


def _verify_counts(claim: Claim, collected: int | None) -> Finding:
    outcomes = claim.detail.get("outcomes", {})
    if collected is None:
        return Finding(
            claim,
            VERDICT_UNCHECKED,
            "the collection could not be run, so no number was available to check against",
        )
    if "collected" in outcomes:
        claimed = outcomes["collected"]
        if claimed == collected:
            return Finding(claim, VERDICT_OK, f"pytest collects {collected}")
        return Finding(
            claim,
            VERDICT_FAIL,
            f"claimed {claimed} collected; pytest collects {collected}",
        )
    if claim.detail.get("partial_run"):
        return Finding(
            claim,
            VERDICT_UNCHECKED,
            (
                "the line names a partial run (a single file, or a -k/-m selection), "
                f"so its numbers cannot be checked against the tree's {collected} collected"
            ),
        )
    total = sum(outcomes.values())
    if total == collected:
        return Finding(claim, VERDICT_OK, f"outcomes sum to {total}, which pytest collects")
    return Finding(
        claim,
        VERDICT_FAIL,
        (
            f"outcomes sum to {total}; pytest collects {collected}. "
            "A partial run (-k, -m, or a single file) legitimately sums low - "
            "if that is what happened, the claim should say so rather than read "
            "as a whole-suite result"
        ),
    )


def verify(claims: list[Claim], root: Path | str, collected: int | None) -> list[Finding]:
    """Check every claim against ground truth. Order is preserved."""
    root = Path(root)
    findings: list[Finding] = []
    for claim in claims:
        if claim.kind == KIND_FILE:
            findings.append(_verify_file(claim, root))
        elif claim.kind == KIND_TEST_COUNT:
            findings.append(_verify_counts(claim, collected))
        else:
            findings.append(
                Finding(
                    claim,
                    VERDICT_UNCHECKED,
                    "green claim carries no number, and this hook does not run the "
                    "full suite - it would add minutes to every session stop",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


@dataclass
class Report:
    transcript: str
    generated_at: str
    collected: int | None
    findings: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        counts = {VERDICT_OK: 0, VERDICT_FAIL: 0, VERDICT_UNCHECKED: 0}
        for finding in self.findings:
            counts[finding.verdict] = counts.get(finding.verdict, 0) + 1
        return counts

    def as_dict(self) -> dict:
        return {
            "schema": SCHEMA,
            "generated_at": self.generated_at,
            "transcript": safe_text(self.transcript),
            "collected": self.collected,
            "counts": self.counts,
            "findings": [finding.as_dict() for finding in self.findings],
            "notes": list(self.notes),
            "not_checked": list(NOT_CHECKED),
        }

    def format(self) -> str:
        counts = self.counts
        lines = [
            "STOP-CLAIM AUDIT - ops/stop_audit.py (ROADMAP OPS-45)",
            f"  generated {self.generated_at}",
            f"  transcript {self.transcript}",
            f"  pytest collects {self.collected if self.collected is not None else 'UNKNOWN'}",
            (
                f"  {counts[VERDICT_FAIL]} refuted, {counts[VERDICT_OK]} confirmed, "
                f"{counts[VERDICT_UNCHECKED]} not checkable"
            ),
        ]
        for note in self.notes:
            lines.append(f"  NOTE {note}")
        for finding in self.findings:
            lines.append(f"  [{finding.verdict.upper()}] {finding.claim.kind}: {finding.reason}")
            lines.append(f"         claim: {finding.claim.text}")
        lines.append("  NOT CHECKED BY THIS AUDITOR:")
        for shape in NOT_CHECKED:
            lines.append(f"    - {shape}")
        return "\n".join(lines)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def audit(
    transcript_path: Path | str,
    root: Path | str,
    collected: int | None,
) -> Report:
    """Read one transcript and check its final main-agent turn."""
    records, note = iter_transcript(transcript_path)
    report = Report(
        transcript=str(transcript_path),
        generated_at=_now(),
        collected=collected,
    )
    if note:
        report.notes.append(note)
    blocks = final_turn_texts(records)
    if not blocks:
        report.notes.append("no main-agent text in the final turn; nothing to audit")
        return report
    claims: list[Claim] = []
    for block in blocks:
        claims.extend(extract_claims(block["text"]))
    if not claims:
        report.notes.append("the final turn made no mechanically checkable claim")
    report.findings = verify(claims, root=root, collected=collected)
    return report


def _write_atomic(text: str, target: Path) -> str:
    """Write ``text`` to ``target`` atomically. Returns "" or the error text."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(target)
    except OSError as exc:
        return f"could not write {target} ({exc.__class__.__name__})"
    return ""


def write_report(report: Report, target: Path | str) -> str:
    return _write_atomic(json.dumps(report.as_dict(), indent=2) + "\n", Path(target))


# ---------------------------------------------------------------------------
# the trace - evidence that this fired, and when, and on what
# ---------------------------------------------------------------------------


def _load_trace(path: Path) -> list[dict]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return []
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def append_trace(row: dict, path: Path) -> str:
    """Append one fire record, keeping the ordinal monotonic across corruption.

    The ordinal continues from the highest one still readable rather than from
    the row count, so a corrupt or truncated row costs evidence without making
    two different fires claim the same ordinal.
    """
    rows = _load_trace(path)
    highest = 0
    for existing in rows:
        value = existing.get("ordinal")
        if isinstance(value, int) and value > highest:
            highest = value
    row = dict(row)
    row["ordinal"] = highest + 1
    rows.append(row)
    rows = rows[-TRACE_KEEP:]
    text = "".join(json.dumps(entry) + "\n" for entry in rows)
    return _write_atomic(text, path)


# ---------------------------------------------------------------------------
# the hook entry point
# ---------------------------------------------------------------------------


def run_hook(
    raw: str,
    root: Path | str | None = None,
    runtime_dir: Path | str | None = None,
    collected=_AUTO,
) -> int:
    """Run the audit for one ``Stop`` event. ALWAYS returns 0.

    Exit code 2 on this event blocks the session from stopping and feeds stderr
    back to the model, which is a loop rather than a warning. Nothing in here is
    allowed to raise past this boundary either: an auditor that crashes a
    session is worse than the false claims it was built to catch.
    """
    root = Path(root) if root is not None else REPO_ROOT
    runtime = Path(runtime_dir) if runtime_dir is not None else RUNTIME_DIR
    started = time.monotonic()
    notes: list[str] = []
    payload: dict = {}
    try:
        parsed = json.loads(raw) if raw and raw.strip() else {}
        if isinstance(parsed, dict):
            payload = parsed
        else:
            notes.append("hook payload was valid JSON but not an object")
    except json.JSONDecodeError as exc:
        notes.append(f"hook payload was not JSON (line {exc.lineno}); audited nothing")
    except Exception as exc:
        # Deeply nested JSON raises RecursionError, which is NOT a
        # JSONDecodeError. Found by this item's adversarial pass, escaping the
        # boundary. A hook that raises breaks the session it was auditing.
        notes.append(f"hook payload could not be parsed ({exc.__class__.__name__})")

    transcript = payload.get("transcript_path") or ""
    session = payload.get("session_id") or ""
    event = payload.get("hook_event_name") or ""

    records: list[dict] = []
    report: Report | None = None
    try:
        if transcript:
            records, read_note = iter_transcript(transcript)
            if read_note:
                notes.append(read_note)
            if collected is _AUTO:
                # Only pay for the collection when a numeric claim is actually
                # on the table. Most turns make none, and a subprocess at the
                # end of every turn is a cost the operator feels for nothing.
                if _has_numeric_claim(records):
                    collected = collect_count(root)
                else:
                    collected = None
                    notes.append(
                        "no numeric suite claim in the final turn, so no collection was run"
                    )
            report = audit(transcript, root=root, collected=collected)
            for note in notes:
                report.notes.insert(0, note)
            error = write_report(report, runtime / REPORT_NAME)
            if error:
                notes.append(error)
        else:
            notes.append("hook payload named no transcript_path")
    except Exception as exc:  # a hook may not raise past this boundary
        notes.append(f"audit raised {exc.__class__.__name__}; nothing was checked")

    counts = report.counts if report is not None else {}
    append_trace(
        {
            "at": _now(),
            "event": str(event),
            "session": str(session),
            "transcript": safe_text(str(transcript)),
            "transcript_exists": bool(transcript) and Path(str(transcript)).is_file(),
            "transcript_lines": len(records),
            "last_main_uuid": last_main_uuid(records),
            "counts": counts,
            "elapsed_ms": int((time.monotonic() - started) * 1000),
            "notes": notes,
        },
        runtime / TRACE_NAME,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stop_audit",
        description=(
            "Audit a session's own claims against ground truth. Run as a Stop "
            "hook, or by hand over any transcript."
        ),
    )
    parser.add_argument(
        "--stop-hook",
        action="store_true",
        help="read the hook payload from stdin and audit the transcript it names",
    )
    parser.add_argument(
        "--audit-transcript",
        metavar="PATH",
        help="audit one transcript file and print the report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the report as JSON rather than as text",
    )
    parser.add_argument(
        "--show-last",
        action="store_true",
        help="print the most recent report this hook wrote, if there is one",
    )
    parser.add_argument(
        "--no-collect",
        action="store_true",
        help="skip the pytest collection; numeric claims report as not checkable",
    )
    return parser


def show_last(runtime_dir: Path | str | None = None) -> str:
    """Render the last report this hook wrote, for a later session to read.

    The report is the point of the hook, and a report nobody reads is the same
    as no report. This is what a wrap or a cold session calls to find out
    whether the PREVIOUS session's closing claims survived contact with the
    filesystem.
    """
    runtime = Path(runtime_dir) if runtime_dir is not None else RUNTIME_DIR
    target = runtime / REPORT_NAME
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError):
        return f"no stop-claim audit report at {target}; the hook has not written one here"
    except json.JSONDecodeError:
        return f"the report at {target} is not valid JSON"
    counts = payload.get("counts", {})
    lines = [
        f"STOP-CLAIM AUDIT, last written {payload.get('generated_at', 'UNKNOWN')}",
        f"  transcript {payload.get('transcript', 'UNKNOWN')}",
        f"  pytest collected {payload.get('collected')}",
        (
            f"  {counts.get(VERDICT_FAIL, 0)} refuted, {counts.get(VERDICT_OK, 0)} confirmed, "
            f"{counts.get(VERDICT_UNCHECKED, 0)} not checkable"
        ),
    ]
    for note in payload.get("notes", []):
        lines.append(f"  NOTE {note}")
    for finding in payload.get("findings", []):
        lines.append(
            f"  [{str(finding.get('verdict', '')).upper()}] "
            f"{finding.get('kind', '')}: {finding.get('reason', '')}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.show_last:
        print(show_last())
        return 0
    if args.stop_hook:
        raw = ""
        try:
            raw = sys.stdin.read()
        except Exception:  # a hook may not raise
            raw = ""
        return run_hook(raw, collected=None if args.no_collect else _AUTO)
    if args.audit_transcript:
        collected = None if args.no_collect else collect_count(REPO_ROOT)
        report = audit(args.audit_transcript, root=REPO_ROOT, collected=collected)
        if args.json:
            print(json.dumps(report.as_dict(), indent=2))
        else:
            print(report.format())
        return 0
    build_parser().print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
