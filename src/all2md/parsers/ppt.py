#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ppt.py
"""PowerPoint 97-2003 (.ppt) to AST converter.

A ``.ppt`` is a CFB container ([MS-CFB], read by :mod:`all2md.utils.cfb`)
whose ``PowerPoint Document`` stream is a sequence of records ([MS-PPT] 2.3):
an 8-byte header (version and instance, type, length) and a body, which for a
container is more records. Saves append to the stream, so the live records are
found from the end: the ``Current User`` stream points at the newest
UserEditAtom, each UserEditAtom points at its persist directory and at the
edit before it, and the directories map persist ids to record offsets, newer
entries hiding older ones.

The DocumentContainer lists the slides in order (SlideListWithText, instance
0), each by persist id. A slide's text lives in the text boxes of its drawing,
in z-order; files from older versions of PowerPoint keep placeholder text in
the slide list instead, and the drawing refers to it by index. A text record
holds the whole box: paragraphs end with a carriage return and a vertical tab
breaks a line. The paragraph runs of the StyleTextPropAtom give each
paragraph's indent level and whether it is bulleted. Speaker notes are slides
of their own, found through the slide's notes id; comments are in the slide's
PowerPoint 2002 tags.

Character formatting, tables (which are groups of text boxes, read in turn),
pictures and charts are not read yet.
"""

from __future__ import annotations

import bisect
import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Iterator, Optional, Union

