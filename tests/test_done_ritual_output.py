"""The /done command's chat output, as ordered by MAIN 1014 (FLEET-KIT v2 item 5).

MAIN 1014 relays the operator, 2026-10-03: the end-of-session review is not
wanted, the next-session prompt is no longer printed into chat, and the wrap's
ONLY chat line is `Done ritual complete, safe to clear`. The hand-off file stays
and MUST carry forward every item the session did not act on. This supersedes
the 2026-09-07 "one copy-pastable fence" instruction (LL-0166).

These tests read the command file a wrap actually follows, so a later edit that
restores the old fenced-prompt step goes red here.
"""

from __future__ import annotations

import re

from tests.conftest import REPO_ROOT

DONE = REPO_ROOT / ".claude" / "commands" / "done.md"
LINE = "Done ritual complete, safe to clear"


def _text() -> str:
    return DONE.read_text(encoding="utf-8")


def test_done_names_the_single_chat_line_verbatim():
    assert LINE in _text()


def test_done_no_longer_orders_the_prompt_printed_as_a_fence():
    collapsed = re.sub(r"\s+", " ", _text())
    assert "Emit the next-session prompt" not in collapsed
    assert "copy-pastable" not in collapsed.replace(
        "no longer a copy-pastable", ""
    )


def test_done_orders_carry_forward_of_unacted_items():
    collapsed = re.sub(r"\s+", " ", _text()).lower()
    assert "carry forward every item not acted on" in collapsed


def test_done_description_frontmatter_matches_the_new_output():
    head = _text().split("---", 2)[1]
    assert "print the next-session prompt" not in head
