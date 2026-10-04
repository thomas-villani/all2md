#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for CFB (OLE2) container sniffing and the routing built on it.

Outlook ``.msg``, Word ``.doc``, PowerPoint ``.ppt`` and Excel ``.xls`` share one
signature. The Outlook parser used to claim all of them, so a ``.doc`` failed with
"Failed to parse MSG file: does not contain a properties stream". The containers
here are built byte by byte so each case is exact and no binary fixture is needed.
"""

import io
import struct

import pytest

from all2md.converter_registry import registry
from all2md.exceptions import FormatError
from all2md.parsers.outlook import _reject_non_message_cfb
from all2md.utils.cfb import CFB_SIGNATURE, sniff_cfb_kind

_SECTOR = 512
_END_OF_CHAIN = 0xFFFFFFFE
_FREE = 0xFFFFFFFF
_FAT_SECTOR = 0xFFFFFFFD
_NO_STREAM = 0xFFFFFFFF


def _entry(name: str, kind: int, right: int = _NO_STREAM, child: int = _NO_STREAM) -> bytes:
    encoded = (name + "\x00").encode("utf-16-le")
    data = bytearray(128)
    data[: len(encoded)] = encoded
    struct.pack_into("<HBB", data, 64, len(encoded), kind, 1)
    struct.pack_into("<III", data, 68, _NO_STREAM, right, child)
    struct.pack_into("<I", data, 116, _END_OF_CHAIN)
    return bytes(data)


def build_cfb(
    root_names: list[str],
    nested: dict[str, list[str]] | None = None,
    *,
    filler_sectors: int = 0,
    loop_directory: bool = False,
) -> bytes:
    """Build a minimal version-3 CFB file.

    ``root_names`` become the root's children, linked as a right-sibling chain; a
    name in ``nested`` is a storage whose children are the listed names.
    ``filler_sectors`` puts the directory past that many unused sectors, as real
    files do, beyond the 1 KB detection sample.
    """
    nested = nested or {}
    entries: list[bytes] = []

    def add_chain(names: list[str]) -> int:
        first = len(entries)
        indexes = list(range(first, first + len(names)))
        entries.extend(b"" for _ in names)
        for position, name in enumerate(names):
            right = indexes[position + 1] if position + 1 < len(names) else _NO_STREAM
            child = add_chain(nested[name]) if name in nested else _NO_STREAM
            entries[indexes[position]] = _entry(name, 1 if name in nested else 2, right=right, child=child)
        return first

    entries.append(b"")
    entries[0] = _entry("Root Entry", 5, child=add_chain(root_names) if root_names else _NO_STREAM)
    directory = b"".join(entries)
    directory += b"\x00" * (-len(directory) % _SECTOR)
    directory_sectors = len(directory) // _SECTOR

    first_directory = 1 + filler_sectors
    fat = [_FREE] * (_SECTOR // 4)
    fat[0] = _FAT_SECTOR
    for offset in range(directory_sectors):
        sector = first_directory + offset
        fat[sector] = sector + 1 if offset + 1 < directory_sectors else _END_OF_CHAIN
    if loop_directory:
        fat[first_directory + directory_sectors - 1] = first_directory

    header = bytearray(_SECTOR)
    header[:8] = CFB_SIGNATURE
    struct.pack_into("<HHHHH", header, 24, 0x3E, 3, 0xFFFE, 9, 6)
    struct.pack_into("<III", header, 44, 1, first_directory, 0)
    struct.pack_into("<IIIII", header, 56, 4096, _END_OF_CHAIN, 0, _END_OF_CHAIN, 0)
    difat = [_FREE] * 109
    difat[0] = 0
    struct.pack_into("<109I", header, 76, *difat)

    fat_sector = struct.pack(f"<{_SECTOR // 4}I", *fat)
    return bytes(header) + fat_sector + b"\x00" * (_SECTOR * filler_sectors) + directory


DOC = ["\x01CompObj", "1Table", "WordDocument", "\x05SummaryInformation"]
PPT = ["Current User", "PowerPoint Document", "\x05SummaryInformation"]
MSG = ["__nameid_version1.0", "__properties_version1.0", "__substg1.0_0037001F"]


@pytest.mark.unit
class TestSniffCfbKind:
    """Classify a container by the names directly under its root."""

    @pytest.mark.parametrize(
        ("names", "kind"),
        [
            (DOC, "doc"),
            (PPT, "ppt"),
            (["Workbook", "\x05SummaryInformation"], "xls"),
            (["Book"], "xls"),
            (MSG, "msg"),
            (["__substg1.0_0037001F"], "msg"),
        ],
    )
    def test_kind_from_root_streams(self, names, kind):
        assert sniff_cfb_kind(build_cfb(names)) == kind

    def test_nested_word_document_does_not_make_a_message_a_doc(self):
        """A .msg carrying an embedded Word file keeps that file in a nested storage."""
        data = build_cfb(
            MSG + ["__attach_version1.0_#00000000"],
            nested={"__attach_version1.0_#00000000": ["__substg1.0_3701000D"], "__substg1.0_3701000D": DOC},
        )
        assert sniff_cfb_kind(data) == "msg"

    def test_unknown_container_is_none(self):
        assert sniff_cfb_kind(build_cfb(["\x05SummaryInformation", "Contents"])) is None

    def test_directory_beyond_detection_sample(self):
        data = build_cfb(DOC, filler_sectors=40)
        assert len(data) > 20 * 1024
        assert sniff_cfb_kind(data) == "doc"

    @pytest.mark.parametrize(
        "data",
        [
            b"",
            b"plain text, not a container",
            CFB_SIGNATURE + b"\x00" * 100,
            build_cfb(DOC)[:600],
        ],
        ids=["empty", "text", "header-only", "truncated"],
    )
    def test_not_or_broken_cfb_is_none(self, data):
        assert sniff_cfb_kind(data) is None

    def test_looping_directory_chain_is_none(self):
        assert sniff_cfb_kind(build_cfb(DOC, loop_directory=True)) is None

    def test_path_input(self, tmp_path):
        path = tmp_path / "report.doc"
        path.write_bytes(build_cfb(DOC))
        assert sniff_cfb_kind(path) == "doc"
        assert sniff_cfb_kind(str(path)) == "doc"

    def test_stream_position_restored(self):
        stream = io.BytesIO(build_cfb(PPT))
        stream.seek(37)
        assert sniff_cfb_kind(stream) == "ppt"
        assert stream.tell() == 37


@pytest.mark.unit
class TestCfbRouting:
    """Detection and the Outlook parser name the container's real format."""

    def test_doc_routes_to_doc_parser(self):
        assert registry.detect_format(build_cfb(DOC)) == "doc"

    def test_ppt_routes_to_ppt_parser(self):
        assert registry.detect_format(build_cfb(PPT)) == "ppt"

    def test_xls_without_a_parser_still_reaches_outlook(self):
        """No parser reads .xls yet; the Outlook parser's error names the real format."""
        assert registry.detect_format(build_cfb(["Workbook", "\x05SummaryInformation"])) == "outlook"

    def test_doc_extension_on_another_container_routes_by_streams(self, tmp_path):
        """The root streams decide before the extension: a message named .doc is a message."""
        path = tmp_path / "mail.doc"
        path.write_bytes(build_cfb(MSG, filler_sectors=4))
        assert registry.detect_format(str(path)) == "outlook"

    def test_message_routes_to_outlook(self, tmp_path):
        path = tmp_path / "mail.bin"
        path.write_bytes(build_cfb(MSG, filler_sectors=4))
        assert registry.detect_format(str(path)) == "outlook"

    @pytest.mark.parametrize(
        ("names", "expected"),
        [
            (DOC, r"Word 97-2003 document.*convert it as 'doc'"),
            (PPT, r"PowerPoint 97-2003 presentation.*convert it as 'ppt'"),
            (["Workbook"], r"Excel 97-2003 workbook.*\.xlsx"),
        ],
    )
    def test_outlook_parser_names_legacy_office_files(self, names, expected):
        with pytest.raises(FormatError, match=expected):
            _reject_non_message_cfb(build_cfb(names))

    @pytest.mark.parametrize("names", [MSG, ["Contents"]], ids=["message", "unknown"])
    def test_outlook_parser_lets_other_containers_through(self, names):
        _reject_non_message_cfb(build_cfb(names))
