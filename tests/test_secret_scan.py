"""The provider-credential detector - ROADMAP ``OPS-103`` criteria 1, 2 and 5.

WHAT IS PINNED HERE, and why each part exists:

1. **Every credential class carries a synthetic POSITIVE and a synthetic
   NEGATIVE**, and the suite fails if any class stops matching its positive. A
   detector believed without that is decoration: a regex that silently stopped
   matching looks exactly like a clean tree. The negatives are the near misses
   - the right prefix at the wrong length, the right length under the wrong
   prefix - because a negative that is nowhere near the shape rules nothing out.
2. **Every specimen is INVENTED and BUILT AT RUN TIME** by concatenation. This
   file is tracked, it is scanned by the very gate it tests on the commit that
   adds it, and GitHub scans the public repository for exactly these shapes. A
   literal specimen would refuse its own commit and look like a leaked key to
   anyone searching. :func:`test_this_module_carries_no_matching_literal`
   holds that line mechanically rather than by review.
3. **No output carries a value**, not in full, not in part, not redacted
   (criterion 5). The finding type has no field that could hold one, and the
   formatted report is checked for every non-trivial fragment of every
   specimen, so a future "helpful" preview of the first four characters goes
   red here.
4. **The gate fires END TO END** (criterion 2). A throwaway repository is wired
   to this repository's REAL ``.githooks/pre-commit``, a synthetic key is
   staged, a real ``git commit`` is attempted, and HEAD is asserted unchanged.
   The same repository then commits a clean file, so the refusal is not the
   hook refusing everything.

Every git repository here is a throwaway under ``tmp_path``. Nothing in this
module touches this repository's own index.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import _toolguard  # noqa: E402
import _tracked  # noqa: E402

from tools import precommit_gate, secret_scan  # noqa: E402

HOOKS_DIR = REPO_ROOT / ".githooks"
SCAN_SOURCE = REPO_ROOT / "tools" / "secret_scan.py"
GATE_SOURCE = REPO_ROOT / "tools" / "precommit_gate.py"

# ---------------------------------------------------------------------------
# Specimens. INVENTED shapes, assembled at run time - never a literal.
# ---------------------------------------------------------------------------

_BODY = "Q7x" * 10 + "Zk4"  # 33 invented characters, digits and both cases
_UPPER = "QX7Z" * 4  # 16 invented upper-case alphanumerics


def _j(*parts: str) -> str:
    return "".join(parts)


#: class -> (positive, negative). The negative is a NEAR MISS for its class.
SPECIMENS: dict[str, tuple[str, str]] = {
    "ANTHROPIC_ADMIN_KEY": (
        _j("sk-", "ant-", "admin", "01-", _BODY, "AA"),
        _j("sk-", "ant-", "admin", "01-", "short"),
    ),
    "ANTHROPIC_API_KEY": (
        _j("sk-", "ant-", "api", "03-", _BODY, "AA"),
        _j("sk-", "ant-", "api", "-", _BODY),  # no version digits
    ),
    "OPENAI_PROJECT_KEY": (
        _j("sk-", "proj-", _BODY, _BODY),
        _j("sk-", "proj-", "tooshort"),
    ),
    "OPENAI_KEY": (
        _j("sk-", _BODY, "Ab12Cd34Ef56"),
        _j("sk-", "learn-", "is-a-library"),
    ),
    "AWS_ACCESS_KEY_ID": (
        _j("AK", "IA", _UPPER),
        _j("AK", "IA", _UPPER[:12]),  # four characters short
    ),
    "GITHUB_TOKEN": (
        _j("gh", "p_", _BODY, "abc"),
        _j("gh", "x_", _BODY, "abc"),  # no such token family
    ),
    "GITHUB_FINE_GRAINED_PAT": (
        _j("github", "_pat_", "11ABCDEFG0", "123456789012", "_", _BODY, _BODY),
        _j("github", "_pat_", "notatoken"),
    ),
    "GOOGLE_API_KEY": (
        _j("AI", "za", "Sy", _BODY),
        _j("AI", "za", "Sy", "short"),
    ),
    "SLACK_TOKEN": (
        _j("xo", "xb-", "123456789012", "-", "AbCdEfGhIjKl"),
        _j("xo", "xq-", "123456789012", "-", "AbCdEfGhIjKl"),  # no such family
    ),
    "BEARER_TOKEN": (
        _j("Authorization: ", "Bea", "rer ", "tok", _BODY),
        _j("Bea", "rer ", "tokens are described in the docs"),
    ),
    "JWT": (
        _j("ey", "J", "hbGciOiJIUzI1NiJ9", ".", "ey", "J", "zdWIiOiIxMjM0NTYifQ", ".", _BODY),
        _j("ey", "J", "hbGciOiJIUzI1NiJ9", ".", "notajwt"),
    ),
    "PRIVATE_KEY_HEADER": (
        _j("-----", "BEGIN ", "RSA ", "PRIVATE ", "KEY", "-----"),
        _j("-----", "BEGIN ", "PUBLIC ", "KEY", "-----"),
    ),
    "ASSIGNED_SECRET": (
        _j("api", "_key", ' = "', "Zq8", _BODY, '"'),
        _j("api", "_key", " = os.environ.get(", '"NAME"', ")"),
    ),
}


def _leaks(value: str, text: str, width: int = 6) -> list[str]:
    """Every ``width``-character run of ``value`` that appears in ``text``.

    Class names are removed from ``text`` first, because a report is SUPPOSED
    to name the class and ``PRIVATE_KEY_HEADER`` shares a run with the header
    it names. Everything else that survives is a fragment of the value.
    """
    for cls in SPECIMENS:
        text = text.replace(cls, " ")
    runs = {value[i : i + width] for i in range(len(value) - width + 1)}
    return sorted(run for run in runs if run in text)


# ---------------------------------------------------------------------------
# Criterion 1 - every class, both directions.
# ---------------------------------------------------------------------------


def test_every_declared_class_has_a_specimen_pair_here():
    """A class added to the module without a pair here is an unproved class."""
    assert set(SPECIMENS) == set(secret_scan.CLASSES), (
        "specimen pairs and declared classes disagree: "
        f"missing pairs {sorted(set(secret_scan.CLASSES) - set(SPECIMENS))}, "
        f"pairs for unknown classes {sorted(set(SPECIMENS) - set(secret_scan.CLASSES))}"
    )


def test_the_minimum_class_set_of_ops_103_is_covered():
    required = {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_ADMIN_KEY",
        "OPENAI_KEY",
        "OPENAI_PROJECT_KEY",
        "AWS_ACCESS_KEY_ID",
        "GITHUB_TOKEN",
        "GITHUB_FINE_GRAINED_PAT",
        "GOOGLE_API_KEY",
        "SLACK_TOKEN",
        "BEARER_TOKEN",
        "JWT",
        "PRIVATE_KEY_HEADER",
        "ASSIGNED_SECRET",
    }
    assert required <= set(secret_scan.CLASSES)


@pytest.mark.parametrize("cls", sorted(SPECIMENS))
def test_each_class_matches_its_positive(cls):
    positive, _ = SPECIMENS[cls]
    classes = {f.cls for f in secret_scan.scan_text(f"prefix line\nx {positive} y\n")}
    assert cls in classes, f"{cls} no longer matches its synthetic positive"


@pytest.mark.parametrize("cls", sorted(SPECIMENS))
def test_each_class_declines_its_negative(cls):
    _, negative = SPECIMENS[cls]
    classes = {f.cls for f in secret_scan.scan_text(f"x {negative} y\n")}
    assert cls not in classes, f"{cls} fired on its near-miss negative"


@pytest.mark.parametrize("cls", sorted(SPECIMENS))
def test_each_positive_fires_on_its_own_class_only_among_the_vendor_families(cls):
    """An Anthropic key must not ALSO be reported as a generic OpenAI key.

    The families share the ``sk-`` prefix. Double-reporting one secret as two
    classes is a count nobody can act on. ASSIGNED_SECRET and BEARER_TOKEN are
    CONTEXT classes and may legitimately co-fire with a vendor class, so the
    check is over the vendor families only.
    """
    positive, _ = SPECIMENS[cls]
    context = {"ASSIGNED_SECRET", "BEARER_TOKEN"}
    got = {f.cls for f in secret_scan.scan_text(positive)} - context
    if cls in context:
        return
    assert got == {cls}, f"{cls} positive reported as {sorted(got)}"


def test_the_line_number_is_the_line_the_secret_is_on():
    positive = SPECIMENS["AWS_ACCESS_KEY_ID"][0]
    findings = secret_scan.scan_text(f"one\ntwo\nthree {positive}\nfour\n")
    assert [(f.cls, f.line) for f in findings] == [("AWS_ACCESS_KEY_ID", 3)]


def test_the_module_self_test_passes_and_is_not_vacuous(monkeypatch):
    """The runtime self-test is what a control trusts before it reports clean.

    Proved not vacuous by breaking ONE pattern and watching the self-test name
    exactly that class.
    """
    assert secret_scan.self_test() == []
    broken = dict(secret_scan.PATTERNS)
    broken["JWT"] = secret_scan.re.compile(r"(?!x)x")
    monkeypatch.setattr(secret_scan, "PATTERNS", broken)
    assert secret_scan.self_test() == ["JWT: positive not matched"]


def test_this_module_carries_no_matching_literal():
    """This file is committed through the gate it tests - it must scan clean."""
    text = Path(__file__).read_text(encoding="utf-8")
    assert secret_scan.scan_text(text) == []


def test_the_detector_module_scans_clean_against_itself():
    assert secret_scan.scan_text(SCAN_SOURCE.read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------------------
# Criterion 5 - class, count, path. Never a value, not even a fragment.
# ---------------------------------------------------------------------------


def test_a_finding_has_no_field_that_could_hold_a_value():
    assert set(secret_scan.Finding.__dataclass_fields__) == {"cls", "line"}


def test_the_report_carries_no_fragment_of_any_value():
    text = "\n".join(pos for pos, _ in SPECIMENS.values())
    findings = secret_scan.scan_text(text)
    report = secret_scan.format_report({"some/file.txt": findings})
    assert "some/file.txt" in report
    for cls, (positive, _) in SPECIMENS.items():
        assert cls in report, f"{cls} missing from report"
        leaked = _leaks(positive, report)
        assert not leaked, f"report carries {len(leaked)} fragment(s) of the {cls} specimen"


def test_the_report_counts_per_class_per_path():
    key = SPECIMENS["GITHUB_TOKEN"][0]
    findings = secret_scan.scan_text(f"{key}\n{key}\n")
    report = secret_scan.format_report({"a.txt": findings})
    assert "GITHUB_TOKEN 2 a.txt" in report


# ---------------------------------------------------------------------------
# Criterion 2 - the staged set, end to end through the real hook.
# ---------------------------------------------------------------------------

GIT_HOOK_ENV = (
    "GIT_DIR",
    "GIT_INDEX_FILE",
    "GIT_WORK_TREE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_QUARANTINE_PATH",
    "GIT_COMMON_DIR",
    "GIT_CONFIG_PARAMETERS",
    "GIT_AUTHOR_DATE",
    "GIT_EDITOR",
)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    for name in GIT_HOOK_ENV:
        env.pop(name, None)
    return env


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_toolguard.require("git"), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=300,
        env=_env(),
        check=False,
    )


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="ascii", newline="\n")


def _repo(tmp_path: Path, *, with_scanner: bool = True) -> Path:
    _toolguard.require_posix_userland()
    repo = tmp_path / "e2e"
    repo.mkdir()
    assert _git(repo, "init", "-q").returncode == 0
    for key, value in (
        ("user.email", "probe@example.invalid"),
        ("user.name", "probe"),
        ("commit.gpgsign", "false"),
        ("core.hooksPath", HOOKS_DIR.as_posix()),
    ):
        assert _git(repo, "config", key, value).returncode == 0, key
    (repo / "tools").mkdir()
    shutil.copy2(GATE_SOURCE, repo / "tools" / "precommit_gate.py")
    if with_scanner:
        shutil.copy2(SCAN_SOURCE, repo / "tools" / "secret_scan.py")
    _write(repo, "seed.txt", "seed\n")
    assert _git(repo, "add", "--", ".").returncode == 0
    # Seeded THROUGH the hook: the scanner's own source is committed by the
    # gate that runs it, so a self-matching module would fail right here.
    first = _git(repo, "commit", "-q", "-m", "seed")
    assert first.returncode == 0, f"the hook refused the seed:\n{first.stderr}"
    return repo


def test_a_staged_synthetic_key_blocks_a_real_commit(tmp_path):
    repo = _repo(tmp_path)
    before = _head(repo)
    positive = SPECIMENS["ANTHROPIC_ADMIN_KEY"][0]
    _write(repo, "config/settings.txt", f"name = demo\nkey: {positive}\n")
    assert _git(repo, "add", "--", "config/settings.txt").returncode == 0

    result = _git(repo, "commit", "-q", "-m", "should be refused")

    assert result.returncode != 0, "the commit carrying a synthetic key LANDED"
    assert _head(repo) == before, "HEAD moved - the key is in history"
    out = result.stdout + result.stderr
    assert "ANTHROPIC_ADMIN_KEY" in out and "config/settings.txt" in out, out
    leaked = _leaks(positive, out)
    assert not leaked, "the refusal printed part of the value it refused"


def test_the_index_is_what_is_judged_not_the_working_tree(tmp_path):
    """A key staged and then scrubbed ONLY in the working tree still blocks."""
    repo = _repo(tmp_path)
    before = _head(repo)
    positive = SPECIMENS["AWS_ACCESS_KEY_ID"][0]
    _write(repo, "notes.txt", f"id {positive}\n")
    assert _git(repo, "add", "--", "notes.txt").returncode == 0
    _write(repo, "notes.txt", "id scrubbed\n")

    result = _git(repo, "commit", "-q", "-m", "should be refused")

    assert result.returncode != 0
    assert _head(repo) == before


def test_a_clean_file_commits_through_the_same_hook(tmp_path):
    repo = _repo(tmp_path)
    before = _head(repo)
    _write(repo, "clean.txt", "api_key = os.environ.get('NAME')\nnothing to see\n")
    assert _git(repo, "add", "--", "clean.txt").returncode == 0

    result = _git(repo, "commit", "-q", "-m", "clean")

    assert result.returncode == 0, result.stderr
    assert _head(repo) != before


def test_a_key_in_a_renamed_file_is_still_seen(tmp_path):
    repo = _repo(tmp_path)
    positive = SPECIMENS["GITHUB_TOKEN"][0]
    _write(repo, "old.txt", "plain\n")
    assert _git(repo, "add", "--", "old.txt").returncode == 0
    assert _git(repo, "commit", "-q", "-m", "plain").returncode == 0
    before = _head(repo)
    assert _git(repo, "mv", "old.txt", "new.txt").returncode == 0
    _write(repo, "new.txt", f"plain\n{positive}\n")
    assert _git(repo, "add", "--", "new.txt").returncode == 0

    result = _git(repo, "commit", "-q", "-m", "rename with key")

    assert result.returncode != 0
    assert _head(repo) == before


def test_the_gate_entry_point_refuses_on_findings_and_permits_clean(tmp_path, monkeypatch):
    """The in-process contract the hook relies on: 1 refuses, 0 permits."""
    repo = _repo(tmp_path)
    positive = SPECIMENS["SLACK_TOKEN"][0]
    _write(repo, "s.txt", f"{positive}\n")
    assert _git(repo, "add", "--", "s.txt").returncode == 0
    for name in GIT_HOOK_ENV:
        monkeypatch.delenv(name, raising=False)
    assert precommit_gate.secrets_staged_main(repo) == 1
    _write(repo, "s.txt", "clean\n")
    assert _git(repo, "add", "--", "s.txt").returncode == 0
    assert precommit_gate.secrets_staged_main(repo) == 0


def test_an_unknown_spelling_of_the_entry_point_refuses():
    assert precommit_gate.dispatch(["--secretsstaged"]) == precommit_gate.USAGE_EXIT_CODE


# ---------------------------------------------------------------------------
# Criterion 6 - the tracked tree is the false-positive measurement.
# ---------------------------------------------------------------------------


def test_the_tracked_tree_carries_no_finding():
    """ZERO findings over every published file is the measured false-positive rate.

    The corpus is ``_tracked.iter_scannable_files`` - tracked files plus
    untracked-but-not-ignored ones, binaries INCLUDED - which is the corpus the
    PII backstop uses, so a file about to be committed is measured before it
    lands and not after. Using the shared walker also declares to
    ``ops/docguards.py`` that this module reads every document.

    If this goes red, the answer is to TRIAGE the hit: a real secret is removed
    and rotated; a false positive is fixed by narrowing the pattern WITH a new
    negative specimen above, never by excluding the file.
    """
    paths = list(_tracked.iter_scannable_files(REPO_ROOT))
    assert len(paths) >= _tracked.MIN_EXPECTED_FILES, (
        f"only {len(paths)} files in the corpus - the measurement did not run"
    )
    hits: dict[str, list] = {}
    for path in paths:
        if not path.is_file():
            continue
        found = secret_scan.scan_bytes(path.read_bytes())
        if found:
            hits[path.relative_to(REPO_ROOT).as_posix()] = found
    assert not hits, secret_scan.format_report(hits)


# ---------------------------------------------------------------------------
# Wide text - an adversarial pass found a UTF-16 key walked straight through.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "encoding", ["utf-16", "utf-16-le", "utf-16-be"], ids=["bom", "le-no-bom", "be-no-bom"]
)
def test_a_utf16_key_is_detected_once(encoding):
    positive = SPECIMENS["GITHUB_TOKEN"][0]
    data = f"header\nkey {positive}\n".encode(encoding)
    found = secret_scan.scan_bytes(data)
    assert [f.cls for f in found] == ["GITHUB_TOKEN"], found


def test_a_narrow_key_in_a_file_that_also_has_nuls_is_counted_once():
    positive = SPECIMENS["AWS_ACCESS_KEY_ID"][0]
    data = b"\x00\x01binary\x00\n" + f"id {positive}\n".encode("ascii") + b"\x00\x00"
    found = secret_scan.scan_bytes(data)
    assert [f.cls for f in found] == ["AWS_ACCESS_KEY_ID"], found
