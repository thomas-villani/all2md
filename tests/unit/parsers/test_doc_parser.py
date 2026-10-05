#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for the Word 97-2003 (.doc) parser.

Two kinds of input: ``.doc`` fixtures that Word itself saved (``basic``,
``footnotes-endnotes-comments`` and ``kitchen-sink``, each from the ``.docx``
beside it), and documents laid out byte by byte by :func:`build_doc`, for the
piece-table and field cases Word does not produce on request and for broken
files.
"""

from __future__ import annotations

import re
import struct
from collections import Counter
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from all2md import to_markdown
from all2md.ast import (
    Comment,
    CommentInline,
    FootnoteDefinition,
    FootnoteReference,
    LineBreak,
    Link,
    Paragraph,
    Text,
)
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, FormatError, MalformedFileError, PasswordProtectedError
from all2md.options.doc import DocOptions
from all2md.options.docx import DocxOptions
from all2md.parsers.doc import DocParser, _hyperlink_target

from ..utils.cfb_builder import build

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "documents"

_COMPRESSED = 0x40000000
_PAIRS = 93
_FIB_SIZE = 154 + 8 * _PAIRS


def build_doc(
    pieces: list[tuple[str, bool]],
    *,
    layout: list[int] | None = None,
    flags: int = 0x0200,
    ident: int = 0xA5EC,
    nfib: int = 0x00C1,
    prc: bytes = b"",
    deleted: tuple[int, int] | None = None,
    streams: dict[str, bytes] | None = None,
) -> bytes:
    """Lay out a Word 97 document whose main text is ``pieces`` in order.

    Each piece is ``(text, compressed)``: compressed pieces are stored as
    cp1252 bytes, the others as UTF-16. ``layout`` gives the order the pieces
    are stored in the WordDocument stream, as a fast save leaves them; the
    piece table still lists them in text order. ``deleted`` marks a CP range
    of the first piece as a tracked deletion.
    """
    word = bytearray(_FIB_SIZE)
    struct.pack_into("<HH", word, 0, ident, nfib)
    struct.pack_into("<H", word, 0x0A, flags)
    struct.pack_into("<H", word, 32, 14)
    struct.pack_into("<H", word, 62, 22)
    text_length = sum(_cp_length(text) for text, _ in pieces)
    struct.pack_into("<i", word, 64 + 4 * 3, text_length)
    struct.pack_into("<H", word, 152, _PAIRS)

    fcs: dict[int, int] = {}
    for index in layout if layout is not None else range(len(pieces)):
        text, compressed = pieces[index]
        if compressed:
            fcs[index] = (len(word) * 2) | _COMPRESSED
            word += text.encode("cp1252")
        else:
            fcs[index] = len(word)
            word += text.encode("utf-16-le")

    cps = [0]
    for text, _ in pieces:
        cps.append(cps[-1] + _cp_length(text))
    plcpcd = struct.pack(f"<{len(cps)}I", *cps)
    plcpcd += b"".join(struct.pack("<HIH", 0, fcs[index], 0) for index in range(len(pieces)))
    clx = prc + b"\x02" + struct.pack("<I", len(plcpcd)) + plcpcd
    table = bytearray(b"\x00" * 16) + clx
    struct.pack_into("<II", word, 154 + 8 * 33, 16, len(clx))

    if deleted is not None:
        # One ChpxFkp page of three runs, the middle one carrying sprmCFRMarkDel,
        # over the first piece (which must be compressed: one byte per CP).
        base = (fcs[0] & ~_COMPRESSED) // 2
        run_fcs = [base, base + deleted[0], base + deleted[1], base + _cp_length(pieces[0][0])]
        word += bytes(-len(word) % 512)
        page = bytearray(512)
        struct.pack_into("<4I", page, 0, *run_fcs)
        page[16:19] = bytes([0, 0x1F0 // 2, 0])
        page[0x1F0 : 0x1F0 + 4] = bytes([3, 0x00, 0x08, 0x01])
        page[511] = 3
        plc = struct.pack("<3I", run_fcs[0], run_fcs[-1], len(word) // 512)
        word += page
        struct.pack_into("<II", word, 154 + 8 * 12, len(table), len(plc))
        table += plc

    table_name = "1Table" if flags & 0x0200 else "0Table"
    return build({"WordDocument": bytes(word), table_name: bytes(table), **(streams or {})}).data


def _cp_length(text: str) -> int:
    """Return a text's length in CPs: UTF-16 code units."""
    return len(text.encode("utf-16-le")) // 2


