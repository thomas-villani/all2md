#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Lay out CFB (OLE2) containers byte by byte for tests.

:func:`build` places each stream in regular sectors or the mini stream by
size, with the FAT and DIFAT first and the streams last, and reports where
everything landed so a test can corrupt one field.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from all2md.utils.cfb import CFB_SIGNATURE

END_OF_CHAIN = 0xFFFFFFFE
FREE = 0xFFFFFFFF
_FAT_SECTOR = 0xFFFFFFFD
_DIFAT_SECTOR = 0xFFFFFFFC
_NO_STREAM = 0xFFFFFFFF
_MINI = 64


@dataclass
class Built:
    """A container and where its parts landed."""

    data: bytes
    sector_size: int
    starts: dict[str, int]
    fat_sectors: list[int]

    def set_fat(self, sector: int, value: int) -> bytes:
        """Return the container with one FAT entry replaced."""
        per_sector = self.sector_size // 4
        location = self.fat_sectors[sector // per_sector]
        offset = (location + 1) * self.sector_size + (sector % per_sector) * 4
        data = bytearray(self.data)
        struct.pack_into("<I", data, offset, value)
        return bytes(data)


def _entry(name: str, kind: int, *, right: int, child: int, start: int, size: int) -> bytes:
    encoded = (name + "\x00").encode("utf-16-le")
    data = bytearray(128)
    data[: len(encoded)] = encoded
    struct.pack_into("<HBB", data, 64, len(encoded), kind, 1)
    struct.pack_into("<III", data, 68, _NO_STREAM, right, child)
    struct.pack_into("<IQ", data, 116, start, size)
    return bytes(data)


def build(
    streams: dict[str, bytes],
    *,
    version: int = 3,
    mini_cutoff: int = 4096,
    min_fat_sectors: int = 0,
) -> Built:
    """Lay out a CFB container holding ``streams``.

    Paths use ``/`` between storage names; storages are created as needed.
    Streams shorter than ``mini_cutoff`` go into the mini stream. Setting
    ``min_fat_sectors`` past 109 forces DIFAT sectors.

    The FAT and DIFAT come first, then the directory, the miniFAT and the mini
    stream, then the regular streams in order, so the last stream ends the file.
    """
    sector_size = 4096 if version == 4 else 512
    per_sector = sector_size // 4

    def sectors_for(size: int) -> int:
        return -(-size // sector_size)

    # Directory tree: every storage's children linked as a right-sibling chain.
    children: dict[str, list[str]] = {"": []}
    for path in streams:
        parts = path.split("/")
        for depth in range(len(parts)):
            parent, name = "/".join(parts[:depth]), "/".join(parts[: depth + 1])
            if name not in children.setdefault(parent, []):
                children[parent].append(name)
            if depth < len(parts) - 1:
                children.setdefault(name, [])
    order = [""]
    for path in order:
        order.extend(children.get(path, []))
    index = {path: position for position, path in enumerate(order)}

    mini_stream = bytearray()
    minifat: list[int] = []
    starts: dict[str, int] = {}
    regular = [path for path, data in streams.items() if len(data) >= mini_cutoff]
    for path, data in streams.items():
        if len(data) < mini_cutoff:
            first = len(mini_stream) // _MINI
            count = -(-len(data) // _MINI)
            mini_stream += data.ljust(count * _MINI, b"\x00")
            minifat.extend(first + offset + 1 if offset + 1 < count else END_OF_CHAIN for offset in range(count))
            starts[path] = first if count else END_OF_CHAIN
    minifat_bytes = struct.pack(f"<{len(minifat)}I", *minifat) if minifat else b""

    # Count the data sectors, then size the FAT and DIFAT to cover them and themselves.
    parts = [len(order) * 128, len(minifat_bytes), len(mini_stream)] + [len(streams[path]) for path in regular]
    data_sectors = sum(sectors_for(size) for size in parts)
    fat_count = max(min_fat_sectors, 1)
    while True:
        difat_count = max(0, -(-(fat_count - 109) // (per_sector - 1)))
        if fat_count * per_sector >= data_sectors + fat_count + difat_count:
            break
        fat_count += 1

    fat = [_FAT_SECTOR] * fat_count + [_DIFAT_SECTOR] * difat_count
    fat_locations = list(range(fat_count))
    difat_locations = list(range(fat_count, fat_count + difat_count))
    body: list[bytes] = []

    def allocate(data: bytes) -> int:
        count = sectors_for(len(data))
        if count == 0:
            return END_OF_CHAIN
        first = len(fat)
        fat.extend(first + offset + 1 if offset + 1 < count else END_OF_CHAIN for offset in range(count))
        body.append(data)
        return first

    directory_start = len(fat)
    fat.extend(directory_start + n + 1 for n in range(sectors_for(len(order) * 128)))
    fat[-1] = END_OF_CHAIN
    minifat_start = allocate(minifat_bytes)
    mini_start = allocate(bytes(mini_stream))
    for path in regular:
        starts[path] = allocate(streams[path])

    entries = []
    for path in order:
        siblings = children.get(path.rpartition("/")[0], []) if path else []
        position = siblings.index(path) if path else 0
        right = index[siblings[position + 1]] if path and position + 1 < len(siblings) else _NO_STREAM
        child = index[children[path][0]] if children.get(path) else _NO_STREAM
        name = path.rpartition("/")[2]
        if not path:
            entries.append(_entry("Root Entry", 5, right=right, child=child, start=mini_start, size=len(mini_stream)))
        elif path in streams:
            entries.append(_entry(name, 2, right=right, child=child, start=starts[path], size=len(streams[path])))
        else:
            entries.append(_entry(name, 1, right=right, child=child, start=0, size=0))
    directory = b"".join(entries)

    fat.extend([FREE] * (fat_count * per_sector - len(fat)))
    sectors = [struct.pack(f"<{per_sector}I", *fat[n * per_sector : (n + 1) * per_sector]) for n in range(fat_count)]
    remaining = fat_locations[109:]
    for position in range(difat_count):
        chunk = remaining[position * (per_sector - 1) : (position + 1) * (per_sector - 1)]
        link = difat_locations[position + 1] if position + 1 < difat_count else END_OF_CHAIN
        sectors.append(struct.pack(f"<{per_sector}I", *(chunk + [FREE] * (per_sector - 1 - len(chunk)) + [link])))

    def padded(data: bytes) -> bytes:
        return data.ljust(sectors_for(len(data)) * sector_size, b"\x00")

    header = bytearray(512)
    header[:8] = CFB_SIGNATURE
    struct.pack_into("<HHHHH", header, 24, 0x3E, version, 0xFFFE, 12 if version == 4 else 9, 6)
    struct.pack_into("<I", header, 40, sectors_for(len(directory)) if version == 4 else 0)
    struct.pack_into("<II", header, 44, fat_count, directory_start)
    struct.pack_into("<III", header, 56, mini_cutoff, minifat_start, sectors_for(len(minifat_bytes)))
    struct.pack_into("<II", header, 68, difat_locations[0] if difat_locations else END_OF_CHAIN, difat_count)
    struct.pack_into("<109I", header, 76, *(fat_locations[:109] + [FREE] * (109 - min(fat_count, 109))))

    data = bytes(header).ljust(sector_size, b"\x00") + b"".join(sectors) + padded(directory)
    data += b"".join(padded(part) for part in body)
    return Built(data, sector_size, starts, fat_locations)
