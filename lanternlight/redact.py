"""Scrub personally identifying data out of Mistfall Hunter log text.

**This module prefers over-redaction to under-redaction, deliberately.** A
false positive costs a slightly less readable fixture. A false negative
publishes the operator's identity to a public git history, where it is
effectively permanent. When a pattern is ambiguous, this module redacts. If
that makes a fixture harder to read, the fixture is the thing to change, not
the rule.

What the real log carries, measured on 2026-08-09, and why each rule exists:

- a SteamID64 - a 17-digit number beginning ``7656119``
- the Steam persona name and ``AccountName``
- GSDK ``openID`` and ``userId`` values, which are long bare digit runs
- an Epic Online Services ``ProductUserId``, 32 hexadecimal characters
- an IP-resolved city, state and country
- session and access tokens

Every replacement is a stable, labelled placeholder such as ``<STEAMID64>``.
Stability matters: a redacted fixture has to diff cleanly against the next
capture, so the scrubber must never emit a counter, a hash or a random token.
Redaction is idempotent - running :func:`redact` on already-redacted text
returns it unchanged.

Two limits, stated rather than hidden:

- A bare persona name with no surrounding key cannot be detected by pattern.
  Only ``key=value`` and ``key: value`` shapes are caught. Free-text chat lines
  are not safe to publish on the strength of this module alone.
- City/state/country are not pattern-detectable either. Redact geolocation
  lines by dropping the line, not by trusting a regex.

Typical use::

    clean = redact(raw_text)
    assert_clean(clean)
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

__all__ = [
    "ALL_LABELS",
    "FILE_SCAN_LABELS",
    "RedactionError",
    "Rule",
    "RULES",
    "assert_clean",
    "iter_sensitive",
    "redact",
]


class RedactionError(ValueError):
    """Raised by :func:`assert_clean` when sensitive data survives redaction."""


@dataclass(frozen=True)
class Rule:
    """One detection rule: a stable label, a pattern, and its replacement."""

    label: str
    pattern: re.Pattern[str]
    replacement: str


# A value that is already a placeholder, so rules skip it and stay idempotent.
_PLACEHOLDER = r"<[A-Z0-9_]+>"

# The value side of a key=value pair. Accepts a quoted string or a bare run,
# but never an existing placeholder.
_VALUE = rf'(?!{_PLACEHOLDER})(?:"[^"\r\n]*"|[^\s,;&\]\}}"\r\n]+)'


def _keyed(label: str, keys: Iterable[str], placeholder: str) -> Rule:
    """Build a ``key=value`` rule that preserves the key and masks the value."""
    alternation = "|".join(keys)
    pattern = re.compile(
        rf"(?P<key>\b(?:{alternation})\b)(?P<sep>\s*[=:]\s*)(?P<value>{_VALUE})"
    )
    return Rule(label=label, pattern=pattern, replacement=rf"\g<key>\g<sep>{placeholder}")


#: Ordered detection rules. Order is significant: the most specific shapes run
#: first so that a keyed value keeps its key label instead of collapsing into
#: the generic long-digit-run rule.
RULES: tuple[Rule, ...] = (
    # 17 digits beginning 7656119. Must precede the generic digit-run rule.
    Rule(
        label="STEAMID64",
        pattern=re.compile(r"(?<!\d)7656119\d{10}(?!\d)"),
        replacement="<STEAMID64>",
    ),
    _keyed(
        "TOKEN",
        (
            "accessToken",
            "access_token",
            "AccessToken",
            "authToken",
            "auth_token",
            "refreshToken",
            "refresh_token",
            "sessionTicket",
            "session_ticket",
            "ticket",
        ),
        "<TOKEN>",
    ),
    _keyed(
        "OPENID",
        ("openID", "openId", "OpenID", "open_id", "openid"),
        "<OPENID>",
    ),
    _keyed(
        "USERID",
        ("userId", "userID", "UserId", "user_id", "userid"),
        "<USERID>",
    ),
    _keyed(
        "ACCOUNT_NAME",
        ("AccountName", "accountName", "account_name", "accountname"),
        "<ACCOUNT_NAME>",
    ),
    _keyed(
        "PERSONA",
        (
            "onelineDisplayName",
            "OnelineDisplayName",
            "oneline_display_name",
            "displayName",
            "DisplayName",
            "display_name",
            "personaName",
            "PersonaName",
            "persona_name",
            "persona",
            "nickName",
            "nickname",
            "NickName",
        ),
        "<PERSONA>",
    ),
    _keyed(
        "PRODUCTUSERID",
        ("ProductUserId", "productUserId", "product_user_id", "puid"),
        "<PRODUCTUSERID>",
    ),
    _keyed(
        "STEAMID64",
        ("steamId", "steamID", "SteamId", "steam_id", "steamid64", "SteamID64"),
        "<STEAMID64>",
    ),
    # Bare 32-char hex: an EOS ProductUserId with no key in sight.
    Rule(
        label="PRODUCTUSERID",
        pattern=re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])"),
        replacement="<PRODUCTUSERID>",
    ),
    # Dotted quad. Over-broad by design: it will also eat a four-part version
    # string. See the module docstring - that trade is intentional.
    Rule(
        label="IPV4",
        pattern=re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"),
        replacement="<IPV4>",
    ),
    # Any remaining bare digit run of 15 or more. Catches GSDK ids that arrive
    # under a key this module has never seen.
    Rule(
        label="LONG_ID",
        pattern=re.compile(r"(?<!\d)\d{15,}(?!\d)"),
        replacement="<LONG_ID>",
    ),
)

#: Every label this module can emit.
ALL_LABELS: frozenset[str] = frozenset(rule.label for rule in RULES)

#: Labels appropriate for scanning repository source files. ``IPV4`` is
#: excluded because a four-part version string is indistinguishable from an
#: address by pattern, and a source tree is full of version strings. That
#: exclusion applies to file scanning only - :func:`assert_clean` on log text
#: still enforces it.
FILE_SCAN_LABELS: frozenset[str] = ALL_LABELS - {"IPV4"}


def redact(text: str) -> str:
    """Return ``text`` with every recognised sensitive value masked.

    Replacements are stable labelled placeholders, so redacting the same input
    twice produces byte-identical output and redacting already-redacted text
    is a no-op.
    """
    if not text:
        return text
    result = text
    for rule in RULES:
        result = rule.pattern.sub(rule.replacement, result)
    return result


def iter_sensitive(
    text: str, labels: Iterable[str] | None = None
) -> Iterator[tuple[str, str, int]]:
    """Yield ``(label, matched_text, offset)`` for each surviving hit.

    ``labels`` restricts the scan to a subset of rule labels; the default is
    every rule. Matches are yielded in rule order, then in text order within a
    rule, so output is deterministic.
    """
    if not text:
        return
    wanted = ALL_LABELS if labels is None else frozenset(labels)
    for rule in RULES:
        if rule.label not in wanted:
            continue
        for match in rule.pattern.finditer(text):
            yield rule.label, match.group(0), match.start()


def assert_clean(text: str, labels: Iterable[str] | None = None) -> None:
    """Raise :class:`RedactionError` if anything sensitive survives in ``text``.

    The exception message names the label, the offending match, the byte
    offset and the 1-based line number, so a failure points at the leak rather
    than merely announcing one.
    """
    for label, matched, offset in iter_sensitive(text, labels):
        line_no = text.count("\n", 0, offset) + 1
        raise RedactionError(
            f"unredacted {label} at offset {offset} (line {line_no}): {matched!r}"
        )
