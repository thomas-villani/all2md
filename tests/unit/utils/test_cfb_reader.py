#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for reading streams out of CFB (OLE2) containers.

The containers are laid out byte by byte by :func:`build`, so each case states
exactly which sectors a stream occupies and each corruption hits one field.
Where olefile is installed (it comes with the Outlook extra) the same
containers are read with it too, and both readers must return the same bytes.
"""

from __future__ import annotations

import io
import struct
from dataclasses import dataclass

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md.exceptions import MalformedFileError
from all2md.utils.cfb import CFB_SIGNATURE, CfbReader, sniff_cfb_kind

_END_OF_CHAIN = 0xFFFFFFFE
_FREE = 0xFFFFFFFF
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
            minifat.extend(first + offset + 1 if offset + 1 < count else _END_OF_CHAIN for offset in range(count))
            starts[path] = first if count else _END_OF_CHAIN
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
            return _END_OF_CHAIN
        first = len(fat)
        fat.extend(first + offset + 1 if offset + 1 < count else _END_OF_CHAIN for offset in range(count))
        body.append(data)
        return first

    directory_start = len(fat)
    fat.extend(directory_start + n + 1 for n in range(sectors_for(len(order) * 128)))
    fat[-1] = _END_OF_CHAIN
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

    fat.extend([_FREE] * (fat_count * per_sector - len(fat)))
    sectors = [struct.pack(f"<{per_sector}I", *fat[n * per_sector : (n + 1) * per_sector]) for n in range(fat_count)]
    remaining = fat_locations[109:]
    for position in range(difat_count):
        chunk = remaining[position * (per_sector - 1) : (position + 1) * (per_sector - 1)]
        link = difat_locations[position + 1] if position + 1 < difat_count else _END_OF_CHAIN
        sectors.append(struct.pack(f"<{per_sector}I", *(chunk + [_FREE] * (per_sector - 1 - len(chunk)) + [link])))

    def padded(data: bytes) -> bytes:
        return data.ljust(sectors_for(len(data)) * sector_size, b"\x00")

    header = bytearray(512)
    header[:8] = CFB_SIGNATURE
    struct.pack_into("<HHHHH", header, 24, 0x3E, version, 0xFFFE, 12 if version == 4 else 9, 6)
    struct.pack_into("<I", header, 40, sectors_for(len(directory)) if version == 4 else 0)
    struct.pack_into("<II", header, 44, fat_count, directory_start)
    struct.pack_into("<III", header, 56, mini_cutoff, minifat_start, sectors_for(len(minifat_bytes)))
    struct.pack_into("<II", header, 68, difat_locations[0] if difat_locations else _END_OF_CHAIN, difat_count)
    struct.pack_into("<109I", header, 76, *(fat_locations[:109] + [_FREE] * (109 - min(fat_count, 109))))

    data = bytes(header).ljust(sector_size, b"\x00") + b"".join(sectors) + padded(directory)
    data += b"".join(padded(part) for part in body)
    return Built(data, sector_size, starts, fat_locations)


def _pattern(size: int, seed: int = 0) -> bytes:
    return bytes((offset * 31 + seed * 7 + offset // 251) % 256 for offset in range(size))


STREAMS = {
    "WordDocument": _pattern(9000, 1),
    "1Table": _pattern(700, 2),
    "\x05SummaryInformation": _pattern(4096, 3),
    "ObjectPool/_1234/\x01Ole": _pattern(20, 4),
    "ObjectPool/_1234/Contents": _pattern(5000, 5),
    "Empty": b"",
}


def _olefile_streams(data: bytes) -> dict[str, bytes]:
    olefile = pytest.importorskip("olefile")
    ole = olefile.OleFileIO(data)
    return {"/".join(path): ole.openstream(path).read() for path in ole.listdir(streams=True, storages=False)}


@pytest.mark.unit
class TestReadStream:
    """Streams come back whole, from regular sectors and from the mini stream."""

    @pytest.mark.parametrize("version", [3, 4])
    def test_every_stream_round_trips(self, version):
        reader = CfbReader(build(STREAMS, version=version).data)
        assert sorted(reader.list_streams()) == sorted(STREAMS)
        for path, data in STREAMS.items():
            assert reader.read_stream(path) == data

    @pytest.mark.parametrize("version", [3, 4])
    def test_agrees_with_olefile(self, version):
        data = build(STREAMS, version=version).data
        reader = CfbReader(data)
        assert {path: reader.read_stream(path) for path in reader.list_streams()} == _olefile_streams(data)

    def test_cutoff_boundary(self):
        """A stream exactly the cutoff long is in regular sectors; one byte less is mini."""
        streams = {"at": _pattern(4096), "below": _pattern(4095)}
        built = build(streams)
        reader = CfbReader(built.data)
        assert reader.read_stream("at") == streams["at"]
        assert reader.read_stream("below") == streams["below"]
        assert reader.entry("at").start == built.starts["at"]

    def test_difat_sectors(self):
        """A FAT too long for the header's 109 slots continues in DIFAT sectors."""
        built = build(STREAMS, min_fat_sectors=200)
        reader = CfbReader(built.data)
        assert reader.read_stream("ObjectPool/_1234/Contents") == STREAMS["ObjectPool/_1234/Contents"]
        assert _olefile_streams(built.data)["WordDocument"] == reader.read_stream("WordDocument")

    def test_paths_match_case_insensitively(self):
        reader = CfbReader(build(STREAMS).data)
        assert reader.read_stream("objectpool/_1234/CONTENTS") == STREAMS["ObjectPool/_1234/Contents"]
        assert reader.exists("ObjectPool/_1234")
        assert not reader.exists("ObjectPool/_9999")

    def test_root_names_are_direct_children_only(self):
        reader = CfbReader(build(STREAMS).data)
        assert reader.root_names() == {"WordDocument", "1Table", "\x05SummaryInformation", "ObjectPool", "Empty"}

    @pytest.mark.parametrize("path", ["Missing", "ObjectPool"], ids=["absent", "storage"])
    def test_reading_a_non_stream_raises_key_error(self, path):
        with pytest.raises(KeyError):
            CfbReader(build(STREAMS).data).read_stream(path)

    def test_path_and_file_inputs(self, tmp_path):
        data = build(STREAMS).data
        path = tmp_path / "report.doc"
        path.write_bytes(data)
        with CfbReader(path) as reader:
            assert reader.read_stream("1Table") == STREAMS["1Table"]
        assert CfbReader(io.BytesIO(data)).read_stream("1Table") == STREAMS["1Table"]

    def test_short_last_sector_is_read_when_the_stream_fits(self):
        """Some writers stop the file where the last stream ends, mid-sector."""
        built = build({"tail": _pattern(5000)})
        end = (built.starts["tail"] + 1) * 512 + 5000
        assert end < len(built.data)
        assert CfbReader(built.data[:end]).read_stream("tail") == _pattern(5000)

    def test_file_cut_inside_the_last_stream_raises(self):
        """A file cut before the stream's last byte must not pad the stream with zeros."""
        built = build({"tail": _pattern(5000)})
        end = (built.starts["tail"] + 1) * 512 + 5000
        reader = CfbReader(built.data[: end - 1])
        with pytest.raises(MalformedFileError, match="cut off"):
            reader.read_stream("tail")


