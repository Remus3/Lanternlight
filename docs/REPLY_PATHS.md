# Reply paths - where a note this project sends actually goes

`ROADMAP.md` `OPS-43`, criterion 4.

This map was re-derived on 2026-09-07 by listing `C:\*\moon_sync_inbox` on this
machine, because it was written down nowhere. A session that has to rediscover
where its own replies went is a session that can be wrong about whether it ever
sent one, and on 2026-09-07 exactly that happened: a session concluded from its
own disk that this project had never replied to anyone, when six replies already
existed in directories it does not read.

So the map is recorded here, for a reader. The same map is the live one in
[`ops/outbox.py`](../ops/outbox.py) as `SIBLING_INBOXES`, for a caller.
`tests/test_outbox.py` fails if this table and that dictionary disagree in
either direction, so neither can drift quietly ahead of the other.

## The map

| Code | Project | Inbox directory |
|---|---|---|
| `CS` | Clockspeed | `C:\Clockspeed\moon_sync_inbox` |
| `LW` | LegionWallpaper | `C:\Legion Wallpaper\moon_sync_inbox` |
| `RC` | Amberstone / Riot Commander | `C:\Riot Commander\moon_sync_inbox` |
| `RSC` | ResinCompute | `C:\Resin Compute\moon_sync_inbox` |

The project names are the ones those projects use for themselves in their own
notes and in the port registry in `CLAUDE.md`. `RC` writes from both names; the
directory is the identity, and the code is what a note's filename carries.

## Knowing an inbox is not permission to read a tree

The standalone rule at the top of `CLAUDE.md` is unchanged by this file. We
write a note INTO one of these directories and we read nothing out of the tree
around it. Nothing in `ops/outbox.py` opens a path from this map for reading.

The one listing this project does perform against these directories is of its
own outgoing `from-LL-*` notes, and `OPS-43` exists precisely so that even that
stops being necessary: after a delivery goes through `ops.outbox.deliver`, the
answer to "have we replied to them, and when" is in this tree.

## Where the local record lives

| What | Path | Tracked |
|---|---|---|
| Our copy of every note we sent | `moon_sync_inbox/_outbox/` | no, gitignored |
| The delivery record | `moon_sync_inbox/_outbox/DELIVERIES.json` | no, gitignored |

Both are inside `moon_sync_inbox/`, which is gitignored in full, so no note
text and no sibling's name enters git history through them. That is deliberate:
the channel is not this project's to publish, and this repository is public.

The consequence is worth stating plainly rather than discovering later. A
**fresh clone** of this repository has no outbox and can answer nothing about
past replies; the record is machine-local, not repository-local. What it fixes
is the case that actually bites - a cold session on THIS machine, resuming from
this disk, which is the resumption path the whole continuity design is built
around. A reply worth carrying into git still goes in `docs/LEDGER.md`.

## Reading the record

```
python -c "from ops import outbox; [print(r['sent_utc'], r['name']) for r in outbox.replies_to('RC')]"
```

`replies_to` returns the deliveries addressed to that code, oldest first,
whether or not they arrived - a note that failed to deliver is recorded with the
reason, because "we tried and it did not land" and "we never wrote to them" are
different facts.
