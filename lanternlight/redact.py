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

Display names - three mechanisms, on purpose
--------------------------------------------

The 2026-08-09 capture carries the operator's two-token display name 686
times, in 40-odd distinct shapes. A single mechanism cannot reach all of them,
so there are three, and which mechanism a pattern belongs to is a decision
about blast radius, not about taste.

1. :data:`RULES` - structural detectors. Some are keyed on *distinctive* names
   such as ``onelineDisplayName``, ``PlayerName`` or ``uName``; the rest are
   keyless slots the game is measured to fill with a display name and nothing
   else, such as ``PlayerOpenTreasureBox <PERSONA>`` or the actor token
   ``<PERSONA>_<19-digit role id>``. These also run over every tracked file in
   the repository (``tests/test_no_pii.py``), so nothing generic enough to fire
   on ordinary source or prose is allowed in here.

2. :data:`LOG_TEXT_RULES` - the same idea for keys that are far too generic to
   point at a source tree, above all a bare lowercase ``name``. Masking is
   local: the value next to the key is replaced and nothing else. These never
   run over repository files.

3. Persona discovery - :func:`discover_personas` harvests candidate display
   names from every shape in (1) and (2), and :func:`redact` then masks every
   literal occurrence of each candidate anywhere in the text. This is what
   reaches an occurrence in no key and no known slot at all: one keyed line
   anywhere in a document cleans the rest of it. Discovery is never wired into
   :data:`RULES`: the file scanner would harvest ordinary identifiers out of
   source code and then flag every occurrence of them, and the guard would be
   useless within a day.

The keyless rules and discovery overlap deliberately. Removing the rules leaves
the isolated shapes still masked - discovery harvests from the same slots - but
it blinds the repository scan, which only ever sees :data:`RULES`. Removing
discovery leaves anything outside an enumerated slot exposed. Both were
mutation-tested; neither is decoration.

Discovery is deliberately narrow about *which* keys it trusts. A key that
carries names and also carries other things - ``instigator`` also carries
``true``, a bare ``name`` also carries the product name - is a masking key at
most, never a harvesting key, because a harvested candidate is masked
everywhere in the document. The candidate filter refuses booleans, pure digit
runs, Unreal class instances and anything with no letter in it.

Excerpts - read this before committing a fixture
------------------------------------------------

Discovery is scope-dependent by construction: it learns the name from a keyed
occurrence, and an excerpt of a dozen interesting dungeon lines may contain
none. The keyless rules in (1) cover every slot measured in this capture, but
they cover an enumerated list, and a build the game ships next month can add a
slot nobody has seen. So the safe order is:

    clean = redact(whole_log)       # the login line is in here
    excerpt = pick_lines(clean)     # cut AFTER redacting, never before
    assert_clean(excerpt)

If the excerpt has to be cut first, name the personas explicitly::

    names = discover_personas(whole_log)
    clean = redact(excerpt, personas=names)
    assert_clean(clean, personas=names)

:func:`assert_clean` enforces this rather than trusting anyone to remember it.
Given text that sits in a known name slot but from which no name could be
determined, it raises instead of reporting clean - "I could not tell" is a
different fact from "it is safe", and only one of them is recoverable after a
push.

Encoded content - a fourth mechanism, and a different trade
-----------------------------------------------------------

Everything above reads plain text, so a single base64 pass defeated all of it
at once. :func:`iter_encoded_sensitive` closes that: it finds base64, hex and
raw wide-character runs, decodes them, and re-runs the structural rules on what
comes out.

The wide-character reading matters most here and it arrived last. Unreal stores
a save's strings as UTF-16 whenever they are not pure ASCII, so an id inside a
``.sav`` sits on disk with a NUL between every digit and no digit-run rule can
see it. Until 2026-08-09 that reading only ran on DECODED bytes, so a UTF-16
identifier wrapped in base64 was caught and the same identifier written raw
into a file was not - backwards from how the two actually arrive.

It is a **detector only, and deliberately not wired into** :func:`redact` or
:func:`assert_clean`. Rewriting bytes inside an encoded blob would corrupt the
blob, so there is nothing for :func:`redact` to do, and an :func:`assert_clean`
that raised on encoded text would be raising on something the caller has no way
to fix. The rule for callers is instead: **redact before encoding, never
after.** The gate that enforces it is the repository scan in
``tests/test_no_pii.py``, which runs both passes over every published file.

Its false-positive budget is also the opposite of this module's. Over-redaction
costs an uglier fixture; a repository guard that fires on innocent text blocks
every commit in the project. So the encoded half is tuned for near-zero false
positives and the number is measured, not asserted - see the block above
:func:`iter_encoded_sensitive`.

Save-file identifiers, and a false-positive family worth naming
---------------------------------------------------------------

The transient ``StandaloneSlot`` save carries id shapes the length-only
``LONG_ID`` rule already catches but cannot describe. ``BATTLEID``,
``OWNER_ROLEID``, ``ROLEID`` and ``SAVE_SLOT`` name them. They are a RENAMING,
not a widening and not a narrowing: each takes a digit run at ``LONG_ID``'s own
floor, so every value they decline is one ``LONG_ID`` declines too. See
:data:`_ID_VALUE` for why the value side is a digit run rather than anything at
all, and :data:`_SAVE_SLOT` for why the slot name is matched by shape.

Measured on the largest generation of that save, 177,878 bytes, 2026-08-11:

- The operator roleId is 19 digits. 38 occurrences of a 19-digit run are
  genuine ids - 18 distinct - and every one of them shares the roleId's first
  12 digits. **The prefix is the smaller half of the problem.** 5 distinct ids
  share 17 of 19 digits, and the roleId itself appears VERBATIM 5 times: twice
  inside a slot name and three times as ``ownerRoleId`` in ``ItemCell`` JSON.
  A fixture that masks the roleId and nothing else still ships 17 of its 19
  digits, five times over.
- ``BattleId`` is a ``StrProperty`` holding 19 digits and shares **12** leading
  digits with the roleId - measured identically across all 250 captured
  generations of the save. An earlier note recording 14 is refuted.

The false positives are a single cause wearing two masks. Unreal stores a
Blueprint property name as ``Name_Index_<32 uppercase hex GUID>`` - a variable
called ``Hp`` becomes ``Hp_10_<GUID>`` - and that GUID trips two independent
rules:

- ``PRODUCTUSERID`` fires 772 times, 67 distinct. 770 occurrences (65 distinct)
  are the Blueprint shape and 2 are ``monsterGuid`` values in JSON. All are
  uppercase and NONE equals the operator's real ProductUserId.