def _parse(data: bytes, **options) -> list:
    return DocParser(DocOptions(**options)).parse(data).children


def _texts(blocks: list) -> list[str]:
    return ["".join(_inline_text(node) for node in block.content) for block in blocks if isinstance(block, Paragraph)]


def _inline_text(node) -> str:
    if isinstance(node, Text):
        return node.content
    if isinstance(node, LineBreak):
        return "\n"
    return "".join(_inline_text(child) for child in getattr(node, "content", []) or [] if not isinstance(child, str))


def _words(markdown: str) -> Counter:
    """Count alphabetic words, leaving out link targets and the HTML tags of underlines."""
    markdown = re.sub(r"</?\w+>", " ", re.sub(r"\]\([^)]*\)", "]", markdown))
    return Counter(word.lower() for word in re.findall(r"[^\W\d_]+", markdown))


@pytest.mark.unit
class TestWordFixtures:
    """Documents Word saved as .doc read with the same text as their .docx."""

    @pytest.mark.parametrize("name", ["basic", "footnotes-endnotes-comments"])
    def test_same_words_as_the_docx(self, name):
        doc = to_markdown(FIXTURES / f"{name}.doc")
        docx = to_markdown(FIXTURES / f"{name}.docx", parser_options=DocxOptions(attachment_mode="skip"))
        assert _words(doc) == _words(docx)

    def test_notes_pair_with_their_marks(self):
        children = DocParser().parse(FIXTURES / "footnotes-endnotes-comments.doc").children
        definitions = {
            node.identifier: _texts(node.content) for node in children if isinstance(node, FootnoteDefinition)
        }
        references = [
            node.identifier
            for block in children
            if isinstance(block, Paragraph)
            for node in block.content
            if isinstance(node, FootnoteReference)
        ]
        assert references == ["1", "end1", "end2", "2"]
        assert set(definitions) == {"1", "2", "end1", "end2"}
        assert all(text and not text[0].startswith(" ") for text in definitions.values())

    def test_kitchen_sink(self):
        children = DocParser().parse(FIXTURES / "kitchen-sink.doc").children
        texts = _texts(children)
        # The text box is anchored in the first paragraph and follows it, as the DOCX parser places it.
        assert texts[:3] == ["Kitchen Sink Title", "Text inside a text box.", "Intro with Ünïcödé — and “quotes” ✓."]
        links = [
            node
            for block in children
            if isinstance(block, Paragraph)
            for node in block.content
            if isinstance(node, Link)
        ]
        assert [(link.url, _inline_text(link)) for link in links] == [("https://example.com/path?q=1", "link here")]
        assert "Line one\nLine two." in texts
        # The PAGE field shows its result; its instruction never does.
        assert "After the table. Page1 " in texts
        assert not any("PAGE" in text or "HYPERLINK" in text for text in texts)
        # Table cells are paragraphs until table structure is read; the empty cell adds nothing.
        assert texts[texts.index("Table follows:") + 1 : texts.index("Table follows:") + 6] == [
            "r0c0",
            "r0c1",
            "r0c2",
            "r1c0",
            "r1c2",
        ]
        assert "Running header text" not in texts

    def test_headers_and_footers_on_request(self):
        texts = _texts(_parse((FIXTURES / "kitchen-sink.doc").read_bytes(), include_headers_footers=True))
        assert texts[0] == "Running header text"
        assert texts[-1] == "Running footer text"

    @pytest.mark.parametrize(
        ("position", "node_type"), [("footnotes", Comment), ("inline", CommentInline)], ids=["blocks", "inline"]
    )
    def test_comments(self, position, node_type):
        data = (FIXTURES / "kitchen-sink.doc").read_bytes()
        assert not any(isinstance(node, Comment) for node in _parse(data))
        children = _parse(data, include_comments=True, comments_position=position)
        found = [node for node in children if isinstance(node, node_type)]
        found += [
            node
            for block in children
            if isinstance(block, Paragraph)
            for node in block.content
            if isinstance(node, node_type)
        ]
        assert len(found) == 1
        assert found[0].content == "A reviewer comment."
        assert found[0].metadata["comment_type"] == "docx_review"
        assert found[0].metadata["author"]

    def test_notes_can_be_left_out(self):
        children = _parse((FIXTURES / "footnotes-endnotes-comments.doc").read_bytes(), include_footnotes=False)
        identifiers = [node.identifier for node in children if isinstance(node, FootnoteDefinition)]
        assert identifiers == ["end1", "end2"]

    def test_metadata(self):
        metadata = DocParser().parse(FIXTURES / "kitchen-sink.doc").metadata
        assert metadata["title"] == "Kitchen Sink"
        assert metadata["author"] == "all2md"
        assert metadata["description"] == "Legacy Word fixture"
        assert metadata["keywords"] == ["alpha", "beta"]
        assert metadata["creation_date"]

    def test_detected_by_streams(self):
        data = (FIXTURES / "kitchen-sink.doc").read_bytes()
        assert registry.detect_format(data) == "doc"
        assert registry.detect_format(str(FIXTURES / "kitchen-sink.doc")) == "doc"

    def test_rtf_named_doc_is_rtf(self, tmp_path):
        path = tmp_path / "letter.doc"
        path.write_bytes((FIXTURES / "basic-format.rtf").read_bytes())
        assert registry.detect_format(str(path)) == "rtf"


