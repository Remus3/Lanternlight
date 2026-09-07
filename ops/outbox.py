"""Keep a local record of every note this project SENDS - ``OPS-43``.

THE PROBLEM THIS EXISTS TO FIX
------------------------------
Lanternlight answers a sibling project by writing a note directly into that
sibling's ``moon_sync_inbox/`` directory. Until this module existed it kept no
copy. ``moon_sync_inbox/`` is gitignored, so neither the working tree nor git
history carried any artifact saying a reply had ever been sent, and the only
evidence of an answer lived in four directories this project does not read.

The consequence is not cosmetic. Every cold session here resumes from disk
alone - that is the design, not a shortcoming - so a session that looks at its
own disk and sees no outgoing mail concludes that this project has been silent.
That happened on 2026-09-07: a subagent reported that Lanternlight had never
replied to any of the notes it received, the claim was relayed without an
independent probe, and it reached ``WAKEUP_NOTES.md``, ledger entry ``LL-0161``
and the title of a delivered note before anyone caught it. Six earlier replies
existed the whole time. Measured the same day, nineteen unique ``from-LL-*``
notes existed across the four sibling inboxes and fourteen left no trace here
at all - a four-to-one undercount.

So: the note this project sends is also written HERE, and a question about our
own outgoing mail is answered from this tree.

THE LOCAL COPY IS WRITTEN FIRST, ON PURPOSE
-------------------------------------------
:func:`deliver` writes the outbox copy and its manifest record BEFORE it
attempts a single sibling write, and it rewrites the record afterwards with
what actually landed. A delivery that fails half way therefore still leaves the
evidence that it was tried, together with the reason it did not arrive. The
other order - deliver, then record - loses exactly the case worth keeping,
because the run that crashes is the run whose note nobody can account for.

Both writes are temporary-plus-``replace``, which this repository requires for
anything a reader might poll. The manifest is rewritten whole rather than
appended to: it is small, and a whole-file replace cannot leave a half-written
final line for a reader that arrives mid-write.

WHAT IS RECORDED, AND WHAT IS NOT
---------------------------------
Recorded: the note's filename, the SHA-256 of its bytes, the UTC and local
timestamps, the recipients it was addressed to, which of those it reached, and
the reason for each that it did not. The note's own text lives in the outbox
copy beside the manifest and is never inlined into it.

Not recorded: anything about a sibling's tree. This module writes INTO a
sibling inbox and reads nothing there. :func:`replies_to` answers "has this
project replied to X, and when" from the manifest alone, which is what makes
the answer available to a session that has no sibling directories at all.

THE OUTBOX LIVES INSIDE ``moon_sync_inbox/``
-------------------------------------------
The operator ruled on 2026-09-07 that ``ops/inbox_watch.py`` covers the
ENTIRETY of that folder, so a directory placed inside it is watched. It is
therefore CLASSIFIED as ours rather than skipped: ``inbox_watch`` recognises
:data:`OUTBOX_DIRNAME` by name, counts it, and keeps it out of both the unread
drops and the withdrawal baseline. Skipping it silently would have been the
same defect ``OPS-34`` fixed, and leaving it unclassified would have returned
every note this project sends as unread mail.

ASCII, LIKE EVERY OTHER AUTHORED FILE HERE
------------------------------------------
A note is an authored artifact, so :func:`deliver` refuses anything outside
7-bit ASCII before it writes a byte. The refusal is deliberate rather than a
silent transcoding: a note that reaches a sibling with a smart quote in it has
already left this machine, and the repository's own hygiene guards never see
it.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "INBOX_DIRNAME",
    "MANIFEST_FILENAME",
    "OUTBOX_DIRNAME",
    "REPO_ROOT",
    "SIBLING_INBOXES",
    "Delivery",
    "backfill",
    "default_inbox",
    "default_manifest",
    "default_outbox",
    "deliver",
    "load_manifest",
    "replies_to",
]

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The shared note channel. Gitignored; nothing under it is committed.
INBOX_DIRNAME = "moon_sync_inbox"

#: Our own outgoing copies, inside the watched folder. ``inbox_watch`` knows
#: this exact string - see that module's handling of the outbox.
OUTBOX_DIRNAME = "_outbox"

#: The delivery record, beside the copies it describes.
MANIFEST_FILENAME = "DELIVERIES.json"

#: Which sibling code corresponds to which inbox directory on this machine.
#:
#: ``OPS-43`` criterion 4. This map was re-derived on 2026-09-07 by listing
#: ``C:\*\moon_sync_inbox`` because it was written down nowhere, which is how a
#: session ends up guessing where its own replies went. It is mirrored in
#: ``docs/REPLY_PATHS.md`` for a reader rather than a caller, and
#: ``tests/test_outbox.py`` refuses to let the two drift apart.
#:
#: KNOWING A NEIGHBOUR'S INBOX IS NOT PERMISSION TO READ ITS TREE. The
#: standalone rule in ``CLAUDE.md`` still holds: we write a note in and we read
#: nothing out. Nothing in this module opens a path from this map for reading.
SIBLING_INBOXES: dict[str, str] = {
    "CS": r"C:\Clockspeed\moon_sync_inbox",
    "LW": r"C:\Legion Wallpaper\moon_sync_inbox",
    "RC": r"C:\Riot Commander\moon_sync_inbox",
    "RSC": r"C:\Resin Compute\moon_sync_inbox",
}


@dataclass
class Delivery:
    """One note, once, with what reached whom.

    ``delivered`` and ``failed`` are disjoint and together cover ``recipients``.
    A recipient appears in exactly one of them, so "we tried and it did not
    arrive" can never be mistaken for "we never addressed them".
    """

    name: str
    digest: str
    sent_utc: str
    sent_local: str
    recipients: tuple[str, ...]
    outbox_path: str
    delivered: tuple[str, ...] = ()
    failed: tuple[tuple[str, str], ...] = ()
    byte_count: int = 0

    def as_record(self) -> dict:
        """The manifest row for this delivery - JSON types only."""
        return {
            "name": self.name,
            "digest": self.digest,
            "sent_utc": self.sent_utc,
            "sent_local": self.sent_local,
            "recipients": list(self.recipients),
            "delivered": list(self.delivered),
            "failed": [{"code": code, "reason": reason} for code, reason in self.failed],
            "byte_count": self.byte_count,
        }


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------


def default_inbox(root: Path | str | None = None) -> Path:
    """The note channel under ``root``, defaulting to this repository."""
    return Path(root or REPO_ROOT) / INBOX_DIRNAME


def default_outbox(root: Path | str | None = None) -> Path:
    """Our own outgoing copies, inside the watched channel."""
    return default_inbox(root) / OUTBOX_DIRNAME


def default_manifest(root: Path | str | None = None) -> Path:
    """The delivery record, beside the copies."""
    return default_outbox(root) / MANIFEST_FILENAME


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def _digest_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_atomically(target: Path, data: bytes) -> None:
    """Write ``data`` to ``target`` through a temporary in the same directory.

    Same directory because ``os.replace`` is only atomic within one filesystem,
    and a temporary parked somewhere else is a copy across a boundary wearing a
    rename's name. The temporary carries the process id so two writers cannot
    collide on it.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(target)


