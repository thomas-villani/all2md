#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/ole_properties.py
r"""Read the summary information property set of a CFB (OLE2) container.

Word 97-2003, PowerPoint 97-2003 and Excel 97-2003 files keep their title,
author, keywords and dates in a ``\x05SummaryInformation`` stream, a property
set in the format of [MS-OLEPS]. Only the value types those properties use are
decoded: strings, integers and FILETIME timestamps. Anything else, or anything
malformed, is skipped rather than raised, since metadata is never worth failing
a conversion over.
"""

from __future__ import annotations

import datetime
import struct
from typing import Union

from all2md.utils.metadata import DocumentMetadata

PropertyValue = Union[str, int, datetime.datetime]

SUMMARY_INFORMATION_STREAM = "\x05SummaryInformation"

# Property identifiers of the summary information set ([MS-OLEPS] 2.25.1).
PID_CODEPAGE = 1
PID_TITLE = 2
PID_SUBJECT = 3
PID_AUTHOR = 4
PID_KEYWORDS = 5
PID_COMMENTS = 6
PID_LAST_AUTHOR = 8
PID_REVISION = 9
PID_APPNAME = 18
PID_CREATED = 12
PID_SAVED = 13
PID_PAGE_COUNT = 14
PID_WORD_COUNT = 15

_VT_I2 = 0x0002
_VT_I4 = 0x0003
_VT_LPSTR = 0x001E
_VT_LPWSTR = 0x001F
_VT_FILETIME = 0x0040

_FILETIME_EPOCH = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
_MAX_PROPERTIES = 1024


def read_property_set(data: bytes) -> dict[int, PropertyValue]:
    r"""Return the properties of the first property set in a property set stream.

    Parameters
    ----------
    data : bytes
        The whole stream, such as ``\x05SummaryInformation``.

    Returns
    -------
    dict[int, str | int | datetime.datetime]
        Each decoded property by identifier. Empty when the stream is not a
        property set.

    """
    try:
        return _read_property_set(data)
    except (struct.error, ValueError, OverflowError):
        return {}


def summary_metadata(data: bytes) -> DocumentMetadata:
    r"""Return document metadata read from a ``\x05SummaryInformation`` stream.

    Parameters
    ----------
    data : bytes
        The stream's contents.

    Returns
    -------
    DocumentMetadata
        Title, author, subject, keywords, dates and counts; the application
        name as ``creator``; comments, last author and revision in ``custom``.

    """
    properties = read_property_set(data)

    def text(pid: int) -> str | None:
        value = properties.get(pid)
        return value.strip() or None if isinstance(value, str) else None

    def number(pid: int) -> int | None:
        value = properties.get(pid)
        return value if isinstance(value, int) and value > 0 else None

    def moment(pid: int) -> datetime.datetime | None:
        value = properties.get(pid)
        # Word writes an unset date as zero, which decodes to 1601.
        return value if isinstance(value, datetime.datetime) and value.year > 1601 else None

    metadata = DocumentMetadata(
        title=text(PID_TITLE),
        author=text(PID_AUTHOR),
        subject=text(PID_SUBJECT),
        creator=text(PID_APPNAME),
        creation_date=moment(PID_CREATED),
        modification_date=moment(PID_SAVED),
        page_count=number(PID_PAGE_COUNT),
        word_count=number(PID_WORD_COUNT),
    )
    keywords = text(PID_KEYWORDS)
    if keywords:
        metadata.keywords = [word.strip() for word in keywords.replace(";", ",").split(",") if word.strip()]
    for pid, name in ((PID_COMMENTS, "comments"), (PID_LAST_AUTHOR, "last_modified_by"), (PID_REVISION, "revision")):
        value = text(pid)
        if value:
            metadata.custom[name] = value
    return metadata


def _read_property_set(data: bytes) -> dict[int, PropertyValue]:
    byte_order, _version, _system, _clsid, set_count = struct.unpack_from("<HHI16sI", data, 0)
    if byte_order != 0xFFFE or set_count < 1:
        return {}
    _fmtid, base = struct.unpack_from("<16sI", data, 28)
    _size, count = struct.unpack_from("<II", data, base)

    entries = [struct.unpack_from("<II", data, base + 8 + 8 * n) for n in range(min(count, _MAX_PROPERTIES))]
    raw: dict[int, tuple[int, int]] = {}
    for pid, offset in entries:
        start = base + offset
        raw[pid] = (struct.unpack_from("<H", data, start)[0], start + 4)

    codepage = 1252
    if PID_CODEPAGE in raw and raw[PID_CODEPAGE][0] == _VT_I2:
        codepage = struct.unpack_from("<H", data, raw[PID_CODEPAGE][1])[0]
    encoding = "utf-16-le" if codepage == 1200 else f"cp{codepage}"

    properties: dict[int, PropertyValue] = {}
    for pid, (value_type, position) in raw.items():
        try:
            value = _decode(data, value_type, position, encoding)
        except (struct.error, ValueError, OverflowError):
            continue
        if value is not None:
            properties[pid] = value
    return properties


def _decode(data: bytes, value_type: int, position: int, encoding: str) -> PropertyValue | None:
    if value_type == _VT_I2:
        return int(struct.unpack_from("<h", data, position)[0])
    if value_type == _VT_I4:
        return int(struct.unpack_from("<i", data, position)[0])
    if value_type == _VT_LPSTR:
        length = struct.unpack_from("<I", data, position)[0]
        raw = data[position + 4 : position + 4 + length]
        try:
            return raw.decode(encoding).split("\x00", 1)[0]
        except (LookupError, UnicodeDecodeError):
            return raw.decode("cp1252", errors="replace").split("\x00", 1)[0]
    if value_type == _VT_LPWSTR:
        length = struct.unpack_from("<I", data, position)[0]
        return data[position + 4 : position + 4 + 2 * length].decode("utf-16-le", errors="replace").split("\x00", 1)[0]
    if value_type == _VT_FILETIME:
        ticks = struct.unpack_from("<Q", data, position)[0]
        return _FILETIME_EPOCH + datetime.timedelta(microseconds=ticks // 10)
    return None
