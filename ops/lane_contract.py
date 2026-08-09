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
    if lane.read_only:
        return (
            "You are given **no worktree**. Read the primary checkout at "
            f"`{lanes.REPO_ROOT}` and write nothing anywhere."
        )
    return (
        f"Your working directory is **`{lane.worktree_path()}`** on branch\n"
        f"**`{lane.branch_name()}`**.\n\n"
        f"You may **never** write into `{lanes.REPO_ROOT}`. A live session may\n"
        "own it, and two writers in one working directory corrupt the git index\n"
        "- which is not recoverable by retrying. Create your worktree and assert\n"
        "you are in it before writing anything:\n\n"
        "```python\n"
        "from ops import lane_launcher, lanes\n"
        f'lane = lanes.by_id("{lane.lane_id}")\n'
        "lane_launcher.ensure_worktree(lane)\n"
        "lane_launcher.assert_in_lane_worktree(lane)\n"
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

    ## Verify before you claim anything

    Never relay a sub-agent's claim. Measure the per-file test counts BEFORE
    dispatching work, then re-probe:

    ```python
    from ops import merge_gate
    report = merge_gate.verify(
        claimed_paths=["files/the/agent/said/it/wrote.py"],
        baseline=COUNT_MEASURED_BEFORE_DISPATCH,
    )
    print(report.format())
    ```

    A global total is not enough once lanes run concurrently - one lane's new
    tests mask another's deletions - so compare per file with
    `merge_gate.check_per_file_counts`.

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
