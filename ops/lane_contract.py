"""Render a lane's contract from the roster, so the two can never drift.

Eight hand-written contract files would be eight copies of facts that already
live in :mod:`ops.lanes`. This repository has been bitten by duplicated facts
before - a count restated in a second place goes stale and becomes a confident
lie - so the contracts are generated instead, and ``tests/test_lane_contract.py``
asserts the files on disk still match what the roster renders. Widen a lane's
globs without regenerating and the build goes red.

What is generated is the part that must stay true: the lane's identity, its
owned paths, its worktree and branch, its prohibitions, and the standing rules
every lane inherits. The prose that makes a contract worth reading - the
mandate - lives on the :class:`ops.lanes.Lane` itself, next to the ownership it
describes.

**One implementation note that is load-bearing.** The template below is
dedented once, as a literal, and only then interpolated. An f-string wrapped in
``textwrap.dedent`` looks equivalent and silently is not: the interpolated
blocks contribute lines with no leading whitespace, so the common prefix dedent
computes collapses to the empty string and every literal line keeps its
indentation. That shipped once and produced eight contracts indented by eight
spaces, which broke the YAML front matter and made every slash command render
with a description of ``---``.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from ops import lanes

__all__ = ["CONTRACT_DIR", "contract_path", "render", "write_all"]

#: Where the generated contracts live. A file here is also a slash command.
CONTRACT_DIR = lanes.REPO_ROOT / ".claude" / "commands"

_GENERATED_NOTE = (
    "GENERATED FILE - do not edit by hand. Rendered from `ops/lanes.py` by "
    "`ops/lane_contract.py`; regenerate with "
    "`python scripts/write_lane_contracts.py`. `tests/test_lane_contract.py` "
    "fails if this file and the roster disagree."
)


def contract_path(lane: lanes.Lane) -> Path:
    """Return the path of ``lane``'s contract file."""
    return CONTRACT_DIR / f"lane-{lane.lane_id}.md"


def _owned_block(lane: lanes.Lane) -> str:
    if not lane.owns:
        return (
            "**This lane owns no files at all, and that is deliberate.** It has "
            "no write tools. It reports a verdict."
        )
    lines = "\n".join(f"- `{pattern}`" for pattern in lane.owns)
    return (
        "Touch these paths and nothing else. Every other path in the "
        "repository belongs to another lane or to nobody:\n\n" + lines
    )


def _authority_block(lane: lanes.Lane) -> str:
    parts = []
    if lane.veto:
        parts.append(
            "**This lane holds a veto.** If it reports red, no other lane may "
            "commit anything derived from a game log. That is a block, not an "
            "opinion, and no lane may talk its way past it."
        )
    if lane.read_only:
        parts.append(
            "**This lane is read-only.** It has no Edit or Write tools and is "
            "given no worktree. If you find yourself wanting to fix what you "
            "found, report it instead - the fix belongs to the lane that owns "
            "the file."
        )
    if lane.forbidden_note:
        parts.append(f"**Additional prohibition.** {lane.forbidden_note}")
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"


