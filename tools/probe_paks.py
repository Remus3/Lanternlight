"""Read UE5 IoStore .utoc headers + legacy .pak footers to determine encryption.

Read-only. Touches no running process. Prints one line per container.
"""
import struct
import sys
from pathlib import Path

PAKS = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Mistfall Hunter"
            r"\MistfallHunter\Content\Paks")

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


def main():
    if not PAKS.is_dir():
        print(f"MISSING: {PAKS}")
        return 1
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
