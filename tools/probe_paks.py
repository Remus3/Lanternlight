"""Read UE5 IoStore .utoc headers + legacy .pak footers to determine encryption.

Read-only. Touches no running process. Prints one line per container.

THE COMMAND LINE REFUSES WHAT IT DOES NOT UNDERSTAND - ROADMAP ``OPS-67``.
Measured 2026-09-08, before this change: ``python tools/probe_paks.py
--paks D:/elsewhere`` read every ``.utoc`` under the hardcoded :data:`PAKS`
directory, printed a full report, and exited 0. The flag was neither honoured
nor mentioned. That is the ``OPS-64`` defect exactly - a confident verdict
about a scope the caller did not ask for - and it was WORSE here than in the
guard that filed it, because the old output named only ``path.name`` per
container and so never said which directory it had read. A pasted transcript
of such a run is indistinguishable from a run of the directory the caller
meant.

Two changes close it, and neither is an option:

- **An unrecognised argument is refused with** :data:`USAGE_EXIT_CODE`, not
  ignored. This module differs from its two ``PostToolUse`` siblings
  (``tools/ascii_check.py`` and ``tools/syntax_check_hook.py``, both decided
  the other way under the same item) in the only respect that matters: it has
  no automated caller at all. It is typed by a person, its exit code is read
  by nothing that a non-zero could wedge, and there is therefore no cost to
  refusing. A hook cannot say that, which is why the three were decided
  separately rather than as one batch.
- **Every run prints the directory it read**, before any container line. The
  refusal above makes a wrong scope unreachable through argv, but the scope is
  still a compile-time constant pointing at one machine's Steam library, and a
  report that does not name its own subject cannot be checked by the person
  reading it later.

NO ``argparse``, AND NO OPTIONS. ``OPS-64`` grew real options for
``tools/archive_link_guard.py`` because that guard genuinely had more than one
scope worth naming. This one has exactly one contract - no arguments at all -
and inventing a ``--paks`` flag to satisfy a consistency argument would add a
capability nobody has asked for and a second code path nobody exercises.
``tools/precommit_gate.py`` reached the same conclusion under ``OPS-66``:
spell the contracts out, refuse everything else.
"""
import struct
import sys
from pathlib import Path

PAKS = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Mistfall Hunter"
            r"\MistfallHunter\Content\Paks")

#: Exit code for a command line this module could not read. 2 matches what
#: ``argparse`` uses for a usage error and what ``tools/archive_link_guard.py``
#: and ``tools/precommit_gate.py`` already return, so a caller that checks any
#: of the three checks them the same way.
USAGE_EXIT_CODE = 2

TOC_MAGIC = b"-==--==--==--==-"
PAK_MAGIC = 0x5A6F12E1

FLAG_NAMES = [
    (1 << 0, "Compressed"),
    (1 << 1, "Encrypted"),
    (1 << 2, "Signed"),
    (1 << 3, "Indexed"),
    (1 << 4, "OnDemand"),
]


def read_utoc(path):
    with path.open("rb") as fh:
        head = fh.read(144)
    if head[:16] != TOC_MAGIC:
        return f"{path.name}: NOT a utoc (magic {head[:16]!r})"
    version = head[16]
    entry_count = struct.unpack_from("<I", head, 24)[0]
    dir_index_size = struct.unpack_from("<I", head, 48)[0]
    container_id = struct.unpack_from("<Q", head, 56)[0]
    key_guid = head[64:80]
    flags = head[80]
    set_flags = [n for bit, n in FLAG_NAMES if flags & bit] or ["none"]
    guid_zero = key_guid == b"\x00" * 16
    return (
        f"{path.name}: tocver={version} entries={entry_count} "
        f"dirindex={dir_index_size} id={container_id:016x} "
        f"flags={'|'.join(set_flags)} keyguid={'ZERO' if guid_zero else key_guid.hex()}"
    )


def read_pak(path):
    size = path.stat().st_size
    with path.open("rb") as fh:
        fh.seek(max(0, size - 221))
        tail = fh.read(221)
    idx = tail.rfind(struct.pack("<I", PAK_MAGIC))
    if idx < 0:
        return f"{path.name}: no pak footer magic in last 221 bytes (IoStore-only stub?)"
    ver = struct.unpack_from("<I", tail, idx + 4)[0]
    enc_index = tail[idx - 1]
    return f"{path.name}: pakver={ver} encrypted_index={bool(enc_index)}"


def main(argv=None):
    """Probe every container under :data:`PAKS`, or REFUSE - ``OPS-67``.

    Args:
        argv: Arguments after the program name, i.e. ``sys.argv[1:]``. ``None``
            means read ``sys.argv[1:]``, which is what the ``__main__`` block
            below relies on. A test passes a list, because a test runner's
            ``sys.argv`` is not this script's and would otherwise be refused.

    Returns:
        ``0`` on a completed probe, ``1`` when the directory is absent, and
        :data:`USAGE_EXIT_CODE` for an argument this module cannot read.
    """
    args = sys.argv[1:] if argv is None else list(argv)
    if args:
        print(
            "probe_paks: unrecognised argument, REFUSING rather than printing "
            f"a report about a directory the caller did not name: {args!r}. "
            "This script takes no arguments; the directory it reads is the "
            "constant PAKS in its own source."
        )
        return USAGE_EXIT_CODE
    if not PAKS.is_dir():
        print(f"MISSING: {PAKS}")
        return 1
    # Named before the per-container lines, not after, so a truncated paste
    # still carries the scope of what follows.
    print(f"SCANNING: {PAKS}")
    for path in sorted(PAKS.iterdir()):
        try:
            if path.suffix == ".utoc":
                print(read_utoc(path))
            elif path.suffix == ".pak":
                print(read_pak(path))
        except OSError as exc:
            print(f"{path.name}: ERROR {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
