# NOTICE - vendored work, `docs/CHANNEL.md`

This directory holds a work that Lanternlight did not write. It is vendored
under Apache-2.0, which is the same license this repository carries, and this
file is the attribution and the statement of changes that Apache-2.0 section
4(b) requires.

## Provenance - CURRENT PIN

| Field | Value |
|---|---|
| File | `docs/CHANNEL.md` |
| Origin project | Amberstone (`RC` on this machine's note channel) |
| Upstream repository | `Remus3/Amberstone` |
| Upstream commit | `6ad1531e2` |
| Upstream path | `docs/CHANNEL.md`, preserved under this directory |
| Declared version | `CHANNEL_VERSION: 2` |
| License | Apache-2.0 |
| Copyright holder | the repository's sole copyright holder, named in that repository's own `LICENSE` and `NOTICE` |
| Vendored | 2026-09-20, `OPS-91`; re-pinned to v2 the same day |

**The holder's name is deliberately not written here as a literal.** It is the
operator's git identity, which `CLAUDE.md` names as an operator identifier and
forbids writing into a tracked file as a literal. Recording "one holder, sole,
named in both `LICENSE` and `NOTICE` upstream" carries the whole legal fact and
none of the exposure. The four files in THIS repository where that identity
appears deliberately - `LICENSE`, `NOTICE`, `CITATION.cff` and `README.md` - are
where Apache-2.0 requires the copyright holder to be named, and this file is not
one of them.

## The license was NAMED, and that is why this is here rather than paraphrased

`CLAUDE.md` forbids copying a drop that carries no license statement, and an
earlier offer of this same file was refused on exactly that ground: Amberstone's
note of 2026-09-15 named a commit and the phrase "public tree", and a visibility
is not a grant. Lanternlight asked Amberstone to name the license and the
repository if they wanted the doc vendorable rather than read for the idea, and
said plainly that the answer decides between the two. Amberstone answered on
2026-09-16: repository `Remus3/Amberstone`, visibility PUBLIC, root `LICENSE`
Apache-2.0, sole copyright holder, authored documentation inside the grant,
vendoring intended.

The operator ruled VENDOR on that basis in chat on 2026-09-20. The rule that
produced the original refusal was not waived - it was satisfied. This is the
second time that sequence has run to completion here; the first produced
`third_party/lw_write_tracer/` under `OPS-84`.

## What was measured here, rather than taken from a note

A note is MAIL, and every claim a note makes is re-measured. Before a byte was
copied - **on BOTH pins, because a licence is a fact about a COMMIT and not
about a repository in general** - the public remote was fetched anonymously at
the commit Amberstone published, and these facts were read off the bytes it
served:

| Checked at `6ad1531e2` | Result |
|---|---|
| `docs/CHANNEL.md` | HTTP 200, 25425 bytes - so the repository is genuinely public to an anonymous reader |
| `sha256` of those bytes | `fc22e86eebe93bb247a91f44835257a3fe717a287c4a3184a8e7a7b9a463fb9c`, equal to the digest Amberstone published for v2 |
| Line endings and encoding | zero CRLF pairs, zero bare CR, zero non-ASCII bytes |
| `LICENSE` at the same commit | Apache License 2.0, 219 lines |
| `LICENSE` copyright lines | two, both RENDERED - a year and a non-empty holder, no unfilled `{{ }}` template |
| `SCOPE OF THIS LICENSE` block | present, putting source code AND authored documentation inside the grant |
| The only carve-out | data files under `data/`. This file is authored documentation outside `data/` |
| `Share/LICENSE.md` | HTTP 404 - the redistribution-forbidding file from the 2026-09-07 three-way contradiction is absent at this commit too |

**The gate was re-run at the NEW commit rather than inherited from the old
one.** A repository that was Apache-2.0 at one commit can be something else at
another, and a re-pin that carried the previous licence check forward would be
asserting a fact nobody had measured.

## Superseded pins - the re-pin history

A digest that has been retired is kept here rather than deleted, so a reader
meeting the old value in a sibling's note or in this repository's own ledger can
resolve it. **Every `sha256` in this file that is not the current pin lives in
this section**, and `tests/test_vendored_channel_md.py` fails if one appears
anywhere else - a stray digest in the prose above would read as a second live
claim.

| Version | Commit | Bytes | sha256 | Retired |
|---|---|---|---|---|
| v1 | `6e3c1c752` | 20633 | `899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b` | 2026-09-20, superseded by the v2 round |

**The v2 round was JOINT, which is what the document's own `CHANNEL_PIN` line
requires.** All six participating repositories voted for a six-participant
roster and a `CHANNEL_VERSION 2` re-pin; Lanternlight's operator ruled YES in
chat on 2026-09-20 and directed that the vote go to every tree. Amberstone
authored v2 and published its digest. This copy was then re-fetched and
re-verified from the public remote rather than copied from any sibling's disk.

**The re-pin was observed RED before it was recorded.** Replacing the bytes
while the constants still named v1 failed four arms at once - the licence
guard's digest, the contract's digest arm, the declared-version arm, and the
filename-grammar arm, which caught that v2's table gained an eighth column. That
is the evidence these guards are not decoration, and it is why the constants
were moved only afterwards and only with this section written.

## Integrity - one digest per pin, and why this file has one where the other vendor has two

`third_party/lw_write_tracer/NOTICE.md` records two hashes because that file
arrived with CRLF on every line while `.gitattributes` pins the checkout to LF,
so its working-file hash and its git blob hash are different facts and naming
only one would be a confident lie.

That does not apply here and it was measured rather than assumed, on both pins.
The bytes served by the remote carry zero CRLF pairs, zero bare CR and zero
non-ASCII bytes, and `.gitattributes` stores `*.md` as LF. The file on disk, the
file in the blob and the file Amberstone published are therefore the same 25425
bytes, and one digest names all three.

## CHANGES MADE TO THE WORK

**None. Not one byte, at either pin.**

The file was fetched, hashed against the published digest, and copied with
`shutil.copyfile` - a byte-level copy, never `Path.write_text`, which on Windows
turns LF into CRLF while `read_text` hides it. The copy hashes to the published
value, which is the proof rather than the intention.

The only thing that differs from upstream is the file's LOCATION: it sits at
`third_party/rc_channel/docs/CHANNEL.md` here rather than at `docs/CHANNEL.md`,
so that it cannot be mistaken for a document this project authored. Its upstream
relative path is preserved beneath this directory.

**A version bump is not a change to the work.** v1 and v2 are two different
works by the same author, each vendored verbatim; this repository has never held
a modified copy of either.

## Do not edit this file

`CLAUDE.md`: "Do not edit a vendored file." The guard named above fails if it
changes, and the honest response to that red is to declare the change in this
NOTICE, never to update the constant. Wrap it instead. `ruff.toml` excludes
`third_party/` for the same reason and says so where it does it.

**A JOINT RE-PIN IS THE ONE EXCEPTION, and it is not a loophole.** The
difference is direction: a re-pin moves the constant to follow a change the
OWNER made and every carrier agreed to, and it is recorded in the Superseded
pins table above before the constant moves. Editing the constant to make a local
change go quiet is the thing that is forbidden, and it leaves no such record.

The point of a byte-identical vendor is that every tree on this channel can pin
one digest and prove it holds the same text. A near-copy would look like
agreement without being it, which is worth less than holding nothing.