@pytest.mark.unit
class TestPieceTable:
    """The text is the pieces in piece-table order, whatever their storage."""

    def test_compressed_and_unicode_pieces(self):
        data = build_doc([("Plain café ", True), ("Ünïcödé ✓\r", False), ("Last\r", True)])
        assert _texts(_parse(data)) == ["Plain café Ünïcödé ✓", "Last"]

    def test_characters_outside_the_bmp(self):
        """A CP is a UTF-16 code unit, so a supplementary character spans two."""
        data = build_doc([("\U00024b62 and \U0001f600\r", False), ("after\r", True)])
        assert _texts(_parse(data)) == ["\U00024b62 and \U0001f600", "after"]

    def test_fast_saved_pieces_out_of_storage_order(self):
        data = build_doc([("First ", True), ("second ", False), ("third\r", True)], layout=[2, 0, 1])
        assert _texts(_parse(data)) == ["First second third"]

    def test_prc_entries_before_the_piece_table(self):
        prc = b"\x01" + struct.pack("<h", 4) + b"\x00" * 4
        data = build_doc([("Text after formatting changes\r", True)], prc=prc)
        assert _texts(_parse(data)) == ["Text after formatting changes"]

    def test_cp1252_specials_in_compressed_pieces(self):
        data = build_doc([("“quoted” — €5\r", True)])
        assert _texts(_parse(data)) == ["“quoted” — €5"]

    def test_tracked_deletions_are_hidden(self):
        """Like the DOCX parser's default, the document reads with changes accepted."""
        data = build_doc([("Keep gone this\r", True), ("tail\r", False)], deleted=(5, 10))
        assert _texts(_parse(data)) == ["Keep this", "tail"]

    def test_deletion_spanning_a_field_hides_it_whole(self):
        text = "A \x13 PAGE \x149\x15 B\r"
        data = build_doc([(text, True)], deleted=(2, text.index("\x15") + 1))
        assert _texts(_parse(data)) == ["A  B"]

    def test_control_characters(self):
        text = "a\x0bb\x1ec\x1fd\x01e\x08f\tg\x0ch\x07i\r"
        assert _texts(_parse(build_doc([(text, True)]))) == ["a\nb-cdef\tg", "h", "i"]