def _check_name(name: str) -> str:
    """A note name is a FILENAME and never steers where bytes land."""
    if not name or name != Path(name).name:
        raise ValueError(f"a note name must be a bare filename, got {name!r}")
    if "/" in name or "\\" in name or name in (".", ".."):
        raise ValueError(f"a note name must be a bare filename, got {name!r}")
    return name


def _encode(text: str) -> bytes:
    """7-bit ASCII or nothing - the repository's authoring rule, enforced early."""
    try:
        return text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "a note must be 7-bit ASCII; refused before anything was written "
            f"({exc.reason} at position {exc.start})"
        ) from exc


def _timestamps(now: str | None) -> tuple[str, str]:
    """Return ``(utc, local)``. ``now`` pins the UTC half for a test."""
    if now is not None:
        return now, now
    moment = datetime.now(UTC)
    utc = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    local = time.strftime("%Y-%m-%dT%H:%M:%S")
    return utc, local


def deliver(
    name: str,
    text: str,
    recipients: list[str] | tuple[str, ...],
    root: Path | str | None = None,
    inboxes: dict[str, str] | None = None,
    now: str | None = None,
) -> Delivery:
    """Write one note to our outbox, then to each recipient's inbox.

    The local copy and its manifest row land BEFORE any sibling write is
    attempted, so a delivery that fails still leaves the record that it was
    tried. The manifest row is then rewritten with what actually arrived.

    Args:
        name: The note's filename. Must be a bare filename.
        text: The note. 7-bit ASCII; anything else is refused before a write.
        recipients: Sibling codes, keys of ``inboxes``.
        root: Repository root. Defaults to this one.
        inboxes: Code-to-directory map. Defaults to :data:`SIBLING_INBOXES`.
        now: Pin the timestamps, for a test.

    Returns:
        The :class:`Delivery`, whose ``failed`` names every recipient that did
        not get it and why.

    Raises:
        ValueError: The name is not a bare filename, or the text is not ASCII.
        KeyError: A recipient is not in the map.
        OSError: The LOCAL write failed. A sibling write failing is recorded,
            not raised - one unreachable neighbour must not lose the others.
    """
    name = _check_name(name)
    data = _encode(text)
    table = dict(SIBLING_INBOXES if inboxes is None else inboxes)
    codes = tuple(recipients)
    unknown = [code for code in codes if code not in table]
    if unknown:
        raise KeyError(
            f"no inbox recorded for {', '.join(unknown)}; see docs/REPLY_PATHS.md"
        )

    sent_utc, sent_local = _timestamps(now)
    copy = default_outbox(root) / name
    record = Delivery(
        name=name,
        digest=_digest_of(data),
        sent_utc=sent_utc,
        sent_local=sent_local,
        recipients=codes,
        outbox_path=str(copy),
        byte_count=len(data),
    )

    # THE LOCAL RECORD FIRST. Both of these raise on failure: if we cannot
    # record that a note was sent, sending it is the thing that must not happen.
    _replace_atomically(copy, data)
    _append_record(record, root)

    delivered: list[str] = []
    failed: list[tuple[str, str]] = []
    for code in codes:
        try:
            _replace_atomically(Path(table[code]) / name, data)
        except OSError as exc:
            failed.append((code, exc.__class__.__name__))
        else:
            delivered.append(code)
    record.delivered = tuple(delivered)
    record.failed = tuple(failed)
    _rewrite_last(record, root)
    return record


