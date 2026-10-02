#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/cfb.py
"""Identify what a Compound File Binary (OLE2) container holds.

Outlook ``.msg``, Word 97-2003 ``.doc``, PowerPoint 97-2003 ``.ppt`` and Excel
97-2003 ``.xls`` files all start with the same eight-byte CFB signature, so the
signature alone cannot route them. What tells them apart is the names of the
streams directly under the root storage ([MS-CFB]), which this module reads
with the standard library only, so detection works on every install.

Only the root's own children are consulted: a ``.msg`` can carry an attached
Word document as a nested storage, and that nested ``WordDocument`` stream must
not turn the message into a ``.doc``.

The directory usually sits near the end of the file, beyond the sample that
format detection reads, so the reader seeks through the whole input; it reads
only the header, the FAT sectors the directory chain needs, and the directory
itself.
"""

from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import IO, Literal, Union

CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

CfbKind = Literal["msg", "doc", "ppt", "xls"]

_HEADER_SIZE = 512
_DIRECTORY_ENTRY_SIZE = 128
_HEADER_DIFAT_ENTRIES = 109
_MAX_REGULAR_SECTOR = 0xFFFFFFFA
_NO_STREAM = 0xFFFFFFFF

# Bounds against malformed or hostile files: a directory chain longer than this
# (64 MiB of directory at 4 KiB sectors) is not a document we route.
_MAX_DIRECTORY_SECTORS = 16384
_MAX_DIFAT_SECTORS = 16384


def sniff_cfb_kind(source: Union[str, Path, bytes, IO[bytes]]) -> CfbKind | None:
    """Return which Office format a CFB container holds, or None.

    Parameters
    ----------
    source : str, Path, bytes or binary file-like
        The whole input. A path is opened and closed here; a file-like object
        must be seekable and has its position restored.

    Returns
    -------
    {"msg", "doc", "ppt", "xls"} or None
        None when the input is not a CFB container, cannot be read, or holds
        something else (an installer, a thumbnail cache, a Visio drawing).

    """
    try:
        if isinstance(source, bytes):
            return _kind_from_names(_root_stream_names(io.BytesIO(source)))
        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                return _kind_from_names(_root_stream_names(f))
        position = source.tell()
        try:
            return _kind_from_names(_root_stream_names(source))
        finally:
            source.seek(position)
    except (OSError, ValueError, struct.error):
        return None


def describe_cfb_kind(kind: CfbKind) -> tuple[str, str]:
    """Return a human-readable name and the modern extension for a CFB kind.

    Parameters
    ----------
    kind : {"msg", "doc", "ppt", "xls"}
        A kind returned by :func:`sniff_cfb_kind`.

    Returns
    -------
    tuple[str, str]
        The format's name and the extension its modern successor uses.

    """
    return {
        "msg": ("Outlook message (.msg)", ".msg"),
        "doc": ("Word 97-2003 document (.doc)", ".docx"),
        "ppt": ("PowerPoint 97-2003 presentation (.ppt)", ".pptx"),
        "xls": ("Excel 97-2003 workbook (.xls)", ".xlsx"),
    }[kind]


def _kind_from_names(names: set[str] | None) -> CfbKind | None:
    if not names:
        return None
    # Each application's main stream decides first; a Word file with an embedded
    # workbook keeps that workbook in a nested storage, never at the root.
    if "WordDocument" in names:
        return "doc"
    if "PowerPoint Document" in names:
        return "ppt"
    if "__properties_version1.0" in names or any(n.startswith("__substg1.0_") for n in names):
        return "msg"
    if "Workbook" in names or "Book" in names:
        return "xls"
    return None


def _root_stream_names(f: IO[bytes]) -> set[str] | None:
    """Read the names of the root storage's children, or None if not a CFB file."""
    f.seek(0)
    header = f.read(_HEADER_SIZE)
    if len(header) < _HEADER_SIZE or not header.startswith(CFB_SIGNATURE):
        return None

    sector_shift = struct.unpack_from("<H", header, 30)[0]
    if sector_shift not in (9, 12):
        return None
    sector_size = 1 << sector_shift
    entries_per_sector = sector_size // 4

    num_fat_sectors = struct.unpack_from("<I", header, 44)[0]
    first_directory_sector = struct.unpack_from("<I", header, 48)[0]
    first_difat_sector = struct.unpack_from("<I", header, 68)[0]
    num_difat_sectors = struct.unpack_from("<I", header, 72)[0]

    def read_sector(sector: int) -> bytes:
        if sector > _MAX_REGULAR_SECTOR:
            raise ValueError("chain points at a special sector")
        f.seek((sector + 1) << sector_shift)
        data = f.read(sector_size)
        if len(data) < sector_size:
            raise ValueError("sector past end of file")
        return data

    # The DIFAT lists where each FAT sector lives: 109 entries in the header,
    # then a chain of DIFAT sectors whose last entry links to the next one.
    fat_locations = list(struct.unpack_from(f"<{_HEADER_DIFAT_ENTRIES}I", header, 76))
    difat_sector = first_difat_sector
    for _ in range(min(num_difat_sectors, _MAX_DIFAT_SECTORS)):
        if difat_sector > _MAX_REGULAR_SECTOR:
            break
        values = struct.unpack(f"<{entries_per_sector}I", read_sector(difat_sector))
        fat_locations.extend(values[:-1])
        difat_sector = values[-1]
    fat_locations = fat_locations[:num_fat_sectors]

    fat_cache: dict[int, tuple[int, ...]] = {}

    def next_sector(sector: int) -> int:
        index, offset = divmod(sector, entries_per_sector)
        if index >= len(fat_locations):
            raise ValueError("sector outside the FAT")
        if index not in fat_cache:
            fat_cache[index] = struct.unpack(f"<{entries_per_sector}I", read_sector(fat_locations[index]))
        return fat_cache[index][offset]

    directory = bytearray()
    sector = first_directory_sector
    seen: set[int] = set()
    while sector <= _MAX_REGULAR_SECTOR:
        if sector in seen or len(seen) >= _MAX_DIRECTORY_SECTORS:
            raise ValueError("directory chain loops or runs too long")
        seen.add(sector)
        directory += read_sector(sector)
        sector = next_sector(sector)

    entry_count = len(directory) // _DIRECTORY_ENTRY_SIZE
    if entry_count == 0:
        return None

    def entry(index: int) -> tuple[str, int, int, int]:
        base = index * _DIRECTORY_ENTRY_SIZE
        name_length = struct.unpack_from("<H", directory, base + 64)[0]
        name_bytes = bytes(directory[base : base + min(name_length, 64)])
        name = name_bytes.decode("utf-16-le", errors="replace").rstrip("\x00")
        left, right, child = struct.unpack_from("<III", directory, base + 68)
        return name, left, right, child

    # Entry 0 is the root storage; its children form a binary tree linked
    # through the left/right sibling fields, starting at the root's child.
    names: set[str] = set()
    pending = [entry(0)[3]]
    visited: set[int] = set()
    while pending:
        index = pending.pop()
        if index == _NO_STREAM or index in visited or index >= entry_count:
            continue
        visited.add(index)
        name, left, right, _child = entry(index)
        names.add(name)
        pending.extend((left, right))
    return names