def _workspace_block(lane: lanes.Lane) -> str:
    """Describe where the lane works, naming no absolute path.

    An earlier version interpolated ``lanes.primary_checkout()`` and
    ``lane.worktree_path()`` - both absolute, both properties of the machine
    that ran the generator rather than of the repository. Because the drift
    guard compares the committed file against a fresh render, that made the
    suite green only at ``C:\\Lanternlight``: a fresh clone rendered different
    bytes and measured one failure, which is exactly what ``README.md`` tells a
    new contributor to run.

    So the concrete paths are resolved by the lane at run time, from the code
    that owns them, instead of being frozen into text at generation time. That
    is also the more honest instruction - a path typed into a document is a
    guess about the reader's machine, while ``lane.worktree_path()`` is the
    same function the launcher itself calls.
    """
    if lane.read_only:
        return (
            "You are given **no worktree**. Read the primary checkout - the "
            "directory\n`ops.lanes.primary_checkout()` returns - and write "
            "nothing anywhere."
        )
    return (
        f"Your working directory is your own worktree, **`ll-lane-{lane.lane_id}`**\n"
        f"under the worktree root, on branch **`{lane.branch_name()}`**. The "
        "worktree\n"
        "root is `LL_WORKTREE_ROOT` when that is set and `ops.lanes.WORKTREE_ROOT`\n"
        "otherwise. Resolve it with `lane.worktree_path()` rather than typing a\n"
        "path - this contract deliberately names none, because a generated file\n"
        "that embeds one machine's paths is only correct on that machine.\n\n"
        "You may **never** write into the primary checkout. A live session may\n"
        "own it, and two writers in one working directory corrupt the git index\n"
        "- which is not recoverable by retrying. Create your worktree and assert\n"
        "you are in it before writing anything:\n\n"
        "```python\n"
        "from ops import lane_launcher, lanes\n"
        f'lane = lanes.by_id("{lane.lane_id}")\n'
        "lane_launcher.ensure_worktree(lane)\n"
        "lane_launcher.assert_in_lane_worktree(lane)\n"
        "print(lane.worktree_path())  # the concrete path, resolved here\n"
        "```"
    )