- ``LONG_ID`` fires 100 times, of which 62 sit INSIDE just two of those GUIDs,
  which happen to contain a 17-digit and a 16-digit decimal stretch. The
  17-digit one recurs 61 times because the same property name repeats per
  ``MonsterData`` entry.

**Neither rule is narrowed, and the reason is not squeamishness.** Uppercase is
not a safe discriminator - the same 32 characters identify the same account in
either case, and any formatter in the path can change one without changing the
other - and position is not either, because a real ProductUserId can sit in the
same textual slot. A narrowing on either axis buys a prettier build log and
sells a silent false negative, which is the one failure this module cannot
recover from. A GUID is a format fact of the shipped asset rather than a
machine fact, so the fixture authors its own GUID suffixes and both classes
vanish without a detector being touched. ``tests/test_redact.py`` pins all of
this as a characterization, with a positive control proving a real-shaped
identifier in the same position is still caught.

Limits, stated rather than hidden:

- **The keyless rules are an enumerated list, not a general solution.** A name
  slot this capture does not contain will not be masked, and if the surrounding
  text carries no other signal it will not be discovered either. The
  cannot-certify path narrows this to slots that share a marker with a known
  one; an entirely novel shape in otherwise unremarkable text is still a silent
  pass.
- **The encoded pass reads standard base64, hex and wide characters only.** The
  URL-safe base64 alphabet is not accepted, because ``_`` separates every
  snake_case identifier in this repository and admitting it would fuse ordinary
  source into multi-hundred-character "runs". Compression, encryption and any
  encoding outside those three are out of reach - there is no general answer,
  and a guard that claimed one would be lying.
- **The wide reading sees ASCII inside UTF-16, not UTF-16 in general.** It
  collapses runs of ``(character, NUL)`` pairs, which is what an ASCII string
  stored as UTF-16 looks like in either endianness. An identifier written in
  non-ASCII digits, or a wide string in an encoding with no NUL half, is not
  reached. Whole-file NUL stripping would reach slightly more and was rejected
  on measured false positives - see the block above :data:`_WIDE_RUNS`.
- A display name shorter than three characters is not literal-masked; masking a
  two-character token by substring would shred ordinary words.
- City/state/country are not pattern-detectable. Redact geolocation lines by
  dropping the line, not by trusting a regex.

Typical use::

    clean = redact(raw_text)
    assert_clean(clean)