def _append_record(record: Delivery, root: Path | str | None) -> None:
    rows = load_manifest(root=root)
    rows.append(record.as_record())
    _write_manifest(rows, root)


def _rewrite_last(record: Delivery, root: Path | str | None) -> None:
    """Replace the row this delivery wrote, in place, with the outcome."""
    rows = load_manifest(root=root)
    for index in range(len(rows) - 1, -1, -1):
        if rows[index]["name"] == record.name and rows[index]["digest"] == record.digest:
            rows[index] = record.as_record()
            break
    else:  # pragma: no cover - the row was written one call ago
        rows.append(record.as_record())
    _write_manifest(rows, root)


def _write_manifest(rows: list[dict], root: Path | str | None) -> None:
    payload = {
        "what": "notes this project SENT, so a cold session can see them",
        "item": "OPS-43",
        "deliveries": rows,
    }
    data = (json.dumps(payload, indent=2, sort_keys=False) + "\n").encode("ascii")
    _replace_atomically(default_manifest(root), data)


def backfill(
    inboxes: dict[str, str] | None = None,
    root: Path | str | None = None,
    prefix: str = "from-LL-",
) -> list[dict]:
    """Recover replies sent before this module existed. Returns the new rows.

    An empty outbox fixes only the future, and the case ``OPS-43`` is actually
    about is the past: twenty five ``from-LL-*`` notes were already sitting in
    four sibling directories when this landed, and a cold session could account
    for none of them. This reads OUR OWN notes back out and records them.

    WHAT A RECONSTRUCTED ROW DOES NOT CLAIM. It carries no ``sent_utc`` and no
    ``sent_local`` - the fields are ABSENT, not null and not zero, because this
    function never watched the send and the repository's measurement doctrine
    keeps "unmeasured" distinguishable from "measured". The one time available
    is the file's mtime on the sibling's disk, recorded as
    ``earliest_seen_local``, which is when the note LANDED there. Every such row
    is flagged ``reconstructed`` so nothing downstream can average the two kinds
    of evidence together.

    A note already recorded by a real :func:`deliver` is left alone. An observed
    send outranks a reconstruction of the same bytes, always.

    THE ONE SIBLING READ THIS PROJECT PERFORMS. It reads files this project
    WROTE, by name prefix, and nothing else in the tree around them - see
    ``docs/REPLY_PATHS.md``. After this runs, listing a sibling's inbox to find
    out whether we answered them stops being necessary at all, which is the
    point.

    Args:
        inboxes: Code-to-directory map. Defaults to :data:`SIBLING_INBOXES`.
        root: Repository root. Defaults to this one.
        prefix: The marker that makes a note ours. Notes without it belong to
            somebody else and are not touched.

    Returns:
        The rows this call added, in name order. Empty on a second run.
    """
    table = dict(SIBLING_INBOXES if inboxes is None else inboxes)
    known = {row.get("name") for row in load_manifest(root=root)}

    found: dict[str, dict] = {}
    for code, where in sorted(table.items()):
        directory = Path(where)
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob(f"*{prefix}*")):
            if not path.is_file() or path.name in known:
                continue
            try:
                data = path.read_bytes()
                stamp = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime)
                )
            except OSError:
                continue
            entry = found.setdefault(
                path.name,
                {
                    "name": path.name,
                    "digest": _digest_of(data),
                    "recipients": [],
                    "delivered": [],
                    "failed": [],
                    "byte_count": len(data),
                    "reconstructed": True,
                    "earliest_seen_local": stamp,
                    "note": (
                        "recovered from a sibling inbox; the time is when the "
                        "file landed there, NOT when it was sent"
                    ),
                },
            )
            entry["recipients"].append(code)
            # It reached this inbox, so for this recipient it demonstrably
            # arrived - that half IS observed, even though the send was not.
            entry["delivered"].append(code)
            entry["earliest_seen_local"] = min(entry["earliest_seen_local"], stamp)
            _replace_atomically(default_outbox(root) / path.name, data)

    if not found:
        return []
    rows = load_manifest(root=root)
    added = [found[name] for name in sorted(found)]
    rows.extend(added)
    _write_manifest(rows, root)
    return added


