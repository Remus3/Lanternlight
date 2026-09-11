# NOTICE - vendored work, `lw_write_tracer.py`

This directory holds a work that Lanternlight did not write. It is vendored
under Apache-2.0, which is the same license this repository carries, and this
file is the attribution and the statement of changes that Apache-2.0 section
4(b) requires.

## Provenance

| Field | Value |
|---|---|
| File | `lw_write_tracer.py` |
| Origin project | Legion Wallpaper (`LW` on this machine's note channel) |
| Upstream repository | `Remus3/Legion-Wallpaper` |
| License | Apache-2.0 |
| Copyright holder | the repository's sole copyright holder, per LW's own statement |
| Received | 2026-09-11, as `moon_sync_inbox/lw_write_tracer.py.from-lw` |

## The license was NAMED, and that is why this is here rather than re-implemented

`CLAUDE.md` forbids copying a drop that carries no license statement, and an
earlier copy of this same file was refused on exactly that ground. Lanternlight
asked LW to name a license if they wanted it vendorable rather than read for the
idea. LW answered on 2026-09-11: both delivered files are tracked in a PUBLIC
Apache-2.0 repository, the operator is sole copyright holder, and vendoring with
attribution and a statement of changes is intended rather than an accident of
publication.

The operator ruled VENDOR on that basis in chat on 2026-09-11. The rule that
produced the original refusal was not waived - it was satisfied.

## Integrity - the two hashes, and why there are two

**A hash of a working file is not a hash of the commit.** `.gitattributes` pins
`*.py` to `eol=lf` in this repository, and the file arrived with CRLF on every
one of its 274 lines. So the bytes on disk here are NOT the bytes LW published,
and recording only one digest would be a confident lie whichever one was chosen.

| Form | Bytes | sha256 |
|---|---|---|
| AS RECEIVED, CRLF | 11267 | `17c3c748f0f04b85701cff41c2df8706f77b46a10aa3a98a3dc0ca60b7136479` |
| AS VENDORED, LF | 10993 | `07041530de8506cd797e93d8d7004a911bdf703e96335423c6cea8bc069d1a47` |

The received digest is the one LW published in its note of 2026-09-11 14:15,
and it was verified against the drop before a byte was copied.

`tests/test_vendored_write_tracer.py` asserts the identity in the form that
survives the policy: it reads the vendored file, restores CRLF, and requires the
result to hash to LW's published value. That holds no matter which line-ending
rule this repository adopts later, and it fails the moment anyone edits the file
in place.

## CHANGES MADE TO THE WORK

**One, and it is mechanical.** Line endings were normalised from CRLF to LF to
satisfy this repository's `.gitattributes` policy, which exists because this
repository is public and a CRLF blob reads as a whole-file diff to every
non-Windows contributor.

**No other byte differs.** No line was added, removed or reordered; no
identifier, docstring or behaviour was changed; no attribution was stripped. The
round-trip assertion above is what makes that statement checkable rather than a
promise.

## IF YOU ARE ABOUT TO EDIT THIS FILE, DO NOT

Edit it and the integrity test fires, correctly. A modified copy is a derivative
work and needs its change declared here - that is the Apache-2.0 obligation, not
a repository preference.

Prefer a wrapper in this repository's own code that imports the plugin and
adjusts behaviour around it. If the work genuinely must be modified, add a
CHANGES section above naming each change, update the vendored digest, and leave
the received digest alone: it is a record of what was licensed, not of what is
on disk.

## What it does not claim about this tree

The plugin states its own limits and they travel with any number it prints. It
does not see writes performed by a CHILD PROCESS, so any count it produces for a
suite that spawns processes is a LOWER BOUND. Lanternlight's suite spawns
processes constantly - every hook test does - so that limit is load-bearing
here, not a footnote.

It was the reason LW's own finding about this repository had to be re-measured:
the write it reported was attributed to a test whose real writes all happen in a
subprocess it could not see. See `OPS-82`.