"""

import base64
import binascii
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

__all__ = [
    "ALL_LABELS",
    "FILE_SCAN_LABELS",
    "LOG_TEXT_RULES",
    "PERSONA_PLACEHOLDER",
    "RedactionError",
    "Rule",
    "RULES",
    "assert_clean",
    "discover_personas",
    "iter_encoded_sensitive",
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


#: The one placeholder this module emits for a display name.
PERSONA_PLACEHOLDER = "<PERSONA>"

# A value that is already a placeholder, so rules skip it and stay idempotent.
_PLACEHOLDER = r"<[A-Z0-9_]+>"

# One unquoted value token: everything up to whitespace or a structural
# delimiter.
_WORD = r'[^\s,;&\]\}"\r\n]+'

# The value side of a key=value pair. Accepts a quoted string or a bare run,
# but never an existing placeholder.
_VALUE = rf'(?!{_PLACEHOLDER})(?:"[^"\r\n]*"|{_WORD})'

# A Steam display name is several words - "<first> <second>" in this capture -
# and the old single-token value pattern published the second half of it. This
# one keeps going past a space, but stops at the next ``key=`` or ``key:``, so
# ``PlayerName=<PERSONA> TagName=Game.PlayState.Gaming`` masks the name and
# leaves the tag alone.
#
# The repeat is bounded rather than open. A display name is a handful of
# tokens; an unbounded run would swallow the whole tail of any line that
# happens to end in prose, and a fixture nobody can read is a fixture nobody
# checks.
_MAX_TRAILING_NAME_WORDS = 3
_DISPLAY_VALUE = (
    rf'(?!{_PLACEHOLDER})'
    rf'(?:"[^"\r\n]*"'
    rf"|{_WORD}(?:[ \t]+(?![^\s]*[=:]){_WORD}){{0,{_MAX_TRAILING_NAME_WORDS}}})"
)

# ``key=``, ``key:``, and the JSON ``"key":`` the game's telemetry blobs use.
#
# Horizontal whitespace only. The game never splits a key from its value across
# a line, but prose does: a sentence ending in a word this module treats as a
# key, followed by a blank line and a table, used to match as a key/value pair
# and fail the repository scan on an innocent document.
_KEY_SEP = r'"?[ \t]*[=:][ \t]*'

# A token that could be a display name: starts with a letter in any script -
# the capture contains a CJK player name - and runs to the next delimiter.
# ``:`` and ``=`` are excluded so a name token can never swallow the next
# field, and a leading digit is excluded so a count is never mistaken for a
# person.
_NAME_TOKEN = r'[^\W\d_][^\s,;:=&\]\}"\r\n]*'

# One name token, or two when the second ends cleanly at a delimiter. The
# second-token branch is what keeps ``Controller <PERSONA>`` from publishing a
# surname, while the end assertion is what stops ``uiProxy <PERSONA> Result:``
# from eating the word Result.
_POSITIONAL_VALUE = rf'(?!{_PLACEHOLDER}){_NAME_TOKEN}'
_POSITIONAL_PAIR_VALUE = (
    rf'(?!{_PLACEHOLDER}){_NAME_TOKEN}(?:[ \t]+{_NAME_TOKEN}(?=[\s,;&\]\}}"]|$))?'
)


def _keyed(
    label: str, keys: Iterable[str], placeholder: str, value: str = _VALUE
) -> Rule:
    """Build a ``key=value`` rule that preserves the key and masks the value."""
    alternation = "|".join(keys)
    pattern = re.compile(
        rf"(?P<key>\b(?:{alternation})\b)(?P<sep>{_KEY_SEP})(?P<value>{value})"
    )
    return Rule(label=label, pattern=pattern, replacement=rf"\g<key>\g<sep>{placeholder}")


def _positional(anchors: Iterable[str], value: str) -> Rule:
    """Build a rule for a name that follows a fixed phrase and carries no key.

    The game writes the operator's display name into a set of fixed slots -
    ``PlayerOpenTreasureBox <PERSONA>`` and friends - with nothing to mark it
    as a name. Those slots are enumerable, and every one of them was measured
    before being listed: on the 2026-08-09 capture each anchor below is
    occupied by the operator's name in 100 percent of its occurrences.

    This is what makes an *excerpt* safe. Discovery needs a keyed occurrence
    somewhere in the same text to learn the name from; a handful of dungeon
    lines lifted out of the middle of a log has none, and before these rules
    existed that excerpt came back from :func:`redact` unchanged and passed
    :func:`assert_clean`.
    """
    alternation = "|".join(anchors)
    pattern = re.compile(
        rf"(?P<key>\b(?:{alternation}))(?P<sep>[ \t]+)(?P<value>{value})"
    )
    return Rule(
        label="PERSONA",
        pattern=pattern,
        replacement=rf"\g<key>\g<sep>{PERSONA_PLACEHOLDER}",
    )


#: Shortest bare digit run this module treats as an identifier. Named rather
#: than repeated so the keyed id rules below and the generic ``LONG_ID`` rule
#: cannot drift apart on the one number that makes them compatible.
_LONG_ID_MIN_DIGITS = 15

# The value side of an identifier rule: a bare digit run at ``LONG_ID``'s own
# floor. Deliberately NOT :data:`_VALUE`, and the reason is measured rather
# than aesthetic.
#
# These rules run over every tracked file (``tests/test_no_pii.py``), so a rule
# generic enough to fire on prose blocks every commit in the project. Two
# collisions in the tree today, both innocent and both already committed:
# ``docs/FINDINGS.md`` records a generated bot's roleId - five digits, negative,
# naming no person - and ``ROADMAP.md`` discusses ``BattleId`` in ordinary
# English. A ``key=<anything>`` rule fires on both.
#
# The digit floor makes these rules a RENAMING rather than a narrowing, which
# is the property that matters: every value they decline is a value ``LONG_ID``
# declines too, so nothing that was caught before stops being caught. What they
# add is the label - a reviewer of a committed fixture needs to know that the
# long number is the operator's own roleId and not a battle serial.
#
# Stated rather than hidden: an identifier written under one of these keys as
# something OTHER than a long digit run - a UUID, a hex blob - is not named by
# these rules. It is not caught by ``LONG_ID`` either, so this is a pre-existing
# blind spot these rules neither widen nor close.
_ID_VALUE = rf"\d{{{_LONG_ID_MIN_DIGITS},}}(?!\d)"

# ``key=``, ``key:`` and the JSON ``"key":"`` form. The trailing ``"?`` steps
# over an opening quote so the quote survives redaction instead of being eaten
# with the value, which keeps a redacted JSON blob parseable.
_ID_KEY_SEP = r'"?[ \t]*[=:][ \t]*"?'


def _keyed_id(label: str, keys: Iterable[str], placeholder: str) -> Rule:
    """Build a ``key=<long digit run>`` rule. See :data:`_ID_VALUE`."""
    alternation = "|".join(keys)
    pattern = re.compile(
        rf"(?P<key>\b(?:{alternation})\b)(?P<sep>{_ID_KEY_SEP})(?P<value>{_ID_VALUE})"
    )
    return Rule(label=label, pattern=pattern, replacement=rf"\g<key>\g<sep>{placeholder}")


def _dashed(label: str, keys: Iterable[str], placeholder: str) -> Rule:
    """Build a ``key-value`` rule. The game emits this shape for names.

    The dash carries no surrounding whitespace on purpose. ``displayName-x`` is
    a field; ``persona - x`` is a sentence, and this module has no business
    rewriting sentences.
    """
    alternation = "|".join(keys)
    pattern = re.compile(
        rf"(?P<key>\b(?:{alternation})\b)(?P<sep>-)(?P<value>{_DISPLAY_VALUE})"
    )
    return Rule(label=label, pattern=pattern, replacement=rf"\g<key>\g<sep>{placeholder}")


#: Display-name keys distinctive enough to be safe over a source tree. Every
#: one of these was checked against the tracked files before being added.
_DISTINCTIVE_PERSONA_KEYS: tuple[str, ...] = (
    "onelineDisplayName",
    "OnelineDisplayName",
    "oneline_display_name",
    "OnlineDisplayName",
    "onlineDisplayName",
    "online_display_name",
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
    "PlayerName",
    "playerName",
    "player_name",
    "memberName",
    "MemberName",
    "member_name",
    "roleName",
    "RoleName",
    "role_name",
    "uName",
    "uname",
    "userName",
    "UserName",
    "user_name",
    "username",
)

#: Capitalised ``Name`` is generic, but it carries no value under any
#: separator anywhere in the tracked tree, and the game uses it for the URL
#: option and the player-state dump. It masks locally and is never a discovery
#: source - harvesting from it would pick up the product name and the word
#: "Player", each of which occurs in the hundreds.
_GENERIC_PERSONA_KEYS: tuple[str, ...] = ("Name",)

#: Lowercase ``name`` fires 20 times in this repository's own tracked files
#: (``name: str``, ``name="reticle"``, agent front-matter). It can never enter
#: :data:`RULES`, so it lives in :data:`LOG_TEXT_RULES` instead.
_LOG_ONLY_PERSONA_KEYS: tuple[str, ...] = ("name",)

#: Keys that carry a display name often enough to harvest from, but that are
#: not safe to mask wholesale. ``instigator`` also carries ``true``, ``false``
#: and Unreal class instances; ``role_id`` normally carries a digit run. The
#: candidate filter throws those away, and what is left is a name.
_HARVEST_ONLY_KEYS: tuple[str, ...] = ("instigator", "role_id")

#: ``channel-`` carries the display name in this capture. The colon form
#: (``"channel":"Steam"``) does not, so only the dash form is masked.
_DASH_ONLY_PERSONA_KEYS: tuple[str, ...] = ("channel",)

# An actor token: a display name welded to a 15-or-more-digit role id, which
# the game writes as ``actor:<PERSONA>_<LONG_ID>``. Before this rule the
# generic long-digit rule ate the id and left the name standing, which is
# exactly backwards - the id is replaceable and the name is not.
#
# The ``(?<!_C)`` carve-out keeps Unreal class instances intact: a token like
# ``BP_Adventurer_C_<id>`` falls through to LONG_ID, which masks the id and
# leaves the class name readable. Measured cost of the rule on the 2026-08-09
# capture: 165 tokens match, 164 of them the operator's name and one an engine
# object (``CampData``), so one legitimate name is lost to over-redaction. At a
# 10-digit threshold the same rule would have collided with 8158 ``_C_``
# instance tokens; 15 digits is the threshold that separates a role id from an
# Unreal object id, and it is the same threshold LONG_ID already uses.
_ACTOR_TOKEN_NAME = r"(?<![A-Za-z0-9_])(?P<value>[A-Za-z][A-Za-z0-9_]*)(?<!_C)"
_ACTOR_TOKEN = re.compile(rf"{_ACTOR_TOKEN_NAME}_\d{{15,}}(?!\d)")

#: Fixed phrases the game follows with a bare display name. Occurrences on the
#: 2026-08-09 capture, every one of them the operator's name and nothing else:
#: PlayerOpenTreasureBox 20, PlayerKillMonster 9, uiProxy 5, ResponseInitInventory
#: 4, playerStartPoint 2 (a third occurrence has an empty slot, which the
#: leading-letter requirement skips), onAdventurerInited 2,
#: LeaderRankScoreComponent 2.
_POSITIONAL_ANCHORS: tuple[str, ...] = (
    "PlayerOpenTreasureBox",
    "PlayerKillMonster",
    "onAdventurerInited",
    "uiProxy",
    "playerStartPoint",
    "ResponseInitInventory",
    r"LeaderRankScoreComponent\]",
)

#: The one anchor whose slot holds the full two-token display name (6 of 6).
_POSITIONAL_PAIR_ANCHORS: tuple[str, ...] = ("PossessedBy Controller",)

# ``<UnrealClass>_C_<id>,<PERSONA>,<digits>`` - the ammunition telemetry writes
# the firing player's name into a bare CSV field. 134 occurrences on the
# capture, all 134 the operator's name, which is why this is a rule and not a
# guess.
_CSV_NAME_SLOT = re.compile(
    rf'(?P<key>\b[A-Za-z][A-Za-z0-9_]*_C_\d{{6,}},)(?P<value>(?!{_PLACEHOLDER})[^\s,\r\n]+)(?=,\d)'
)

# ``Player <PERSONA>'s state ...``. The possessive is what makes this specific
# enough to be safe; a bare ``Player <word>`` is not.
_POSSESSIVE_NAME = re.compile(
    rf"(?P<key>\bPlayer)(?P<sep>[ \t]+)(?P<value>{_POSITIONAL_VALUE})(?=')"
)

# ``StandaloneSlot_<19-digit roleId>``, the name the game gives a save slot,
# measured under the keys ``AutoSaveTempSlot`` and ``AutoSaveFinalSlot`` (the
# temp one carries a trailing ``_Temp``). It is masked by SHAPE rather than by
# key, for a reason specific to this file format: a ``.sav`` is GVAS, where a
# key and its value are two separate length-prefixed strings with no separator
# between them at all. There is no ``key=value`` for a keyed rule to find, so a
# keyless shape rule is the only one that reaches the value on disk.
#
# It must precede the ACTOR rule. ``StandaloneSlot_<19 digits>`` fits the actor
# token exactly - an identifier welded to a 15-or-more-digit run - so without
# this the slot name is reported as a player display name, which is a wrong
# answer rather than a merely imprecise one.
_SAVE_SLOT = re.compile(
    rf"(?<![A-Za-z0-9_])StandaloneSlot_\d{{{_LONG_ID_MIN_DIGITS},}}(?!\d)"
)

# ``BP_Adventurer_C_<id>__<PERSONA>enter portal``. The game concatenates the
# actor label, the name and sometimes the next word with no separator at all,
# so there is no token boundary to find the end of the name by. Masking the
# whole run takes a word of ordinary text with it - measured cost on the
# capture: the word "enter", once - and that is the right direction to err in.
_WELDED_NAME = re.compile(
    rf"(?P<key>_C_\d{{6,}}__)(?P<value>{_POSITIONAL_VALUE})"
)


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
        _DISTINCTIVE_PERSONA_KEYS + _GENERIC_PERSONA_KEYS,
        PERSONA_PLACEHOLDER,
        value=_DISPLAY_VALUE,
    ),
    # Keyless name slots. These are what make a redacted excerpt safe without
    # a login line in it - see _positional().
    _positional(_POSITIONAL_ANCHORS, _POSITIONAL_VALUE),
    _positional(_POSITIONAL_PAIR_ANCHORS, _POSITIONAL_PAIR_VALUE),
    Rule(
        label="PERSONA",
        pattern=_CSV_NAME_SLOT,
        replacement=rf"\g<key>{PERSONA_PLACEHOLDER}",
    ),
    Rule(
        label="PERSONA",
        pattern=_POSSESSIVE_NAME,
        replacement=rf"\g<key>\g<sep>{PERSONA_PLACEHOLDER}",
    ),
    Rule(
        label="PERSONA",
        pattern=_WELDED_NAME,
        replacement=rf"\g<key>{PERSONA_PLACEHOLDER}",
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
    # Save-file id shapes. Each names a long digit run the LONG_ID rule below
    # already catches by length alone - see _ID_VALUE for why naming it matters
    # and why the value side is a digit run rather than anything at all.
    #
    # OWNER_ROLEID precedes ROLEID for readability only; ``\b`` cannot match
    # inside ``OwnerRoleId`` anyway, because the character before ``RoleId``
    # there is a word character.
    _keyed_id(
        "BATTLEID",
        ("BattleId", "battleId", "BattleID", "battle_id", "battleid"),
        "<BATTLEID>",
    ),
    _keyed_id(
        "OWNER_ROLEID",
        ("OwnerRoleId", "ownerRoleId", "OwnerRoleID", "owner_role_id", "ownerroleid"),
        "<OWNER_ROLEID>",
    ),
    _keyed_id("ROLEID", ("roleId", "RoleId", "RoleID", "role_id", "roleid"), "<ROLEID>"),
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
    # A save slot name. Must precede ACTOR - see _SAVE_SLOT.
    Rule(label="SAVE_SLOT", pattern=_SAVE_SLOT, replacement="<SAVE_SLOT>"),
    # Name welded to a role id. Must precede LONG_ID, or LONG_ID masks the id
    # and publishes the name.
    Rule(label="ACTOR", pattern=_ACTOR_TOKEN, replacement="<ACTOR>"),
    # Any remaining bare digit run of 15 or more. Catches GSDK ids that arrive
    # under a key this module has never seen.
    Rule(
        label="LONG_ID",
        pattern=re.compile(rf"(?<!\d)\d{{{_LONG_ID_MIN_DIGITS},}}(?!\d)"),
        replacement="<LONG_ID>",
    ),
)

#: Rules for log text only. These keys are too generic to point at a source
#: tree, so they are kept out of :data:`RULES` and therefore out of the
#: repository scan in ``tests/test_no_pii.py``. :func:`redact` and
#: :func:`assert_clean` apply them; :func:`iter_sensitive` does not.
LOG_TEXT_RULES: tuple[Rule, ...] = (
    _keyed("PERSONA", _LOG_ONLY_PERSONA_KEYS, PERSONA_PLACEHOLDER, value=_DISPLAY_VALUE),
    _dashed(
        "PERSONA",
        _LOG_ONLY_PERSONA_KEYS
        + _DASH_ONLY_PERSONA_KEYS
        + _DISTINCTIVE_PERSONA_KEYS
        + _GENERIC_PERSONA_KEYS,
        PERSONA_PLACEHOLDER,
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


# --------------------------------------------------------------------------
# persona discovery
# --------------------------------------------------------------------------

#: Shapes a display name can be harvested from. Every one of these is a key
#: the game uses for a person, or the actor token, which is a person's name
#: welded to their role id.
_DISCOVERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        rf"\b(?:{'|'.join(_DISTINCTIVE_PERSONA_KEYS + _HARVEST_ONLY_KEYS)})\b"
        rf"(?:{_KEY_SEP}|-)(?P<value>{_DISPLAY_VALUE})"
    ),
    # The role blob spells the display name under a bare ``name``, but only in
    # its JSON form. The unquoted form of that same key carries the product
    # name and device strings, so it is not harvested.
    re.compile(r'"names?"[ \t]*:[ \t]*(?P<value>"[^"\r\n]*")'),
    _ACTOR_TOKEN,
    # The keyless slots harvest as well as mask. One dungeon line is then
    # enough to clean every other occurrence in the same excerpt, including
    # shapes that carry no anchor of their own.
    _positional(_POSITIONAL_ANCHORS, _POSITIONAL_VALUE).pattern,
    _positional(_POSITIONAL_PAIR_ANCHORS, _POSITIONAL_PAIR_VALUE).pattern,
    _CSV_NAME_SLOT,
    _POSSESSIVE_NAME,
    _WELDED_NAME,
)

#: Contexts this log is measured to fill with a bare display name. Their
#: presence is what turns "nothing found" into "nothing could be determined" -
#: see :func:`assert_clean`.
_POSITIONAL_RISK = re.compile(
    "|".join(
        (
            rf"\b(?:{'|'.join(_POSITIONAL_ANCHORS + _POSITIONAL_PAIR_ANCHORS)})[ \t]",
            r"_C_\d{6,}[,_]",
            r"\bactor:",
            r"\binstigator[-=:]",
        )
    )
)

#: Evidence that a persona pass has already run over this text.
_PERSONA_EVIDENCE = re.compile(r"<PERSONA>|<ACTOR>")

#: Values a name-shaped key carries that are not people.
_NON_PERSON_VALUES: frozenset[str] = frozenset(
    {"true", "false", "null", "none", "nil", "undefined", "nan", "unknown"}
)

# ``BP_Warden_C_2147408590``, ``DungeonPlayerState_C_2147446955``: an Unreal
# class instance, never a player.
_UNREAL_INSTANCE = re.compile(r"_C_\d|_\d{6,}")

#: Shorter than this and a candidate is not literal-masked. Masking a
#: two-character token by substring would shred ordinary words, and the cure
#: would be worse than the leak.
_MIN_PERSONA_LENGTH = 3


def _clean_candidate(raw: str) -> str:
    """Strip quoting and trailing punctuation off a harvested value."""
    value = raw.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return value.strip().strip(".,;:!?")


def _is_persona_candidate(value: str) -> bool:
    """Return whether ``value`` is name-shaped enough to mask everywhere.

    A candidate is masked at every literal occurrence in the document, so a
    wrong one is expensive: harvesting ``true`` once would blank every ``true``
    in the log. This filter is the thing standing between a name-shaped key and
    that outcome.
    """
    if len(value) < _MIN_PERSONA_LENGTH:
        return False
    if not any(char.isalpha() for char in value):
        return False
    if any(char in value for char in '<>="\\/'):
        return False
    if value.lower() in _NON_PERSON_VALUES:
        return False
    return not _UNREAL_INSTANCE.search(value)


def _normalise_personas(values: Iterable[str]) -> tuple[str, ...]:
    """Deduplicate and order candidates longest first.

    Longest first is not cosmetic. ``<first> <second>`` has to be matched
    before ``<first>``, or a two-token name comes out half-masked with the
    surname still readable.
    """
    seen = {value.strip() for value in values if value and value.strip()}
    return tuple(sorted(seen, key=lambda name: (-len(name), name)))


def discover_personas(text: str) -> tuple[str, ...]:
    """Return display-name candidates harvested from ``text``, longest first.

    Both the whole value and each of its whitespace-separated tokens are
    returned, because the log spells the name both ways - ``uName`` carries
    ``<first> <second>`` while ``instigator-`` carries ``<first>`` alone.
    """
    if not text:
        return ()
    found: set[str] = set()
    for pattern in _DISCOVERY_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _clean_candidate(match.group("value"))
            if not _is_persona_candidate(candidate):
                continue
            found.add(candidate)
            if " " in candidate:
                for token in candidate.split():
                    cleaned = _clean_candidate(token)
                    if _is_persona_candidate(cleaned):
                        found.add(cleaned)
    return _normalise_personas(found)


def _persona_pattern(personas: tuple[str, ...]) -> re.Pattern[str] | None:
    """Compile one alternation over ``personas`` that steps over placeholders.

    The placeholder branch comes first and is echoed back unchanged, so a name
    that happens to sit inside ``<...>`` is never masked twice. That is what
    keeps :func:`redact` idempotent when the caller passes the same names in
    again.
    """
    if not personas:
        return None
    alternation = "|".join(re.escape(name) for name in personas)
    return re.compile(rf"(?P<placeholder>{_PLACEHOLDER})|(?P<hit>{alternation})")


def _mask_personas(text: str, personas: tuple[str, ...]) -> str:
    """Replace every literal occurrence of each name with the placeholder.

    Matching is plain substring, not word-bounded. The capture contains a line
    where the game welds the name to the following word with no separator at
    all, and a word-bounded pass walks straight past it.
    """
    pattern = _persona_pattern(personas)
    if pattern is None:
        return text

    def _replace(match: re.Match[str]) -> str:
        placeholder = match.group("placeholder")
        return placeholder if placeholder is not None else PERSONA_PLACEHOLDER

    return pattern.sub(_replace, text)


# --------------------------------------------------------------------------
# public entry points
# --------------------------------------------------------------------------


def redact(text: str, personas: Iterable[str] | None = None) -> str:
    """Return ``text`` with every recognised sensitive value masked.

    ``personas`` names display names to mask literally. Leave it at ``None`` to
    discover them from ``text`` itself; pass a sequence to use exactly those,
    which is what a caller redacting a fragment of a larger log should do. An
    empty sequence disables the literal pass entirely.

    Replacements are stable labelled placeholders, so redacting the same input
    twice produces byte-identical output and redacting already-redacted text
    is a no-op.
    """
    if not text:
        return text
    candidates = (
        discover_personas(text) if personas is None else _normalise_personas(personas)
    )
    result = text
    for rule in RULES:
        result = rule.pattern.sub(rule.replacement, result)
    for rule in LOG_TEXT_RULES:
        result = rule.pattern.sub(rule.replacement, result)
    return _mask_personas(result, candidates)


def iter_sensitive(
    text: str, labels: Iterable[str] | None = None
) -> Iterator[tuple[str, str, int]]:
    """Yield ``(label, matched_text, offset)`` for each surviving hit.

    ``labels`` restricts the scan to a subset of rule labels; the default is
    every rule. Matches are yielded in rule order, then in text order within a
    rule, so output is deterministic.

    This walks :data:`RULES` only. :data:`LOG_TEXT_RULES` and persona discovery
    are log-text mechanisms and are deliberately absent, because this function
    is also what scans the repository tree - see the module docstring.
    """
    if not text:
        return
    wanted = ALL_LABELS if labels is None else frozenset(labels)
    for rule in RULES:
        if rule.label not in wanted:
            continue
        for match in rule.pattern.finditer(text):
            yield rule.label, match.group(0), match.start()


# --------------------------------------------------------------------------
# encoded content
# --------------------------------------------------------------------------
#
# Every rule above works on plain text, so a single base64 pass defeats all of
# them at once. Measured 2026-08-09::
#
#     planted = "player " + "76561190" + "000000042" + " x"
#     iter_sensitive(planted)                     -> STEAMID64, LONG_ID
#     iter_sensitive(b64encode(planted))          -> nothing at all
#
# That matters because the pressure to commit encoded bytes is structural, not
# occasional: ``.gitignore`` blocks ``*.sav``, so anyone who needs a save
# fixture reaches for an encoded copy, and the guard that is supposed to stand
# behind the ignore rules cannot see into one.
#
# The design constraint runs the opposite way from the rest of this module.
# Over-redaction is cheap - an uglier fixture - but a repository guard that
# fires on innocent text blocks every commit in the project, which is a denial
# of service on the work. So this half is tuned for near-zero false positives
# and says so:
#
#   - A run must be long enough to hold the shortest identifier that exists
#     (15 digits, so 20 base64 characters), or it is far likelier to be a hash,
#     a token or an ordinary CamelCase word than an encoded id.
#   - It must decode, under a strict alphabet check.
#   - The DECODED bytes then have to match one of the rules above. That is the
#     filter doing the real work: garbage bytes essentially never contain 15
#     consecutive ASCII digits (about 1e-22 per position) or 32 consecutive hex
#     characters, so a decoded blob of noise yields nothing.
#
# Measured false-positive rate on the tracked tree: 0 findings across every
# published file, before and after the wide-character reading was added. See
# tests/test_no_pii.py, and the block above _WIDE_RUNS for the control-corpus
# numbers that decided the shape of that rule.

#: Shortest identifier this module knows is 15 digits (``LONG_ID``), which
#: needs 15 decoded bytes, which needs 20 base64 characters. Below that a run
#: cannot be an encoded identifier however it decodes.
_MIN_DECODED_BYTES = 15
_B64_MIN_RUN = 20

#: Standard base64 alphabet only, with ``=`` accepted as trailing padding and
#: never inside the run. Letting ``=`` into the body would weld ``key=`` onto
#: the value that follows it and shift the whole decode out of phase.
#:
#: The URL-safe alphabet is deliberately NOT accepted: ``_`` is the separator
#: in every snake_case identifier in this repository, so admitting it would
#: fuse ordinary Python names into multi-hundred-character "runs". A urlsafe
#: blob is therefore a known blind spot, stated rather than hidden.
_B64_RUN = re.compile(rf"[A-Za-z0-9+/]{{{_B64_MIN_RUN},}}={{0,2}}")

#: A whole line that is nothing but one base64 run. Consecutive such lines are
#: joined before decoding, because an encoder that wraps at 76 columns puts a
#: line break wherever it likes - possibly through the middle of an identifier
#: - and decoding each line on its own would then miss it.
_B64_LINE = re.compile(rf"[A-Za-z0-9+/]{{{_B64_MIN_RUN},}}={{0,2}}")

#: Hex needs twice the characters for the same bytes. 40 is also the length of
#: a git sha, which is the shape this will most often decode and discard.
_HEX_MIN_RUN = _MIN_DECODED_BYTES * 2
_HEX_RUN = re.compile(rf"(?<![0-9A-Za-z])[0-9a-fA-F]{{{_HEX_MIN_RUN},}}(?![0-9A-Za-z])")

# Wide characters, which is the one encoding this project meets more often than
# base64. Unreal stores a save's strings as UTF-16 whenever they are not pure
# ASCII, so a 17-digit id in a `.sav` sits on disk as ``7 NUL 6 NUL 5 NUL ...``
# and no digit-run rule can see it. Measured 2026-08-09 against the merged
# tree, which is what makes this a defect rather than a theory::
#
#     UTF-16 identifier INSIDE a base64 blob -> caught
#     RAW UTF-16 identifier in a file        -> MISSED
#
# The NUL-stripped reading in _views only ever ran on DECODED bytes, one layer
# down. It never saw a file's own content, so the exotic case was covered and
# the likely one was not.
#
# WHY PAIRS AND NOT A WHOLE-FILE NUL STRIP. Dropping every NUL in a file is the
# obvious fix and it is the wrong one: a binary is mostly padding, so stripping
# welds a digit before a 64-byte run of NULs onto a digit after it and
# manufactures a 15-digit "identifier" out of two short numbers that were never
# adjacent. Collapsing only maximal runs of (character, NUL) pairs cannot do
# that, because two consecutive NULs break the alternation - and two consecutive
# NULs is exactly what padding is.
#
# Measured 2026-08-09, whole-file strip against the pair rule, same harness and
# same run:
#
#   - this repository's own `__pycache__`: naive 32 findings over 4 `.pyc`
#     files, every one invented by the strip. Pair rule: 0.
#   - a 22,110-file control corpus (a Python install, deliberately hostile -
#     compiled `.pyd` and `.dll` binaries full of 16-bit tables that look
#     exactly like wide characters): naive 5301 findings over 395 files, 12 of
#     which the existing plain scan does not already flag. Pair rule as shipped:
#     178 findings over 14 files, 5 of which the plain scan does not already
#     flag. Every one of those 5 is a compiled extension module whose uint16
#     lookup tables happen to hold ASCII digit values.
#   - every published file in this repository, which is the set the guard
#     actually walks: 0 findings before the change and 0 after.
#
# So the marginal cost of this rule, in commits that would newly be refused, is
# zero here and 5 files in 22,110 on a corpus of a kind this repository does not
# contain. The rejected alternative costs 2.4 times that in files and 30 times
# that in findings, and it fires on this project's own build artifacts.
#
# The two endiannesses are separate patterns rather than one alternation so
# that each keeps its own phase. A run is read by taking every second byte,
# starting at 0 for little-endian and at 1 for big-endian.
#
# The minimum is the same 15 bytes the rest of this section uses, expressed in
# pairs. A shorter run cannot hold the shortest identifier that exists however
# it is read, so collapsing it can only manufacture noise.
_WIDE_MIN_PAIRS = _MIN_DECODED_BYTES
_WIDE_RUNS: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (re.compile(rf"(?:[^\x00]\x00){{{_WIDE_MIN_PAIRS},}}"), 0, "little-endian"),
    (re.compile(rf"(?:\x00[^\x00]){{{_WIDE_MIN_PAIRS},}}"), 1, "big-endian"),
)

#: How many times to peel an encoding. 1 catches base64-of-a-save, which is the
#: realistic accident; 2 also catches base64-of-hex and the deliberate double
#: encode. Deeper costs more than it can plausibly buy, and each extra layer is
#: nearly free of false positives only because decoded noise almost never
#: contains a 20-character run of base64 alphabet either.
_MAX_ENCODED_DEPTH = 2


def _decode_b64(run: str) -> bytes | None:
    """Decode one base64 run, or return None if it is not base64 after all.

    Padding is recomputed rather than trusted. A run clipped out of a larger
    stream arrives unpadded, and refusing those would blind this to every
    unpadded encoder for no gain - an invalid body still fails ``validate``.
    """
    core = run.rstrip("=")
    remainder = len(core) % 4
    if remainder == 1:
        # No byte string encodes to 4n+1 characters, so this is not base64.
        return None
    try:
        return base64.b64decode(core + "=" * ((4 - remainder) % 4), validate=True)
    except (binascii.Error, ValueError):
        return None


def _decode_hex(run: str) -> Iterator[bytes]:
    """Yield the byte views of one hex run.

    An odd-length run is one character out of phase at exactly one end, and
    which end is unknowable, so both are tried. An even-length run is taken as
    written.

    A run carrying no hex LETTER is a decimal number, not a hex blob, and is
    skipped. This is the one systematic false-positive class measured on a
    20,077-file corpus: ``0x33`` is the character ``3``, so hex-decoding a long
    decimal literal such as ``0.3333...`` hands back a run of digits and trips
    ``LONG_ID``. Skipping it costs no coverage at all, because a hex dump of an
    ASCII identifier is itself a long digit run - ``76561190...`` hex-encodes to
    ``3736353631...`` - which the plain ``LONG_ID`` rule already catches without
    decoding anything. Measured: this removed 7 of 23 findings on that corpus
    and 0 of the true positives.
    """
    if not any(char in "abcdefABCDEF" for char in run):
        return
    for start in (0, 1) if len(run) % 2 else (0,):
        usable = run[start:]
        usable = usable[: len(usable) - len(usable) % 2]
        if len(usable) < _HEX_MIN_RUN:
            continue
        try:
            yield bytes.fromhex(usable)
        except ValueError:
            continue


def _views(raw: bytes) -> Iterator[tuple[str, str]]:
    """Yield ``(marker, text)`` readings of decoded bytes.

    latin-1 rather than utf-8-with-replace: the payload is arbitrary bytes, and
    ``replace`` fuses invalid sequences into a single U+FFFD, which silently
    joins or destroys the runs being looked for. latin-1 is total and
    length-preserving, so nothing is lost and offsets stay byte-exact.

    The NUL-stripped reading is what reaches a UTF-16 string. Unreal writes a
    save's text as UTF-16 whenever it is not pure ASCII, and a 17-digit id
    stored that way reads as ``7.6.5.6...`` with a NUL between every digit -
    which no digit-run rule can see. Dropping the NULs collapses it back.
    """
    yield "", raw.decode("latin-1")
    if b"\x00" in raw:
        yield " (nul-stripped reading)", raw.replace(b"\x00", b"").decode("latin-1")


def _b64_blocks(text: str) -> Iterator[tuple[int, str, int]]:
    """Yield ``(offset, joined, line_count)`` for each wrapped base64 block."""
    group: list[tuple[int, str]] = []
    cursor = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if _B64_LINE.fullmatch(stripped):
            group.append((cursor, stripped))
        else:
            if len(group) >= 2:
                yield group[0][0], "".join(part for _, part in group), len(group)
            group = []
        cursor += len(line)
    if len(group) >= 2:
        yield group[0][0], "".join(part for _, part in group), len(group)


def _wide_candidates(text: str) -> Iterator[tuple[int, bytes, str]]:
    """Yield ``(offset, narrowed_bytes, description)`` for wide-character runs.

    A run is every second byte of a maximal ``(character, NUL)`` alternation -
    which is what a UTF-16 string of ASCII looks like on disk, in either
    endianness. See the block above :data:`_WIDE_RUNS` for why the alternation
    is matched in pairs rather than by stripping every NUL in the file.
    """
    for pattern, phase, endianness in _WIDE_RUNS:
        for match in pattern.finditer(text):
            run = match.group(0)
            narrowed = run[phase::2].encode("latin-1")
            if len(narrowed) >= _MIN_DECODED_BYTES:
                yield match.start(), narrowed, (
                    f"a {len(narrowed)}-character {endianness} wide-character run"
                )


def _encoded_candidates(text: str) -> Iterator[tuple[int, bytes, str]]:
    """Yield ``(offset, decoded_bytes, description)`` for every encoded run.

    The description never carries the decoded value - see
    :func:`iter_encoded_sensitive`.
    """
    yield from _wide_candidates(text)

    for match in _B64_RUN.finditer(text):
        run = match.group(0)
        raw = _decode_b64(run)
        if raw is not None and len(raw) >= _MIN_DECODED_BYTES:
            yield match.start(), raw, f"a {len(run)}-character base64 run"

    for offset, joined, line_count in _b64_blocks(text):
        raw = _decode_b64(joined)
        if raw is not None and len(raw) >= _MIN_DECODED_BYTES:
            yield offset, raw, (
                f"a {line_count}-line base64 block ({len(joined)} characters)"
            )

    for match in _HEX_RUN.finditer(text):
        run = match.group(0)
        for raw in _decode_hex(run):
            if len(raw) >= _MIN_DECODED_BYTES:
                yield match.start(), raw, f"a {len(run)}-character hex run"


def _iter_encoded_hits(
    text: str, wanted: frozenset[str], depth: int
) -> Iterator[tuple[str, str, int, str]]:
    """Yield ``(label, matched, offset, description)``, recursing into layers."""
    if depth <= 0 or not text:
        return
    for offset, raw, description in _encoded_candidates(text):
        for marker, view in _views(raw):
            detail = description + marker
            for label, matched, _ in iter_sensitive(view, wanted):
                yield label, matched, offset, detail
            for label, matched, _, inner in _iter_encoded_hits(view, wanted, depth - 1):
                yield label, matched, offset, f"{detail} containing {inner}"


def iter_encoded_sensitive(
    text: str,
    labels: Iterable[str] | None = None,
    depth: int = _MAX_ENCODED_DEPTH,
) -> Iterator[tuple[str, str, int]]:
    """Yield ``(label, description, offset)`` for identifiers hidden in encodings.

    Companion to :func:`iter_sensitive`, not a replacement: that one reads the
    text as written, this one reads what its base64 and hex runs decode to.
    ``offset`` indexes ``text`` at the start of the encoded run, so a caller can
    turn it into a line number the same way.

    **The second element is a description of the container, never the decoded
    value.** The plain scanner can quote its match because the match is already
    sitting in the file in that form; this one would be converting an encoded
    identifier into a plaintext one and printing it into CI output at the exact
    moment the guard fires. So it reports "a 44-character base64 run" and the
    offset, which is enough to find it and not enough to leak it.

    Findings are deduplicated by ``(label, decoded match)``, so an identifier
    reached by both the per-line and the joined-block pass is reported once.

    This is a detector only. There is deliberately no encoded counterpart to
    :func:`redact` - rewriting bytes inside an encoded blob would corrupt the
    blob, and the right fix is always to redact before encoding.
    """
    if not text:
        return
    wanted = ALL_LABELS if labels is None else frozenset(labels)
    seen: set[tuple[str, str]] = set()
    for label, matched, offset, description in _iter_encoded_hits(text, wanted, depth):
        key = (label, matched)
        if key in seen:
            continue
        seen.add(key)
        yield label, description, offset


def _raise_leak(text: str, label: str, matched: str, offset: int) -> None:
    """Raise a :class:`RedactionError` that points at the leak.

    A display name is described rather than quoted. This message can end up in
    CI output or a bug report, and echoing the very name the guard exists to
    protect would hand it over at the moment the guard fires.
    """
    line_no = text.count("\n", 0, offset) + 1
    if label == "PERSONA":
        detail = (
            f"a {len(matched)}-character display name, not quoted here because "
            "this message travels"
        )
    else:
        detail = repr(matched)
    raise RedactionError(f"unredacted {label} at offset {offset} (line {line_no}): {detail}")


def assert_clean(
    text: str,
    labels: Iterable[str] | None = None,
    personas: Iterable[str] | None = None,
) -> None:
    """Raise :class:`RedactionError` if anything sensitive survives in ``text``.

    Three passes, matching the three mechanisms in :func:`redact`: the
    structural rules, the log-text-only rules, and a persona pass that
    rediscovers display names from ``text`` and fails if any of them is still
    readable. Skipping that third pass is what made this guard vacuous for
    every unkeyed shape in the log.

    ``personas`` supplies names instead of rediscovering them. Use it whenever
    the names are known, because a redacted fragment no longer carries the keys
    discovery works from - which is the one hole this function cannot close on
    its own.

    The exception message names the label, the byte offset and the 1-based line
    number. It quotes the offending match for every label except ``PERSONA``.

    **This does not decode anything.** Text certified here can still carry an
    identifier inside a base64 or hex run - see :func:`iter_encoded_sensitive`
    for why that pass is kept separate, and redact before encoding rather than
    after.
    """
    wanted = ALL_LABELS if labels is None else frozenset(labels)
    for label, matched, offset in iter_sensitive(text, wanted):
        _raise_leak(text, label, matched, offset)

    if "PERSONA" not in wanted:
        return

    for rule in LOG_TEXT_RULES:
        match = rule.pattern.search(text)
        if match is not None:
            _raise_leak(text, rule.label, match.group("value"), match.start("value"))

    supplied = personas is not None
    candidates = _normalise_personas(personas) if supplied else discover_personas(text)
    pattern = _persona_pattern(candidates)
    if pattern is not None:
        for match in pattern.finditer(text):
            if match.group("hit") is not None:
                _raise_leak(text, "PERSONA", match.group("hit"), match.start("hit"))

    # The third outcome. Everything above answers "did I find a name"; none of
    # it answers "was there a name to find". Text that sits in a slot the log
    # fills with a bare display name, from which nothing could be discovered
    # and for which the caller named nothing, is text this function cannot
    # certify - and reporting it clean is the one failure that cannot be undone
    # once it reaches a public history.
    if supplied or candidates:
        return
    if _PERSONA_EVIDENCE.search(text) or not _POSITIONAL_RISK.search(text):
        return
    raise RedactionError(
        "cannot certify: this text sits in a context the log fills with a bare "
        "display name, no name could be discovered from it, and none was "
        "supplied. Redact the whole log and take the excerpt from the redacted "
        "text, or pass personas=[...]. Pass personas=[] to assert there is no "
        "display name in it."
    )
