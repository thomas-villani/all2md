#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/doc.py
r"""Word 97-2003 (.doc) to AST converter.

A ``.doc`` is a CFB container ([MS-CFB], read by :mod:`all2md.utils.cfb`)
whose ``WordDocument`` stream opens with the File Information Block (FIB,
[MS-DOC] 2.5). The FIB gives the length of each story in characters (main
text, footnotes, headers, comments, endnotes, text boxes) and the location,
in the ``0Table`` or ``1Table`` stream, of the piece table: the list of runs
of characters, each 8-bit (cp1252) or UTF-16, that make up the text, in
whatever order fast saves left them.

The text is read whole through the piece table and then split into stories.
Within a story, ``\r`` ends a paragraph, ``\x0b`` is a line break, and
``\x13 instructions \x14 result \x15`` is a field, of which only the result
shows; a ``HYPERLINK`` field's result becomes a link. Footnotes, endnotes and
comments are paired with their reference marks through the PLCs the FIB names,
and a text box is placed after the paragraph that anchors it.

Formatting is not read yet: paragraph styles (so headings), tables, lists and
character formatting live in the formatting PLCs, and come back as plain
paragraphs, a table's cells one paragraph each.
"""

from __future__ import annotations

import bisect
import logging
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import (
    Comment,
    CommentInline,
    Document,
    FootnoteDefinition,
    FootnoteReference,
    LineBreak,
    Link,
    Node,
    Paragraph,
    Text,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import FormatError, MalformedFileError, PasswordProtectedError
from all2md.options.doc import DocOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.cfb import CFB_SIGNATURE, CfbReader, describe_cfb_kind, sniff_cfb_kind
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.ole_properties import SUMMARY_INFORMATION_STREAM, summary_metadata

logger = logging.getLogger(__name__)

_WORD_IDENT = 0xA5EC
_WORD6_IDENT = 0xA5DC
_MIN_NFIB = 0x00C0  # Word 97; Word 6 and Word 95 files carry smaller numbers
_FLAG_ENCRYPTED = 0x0100
_FLAG_TABLE_1 = 0x0200
_COMPRESSED = 0x40000000

# Indexes of fc/lcb pairs in FibRgFcLcb97 ([MS-DOC] 2.5.6).
_PLCFFNDREF = 2
_PLCFFNDTXT = 3
_PLCFANDREF = 4
_PLCFANDTXT = 5
_PLCFHDD = 11
_PLCFBTECHPX = 12
_CLX = 33
_GRPXSTATNOWNERS = 36
_PLCSPAMOM = 40
_PLCFENDREF = 46
_PLCFENDTXT = 47
_PLCFTXBXTXT = 56

# The stories in CP order, after the main text ([MS-DOC] 2.3.1).
_STORIES = ("main", "footnotes", "headers", "macros", "comments", "endnotes", "textboxes", "header_textboxes")

_FSPA_SIZE = 26
_FTXBXS_SIZE = 22
_ATRD_SIZE = 30
_FRD_SIZE = 2
_FKP_SIZE = 512
# sprmCFRMarkDel: the run is text deleted with tracked changes ([MS-DOC] 2.6.1).
_SPRM_DELETED = 0x0800
# Operand size by a sprm's spra bits; spra 6 is variable, its first byte the length.
_SPRM_OPERAND_SIZES = {0: 1, 1: 1, 2: 2, 3: 4, 4: 2, 5: 2, 7: 3}
# The first six header stories are the footnote and endnote separators; then
# each section has six: even header, odd header, even footer, odd footer, first
# page header, first page footer.
_SEPARATOR_STORIES = 6
_FOOTER_SLOTS = (2, 3, 5)

_PARAGRAPH_ENDS = frozenset("\r\x07\x0c\x0e")
_LINE_BREAK = "\x0b"
_NON_BREAKING_HYPHEN = "\x1e"

# cp1252 for the 8-bit pieces; the five bytes cp1252 leaves undefined read as Latin-1 ([MS-DOC] 2.4.1).
_CP1252 = {byte: bytes([byte]).decode("cp1252", errors="ignore") or chr(byte) for byte in range(0x80, 0xA0)}
_CP1252_TABLE = str.maketrans({chr(byte): text for byte, text in _CP1252.items()})

_HYPERLINK = re.compile(r"\s*HYPERLINK\b(?P<args>.*)", re.IGNORECASE | re.DOTALL)
_FIELD_ARGUMENT = re.compile(r'"(?P<quoted>[^"]*)"?|(?P<switch>\\[A-Za-z])|(?P<bare>\S+)')
_SWITCHES_WITH_ARGUMENT = frozenset({"\\l", "\\o", "\\t"})


@dataclass
class _Field:
    instructions: list[str] = field(default_factory=list)
    in_result: bool = False
    href: Optional[str] = None


def _hyperlink_target(instructions: str) -> Optional[str]:
    r"""Return the target of a ``HYPERLINK`` field, or None for any other field.

    ``HYPERLINK "url"`` links to the URL and ``HYPERLINK "url" \l "anchor"`` to
    a place in it. A link with only ``\l`` points at a bookmark in this
    document, which Markdown has no target for; like the DOCX parser, it reads
    as plain text.
    """
    match = _HYPERLINK.match(instructions.replace("\x01", ""))
    if not match:
        return None
    url: Optional[str] = None
    anchor: Optional[str] = None
    pending_switch: Optional[str] = None
    for token in _FIELD_ARGUMENT.finditer(match.group("args")):
        switch = token.group("switch")
        if switch:
            pending_switch = switch.lower() if switch.lower() in _SWITCHES_WITH_ARGUMENT else None
            continue
        value = token.group("quoted") if token.group("quoted") is not None else token.group("bare")
        if pending_switch == "\\l":
            anchor = value
        elif pending_switch is None and url is None:
            url = value
        pending_switch = None
    if not url:
        return None
    return f"{url}#{anchor}" if anchor else url


class _WordBinary:
    """The text and story layout of a Word 97-2003 binary document."""

    def __init__(self, reader: CfbReader):
        self.word = reader.read_stream("WordDocument")
        self._parse_fib()
        table_name = "1Table" if self.flags & _FLAG_TABLE_1 else "0Table"
        if not reader.exists(table_name):
            raise MalformedFileError(f"Word document has no {table_name} stream")
        self.table = reader.read_stream(table_name)
        # (FC, first CP, end CP, bytes per character) of each piece.
        self.pieces: list[tuple[int, int, int, int]] = []
        self.text = self._read_text()
        self.deleted = self._deleted_mask()
        self.story_start: dict[str, int] = {}
        position = 0
        for name, length in zip(_STORIES, self.story_lengths, strict=True):
            self.story_start[name] = position
            position += length
        if position > len(self.text) + 1:
            raise MalformedFileError("Word document's stories run past the end of its text")

    def _parse_fib(self) -> None:
        word = self.word
        if len(word) < 0x22:
            raise MalformedFileError("WordDocument stream is too short for a FIB")
        ident, nfib = struct.unpack_from("<HH", word, 0)
        if ident == _WORD6_IDENT or (ident == _WORD_IDENT and nfib < _MIN_NFIB):
            raise FormatError(
                "This is a Word 6.0 or Word 95 document, which all2md cannot read; "
                "save it as .docx (or .doc from Word 97 or later) and convert that instead.",
                format_type="doc",
            )
        if ident != _WORD_IDENT:
            raise MalformedFileError(f"WordDocument stream has an unknown identifier {ident:#06x}")
        self.flags = struct.unpack_from("<H", word, 0x0A)[0]
        if self.flags & _FLAG_ENCRYPTED:
            raise PasswordProtectedError("This Word document is encrypted; remove its password and convert again.")

        # FibBase (32 bytes), then three counted arrays: csw 16-bit words,
        # cslw 32-bit words (the story lengths), cbRgFcLcb fc/lcb pairs.
        csw = struct.unpack_from("<H", word, 32)[0]
        longs_at = 34 + 2 * csw
        cslw = struct.unpack_from("<H", word, longs_at)[0]
        if cslw < 11:
            raise MalformedFileError("Word document's FIB has too few story lengths")
        longs = struct.unpack_from(f"<{cslw}i", word, longs_at + 2)
        if any(length < 0 for length in longs[3:11]):
            raise MalformedFileError("Word document's FIB has a negative story length")
        self.story_lengths = longs[3:11]
        pairs_at = longs_at + 2 + 4 * cslw
        count = struct.unpack_from("<H", word, pairs_at)[0]
        self.pairs = [struct.unpack_from("<II", word, pairs_at + 2 + 8 * n) for n in range(count)]

    def pair(self, index: int) -> tuple[int, int]:
        return self.pairs[index] if index < len(self.pairs) else (0, 0)

    def plc(self, index: int, data_size: int) -> tuple[list[int], list[bytes]]:
        """Read the PLC at fc/lcb pair ``index``: n+1 CPs, then n data items."""
        offset, length = self.pair(index)
        if length < 4:
            return [], []
        if offset + length > len(self.table):
            raise MalformedFileError(f"Word document's PLC {index} lies past the end of the table stream")
        count = (length - 4) // (4 + data_size)
        cps = list(struct.unpack_from(f"<{count + 1}I", self.table, offset))
        data_at = offset + 4 * (count + 1)
        items = [self.table[data_at + n * data_size : data_at + (n + 1) * data_size] for n in range(count)]
        return cps, items

    def _read_text(self) -> str:
        """Concatenate the pieces the piece table lists ([MS-DOC] 2.9.38 Clx)."""
        offset, length = self.pair(_CLX)
        clx = self.table[offset : offset + length]
        if length == 0 or len(clx) < length:
            raise MalformedFileError("Word document has no readable piece table")
        position = 0
        # Prc entries (formatting changes made by fast saves) precede the piece table.
        while position < len(clx) and clx[position] == 0x01:
            position += 3 + struct.unpack_from("<h", clx, position + 1)[0]
        if position + 5 > len(clx) or clx[position] != 0x02:
            raise MalformedFileError("Word document's piece table is missing")
        size = struct.unpack_from("<I", clx, position + 1)[0]
        plc = clx[position + 5 : position + 5 + size]
        if len(plc) < size or size < 16:
            raise MalformedFileError("Word document's piece table is cut short")
        count = (size - 4) // 12
        cps = struct.unpack_from(f"<{count + 1}I", plc)
        parts: list[str] = []
        total = 0
        for index in range(count):
            start, end = cps[index], cps[index + 1]
            if end < start or start != total:
                raise MalformedFileError("Word document's piece table is out of order")
            fc = struct.unpack_from("<I", plc, 4 * (count + 1) + 8 * index + 2)[0]
            chars = end - start
            if fc & _COMPRESSED:
                piece_fc, width = (fc & ~_COMPRESSED) // 2, 1
                raw = self.word[piece_fc : piece_fc + chars]
                text = raw.decode("latin-1").translate(_CP1252_TABLE)
            else:
                piece_fc, width = fc, 2
                raw = self.word[fc : fc + 2 * chars]
                if len(raw) < 2 * chars:
                    raise MalformedFileError("Word document's piece table points past the end of its text")
                text = raw.decode("utf-16-le", errors="surrogatepass")
                if len(text) != chars:
                    # A CP counts UTF-16 code units, so a character outside the BMP is two
                    # CPs: keep its surrogates apart until the text is output.
                    text = "".join(map(chr, struct.unpack(f"<{chars}H", raw)))
            if len(text) < chars:
                raise MalformedFileError("Word document's piece table points past the end of its text")
            parts.append(text)
            self.pieces.append((piece_fc, start, end, width))
            total = end
        return "".join(parts)

    def _deleted_mask(self) -> bytearray:
        """Mark the CPs of text deleted with tracked changes, which Word does not show.

        Character formatting is a PLC over byte offsets (FCs) in the
        WordDocument stream (PlcBteChpx), whose entries name 512-byte pages
        (ChpxFkp) of runs, each with a list of property changes (sprms). A run
        carrying sprmCFRMarkDel is deleted text; its FCs map back to CPs
        through the piece holding them.
        """
        mask = bytearray(len(self.text))
        _, pages = self.plc(_PLCFBTECHPX, 4)
        runs: list[tuple[int, int]] = []
        for page_number in sorted({struct.unpack_from("<I", item)[0] & 0x3FFFFF for item in pages}):
            page = self.word[page_number * _FKP_SIZE : (page_number + 1) * _FKP_SIZE]
            if len(page) < _FKP_SIZE:
                continue
            count = page[_FKP_SIZE - 1]
            if 5 * count + 4 > _FKP_SIZE - 1:
                continue
            fcs = struct.unpack_from(f"<{count + 1}I", page)
            for index in range(count):
                offset = 2 * page[4 * (count + 1) + index]
                if (
                    offset
                    and offset < _FKP_SIZE - 1
                    and _sprm_set(page[offset + 1 : offset + 1 + page[offset]], _SPRM_DELETED)
                ):
                    runs.append((fcs[index], fcs[index + 1]))
        # Pieces in storage order, so each run finds the pieces it overlaps by bisection.
        pieces = sorted(self.pieces)
        piece_fcs = [piece[0] for piece in pieces]
        # Overlapping runs merged, so no piece is visited more than once per run of deleted text.
        merged: list[tuple[int, int]] = []
        for fc_start, fc_end in sorted(runs):
            if merged and fc_start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], fc_end))
            else:
                merged.append((fc_start, fc_end))
        for fc_start, fc_end in merged:
            index = max(bisect.bisect_right(piece_fcs, fc_start) - 1, 0)
            while index < len(pieces) and pieces[index][0] < fc_end:
                piece_fc, cp_start, cp_end, width = pieces[index]
                index += 1
                low = max(fc_start, piece_fc)
                high = min(fc_end, piece_fc + (cp_end - cp_start) * width)
                if low < high:
                    first = cp_start + (low - piece_fc) // width
                    last = cp_start + (high - piece_fc + width - 1) // width
                    mask[first:last] = bytes([1]) * (last - first)
        return mask

    def story(self, name: str) -> tuple[int, int]:
        start = min(self.story_start[name], len(self.text))
        return start, min(start + self.story_lengths[_STORIES.index(name)], len(self.text))