@pytest.mark.unit
class TestFields:
    """Fields show their result; HYPERLINK results are links."""

    def test_result_kept_instructions_dropped(self):
        data = build_doc([("Page \x13 PAGE \x143\x15 of \x13 NUMPAGES \x149\x15\r", True)])
        assert _texts(_parse(data)) == ["Page 3 of 9"]

    def test_field_without_result_is_dropped(self):
        data = build_doc([('Term\x13 XE "Term" \x15 here\r', True)])
        assert _texts(_parse(data)) == ["Term here"]

    def test_nested_fields(self):
        data = build_doc([("A \x13 IF \x13 PAGE \x141\x15 = 1 \x14yes\x15 B\r", True)])
        assert _texts(_parse(data)) == ["A yes B"]

    def test_hyperlink(self):
        data = build_doc([('Go \x13 HYPERLINK "https://example.org" \x01\x14there\x15 now\r', True)])
        paragraph = _parse(data)[0]
        link = next(node for node in paragraph.content if isinstance(node, Link))
        assert link.url == "https://example.org"
        assert _inline_text(link) == "there"
        assert _texts([paragraph]) == ["Go there now"]

    def test_field_result_spanning_paragraphs(self):
        data = build_doc([("\x13 TOC \x14One\rTwo\r\x15After\r", True)])
        assert _texts(_parse(data)) == ["One", "Two", "After"]

    def test_unbalanced_field_marks_do_not_raise(self):
        data = build_doc([("a\x14b\x15c\x13 open\r", True)])
        assert _texts(_parse(data)) == ["abc"]

    @pytest.mark.parametrize(
        ("instructions", "target"),
        [
            (' HYPERLINK "https://a.example/x" ', "https://a.example/x"),
            (" HYPERLINK https://b.example ", "https://b.example"),
            (' HYPERLINK "https://c.example/" \\l "part" ', "https://c.example/#part"),
            (' HYPERLINK \\l "bookmark" ', None),
            (' HYPERLINK "https://d.example" \\o "tip" \\t "_blank" ', "https://d.example"),
            (' hyperlink "https://e.example"\x01', "https://e.example"),
            (" PAGEREF _Toc1 \\h ", None),
        ],
    )
    def test_hyperlink_target(self, instructions, target):
        assert _hyperlink_target(instructions) == target


@pytest.mark.unit
class TestRejected:
    """Inputs the parser does not read raise a specific, catchable error."""

    def test_encrypted(self):
        with pytest.raises(PasswordProtectedError):
            _parse(build_doc([("secret\r", True)], flags=0x0200 | 0x0100))

    @pytest.mark.parametrize(("ident", "nfib"), [(0xA5DC, 0x0065), (0xA5EC, 0x0068)], ids=["word6", "word95"])
    def test_word_6_and_95(self, ident, nfib):
        with pytest.raises(FormatError, match="Word 6.0 or Word 95"):
            _parse(build_doc([("old\r", True)], ident=ident, nfib=nfib))

    def test_another_container(self):
        data = build({"__properties_version1.0": b"\x00" * 32, "__substg1.0_0037001F": b"s\x00"}).data
        with pytest.raises(FormatError, match="Outlook message"):
            _parse(data)

    def test_not_a_container(self):
        with pytest.raises(FormatError, match="not a Word 97-2003"):
            _parse(b"{\\rtf1 hello}")

    def test_table_stream_chosen_by_flag(self):
        """The FIB flag picks 1Table or 0Table; the one it names must exist."""
        assert _texts(_parse(build_doc([("text\r", True)], flags=0))) == ["text"]
        renamed = build_doc([("text\r", True)])
        broken = renamed.replace("1Table".encode("utf-16-le"), "2Table".encode("utf-16-le"))
        with pytest.raises(MalformedFileError, match="1Table"):
            _parse(broken)

    def test_piece_past_end_of_stream(self):
        data = bytearray(build_doc([("text\r", True)]))
        # Point the piece far past the WordDocument stream.
        position = data.find(struct.pack("<I", (_FIB_SIZE * 2) | _COMPRESSED))
        struct.pack_into("<I", data, position, (900_000 * 2) | _COMPRESSED)
        with pytest.raises(MalformedFileError, match="piece table"):
            _parse(bytes(data))

    def test_fib_count_past_end_of_stream(self):
        """A damaged count in the FIB is a malformed file, not a struct.error (found by the fuzz test)."""
        data = bytearray(build_doc([("text\r", True)]))
        fib = data.find(struct.pack("<H", 0xA5EC))
        struct.pack_into("<H", data, fib + 32, 0xFFFF)  # csw: 64 K words of FibRgW97
        with pytest.raises(MalformedFileError, match="FIB"):
            _parse(bytes(data))

    @settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    @given(st.data())
    def test_mutations_raise_only_all2md_errors(self, draw):
        data = bytearray(build_doc([("Plain ", True), ("Ünïcödé \x13 PAGE \x141\x15\r", False), ("End\r", True)]))
        if draw.draw(st.booleans()):
            data = data[: draw.draw(st.integers(0, len(data)))]
        else:
            for _ in range(draw.draw(st.integers(1, 6))):
                data[draw.draw(st.integers(0, len(data) - 1))] = draw.draw(st.integers(0, 255))
        try:
            _parse(bytes(data))
        except All2MdError:
            pass
