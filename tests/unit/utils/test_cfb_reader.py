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

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md.exceptions import MalformedFileError
from all2md.utils.cfb import CfbReader, sniff_cfb_kind

from .cfb_builder import END_OF_CHAIN, FREE, build


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
        reader = CfbReader(built.set_fat(start, END_OF_CHAIN))
        with pytest.raises(MalformedFileError, match="ends before"):
            reader.read_stream("WordDocument")

    def test_stream_chain_reaches_free_sector(self):
        built = build(STREAMS)
        start = built.starts["WordDocument"]
        reader = CfbReader(built.set_fat(start, FREE))
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