from all2md.ast import (
    Comment,
    Document,
    Heading,
    LineBreak,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Text,
    ThematicBreak,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import FormatError, MalformedFileError, PasswordProtectedError
from all2md.options.ppt import PptOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.cfb import CFB_SIGNATURE, CfbReader, describe_cfb_kind, sniff_cfb_kind
from all2md.utils.inputs import parse_page_ranges
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.ole_properties import SUMMARY_INFORMATION_STREAM, summary_metadata

logger = logging.getLogger(__name__)

_DOCUMENT_STREAM = "PowerPoint Document"
_CURRENT_USER_STREAM = "Current User"
_HEADER_TOKEN_ENCRYPTED = 0xF3D1C4DF

# Record types ([MS-PPT] 2.13.24).
_RT_DOCUMENT = 0x03E8
_RT_SLIDE = 0x03EE
_RT_SLIDE_ATOM = 0x03EF
_RT_NOTES = 0x03F0
_RT_SLIDE_PERSIST_ATOM = 0x03F3
_RT_EX_OBJ_LIST = 0x0409
_RT_PROG_TAGS = 0x1388
_RT_PROG_BINARY_TAG = 0x138A
_RT_BINARY_TAG_DATA_BLOB = 0x138B
_RT_OUTLINE_TEXT_REF_ATOM = 0x0F9E
_RT_TEXT_HEADER_ATOM = 0x0F9F
_RT_TEXT_CHARS_ATOM = 0x0FA0
_RT_STYLE_TEXT_PROP_ATOM = 0x0FA1
_RT_TEXT_BYTES_ATOM = 0x0FA8
_RT_CSTRING = 0x0FBA
_RT_EX_HYPERLINK_ATOM = 0x0FD3
_RT_EX_HYPERLINK = 0x0FD7
_RT_SLIDE_NUMBER_META_CHAR = 0x0FD8
_RT_TEXT_INTERACTIVE_INFO_ATOM = 0x0FDF
_RT_SLIDE_LIST_WITH_TEXT = 0x0FF0
_RT_INTERACTIVE_INFO = 0x0FF2
_RT_INTERACTIVE_INFO_ATOM = 0x0FF3
_RT_USER_EDIT_ATOM = 0x0FF5
_RT_PERSIST_DIRECTORY_ATOM = 0x1772
_RT_COMMENT10 = 0x2EE0
_RT_CLIENT_TEXTBOX = 0xF00D

# Meta characters: a placeholder character in the text stands for a field.
_META_CHAR_TYPES = frozenset({_RT_SLIDE_NUMBER_META_CHAR, 0x0FF7, 0x0FF8, 0x0FF9, 0x0FFA, 0x1015})

# TextHeaderAtom text types ([MS-PPT] 2.13.33).
_TITLE_TYPES = frozenset({0, 6})
_BULLETED_TYPES = frozenset({1, 7, 8})
_NOTES_TYPE = 2

# SlideListWithText instances.
_SLIDE_LIST = 0
_NOTES_LIST = 2

_PARAGRAPH_END = chr(13)
_LINE_BREAK = chr(11)
_MAX_DEPTH = 32
_MAX_INDENT_LEVEL = 8


@dataclass
class _Record:
    """One record: its type, instance, version and the extent of its body."""

    type: int
    instance: int
    version: int
    start: int
    end: int

    @property
    def is_container(self) -> bool:
        return self.version == 0xF


@dataclass
class _TextBlock:
    """The text of one text box, with what the records around it say about it."""

    text_type: int
    text: str = ""
    paragraphs: list[tuple[int, int, Optional[bool]]] = field(default_factory=list)
    meta_chars: dict[int, int] = field(default_factory=dict)
    links: list[tuple[int, int, int]] = field(default_factory=list)
    outline_ref: Optional[int] = None


def _records(data: bytes, start: int, end: int) -> Iterator[_Record]:
    """Yield the records laid end to end between ``start`` and ``end``.

    A record that runs past its container ends the run, so a damaged shape
    loses only itself and what follows it, not the slide.
    """
    position = start
    while position + 8 <= end:
        record = _record_at(data, position, end)
        if record is None:
            logger.debug("PowerPoint record at %d runs past its container; skipping the rest", position)
            return
        yield record
        position = record.end


def _record_at(data: bytes, position: int, end: int) -> Optional[_Record]:
    """Return the record at ``position``, or None when it does not fit before ``end``."""
    if position < 0 or position + 8 > end:
        return None
    version_instance, record_type, length = struct.unpack_from("<HHI", data, position)
    if position + 8 + length > end:
        return None
    return _Record(record_type, version_instance >> 4, version_instance & 0xF, position + 8, position + 8 + length)


class _PresentationBinary:
    """The live records of a ``PowerPoint Document`` stream."""

    def __init__(self, reader: CfbReader):
        self.data = reader.read_stream(_DOCUMENT_STREAM)
        current_edit = self._current_edit(reader)
        self.persist = self._persist_directory(current_edit)
        self.document = self.container(self._document_ref, _RT_DOCUMENT)
        self.slide_lists = {
            record.instance: record
            for record in _records(self.data, self.document.start, self.document.end)
            if record.type == _RT_SLIDE_LIST_WITH_TEXT
        }
        self.hyperlinks = self._hyperlinks()

    def _current_edit(self, reader: CfbReader) -> int:
        """Return the offset of the newest UserEditAtom."""
        if reader.exists(_CURRENT_USER_STREAM):
            current = reader.read_stream(_CURRENT_USER_STREAM)
            if len(current) >= 20:
                token, offset = struct.unpack_from("<II", current, 12)
                if token == _HEADER_TOKEN_ENCRYPTED:
                    raise PasswordProtectedError("This PowerPoint presentation is encrypted.")
                if self._is_user_edit(offset):
                    return offset
        # A missing or stale pointer: the newest edit is the last one in the stream.
        last = None
        for record in _records(self.data, 0, len(self.data)):
            if record.type == _RT_USER_EDIT_ATOM:
                last = record.start - 8
        if last is None:
            raise MalformedFileError("This PowerPoint presentation has no edit record.")
        return last

    def _is_user_edit(self, offset: int) -> bool:
        record = _record_at(self.data, offset, len(self.data))
        return record is not None and record.type == _RT_USER_EDIT_ATOM and record.end - record.start >= 28

    def _persist_directory(self, edit: int) -> dict[int, int]:
        """Merge the persist directories of the edit chain, newest first."""
        persist: dict[int, int] = {}
        seen: set[int] = set()
        self._document_ref = 0
        newest = True
        while edit not in seen and self._is_user_edit(edit):
            seen.add(edit)
            length = struct.unpack_from("<I", self.data, edit + 4)[0]
            last_edit, directory, document_ref = struct.unpack_from("<III", self.data, edit + 16)
            if newest:
                self._document_ref = document_ref
                if length >= 32 and struct.unpack_from("<I", self.data, edit + 36)[0]:
                    raise PasswordProtectedError("This PowerPoint presentation is encrypted.")
                newest = False
            for persist_id, offset in self._directory_entries(directory):
                persist.setdefault(persist_id, offset)
            if last_edit == 0:
                break
            edit = last_edit
        if not persist:
            raise MalformedFileError("This PowerPoint presentation has no persist directory.")
        return persist

    def _directory_entries(self, offset: int) -> Iterator[tuple[int, int]]:
        record = _record_at(self.data, offset, len(self.data))
        if record is None or record.type != _RT_PERSIST_DIRECTORY_ATOM:
            raise MalformedFileError(f"No PowerPoint persist directory at offset {offset}.")
        position = record.start
        while position + 4 <= record.end:
            word = struct.unpack_from("<I", self.data, position)[0]
            first, count = word & 0xFFFFF, word >> 20
            position += 4
            if position + 4 * count > record.end:
                raise MalformedFileError("A PowerPoint persist directory entry runs past its record.")
            for index, target in enumerate(struct.unpack_from(f"<{count}I", self.data, position)):
                yield first + index, target
            position += 4 * count

    def container(self, persist_id: int, record_type: int) -> _Record:
        """Return the record a persist id points at, which must be of ``record_type``."""
        offset = self.persist.get(persist_id)
        record = None if offset is None else _record_at(self.data, offset, len(self.data))
        if record is None:
            raise MalformedFileError(f"PowerPoint persist id {persist_id} points nowhere.")
        if record.type != record_type:
            raise MalformedFileError(
                f"PowerPoint persist id {persist_id} holds record {record.type:#06x}, not {record_type:#06x}."
            )
        return record

    def _hyperlinks(self) -> dict[int, str]:
        """Map each hyperlink id to its target, from the document's ExObjList."""
        links: dict[int, str] = {}
        for record in _records(self.data, self.document.start, self.document.end):
            if record.type != _RT_EX_OBJ_LIST:
                continue
            for item in _records(self.data, record.start, record.end):
                if item.type != _RT_EX_HYPERLINK:
                    continue
                link_id = None
                target = location = ""
                for part in _records(self.data, item.start, item.end):
                    if part.type == _RT_EX_HYPERLINK_ATOM and part.end - part.start >= 4:
                        link_id = struct.unpack_from("<I", self.data, part.start)[0]
                    elif part.type == _RT_CSTRING and part.instance == 1:
                        target = self.string(part)
                    elif part.type == _RT_CSTRING and part.instance == 3:
                        location = self.string(part)
                if link_id is not None and target:
                    links[link_id] = target + (f"#{location}" if location and "#" not in target else "")
        return links

    def string(self, record: _Record) -> str:
        return self.data[record.start : record.end].decode("utf-16-le", "replace")

    def slide_entries(self, instance: int) -> list[tuple[int, int, list[_TextBlock]]]:
        """Return (persist id, slide id, outline texts) for each slide in a SlideListWithText."""
        slide_list = self.slide_lists.get(instance)
        if slide_list is None:
            return []
        entries: list[tuple[int, int, list[_TextBlock]]] = []
        group: list[_Record] = []
        for record in _records(self.data, slide_list.start, slide_list.end):
            if record.type == _RT_SLIDE_PERSIST_ATOM:
                if entries:
                    entries[-1][2].extend(self.text_blocks(group))
                group = []
                if record.end - record.start >= 16:
                    persist_id, _, _, slide_id = struct.unpack_from("<IIII", self.data, record.start)
                    entries.append((persist_id, slide_id, []))
            else:
                group.append(record)
        if entries:
            entries[-1][2].extend(self.text_blocks(group))
        return entries

    def text_blocks(self, records: list[_Record]) -> list[_TextBlock]:
        """Read the text blocks in a run of sibling records, each opened by a TextHeaderAtom."""
        blocks: list[_TextBlock] = []
        pending_link: Optional[int] = None
        for record in records:
            body = self.data[record.start : record.end]
            if record.type == _RT_TEXT_HEADER_ATOM and len(body) >= 4:
                blocks.append(_TextBlock(struct.unpack_from("<I", body)[0]))
                continue
            if not blocks:
                if record.type == _RT_OUTLINE_TEXT_REF_ATOM and len(body) >= 4:
                    blocks.append(_TextBlock(-1, outline_ref=struct.unpack_from("<I", body)[0]))
                continue
            block = blocks[-1]
            if record.type == _RT_TEXT_CHARS_ATOM:
                block.text = body.decode("utf-16-le", "replace")
            elif record.type == _RT_TEXT_BYTES_ATOM:
                block.text = body.decode("latin-1")
            elif record.type == _RT_STYLE_TEXT_PROP_ATOM:
                block.paragraphs = _paragraph_runs(body, len(block.text) + 1)
            elif record.type == _RT_OUTLINE_TEXT_REF_ATOM and len(body) >= 4:
                block.outline_ref = struct.unpack_from("<I", body)[0]
            elif record.type in _META_CHAR_TYPES and len(body) >= 4:
                block.meta_chars[struct.unpack_from("<I", body)[0]] = record.type
            elif record.type == _RT_INTERACTIVE_INFO and record.instance == 0:
                pending_link = self._interactive_link(record)
            elif record.type == _RT_TEXT_INTERACTIVE_INFO_ATOM and len(body) >= 8:
                if pending_link is not None:
                    start, end = struct.unpack_from("<II", body)
                    block.links.append((start, end, pending_link))
                pending_link = None
        return blocks

    def _interactive_link(self, record: _Record) -> Optional[int]:
        for part in _records(self.data, record.start, record.end):
            if part.type == _RT_INTERACTIVE_INFO_ATOM and part.end - part.start >= 8:
                return int(struct.unpack_from("<I", self.data, part.start + 4)[0])
        return None

    def drawing_blocks(self, container: _Record) -> list[_TextBlock]:
        """Return the text blocks of a slide's or notes page's drawing, in z-order."""
        blocks: list[_TextBlock] = []

        def walk(start: int, end: int, depth: int) -> None:
            for record in _records(self.data, start, end):
                if record.type == _RT_CLIENT_TEXTBOX:
                    blocks.extend(self.text_blocks(list(_records(self.data, record.start, record.end))))
                elif record.is_container and depth < _MAX_DEPTH and record.type != _RT_PROG_TAGS:
                    walk(record.start, record.end, depth + 1)

        walk(container.start, container.end, 0)
        return blocks

    def comments(self, container: _Record) -> list[tuple[str, str, str]]:
        """Return (author, initials, text) for each comment in a slide's PowerPoint 2002 tags."""
        found: list[tuple[str, str, str]] = []
        for tags in _records(self.data, container.start, container.end):
            if tags.type != _RT_PROG_TAGS:
                continue
            for tag in _records(self.data, tags.start, tags.end):
                if tag.type != _RT_PROG_BINARY_TAG:
                    continue
                for blob in _records(self.data, tag.start, tag.end):
                    if blob.type != _RT_BINARY_TAG_DATA_BLOB:
                        continue
                    for item in _records(self.data, blob.start, blob.end):
                        if item.type == _RT_COMMENT10:
                            strings = {
                                part.instance: self.string(part)
                                for part in _records(self.data, item.start, item.end)
                                if part.type == _RT_CSTRING
                            }
                            found.append((strings.get(0, ""), strings.get(2, ""), strings.get(1, "")))
        return found

    def slide_atom_notes_id(self, slide: _Record) -> int:
        """Return the notes id a slide's SlideAtom names, or 0 when it has no notes."""
        for record in _records(self.data, slide.start, slide.end):
            if record.type == _RT_SLIDE_ATOM and record.end - record.start >= 20:
                return int(struct.unpack_from("<I", self.data, record.start + 16)[0])
        return 0


def _paragraph_runs(body: bytes, length: int) -> list[tuple[int, int, Optional[bool]]]:
    """Return (end offset, indent level, bulleted or None when inherited) per paragraph run.

    The paragraph runs of a StyleTextPropAtom ([MS-PPT] 2.9.44) each cover a
    number of characters, one paragraph or several alike, and carry a
    TextPFException whose mask says which properties follow. Only the bullet
    flag and the indent level are kept; a malformed run ends the list, leaving
    the rest of the paragraphs at their defaults.
    """
    runs: list[tuple[int, int, Optional[bool]]] = []
    position = covered = 0
    while covered < length and position + 10 <= len(body):
        count, level, masks = struct.unpack_from("<IHI", body, position)
        position += 10
        bulleted: Optional[bool] = None
        if masks & 0x000F:
            if position + 2 > len(body):
                break
            flags = struct.unpack_from("<H", body, position)[0]
            if masks & 0x0001:
                bulleted = bool(flags & 0x0001)
            position += 2
        size = _pf_exception_size(body, position, masks)
        covered += max(count, 1)
        runs.append((covered, min(level, _MAX_INDENT_LEVEL), bulleted))
        if size is None:
            break
        position += size
    return runs


def _paragraph_format(block: _TextBlock, offset: int) -> tuple[int, Optional[bool]]:
    """Return the indent level and bullet flag of the paragraph starting at ``offset``."""
    index = bisect.bisect_right([end for end, _, _ in block.paragraphs], offset)
    if index < len(block.paragraphs):
        return block.paragraphs[index][1], block.paragraphs[index][2]
    return 0, None


def _pf_exception_size(body: bytes, position: int, masks: int) -> Optional[int]:
    """Return the size of a TextPFException's fields after its bullet flags, or None if cut off."""
    size = 0
    for bit, width in (
        (0x0080, 2),  # bulletChar
        (0x0010, 2),  # bulletFontRef
        (0x0040, 2),  # bulletSize
        (0x0020, 4),  # bulletColor
        (0x0800, 2),  # textAlignment
        (0x1000, 2),  # lineSpacing
        (0x2000, 2),  # spaceBefore
        (0x4000, 2),  # spaceAfter
        (0x0100, 2),  # leftMargin
        (0x0400, 2),  # indent
        (0x8000, 2),  # defaultTabSize
    ):
        if masks & bit:
            size += width
    if masks & 0x100000:  # tabStops: a count, then 4 bytes per stop
        if position + size + 2 > len(body):
            return None
        size += 2 + 4 * struct.unpack_from("<H", body, position + size)[0]
    if masks & 0x10000:  # fontAlign
        size += 2
    if masks & 0xE0000:  # wrapFlags
        size += 2
    if masks & 0x200000:  # textDirection
        size += 2
    return size if position + size <= len(body) else None


class PptParser(BaseParser):
    """Convert PowerPoint 97-2003 (.ppt) presentations to AST representation.

    Parameters
    ----------
    options : PptOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
        >>> parser = PptParser()
        >>> doc = parser.parse("deck.ppt")  # doctest: +SKIP

    """

    def __init__(self, options: PptOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the .ppt parser with options and progress callback."""
        BaseParser._validate_options_type(options, PptOptions, "ppt")
        options = options or PptOptions()
        super().__init__(options, progress_callback)
        self.options: PptOptions = options
        self._metadata = DocumentMetadata()

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse a PowerPoint 97-2003 presentation into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The presentation: a file path, raw bytes or a binary stream.

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        FormatError
            If the input is another kind of CFB container.
        PasswordProtectedError
            If the presentation is encrypted.
        MalformedFileError
            If the container or the presentation's structure is broken.

        """
        self._emit_progress("started", "Parsing PowerPoint 97-2003 presentation", current=0, total=100)
        data = self._load_bytes_content(input_data)
        if not data.startswith(CFB_SIGNATURE):
            raise FormatError("This file is not a PowerPoint 97-2003 presentation.", format_type="ppt")
        with CfbReader(data) as reader:
            if not reader.exists(_DOCUMENT_STREAM):
                kind = sniff_cfb_kind(data)
                name = describe_cfb_kind(kind)[0] if kind else "OLE2 container"
                raise FormatError(f"This file is a {name}, not a PowerPoint 97-2003 presentation.", format_type="ppt")
            binary = _PresentationBinary(reader)
            self._metadata = (
                summary_metadata(reader.read_stream(SUMMARY_INFORMATION_STREAM))
                if reader.exists(SUMMARY_INFORMATION_STREAM)
                else DocumentMetadata()
            )
        builder = _SlideBuilder(binary, self.options)
        children = builder.build()
        self._metadata.custom["slide_count"] = builder.slide_count
        self._emit_progress("finished", "Parsing complete", current=100, total=100)
        return Document(children=children, metadata=self._metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Return the metadata read from the summary information stream.

        Parameters
        ----------
        document : Any
            Unused; the metadata is read while parsing.

        Returns
        -------
        DocumentMetadata
            Title, author, dates and the slide count.

        """
        return self._metadata


class _SlideBuilder:
    """Turn the slides of a :class:`_PresentationBinary` into AST blocks."""

    def __init__(self, binary: _PresentationBinary, options: PptOptions):
        self.binary = binary
        self.options = options
        self.slides = binary.slide_entries(_SLIDE_LIST)
        self.slide_count = len(self.slides)
        self.notes = {
            slide_id: (persist_id, texts) for persist_id, slide_id, texts in binary.slide_entries(_NOTES_LIST)
        }

    def build(self) -> list[Node]:
        indexes = (
            parse_page_ranges(self.options.slides, self.slide_count) if self.options.slides else range(self.slide_count)
        )
        children: list[Node] = []
        for index in indexes:
            persist_id, _, outline = self.slides[index]
            try:
                slide = self.binary.container(persist_id, _RT_SLIDE)
            except MalformedFileError as error:
                logger.warning("Skipping slide %d: %s", index + 1, error)
                continue
            nodes = self._slide(slide, outline, index + 1)
            if nodes:
                children.extend(nodes)
                children.append(ThematicBreak())
        return children

    def _slide(self, slide: _Record, outline: list[_TextBlock], number: int) -> list[Node]:
        blocks = _resolve_outline(self.binary.drawing_blocks(slide), outline)
        title: list[Node] = []
        body: list[Node] = []
        for block in blocks:
            if _only_fields(block):
                continue
            if block.text_type in _TITLE_TYPES and not title:
                text = _plain_text(self._inlines(block, block.text, 0, number)).strip()
                if text:
                    if self.options.include_titles_as_h2:
                        if self.options.include_slide_numbers:
                            text = f"Slide {number}: {text}"
                        title.append(Heading(level=2, content=[Text(content=text)]))
                    else:
                        title.append(Paragraph(content=[Text(content=text)]))
                    continue
            body.extend(self._block_nodes(block, number))
        nodes = title + body
        if self.options.include_notes and self.options.comment_mode != "ignore":
            nodes.extend(self._notes(slide, number))
        for author, initials, text in self.binary.comments(slide):
            metadata: dict[str, Any] = {"comment_type": "ppt_comment", "slide_number": number}
            if author:
                metadata["author"] = author
            if initials:
                metadata["initials"] = initials
            nodes.append(Comment(content=text.strip(), metadata=metadata))
        return nodes

    def _notes(self, slide: _Record, number: int) -> list[Node]:
        notes_id = self.binary.slide_atom_notes_id(slide)
        if not notes_id or notes_id not in self.notes:
            return []
        persist_id, outline = self.notes[notes_id]
        try:
            container = self.binary.container(persist_id, _RT_NOTES)
        except MalformedFileError as error:
            logger.warning("Skipping the notes of slide %d: %s", number, error)
            return []
        blocks = [
            block
            for block in _resolve_outline(self.binary.drawing_blocks(container), outline)
            if block.text_type == _NOTES_TYPE
        ]
        if self.options.comment_mode == "comment":
            text = "\n".join(
                _plain_text(self._inlines(block, text, start, number)).strip()
                for block in blocks
                for start, text in _paragraphs(block)
            ).strip()
            if not text:
                return []
            return [Comment(content=text, metadata={"comment_type": "ppt_speaker_notes", "slide_number": number})]
        nodes = [node for block in blocks for node in self._block_nodes(block, number)]
        if not nodes:
            return []
        return [Heading(level=3, content=[Text(content="Speaker Notes")]), *nodes]

    def _block_nodes(self, block: _TextBlock, number: int) -> list[Node]:
        """Return a text block's paragraphs, the bulleted ones as nested lists."""
        nodes: list[Node] = []
        stack: list[tuple[int, List]] = []
        for start, text in _paragraphs(block):
            level, bulleted = _paragraph_format(block, start)
            if bulleted is None:
                bulleted = block.text_type in _BULLETED_TYPES
            content = self._inlines(block, text.rstrip(), start, number)
            if not _plain_text(content).strip():
                continue
            paragraph = Paragraph(content=content)
            if not bulleted:
                stack.clear()
                nodes.append(paragraph)
                continue
            while stack and stack[-1][0] > level:
                stack.pop()
            if stack and stack[-1][0] == level:
                stack[-1][1].items.append(ListItem(children=[paragraph]))
                continue
            new_list = List(ordered=False, items=[ListItem(children=[paragraph])], tight=True)
            if stack and stack[-1][1].items:
                stack[-1][1].items[-1].children.append(new_list)
            else:
                nodes.append(new_list)
            stack.append((level, new_list))
        return nodes

    def _inlines(self, block: _TextBlock, text: str, start: int, number: int) -> list[Node]:
        """Return a paragraph's text as inline nodes: fields filled, line breaks and links made."""
        pieces: list[tuple[str, Optional[str]]] = []
        for position, char in enumerate(text, start):
            meta = block.meta_chars.get(position)
            if meta is not None:
                char = str(number) if meta == _RT_SLIDE_NUMBER_META_CHAR else ""
            target = None
            for link_start, link_end, link_id in block.links:
                if link_start <= position < link_end:
                    target = self.binary.hyperlinks.get(link_id)
                    break
            if pieces and pieces[-1][1] == target and char != _LINE_BREAK and not pieces[-1][0].endswith(_LINE_BREAK):
                pieces[-1] = (pieces[-1][0] + char, target)
            else:
                pieces.append((char, target))
        inlines: list[Node] = []
        for chunk, target in pieces:
            if chunk == _LINE_BREAK:
                inlines.append(LineBreak())
                continue
            chunk = "".join(ch for ch in chunk if ch >= " " or ch == "\t")
            if not chunk:
                continue
            node: Node = Text(content=chunk)
            if target:
                if inlines and isinstance(inlines[-1], Link) and inlines[-1].url == target:
                    inlines[-1].content.append(node)
                    continue
                node = Link(url=target, content=[node])
            inlines.append(node)
        return inlines


def _only_fields(block: _TextBlock) -> bool:
    """Whether a text block holds fields and nothing else, as slide number and date placeholders do."""
    rest = "".join(char for position, char in enumerate(block.text) if position not in block.meta_chars)
    return bool(block.meta_chars) and not rest.strip()


def _paragraphs(block: _TextBlock) -> Iterator[tuple[int, str]]:
    """Yield (offset, text) for each paragraph of a text block."""
    offset = 0
    for text in block.text.split(_PARAGRAPH_END):
        yield offset, text
        offset += len(text) + 1


def _resolve_outline(blocks: list[_TextBlock], outline: list[_TextBlock]) -> list[_TextBlock]:
    """Replace outline references with the slide list's text; keep any text no shape refers to."""
    resolved: list[_TextBlock] = []
    used: set[int] = set()
    for block in blocks:
        if block.outline_ref is not None and not block.text:
            if 0 <= block.outline_ref < len(outline):
                resolved.append(outline[block.outline_ref])
                used.add(block.outline_ref)
            continue
        resolved.append(block)
    resolved.extend(block for index, block in enumerate(outline) if index not in used)
    return resolved


def _plain_text(nodes: list[Node]) -> str:
    parts: list[str] = []
    for node in nodes:
        if isinstance(node, Text):
            parts.append(node.content)
        elif isinstance(node, LineBreak):
            parts.append(" ")
        elif isinstance(node, Link):
            parts.append(_plain_text(node.content))
    return "".join(parts)


def _is_powerpoint_presentation(content: bytes) -> bool:
    """Accept a CFB container; which kind it is, the registry asks the root streams."""
    return content.startswith(CFB_SIGNATURE)


CONVERTER_METADATA = ConverterMetadata(
    format_name="ppt",
    extensions=[".ppt", ".pps", ".pot"],
    mime_types=["application/vnd.ms-powerpoint"],
    magic_bytes=[],
    content_detector=_is_powerpoint_presentation,
    parser_class=PptParser,
    renderer_class=None,
    renders_as_string=False,
    parser_required_packages=[],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=PptOptions,
    renderer_options_class=None,
    description="Parse PowerPoint 97-2003 presentations (.ppt) with the standard library",
    priority=10,
)