@pytest.mark.unit
class TestMalformed:
    """Every broken chain, size or index raises MalformedFileError, nothing else."""

    def test_not_a_container(self):
        with pytest.raises(MalformedFileError):
            CfbReader(b"plain text")

    def test_stream_chain_loop(self):
        built = build(STREAMS)
        start = built.starts["WordDocument"]
        reader = CfbReader(built.set_fat(start + 1, start))
        with pytest.raises(MalformedFileError, match="loops"):
            reader.read_stream("WordDocument")

    def test_stream_chain_past_end_of_file(self):
        built = build(STREAMS)
        start = built.starts["WordDocument"]
        reader = CfbReader(built.set_fat(start, 0x00FFFFFF))
        with pytest.raises(MalformedFileError, match="outside"):
            reader.read_stream("WordDocument")

    def test_stream_chain_ends_early(self):
        built = build(STREAMS)
        start = built.starts["WordDocument"]
        reader = CfbReader(built.set_fat(start, _END_OF_CHAIN))
        with pytest.raises(MalformedFileError, match="ends before"):
            reader.read_stream("WordDocument")

    def test_stream_chain_reaches_free_sector(self):
        built = build(STREAMS)
        start = built.starts["WordDocument"]
        reader = CfbReader(built.set_fat(start, _FREE))
        with pytest.raises(MalformedFileError, match="special"):
            reader.read_stream("WordDocument")

    def test_size_larger_than_file(self):
        built = build(STREAMS)
        data = bytearray(built.data)
        reader = CfbReader(bytes(data))
        position = data.find("WordDocument".encode("utf-16-le"))
        struct.pack_into("<I", data, position + 120, 0x7FFFFFFF)
        with pytest.raises(MalformedFileError, match="claims"):
            CfbReader(bytes(data)).read_stream("WordDocument")
        assert reader.read_stream("WordDocument") == STREAMS["WordDocument"]

    def test_version_3_ignores_high_size_bits(self):
        """[MS-CFB] lets version 3 writers leave garbage in the size's high half."""
        data = bytearray(build(STREAMS).data)
        position = data.find("1Table".encode("utf-16-le"))
        struct.pack_into("<I", data, position + 124, 0xDEADBEEF)
        assert CfbReader(bytes(data)).read_stream("1Table") == STREAMS["1Table"]

    def test_mini_size_larger_than_mini_stream(self):
        data = bytearray(build(STREAMS).data)
        position = data.find("1Table".encode("utf-16-le"))
        struct.pack_into("<I", data, position + 120, 4000)
        with pytest.raises(MalformedFileError, match="mini stream"):
            CfbReader(bytes(data)).read_stream("1Table")

    def test_mini_start_outside_mini_stream(self):
        data = bytearray(build(STREAMS).data)
        position = data.find("1Table".encode("utf-16-le"))
        struct.pack_into("<I", data, position + 116, 5000)
        with pytest.raises(MalformedFileError, match="outside the mini stream"):
            CfbReader(bytes(data)).read_stream("1Table")

    def test_file_cut_inside_a_middle_sector(self):
        built = build(STREAMS)
        path = "ObjectPool/_1234/Contents"
        reader = CfbReader(built.data[: (built.starts[path] + 2) * 512 + 100])
        with pytest.raises(MalformedFileError, match="cut off"):
            reader.read_stream(path)
        assert reader.read_stream("WordDocument") == STREAMS["WordDocument"]

    def test_header_claims_more_fat_than_file(self):
        data = bytearray(build(STREAMS).data)
        struct.pack_into("<I", data, 44, 1_000_000)
        with pytest.raises(MalformedFileError, match="FAT sectors"):
            CfbReader(bytes(data))

    def test_directory_cycle_is_walked_once(self):
        """A sibling link back to an earlier entry is not followed twice."""
        data = bytearray(build(STREAMS).data)
        position = data.find("Empty".encode("utf-16-le"))
        struct.pack_into("<I", data, position + 72, 1)
        reader = CfbReader(bytes(data))
        assert sorted(reader.list_streams()) == sorted(STREAMS)

    def test_sniff_still_returns_none_for_broken_containers(self):
        assert sniff_cfb_kind(build(STREAMS).data[:600]) is None

    @settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.data())
    def test_mutations_raise_only_malformed_file_error(self, draw):
        data = bytearray(build(STREAMS).data)
        if draw.draw(st.booleans()):
            data = data[: draw.draw(st.integers(0, len(data)))]
        else:
            for _ in range(draw.draw(st.integers(1, 8))):
                position = draw.draw(st.integers(0, len(data) - 1))
                data[position] = draw.draw(st.integers(0, 255))
        try:
            reader = CfbReader(bytes(data))
        except MalformedFileError:
            return
        for path in reader.list_streams():
            try:
                stream = reader.read_stream(path)
            except MalformedFileError:
                continue
            assert len(stream) == reader.entry(path).size
