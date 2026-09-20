# NOTICE - vendored work, `docs/CHANNEL.md`

This directory holds a work that Lanternlight did not write. It is vendored
under Apache-2.0, which is the same license this repository carries, and this
file is the attribution and the statement of changes that Apache-2.0 section
4(b) requires.

## Provenance

| Field | Value |
|---|---|
| File | `docs/CHANNEL.md` |
| Origin project | Amberstone (`RC` on this machine's note channel) |
| Upstream repository | `Remus3/Amberstone` |
| Upstream commit | `6e3c1c752` |
| Upstream path | `docs/CHANNEL.md`, preserved under this directory |
| License | Apache-2.0 |
| Copyright holder | the repository's sole copyright holder, named in that repository's own `LICENSE` and `NOTICE` |
| Vendored | 2026-09-20, `OPS-91` |

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

## What was measured here, rather than taken from the note

A note is MAIL, and every claim a note makes is re-measured. Before a byte was
copied, the public remote was fetched anonymously at the commit Amberstone
published, and these facts were read off the bytes it served rather than off the
note:

| Checked | Result |
|---|---|
| `docs/CHANNEL.md` at `6e3c1c752` | HTTP 200, 20633 bytes - so the repository is genuinely public to an anonymous reader |
| `sha256` of those bytes | `899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b`, equal to the digest Amberstone published |
| `LICENSE` at the same commit | Apache License 2.0, 219 lines |
| `LICENSE` copyright lines | two, both RENDERED - a year and a non-empty holder, no unfilled `{{ }}` template |
| `LICENSE` `SCOPE OF THIS LICENSE` block | puts source code AND authored documentation, including "the Markdown that describes them", inside the grant |
| The only carve-out | data files under `data/`, third-party sourced. `docs/CHANNEL.md` is authored documentation outside `data/` |
| `Share/LICENSE.md` at the same commit | HTTP 404 - the redistribution-forbidding file from the 2026-09-07 three-way contradiction is gone at the commit vendored here, rather than merely untracked |

The three-way licence contradiction Amberstone itself reported on 2026-09-07 -
an Apache-2.0 `LICENSE`, a `Share/LICENSE.md` forbidding redistribution, and a
README claiming all rights reserved - is the first trap listed under the license
gate in `CLAUDE.md`. It was not taken as resolved on Amberstone's word: the
404 above is this project's own measurement of the half that mattered, taken at
the exact commit whose bytes are in this directory.

## Integrity - one digest, and why this file has one where the other vendor has two

`third_party/lw_write_tracer/NOTICE.md` records two hashes because that file
arrived with CRLF on every line while `.gitattributes` pins the checkout to LF,
so its working-file hash and its git blob hash are different facts and naming
only one would be a confident lie.

That does not apply here and it was measured rather than assumed. The bytes
served by the remote carry **zero CRLF pairs, zero bare CR, and zero non-ASCII
bytes**, and `.gitattributes` stores `*.md` as LF. The file on disk, the file in
the blob and the file Amberstone published are therefore the same 20633 bytes,
and one digest names all three.

| Form | Bytes | sha256 |
|---|---|---|
| AS PUBLISHED and AS VENDORED, LF | 20633 | `899f6eb957cc26ee25993d83d65d8ca291841fe4eec24a48f729c2dc005f4c6b` |

`tests/test_vendored_channel_md.py` pins that digest, the byte count, the
absence of CRLF and non-ASCII, and the fields in this NOTICE. It also fails if
this NOTICE ever names a `sha256` the guard does not pin, because a NOTICE
quoting one hash while the guard pins another reads as two independent records
corroborating each other when it is one record contradicting itself.

## CHANGES MADE TO THE WORK

**None. Not one byte.**

The file was fetched, hashed against the published digest, and copied with
`shutil.copyfile` - a byte-level copy, never `Path.write_text`, which on Windows
turns LF into CRLF while `read_text` hides it. The copy hashes to the published
value, which is the proof rather than the intention.

The only thing that differs from upstream is the file's LOCATION: it sits at
`third_party/rc_channel/docs/CHANNEL.md` here rather than at `docs/CHANNEL.md`,
so that it cannot be mistaken for a document this project authored. Its upstream
relative path is preserved beneath this directory.

## Do not edit this file

`CLAUDE.md`: "Do not edit a vendored file." The guard named above fails if it
changes, and the honest response to that red is to declare the change in this
NOTICE, never to update the constant. Wrap it instead. `ruff.toml` excludes
`third_party/` for the same reason and says so where it does it.

The point of a byte-identical vendor is that every tree on this channel can pin
one digest and prove it holds the same text. A near-copy would look like
agreement without being it, which is worth less than holding nothing.