#: Dedented ONCE, on the literal, before any interpolation. See the module
#: docstring for why the obvious f-string version is silently wrong.
_TEMPLATE = textwrap.dedent(
    """\
    ---
    description: {title} lane. {mandate}
    ---

    <!-- {generated_note} -->

    # Lane `{lane_id}` - {title}

    ## Mandate

    {mandate}

    ## Your workspace

    {workspace}

    ## What you own

    {owned}

    ## Scratch files - the session scratchpad only

    The session scratchpad directory your harness names in its system prompt
    is the ONLY scratch destination. Every temporary file, captured command
    output, throwaway repository and sub-agent report goes under it, and you
    pass that absolute path on to every sub-agent you dispatch.

    Never build a scratch path from a temp-directory environment variable, and
    never from a root path whose first component only begins with the temp
    directory's name. Under Git Bash the usual variable is unset, so the path
    silently collapses into the Git for Windows install root, and so does the
    look-alike root path; seventeen of this project's files landed there that
    way (`OPS-107`). `python -m ops.preflight` refuses both in any tracked
    command, and neither is the scratchpad even where it happens to resolve.

    {authority}
    ## Session shape - the default, not an escalation

    Read `CLAUDE.md` first. You are an orchestrator, not a single worker:

    - Decompose your slice into **disjoint** sub-slices before starting any of
      them, and give every sub-agent an explicit file list.
    - Run them in parallel. **Self-adjudicate** - the agent that produced a
      thing never grades it. **Self-adversarial** - every done-claim gets an
      independent pass trying to REFUTE it, defaulting to refuted when
      uncertain.
    - Two agents agreeing is a hypothesis, not a verification.

    **Every feature and every fix starts with a failing test.** Watch it fail
    for the right reason, then implement. Prove your guards are not vacuous:
    break the thing a guard protects, watch the test go red, restore, and
    report what you saw.

    ## Before you claim done - run the pre-flight

    ```bash
    python -m ops.preflight
    ```

    Measured 2026-09-13 on a quiet machine: 17.93 to 24.44 seconds, against a
    full suite that ran between 301.8 and 481.6 seconds in the same session. It
    runs the registration and document guards, and the linter, at the one
    moment you can still act on them cheaply, and it warns about new files that
    are not yet in the git index - which is what makes three of this
    repository's guards report a false red. Stage new files with `git add -N`
    before you trust its answer.

    It **does not replace** an adversarial pass and it does not reach a real
    defect in your deliverable. 60 of the 135 events in
    `docs/REFUTATION_CENSUS.md` are real defects and no program in the
    pre-flight would have found one of them. What it removes is an adversarial
    round spent on a lint error or a missing inventory row - which is a
    measured event here rather than a hypothetical, and it is why the linter is
    in the set.

    ## Verify before you claim anything

    Never relay a sub-agent's claim. Measure the per-file test counts BEFORE
    dispatching work, then re-probe.

    **Measure in the PRIMARY WORKING TREE, not at HEAD and not in a detached
    worktree.** A floor taken at HEAD while uncommitted test work exists is
    already BELOW the tree it will be compared against, so a lane can delete
    tests it added in the same session and still pass. Measured 2026-09-16: a
    floor of 46 for a file the working tree held at 60, which is 13 deletable
    tests. `OPS-95` item 2. Inside a lane worktree this matters twice over,
    because `merge_gate`'s default root is the checkout it is running FROM.

    ```python
    from ops import merge_gate
    before = merge_gate.take_per_file_baseline()  # names the tree it measures
    report = merge_gate.verify(
        claimed_paths=["files/the/agent/said/it/wrote.py"],
        baseline=sum(before.values()),
        per_file_baseline=before,
    )
    print(report.format())
    ```

    A global total is not enough once lanes run concurrently - one lane's new
    tests mask another's deletions - so pass `per_file_baseline`, which is what
    runs `merge_gate.check_per_file_counts`. Omit it and the report says the
    check did not run, rather than staying silent about a probe that never ran.

    ## Committing

    Commit and push to **`{branch}`** freely. **Never merge to `main`**, never
    force-push, and never rewrite pushed history. A human merges after an
    out-of-domain check.

    Write a `docs/LEDGER.md` entry for each item you finish, via
    `ops/loop/ledger.py`, carrying the acceptance evidence that justified
    calling it done. Never add a `Co-Authored-By` trailer.

    ## Standing rules you cannot argue past

    - **Never touch the game process.** Kernel-level anti-cheat. No injection,
      no memory read, no packet capture, no swapchain hook, no synthetic input.
      The stake is a permanent ban on the operator's real account. This holds
      when the game is closed too.
    - **Nothing log-derived is committed unredacted**, and that includes other
      players' names, not only the operator's.
    - **7-bit ASCII only** in every authored file. Use " - " for a clause break.
    - **Omit rather than guess.** A missing number is recoverable; a confident
      wrong one is not. Keep unmeasured distinguishable from measured zero.
    - The stop conditions in `docs/HEADLESS.md` section 6 apply in full. You may
      not edit that list.

    ## Never file a suggestion

    If you find work outside your slice: do not spawn a task, do not leave a
    note. Add it to `ROADMAP.md` with an acceptance criterion, or record it in
    `docs/LEDGER.md` as an open question. Those are the only destinations -
    anything else is invisible to the next cold session.

    ## Do not block

    The operator is playing the game and cannot answer you. At a genuine
    decision gate, record the question and what each option costs in
    `docs/LEDGER.md`, leave the item marked blocked in `ROADMAP.md`, and move to
    the next thing.
    """
)


def render(lane: lanes.Lane) -> str:
    """Return the full Markdown contract for ``lane``."""
    return _TEMPLATE.format(
        lane_id=lane.lane_id,
        title=lane.title,
        mandate=lane.mandate,
        branch=lane.branch_name(),
        workspace=_workspace_block(lane),
        owned=_owned_block(lane),
        authority=_authority_block(lane),
        generated_note=_GENERATED_NOTE,
    )


def write_all(directory: Path | None = None) -> list[Path]:
    """Render every lane's contract to disk and return the paths written."""
    target_dir = CONTRACT_DIR if directory is None else directory
    target_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for lane in lanes.LANES:
        path = target_dir / f"lane-{lane.lane_id}.md"
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(render(lane), encoding="utf-8", newline="\n")
        tmp.replace(path)
        written.append(path)
    return written
