"""Lanternlight unattended-loop package - continuity that lives on disk.

The operator's goal is to play Mistfall Hunter while Lanternlight keeps being
built, without alt-tabbing into the Claude session to unblock it. That goal
imposes one hard architectural constraint on everything in this package:

    **Continuity lives on DISK, never in a context window.**

A context window is not durable storage. It gets cleared, it gets compacted,
and it silently drops the middle of itself when it fills. Any loop whose next
step depends on remembering the last step is a loop that dies the first time
the session is compacted, and it dies quietly - it keeps producing plausible
output that is no longer grounded in anything.

So the loop keeps its whole working memory in files that a cold session can
read from scratch:

* ``git`` history - what actually landed, and in what order. The only record
  that cannot be edited by a confused agent without leaving a trace.
* ``docs/LEDGER.md`` - the append-only per-item ledger. One entry per item,
  newest first, each carrying its acceptance evidence. See :mod:`ops.loop.ledger`.
* ``ROADMAP.md`` - what is next, with an acceptance criterion attached. The
  loop picks its next item from here, not from a plan it is holding in mind.
* the directive chain - the current cycle's instruction text, persisted in
  ``ops/runtime/loop_state.json``. See :mod:`ops.loop.state`.

The test of the design is blunt: kill the session mid-cycle, start a brand new
one with an empty context, and it must be able to pick up from the files alone.
If any step of the loop needs something that was only ever said in chat, that
step is broken and belongs on disk instead.

Modules
-------

``state``
    The on-disk loop state - cycle number, active directive, in-flight item,
    timestamp, completed item ids. Atomic writes, and it never raises on a
    missing or corrupt file.
``guard``
    Single-instance guard. Two loops running at once would interleave commits
    and fight over the same worktree. The guard only ever refuses to start; it
    never kills anything.
``ledger``
    Append-only writer for ``docs/LEDGER.md``.

Operator documentation for running unattended, including the stop conditions
the loop must never violate, is in ``docs/HEADLESS.md``.
"""

from ops.loop import guard, ledger, state

__all__ = ["guard", "ledger", "state"]