# ---------------------------------------------------------------------------
# reading - this tree only
# ---------------------------------------------------------------------------


def load_manifest(
    path: Path | str | None = None, root: Path | str | None = None
) -> list[dict]:
    """Every delivery this project has recorded, oldest first.

    An ABSENT manifest is an empty list: we have sent nothing. A manifest that
    exists and cannot be parsed raises, because "the store is broken" and "we
    never replied" are different facts and this module exists precisely because
    the second one was believed once already.
    """
    target = Path(path) if path is not None else default_manifest(root)
    if not target.exists():
        return []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{target} exists but could not be read: {exc}") from exc
    rows = payload.get("deliveries") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{target} has no deliveries list")
    return [row for row in rows if isinstance(row, dict)]


def replies_to(
    code: str, root: Path | str | None = None, manifest: Path | str | None = None
) -> list[dict]:
    """Has this project replied to ``code``, and when - answered from our disk.

    Returns the deliveries addressed to ``code``, oldest first, whether or not
    they arrived. An empty list means we have no record of writing to them,
    which is a real answer and the one a cold session most needs.

    NO SIBLING DIRECTORY IS OPENED. That is the whole point of the criterion:
    the answer must survive a machine where the neighbours are gone.
    """
    rows = load_manifest(path=manifest, root=root)
    matching = [row for row in rows if code in row.get("recipients", ())]
    # A reconstructed row has NO sent_utc - see backfill - so the ordering key
    # falls back to when the note was first seen on the recipient's disk. The
    # two are different facts and the row says which it carries; only the sort
    # treats them alike, and only so that one list can be printed in order.
    matching.sort(
        key=lambda row: (
            row.get("sent_utc") or row.get("earliest_seen_local") or "",
            row.get("name", ""),
        )
    )
    return matching
