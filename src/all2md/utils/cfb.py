#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/cfb.py
"""Read Compound File Binary (OLE2) containers with the standard library.

Outlook ``.msg``, Word 97-2003 ``.doc``, PowerPoint 97-2003 ``.ppt`` and Excel
97-2003 ``.xls`` files all start with the same eight-byte CFB signature, so the
signature alone cannot route them. What tells them apart is the names of the
streams directly under the root storage ([MS-CFB]); :func:`sniff_cfb_kind`
reads those, so detection works on every install.

Only the root's own children are consulted when sniffing: a ``.msg`` can carry
an attached Word document as a nested storage, and that nested ``WordDocument``
stream must not turn the message into a ``.doc``.

:class:`CfbReader` also reads stream contents, for the parsers of the binary
Office formats. A stream at least the header's cutoff (normally 4096 bytes)
long is a chain of regular sectors linked through the FAT; a shorter one is a
chain of 64-byte mini sectors inside the mini stream, linked through the
miniFAT. The reader loads FAT sectors as chains need them, so sniffing a large
file reads only the header, the directory, and the FAT sectors that cover it.

Every chain, size and index comes from the file, so each is checked before it
is followed: a chain that loops, leaves the FAT, points past the end of the
file or ends before the declared size raises :class:`MalformedFileError`, and
no stream may claim more bytes than the file holds.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal, Union

from all2md.exceptions import MalformedFileError

CFB_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

CfbKind = Literal["msg", "doc", "ppt", "xls"]

_HEADER_SIZE = 512
_DIRECTORY_ENTRY_SIZE = 128
_HEADER_DIFAT_ENTRIES = 109
_MAX_REGULAR_SECTOR = 0xFFFFFFFA
_END_OF_CHAIN = 0xFFFFFFFE
_NO_STREAM = 0xFFFFFFFF

_ENTRY_STORAGE = 1
_ENTRY_STREAM = 2
_ENTRY_ROOT = 5

# Bounds against malformed or hostile files: a directory chain longer than this
# (64 MiB of directory at 4 KiB sectors) is not a document we read.
_MAX_DIRECTORY_SECTORS = 16384
_MAX_DIFAT_SECTORS = 16384


@dataclass(frozen=True)
class CfbEntry:
    """One directory entry: a storage, a stream, or the root storage.

    Attributes
    ----------
    name : str
        The entry's name within its parent storage.
    kind : int
        1 for a storage, 2 for a stream, 5 for the root storage.
    left, right, child : int
        Directory indexes of the left and right siblings and, for a storage,
        the root of its children's tree; 0xFFFFFFFF for none.
    start : int
        First sector of the entry's data (a mini sector for a short stream).
    size : int
        Length of the entry's data in bytes.

    """

    name: str
    kind: int
    left: int
    right: int
    child: int
    start: int
    size: int


class CfbReader:
    """Read the directory and streams of a CFB container.

    Parameters
    ----------
    source : str, Path, bytes or binary file-like
        The whole container. A path is opened here and closed by :meth:`close`
        (or the ``with`` block); a file-like object must be seekable and is
        left open.

    Raises
    ------
    MalformedFileError
        If the input is not a CFB container or its header or directory cannot
        be read.

    Notes
    -----
    Stream paths join storage names with ``/``, as in
    ``"ObjectPool/_1234/WordDocument"``, and match case-insensitively, as
    [MS-CFB] compares names.

    """

    def __init__(self, source: Union[str, Path, bytes, IO[bytes]]):
        """Parse the header and directory of ``source``."""
        self._owned: IO[bytes] | None = None
        if isinstance(source, bytes):
            self._file: IO[bytes] = io.BytesIO(source)
        elif isinstance(source, (str, Path)):
            self._owned = self._file = open(source, "rb")
        else:
            self._file = source
        try:
            self._parse_header()
            self.entries: list[CfbEntry] = self._read_directory()
            self._paths = self._walk_tree()
            self._folded: dict[str, int] = {}
            for path, index in self._paths.items():
                self._folded.setdefault(path.casefold(), index)
        except (OSError, struct.error) as error:
            self.close()
            raise MalformedFileError(f"Unreadable CFB container: {error}", original_error=error) from error
        except MalformedFileError:
            self.close()
            raise
        self._mini_stream: bytes | None = None
        self._minifat: tuple[int, ...] | None = None

    def __enter__(self) -> CfbReader:
        """Return the reader for a ``with`` block."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Close a file this reader opened."""
        self.close()

    def close(self) -> None:
        """Close the file if this reader opened it from a path."""
        if self._owned is not None:
            self._owned.close()
            self._owned = None

    # -- public API ---------------------------------------------------------

    def root_names(self) -> set[str]:
        """Return the names of the root storage's direct children."""
        return {path for path in self._paths if "/" not in path}

    def list_streams(self) -> list[str]:
        """Return the path of every stream, in directory order."""
        return [path for path, index in self._paths.items() if self.entries[index].kind == _ENTRY_STREAM]

    def exists(self, path: str) -> bool:
        """Return whether a stream or storage exists at ``path``."""
        return self._lookup(path) is not None

    def entry(self, path: str) -> CfbEntry:
        """Return the directory entry at ``path``.

        Raises
        ------
        KeyError
            If nothing exists at ``path``.

        """
        index = self._lookup(path)
        if index is None:
            raise KeyError(path)
        return self.entries[index]

    def read_stream(self, path: str) -> bytes:
        """Return the whole contents of the stream at ``path``.

        Raises
        ------
        KeyError
            If no stream exists at ``path``.
        MalformedFileError
            If the stream's sector chain is broken.

        """
        entry = self.entry(path)
        if entry.kind != _ENTRY_STREAM:
            raise KeyError(path)
        try:
            if entry.size < self._mini_cutoff:
                return self._read_mini(entry.start, entry.size)
            return self._read_chain(entry.start, entry.size)
        except (OSError, struct.error) as error:
            raise MalformedFileError(f"Unreadable CFB stream {path!r}: {error}", original_error=error) from error

    # -- header, FAT and chains ---------------------------------------------

    def _parse_header(self) -> None:
        f = self._file
        f.seek(0, io.SEEK_END)
        self._file_size = f.tell()
        f.seek(0)
        header = f.read(_HEADER_SIZE)
        if len(header) < _HEADER_SIZE or not header.startswith(CFB_SIGNATURE):
            raise MalformedFileError("Not a CFB container: missing signature")

        self._version = struct.unpack_from("<H", header, 26)[0]
        sector_shift, mini_shift = struct.unpack_from("<HH", header, 30)
        if sector_shift not in (9, 12):
            raise MalformedFileError(f"Unsupported CFB sector size 2^{sector_shift}")
        if mini_shift != 6:
            raise MalformedFileError(f"Unsupported CFB mini sector size 2^{mini_shift}")
        self._sector_shift = sector_shift
        self._sector_size = 1 << sector_shift
        self._entries_per_sector = self._sector_size // 4
        # Sectors in the file, counting a short last one; sector 0 follows the header sector.
        self._sector_count = max(0, -(-self._file_size // self._sector_size) - 1)

        num_fat_sectors = struct.unpack_from("<I", header, 44)[0]
        self._first_directory_sector = struct.unpack_from("<I", header, 48)[0]
        self._mini_cutoff, self._first_minifat_sector, num_minifat_sectors = struct.unpack_from("<III", header, 56)
        first_difat_sector, num_difat_sectors = struct.unpack_from("<II", header, 68)
        self._num_minifat_sectors = num_minifat_sectors
        if num_fat_sectors > self._sector_count:
            raise MalformedFileError("CFB header declares more FAT sectors than the file holds")

        # The DIFAT lists where each FAT sector lives: 109 entries in the header,
        # then a chain of DIFAT sectors whose last entry links to the next one.
        fat_locations = list(struct.unpack_from(f"<{_HEADER_DIFAT_ENTRIES}I", header, 76))
        difat_sector = first_difat_sector
        seen: set[int] = set()
        for _ in range(min(num_difat_sectors, _MAX_DIFAT_SECTORS)):
            if len(fat_locations) >= num_fat_sectors or difat_sector > _MAX_REGULAR_SECTOR:
                break
            if difat_sector in seen:
                raise MalformedFileError("CFB DIFAT chain loops")
            seen.add(difat_sector)
            values = struct.unpack(f"<{self._entries_per_sector}I", self._read_sector(difat_sector))
            fat_locations.extend(values[:-1])
            difat_sector = values[-1]
        self._fat_locations = fat_locations[:num_fat_sectors]
        self._fat_cache: dict[int, tuple[int, ...]] = {}

    def _read_sector(self, sector: int, need: int | None = None) -> bytes:
        """Read one sector, of which at least ``need`` bytes (all, by default) must exist.

        Some writers leave the file's last sector short; a stream may end inside
        it, but nothing may be read from past the end of the file.
        """
        if sector >= self._sector_count:
            raise MalformedFileError(f"CFB sector {sector:#x} lies outside the file")
        self._file.seek((sector + 1) << self._sector_shift)
        data = self._file.read(self._sector_size)
        if len(data) < (self._sector_size if need is None else need):
            raise MalformedFileError(f"CFB sector {sector:#x} is cut off by the end of the file")
        return data

    def _next_sector(self, sector: int) -> int:
        index, offset = divmod(sector, self._entries_per_sector)
        if index >= len(self._fat_locations):
            raise MalformedFileError(f"CFB sector {sector:#x} lies outside the FAT")
        if index not in self._fat_cache:
            data = self._read_sector(self._fat_locations[index])
            self._fat_cache[index] = struct.unpack(f"<{self._entries_per_sector}I", data)
        return self._fat_cache[index][offset]

    def _chain(self, start: int, limit: int) -> list[int]:
        """Follow a FAT chain from ``start``, at most ``limit`` sectors long.

        A chain may end before ``limit`` (its end-of-chain marker); a chain
        that revisits a sector or names a sector the file lacks is malformed.
        """
        sectors: list[int] = []
        seen: set[int] = set()
        sector = start
        while sector != _END_OF_CHAIN and len(sectors) < limit:
            if sector > _MAX_REGULAR_SECTOR:
                raise MalformedFileError(f"CFB chain reaches special sector {sector:#x}")
            if sector in seen:
                raise MalformedFileError("CFB sector chain loops")
            seen.add(sector)
            sectors.append(sector)
            sector = self._next_sector(sector)
        return sectors

    def _read_chain(self, start: int, size: int) -> bytes:
        if size > self._file_size:
            raise MalformedFileError(f"CFB stream claims {size} bytes in a {self._file_size}-byte file")
        needed = -(-size // self._sector_size)
        sectors = self._chain(start, needed)
        if len(sectors) < needed:
            raise MalformedFileError("CFB sector chain ends before the stream does")
        tail = size - (needed - 1) * self._sector_size
        parts = [self._read_sector(sector) for sector in sectors[:-1]]
        parts.extend(self._read_sector(sector, tail) for sector in sectors[-1:])
        return b"".join(parts)[:size]

    def _read_mini(self, start: int, size: int) -> bytes:
        if self._mini_stream is None:
            root = self.entries[0]
            self._mini_stream = self._read_chain(root.start, root.size) if root.size else b""
            limit = min(self._num_minifat_sectors, self._sector_count)
            data = b"".join(self._read_sector(sector) for sector in self._chain(self._first_minifat_sector, limit))
            self._minifat = struct.unpack(f"<{len(data) // 4}I", data)
        minifat = self._minifat or ()
        mini_stream = self._mini_stream

        if size > len(mini_stream):
            raise MalformedFileError(f"CFB stream claims {size} bytes in a {len(mini_stream)}-byte mini stream")
        needed = -(-size // 64)
        parts: list[bytes] = []
        seen: set[int] = set()
        sector = start
        while len(parts) < needed:
            if sector in seen:
                raise MalformedFileError("CFB mini sector chain loops")
            if sector >= len(minifat) or sector * 64 >= len(mini_stream):
                raise MalformedFileError(f"CFB mini sector {sector:#x} lies outside the mini stream")
            seen.add(sector)
            parts.append(mini_stream[sector * 64 : (sector + 1) * 64])
            sector = minifat[sector]
        data = b"".join(parts)
        if len(data) < size:
            raise MalformedFileError("CFB mini stream ends before the stream does")
        return data[:size]

    # -- directory ----------------------------------------------------------

    def _read_directory(self) -> list[CfbEntry]:
        sectors = self._chain(self._first_directory_sector, _MAX_DIRECTORY_SECTORS)
        if len(sectors) == _MAX_DIRECTORY_SECTORS and self._next_sector(sectors[-1]) != _END_OF_CHAIN:
            raise MalformedFileError("CFB directory chain runs too long")
        directory = b"".join(self._read_sector(sector) for sector in sectors)
        entries = [
            self._parse_entry(directory, base)
            for base in range(0, len(directory) - _DIRECTORY_ENTRY_SIZE + 1, _DIRECTORY_ENTRY_SIZE)
        ]
        if not entries or entries[0].kind != _ENTRY_ROOT:
            raise MalformedFileError("CFB directory has no root entry")
        return entries

    def _parse_entry(self, directory: bytes, base: int) -> CfbEntry:
        name_length = struct.unpack_from("<H", directory, base + 64)[0]
        name = directory[base : base + min(name_length, 64)].decode("utf-16-le", errors="replace").rstrip("\x00")
        kind = directory[base + 66]
        left, right, child = struct.unpack_from("<III", directory, base + 68)
        start, size = struct.unpack_from("<IQ", directory, base + 116)
        if self._version == 3:
            # Version 3 writers may leave garbage in the high half of the size ([MS-CFB] 2.6.3).
            size &= 0xFFFFFFFF
        return CfbEntry(name, kind, left, right, child, start, size)

    def _walk_tree(self) -> dict[str, int]:
        """Map each stream and storage path to its directory index.

        Each storage's children form a binary tree linked through the left
        and right sibling fields, starting at the storage's child. An entry
        reached twice (a cycle, or two parents) is visited only the first time.
        """
        paths: dict[str, int] = {}
        visited = {0}
        pending: list[tuple[int, str]] = [(self.entries[0].child, "")]
        while pending:
            index, prefix = pending.pop()
            if index == _NO_STREAM or index in visited or index >= len(self.entries):
                continue
            visited.add(index)
            entry = self.entries[index]
            pending.extend(((entry.right, prefix), (entry.left, prefix)))
            if entry.kind not in (_ENTRY_STORAGE, _ENTRY_STREAM):
                continue
            path = prefix + entry.name
            paths.setdefault(path, index)
            if entry.kind == _ENTRY_STORAGE:
                pending.append((entry.child, path + "/"))
        return paths

    def _lookup(self, path: str) -> int | None:
        return self._folded.get(path.strip("/").casefold())


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
    if isinstance(source, (bytes, str, Path)):
        return _sniff(source)
    position = source.tell()
    try:
        return _sniff(source)
    finally:
        source.seek(position)


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


def _sniff(source: Union[str, Path, bytes, IO[bytes]]) -> CfbKind | None:
    try:
        with CfbReader(source) as reader:
            return _kind_from_names(reader.root_names())
    except (OSError, MalformedFileError):
        return None


def _kind_from_names(names: set[str]) -> CfbKind | None:
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