class DocParser(BaseParser):
    r"""Convert Word 97-2003 (.doc) documents to AST representation.

    Parameters
    ----------
    options : DocOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
        >>> parser = DocParser()
        >>> doc = parser.parse("report.doc")  # doctest: +SKIP

    """

    def __init__(self, options: DocOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the .doc parser with options and progress callback."""
        BaseParser._validate_options_type(options, DocOptions, "doc")
        options = options or DocOptions()
        super().__init__(options, progress_callback)
        self.options: DocOptions = options
        self._metadata = DocumentMetadata()

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse a Word 97-2003 document into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The document: a file path, raw bytes or a binary stream.

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        FormatError
            If the input is another kind of CFB container, or a Word 6/95 file.
        PasswordProtectedError
            If the document is encrypted.
        MalformedFileError
            If the container or the document's structure is broken.

        """
        self._emit_progress("started", "Parsing Word 97-2003 document", current=0, total=100)
        data = self._load_bytes_content(input_data)
        if not data.startswith(CFB_SIGNATURE):
            raise FormatError("This file is not a Word 97-2003 binary document.", format_type="doc")
        with CfbReader(data) as reader:
            if not reader.exists("WordDocument"):
                kind = sniff_cfb_kind(data)
                name = describe_cfb_kind(kind)[0] if kind else "OLE2 container"
                raise FormatError(f"This file is a {name}, not a Word 97-2003 document.", format_type="doc")
            binary = _WordBinary(reader)
            self._metadata = (
                summary_metadata(reader.read_stream(SUMMARY_INFORMATION_STREAM))
                if reader.exists(SUMMARY_INFORMATION_STREAM)
                else DocumentMetadata()
            )
        children = _DocumentBuilder(binary, self.options).build()
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
            Title, author, dates and counts, when the document records them.

        """
        return self._metadata


class _DocumentBuilder:
    """Turn the stories of a :class:`_WordBinary` into AST blocks."""

    def __init__(self, binary: _WordBinary, options: DocOptions):
        self.binary = binary
        self.options = options
        self.text = binary.text

    def build(self) -> list[Node]:
        marks: dict[int, Optional[Node]] = {}
        notes: list[FootnoteDefinition] = []
        if self.options.include_footnotes:
            notes += self._notes(_PLCFFNDREF, _PLCFFNDTXT, "footnotes", "", marks)
        if self.options.include_endnotes:
            notes += self._notes(_PLCFENDREF, _PLCFENDTXT, "endnotes", "end", marks)
        comments = self._comments(marks) if self.options.include_comments else []
        anchored, unanchored = self._text_boxes()

        headers, footers = self._headers_footers() if self.options.include_headers_footers else ([], [])
        body = self.blocks(*self.binary.story("main"), marks=marks, anchors=anchored)
        children: list[Node] = [*headers, *body, *unanchored, *footers, *notes]
        if self.options.comments_position == "footnotes":
            children.extend(comments)
        return children

    # -- stories -------------------------------------------------------------

    def _notes(
        self, ref_index: int, text_index: int, story: str, prefix: str, marks: dict[int, Optional[Node]]
    ) -> list[FootnoteDefinition]:
        """Pair each note reference with its text; footnotes and endnotes share this layout."""
        refs, _ = self.binary.plc(ref_index, _FRD_SIZE)
        bounds, _ = self.binary.plc(text_index, 0)
        start, end = self.binary.story(story)
        definitions = []
        for number, cp in enumerate(refs[:-1], start=1):
            if number >= len(bounds):
                break
            identifier = f"{prefix}{number}"
            marks[cp] = FootnoteReference(identifier=identifier)
            note_start = min(start + bounds[number - 1], end)
            note_end = min(start + bounds[number], end)
            content = self.blocks(note_start, note_end, note=True)
            definitions.append(FootnoteDefinition(identifier=identifier, content=content))
        return definitions

    def _comments(self, marks: dict[int, Optional[Node]]) -> list[Node]:
        refs, records = self.binary.plc(_PLCFANDREF, _ATRD_SIZE)
        bounds, _ = self.binary.plc(_PLCFANDTXT, 0)
        owners = self._comment_owners()
        start, end = self.binary.story("comments")
        comments: list[Node] = []
        for number, (cp, record) in enumerate(zip(refs[:-1], records, strict=False), start=1):
            if number >= len(bounds):
                break
            initials_length = min(struct.unpack_from("<H", record, 0)[0], 9)
            initials = record[2 : 2 + 2 * initials_length].decode("utf-16-le", errors="replace")
            owner = struct.unpack_from("<H", record, 20)[0]
            metadata: dict[str, Any] = {
                "comment_type": "docx_review",
                "identifier": str(number),
                "label": str(number),
                "author": owners[owner] if owner < len(owners) else initials,
                "initials": initials,
            }
            blocks = self.blocks(min(start + bounds[number - 1], end), min(start + bounds[number], end), note=True)
            text = "\n".join(_plain_text(block) for block in blocks)
            if self.options.comments_position == "inline":
                marks[cp] = CommentInline(content=text, metadata=metadata)
            else:
                comments.append(Comment(content=text, metadata=metadata))
        return comments

    def _comment_owners(self) -> list[str]:
        """Read GrpXstAtnOwners: the comment authors' names, each a counted UTF-16 string."""
        offset, length = self.binary.pair(_GRPXSTATNOWNERS)
        data = self.binary.table[offset : offset + length]
        owners: list[str] = []
        position = 0
        while position + 2 <= len(data):
            count = struct.unpack_from("<H", data, position)[0]
            owners.append(data[position + 2 : position + 2 + 2 * count].decode("utf-16-le", errors="replace"))
            position += 2 + 2 * count
        return owners

    def _text_boxes(self) -> tuple[dict[int, list[Node]], list[Node]]:
        """Read each text box, keyed by the CP of its anchor in the main text.

        A shape's anchor (PlcSpaMom) names its shape id; a text box story
        (PlcftxbxTxt) names the shape it belongs to. A story whose shape is not
        found still has its text kept, after the body.
        """
        start, end = self.binary.story("textboxes")
        if start == end:
            return {}, []
        anchors, shapes = self.binary.plc(_PLCSPAMOM, _FSPA_SIZE)
        bounds, boxes = self.binary.plc(_PLCFTXBXTXT, _FTXBXS_SIZE)
        anchor_by_shape = {
            struct.unpack_from("<I", shape, 0)[0]: cp for cp, shape in zip(anchors, shapes, strict=False)
        }
        anchored: dict[int, list[Node]] = {}
        unanchored: list[Node] = []
        # The last story entry is a sentinel past the final text box.
        for index, box in enumerate(boxes[:-1]):
            reusable = struct.unpack_from("<H", box, 8)[0]
            if reusable:
                continue
            blocks = self.blocks(min(start + bounds[index], end), min(start + bounds[index + 1], end))
            shape = struct.unpack_from("<i", box, 14)[0]
            cp = anchor_by_shape.get(shape & 0xFFFFFFFF)
            if cp is None:
                unanchored.extend(blocks)
            else:
                anchored.setdefault(cp, []).extend(blocks)
        return anchored, unanchored

    def _headers_footers(self) -> tuple[list[Node], list[Node]]:
        bounds, _ = self.binary.plc(_PLCFHDD, 0)
        start, end = self.binary.story("headers")
        headers: list[Node] = []
        footers: list[Node] = []
        seen: set[str] = set()
        for index in range(_SEPARATOR_STORIES, len(bounds) - 2):
            blocks = self.blocks(min(start + bounds[index], end), min(start + bounds[index + 1], end))
            key = "\n".join(_plain_text(block) for block in blocks).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            slot = (index - _SEPARATOR_STORIES) % 6
            (footers if slot in _FOOTER_SLOTS else headers).extend(blocks)
        return headers, footers

    # -- characters to blocks ----------------------------------------------

    def _resolve_fields(self, start: int, end: int) -> list[tuple[int, str, Optional[str]]]:
        """Return the visible characters of a story range with their CPs and link targets.

        A field's instructions are dropped and its result kept; fields nest,
        and a character inside an outer field's instructions is never shown.
        """
        text = self.text
        deleted = self.binary.deleted
        if "\x13" not in text[start:end]:
            return [(cp, text[cp], None) for cp in range(start, end) if not deleted[cp]]
        visible: list[tuple[int, str, Optional[str]]] = []
        stack: list[_Field] = []
        for cp in range(start, end):
            if deleted[cp]:
                continue
            char = text[cp]
            if char == "\x13":
                stack.append(_Field())
            elif char == "\x14":
                if stack and not stack[-1].in_result:
                    stack[-1].in_result = True
                    stack[-1].href = _hyperlink_target("".join(stack[-1].instructions))
            elif char == "\x15":
                if stack:
                    stack.pop()
            else:
                open_instruction = next((frame for frame in reversed(stack) if not frame.in_result), None)
                if open_instruction is not None:
                    open_instruction.instructions.append(char)
                else:
                    href = next((frame.href for frame in reversed(stack) if frame.href), None)
                    visible.append((cp, char, href))
        return visible

    def blocks(
        self,
        start: int,
        end: int,
        *,
        marks: Optional[dict[int, Optional[Node]]] = None,
        anchors: Optional[dict[int, list[Node]]] = None,
        note: bool = False,
    ) -> list[Node]:
        """Build paragraphs from the characters in ``[start, end)``.

        Parameters
        ----------
        start, end
            The CP range, within one story.
        marks
            Inline nodes (note references, comments) standing in for the
            character at a CP; None drops the character.
        anchors
            Blocks (text boxes) to place after the paragraph holding a CP.
        note
            The range is a note or comment: drop the leading space Word puts
            after the note's own mark.

        """
        marks = marks or {}
        anchors = anchors or {}
        blocks: list[Node] = []
        inlines: list[Node] = []
        pending: list[Node] = []
        buffer: list[str] = []
        href: Optional[str] = None

        def flush() -> None:
            if not buffer:
                return
            content = _join_surrogates("".join(buffer))
            buffer.clear()
            if href is None:
                inlines.append(Text(content=content))
            elif inlines and isinstance(inlines[-1], Link) and inlines[-1].url == href:
                inlines[-1].content.append(Text(content=content))
            else:
                inlines.append(Link(url=href, content=[Text(content=content)]))

        def end_paragraph() -> None:
            flush()
            if any(not isinstance(node, (Text, LineBreak)) or _plain_text(node).strip() for node in inlines):
                while inlines and isinstance(inlines[-1], LineBreak):
                    inlines.pop()
                blocks.append(Paragraph(content=list(inlines)))
            inlines.clear()
            blocks.extend(pending)
            pending.clear()

        for cp, char, link in self._resolve_fields(start, end):
            if cp in marks:
                flush()
                node = marks[cp]
                if node is not None:
                    inlines.append(node)
                continue
            if cp in anchors:
                pending.extend(anchors[cp])
            if link != href:
                flush()
                href = link
            if char in _PARAGRAPH_ENDS:
                end_paragraph()
            elif char == _LINE_BREAK:
                flush()
                inlines.append(LineBreak())
            elif char == _NON_BREAKING_HYPHEN:
                buffer.append("-")
            elif char >= " " or char == "\t":
                buffer.append(char)
        end_paragraph()

        if note and blocks and isinstance(blocks[0], Paragraph):
            first = blocks[0].content
            while first and isinstance(first[0], Text) and not first[0].content.strip():
                first.pop(0)
            if first and isinstance(first[0], Text):
                first[0] = Text(content=first[0].content.lstrip())
        return blocks


def _sprm_set(grpprl: bytes, wanted: int) -> bool:
    """Return whether a list of property changes turns the toggle ``wanted`` on."""
    position = 0
    while position + 2 <= len(grpprl):
        sprm = struct.unpack_from("<H", grpprl, position)[0]
        position += 2
        if position >= len(grpprl):
            return False
        if sprm == wanted:
            # 1 is on; 0x81 is "the opposite of the style", and styles leave these off.
            return grpprl[position] in (0x01, 0x81)
        spra = sprm >> 13
        position += grpprl[position] + 1 if spra == 6 else _SPRM_OPERAND_SIZES[spra]
    return False


_SURROGATE = re.compile("[\ud800-\udfff]")


def _join_surrogates(text: str) -> str:
    """Combine surrogate pairs into characters; a lone surrogate becomes U+FFFD."""
    if not _SURROGATE.search(text):
        return text
    return text.encode("utf-16-le", errors="surrogatepass").decode("utf-16-le", errors="replace")


def _plain_text(node: Node) -> str:
    if isinstance(node, Text):
        return node.content
    if isinstance(node, LineBreak):
        return "\n"
    return "".join(_plain_text(child) for child in getattr(node, "content", None) or [] if isinstance(child, Node))


def _is_word_document(content: bytes) -> bool:
    """Accept a CFB container; which kind it is, the registry asks the root streams."""
    return content.startswith(CFB_SIGNATURE)


CONVERTER_METADATA = ConverterMetadata(
    format_name="doc",
    extensions=[".doc", ".dot"],
    mime_types=["application/msword"],
    magic_bytes=[],
    content_detector=_is_word_document,
    parser_class=DocParser,
    renderer_class=None,
    renders_as_string=False,
    parser_required_packages=[],
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=DocOptions,
    renderer_options_class=None,
    description="Parse Word 97-2003 binary documents (.doc) with the standard library",
    priority=10,
)
