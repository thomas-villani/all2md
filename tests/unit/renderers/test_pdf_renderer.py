#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_pdf_renderer.py
"""Unit tests for PdfRenderer.

Tests cover:
- Rendering all node types to PDF
- Page layout and formatting
- Font and style options
- Table rendering
- Edge cases and nested structures

Note: These tests require reportlab to be installed.
PDF content verification is limited as we mainly test structure, not exact layout.

"""

from io import BytesIO

import pytest

try:
    import PyPDF2

    PDF_VERIFICATION_AVAILABLE = True
except ImportError:
    PDF_VERIFICATION_AVAILABLE = False

try:
    from reportlab.platypus import SimpleDocTemplate  # noqa: F401

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.options import PdfRendererOptions

if REPORTLAB_AVAILABLE:
    from all2md.renderers.pdf import PdfRenderer

pytestmark = pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")


def get_pdf_text(pdf_path):
    """Extract text from PDF file for verification."""
    if not PDF_VERIFICATION_AVAILABLE:
        return ""
    try:
        with open(pdf_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
            return text
    except Exception:
        return ""


@pytest.mark.unit
@pytest.mark.pdf
class TestBasicRendering:
    """Tests for basic PDF rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = PdfRenderer()
        output_file = tmp_path / "empty.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_render_text_only(self, tmp_path):
        """Test rendering plain text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "text.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Hello world" in text

    def test_render_multiple_paragraphs(self, tmp_path):
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "paras.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "First paragraph" in text
            assert "Second paragraph" in text

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = PdfRenderer()
        output = BytesIO()
        renderer.render(doc, output)

        assert output.getvalue()
        assert len(output.getvalue()) > 0


@pytest.mark.unit
@pytest.mark.pdf
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1(self, tmp_path):
        """Test rendering h1."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "h1.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Title" in text

    def test_heading_level_2(self, tmp_path):
        """Test rendering h2."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "h2.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Subtitle" in text

    def test_multiple_headings(self, tmp_path):
        """Test multiple heading levels."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Chapter")]),
                Heading(level=2, content=[Text(content="Section")]),
                Heading(level=3, content=[Text(content="Subsection")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "headings.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_strong(self, tmp_path):
        """Test bold text rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = PdfRenderer()
        output_file = tmp_path / "bold.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "bold" in text

    def test_emphasis(self, tmp_path):
        """Test italic text rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = PdfRenderer()
        output_file = tmp_path / "italic.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_code(self, tmp_path):
        """Test inline code rendering."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "code.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_strikethrough(self, tmp_path):
        """Test strikethrough rendering."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = PdfRenderer()
        output_file = tmp_path / "strike.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_nested_formatting(self, tmp_path):
        """Test nested inline formatting."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "nested.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestListRendering:
    """Tests for list rendering."""

    def test_unordered_list(self, tmp_path):
        """Test unordered list rendering."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "ul.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Item 1" in text
            assert "Item 2" in text

    def test_ordered_list(self, tmp_path):
        """Test ordered list rendering."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "ol.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestTableRendering:
    """Tests for table rendering."""

    def test_simple_table(self, tmp_path):
        """Test basic table rendering."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]
                        )
                    ],
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "table.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Name" in text
            assert "Alice" in text

    def test_table_without_header(self, tmp_path):
        """Test table without header row."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])])
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "table_no_header.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_multi_row_table(self, tmp_path):
        """Test table with multiple rows."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content=f"Row {i}")])]) for i in range(5)],
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "table_multi_row.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestBlockElements:
    """Tests for block-level elements."""

    def test_code_block(self, tmp_path):
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('world')", language="python")])
        renderer = PdfRenderer()
        output_file = tmp_path / "codeblock.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "def hello" in text

    def test_blockquote(self, tmp_path):
        """Test blockquote rendering."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])])])
        renderer = PdfRenderer()
        output_file = tmp_path / "blockquote.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_thematic_break(self, tmp_path):
        """Test horizontal rule rendering."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "hr.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestPageLayoutOptions:
    """Tests for page layout options."""

    def test_letter_page_size(self, tmp_path):
        """Test letter page size."""
        doc = Document(children=[Paragraph(content=[Text(content="Letter size")])])
        options = PdfRendererOptions(page_size="letter")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "letter.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_a4_page_size(self, tmp_path):
        """Test A4 page size."""
        doc = Document(children=[Paragraph(content=[Text(content="A4 size")])])
        options = PdfRendererOptions(page_size="a4")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "a4.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_legal_page_size(self, tmp_path):
        """Test legal page size."""
        doc = Document(children=[Paragraph(content=[Text(content="Legal size")])])
        options = PdfRendererOptions(page_size="legal")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "legal.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_custom_margins(self, tmp_path):
        """Test custom margin settings."""
        doc = Document(children=[Paragraph(content=[Text(content="Custom margins")])])
        options = PdfRendererOptions(margin_top=100, margin_bottom=100, margin_left=50, margin_right=50)
        renderer = PdfRenderer(options)
        output_file = tmp_path / "margins.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestFontOptions:
    """Tests for font options."""

    def test_custom_font(self, tmp_path):
        """Test custom font settings."""
        doc = Document(children=[Paragraph(content=[Text(content="Custom font")])])
        options = PdfRendererOptions(font_name="Times-Roman", font_size=14)
        renderer = PdfRenderer(options)
        output_file = tmp_path / "custom_font.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_code_font_option(self, tmp_path):
        """Test code font option."""
        doc = Document(children=[CodeBlock(content="code here")])
        options = PdfRendererOptions(code_font="Courier")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "code_font.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_line_spacing(self, tmp_path):
        """Test line spacing option."""
        doc = Document(children=[Paragraph(content=[Text(content="Line spacing test")])])
        options = PdfRendererOptions(line_spacing=1.5)
        renderer = PdfRenderer(options)
        output_file = tmp_path / "line_spacing.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestDocumentMetadata:
    """Tests for document metadata."""

    def test_title_from_metadata(self, tmp_path):
        """Test document title from metadata."""
        doc = Document(metadata={"title": "Test Document"}, children=[Paragraph(content=[Text(content="Content")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "metadata.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Test Document" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestDefinitionLists:
    """Tests for definition list rendering."""

    def test_definition_list(self, tmp_path):
        """Test definition list rendering."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term")]),
                            [DefinitionDescription(content=[Text(content="Description")])],
                        )
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "deflist.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Term" in text
            assert "Description" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestMathRendering:
    """Tests for math rendering."""

    def test_inline_math(self, tmp_path):
        """Test inline math rendering."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "math_inline.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_block_math(self, tmp_path):
        """Test block math rendering."""
        doc = Document(children=[MathBlock(content="E = mc^2", notation="latex")])
        renderer = PdfRenderer()
        output_file = tmp_path / "math_block.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_reference(self, tmp_path):
        """Test footnote reference rendering."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Text(content="Footnote text")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "footnote.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Text" in text
            # Footnote text should appear at bottom
            assert "Footnote text" in text

    def test_multiple_references_same_footnote(self, tmp_path):
        """Test multiple references to the same footnote use the same number."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="First reference"),
                        FootnoteReference(identifier="note1"),
                        Text(content=" and second reference"),
                        FootnoteReference(identifier="note1"),
                    ]
                ),
                FootnoteDefinition(identifier="note1", content=[Text(content="Shared footnote")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "multiple_refs.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "First reference" in text
            assert "second reference" in text
            assert "Shared footnote" in text

    def test_footnote_with_paragraph(self, tmp_path):
        """Test footnote with proper Paragraph content."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Main text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote paragraph")])]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "footnote_paragraph.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Main text" in text
            assert "Footnote paragraph" in text

    def test_footnote_with_multiple_paragraphs(self, tmp_path):
        """Test footnote with multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Reference"), FootnoteReference(identifier="note")]),
                FootnoteDefinition(
                    identifier="note",
                    content=[
                        Paragraph(content=[Text(content="First paragraph.")]),
                        Paragraph(content=[Text(content="Second paragraph.")]),
                    ],
                ),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "footnote_multi_para.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Reference" in text
            assert "First paragraph" in text
            assert "Second paragraph" in text

    def test_footnote_with_list(self, tmp_path):
        """Test footnote containing a list."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="See note"), FootnoteReference(identifier="list")]),
                FootnoteDefinition(
                    identifier="list",
                    content=[
                        List(
                            ordered=False,
                            items=[
                                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                            ],
                        )
                    ],
                ),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "footnote_list.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "See note" in text
            assert "Item 1" in text
            assert "Item 2" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestComplexDocuments:
    """Tests for complex document structures."""

    def test_mixed_content(self, tmp_path):
        """Test document with mixed content types."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Introduction paragraph")]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Point 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Point 2")])]),
                    ],
                ),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Data")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Value")])])],
                ),
                CodeBlock(content="code example"),
                Paragraph(content=[Text(content="Conclusion")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "mixed.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_deeply_nested_content(self, tmp_path):
        """Test deeply nested structures."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(
                            content=[
                                Text(content="Quote with "),
                                Strong(content=[Emphasis(content=[Text(content="nested formatting")])]),
                            ]
                        )
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "nested.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_paragraph(self, tmp_path):
        """Test empty paragraph handling."""
        doc = Document(children=[Paragraph(content=[])])
        renderer = PdfRenderer()
        output_file = tmp_path / "empty_para.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_very_long_text(self, tmp_path):
        """Test handling of very long text."""
        long_text = "Lorem ipsum " * 1000
        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])
        renderer = PdfRenderer()
        output_file = tmp_path / "long_text.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_special_characters(self, tmp_path):
        """Test handling of special characters."""
        doc = Document(children=[Paragraph(content=[Text(content="Special: &<>\"'©®™")])])
        renderer = PdfRenderer()
        output_file = tmp_path / "special.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestLinks:
    """Tests for link rendering."""

    def test_simple_link(self, tmp_path):
        """Test basic link rendering."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Example")])])]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "link.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestRenderToBytes:
    """Tests for render_to_bytes method."""

    def test_render_to_bytes_simple(self):
        """Test render_to_bytes returns valid PDF bytes."""
        doc = Document(children=[Paragraph(content=[Text(content="Byte content")])])
        renderer = PdfRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert len(result) > 0
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"


@pytest.mark.unit
@pytest.mark.pdf
class TestTableSpanning:
    """Tests for table colspan and rowspan."""

    def test_table_with_colspan(self, tmp_path):
        """Test table with column spanning."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Merged Header")], colspan=2),
                            TableCell(content=[Text(content="Single")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                                TableCell(content=[Text(content="C")]),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "table_colspan.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Merged Header" in text
            assert "Single" in text

    def test_table_with_rowspan(self, tmp_path):
        """Test table with row spanning."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Merged")], rowspan=2),
                                TableCell(content=[Text(content="Row 1")]),
                            ]
                        ),
                        TableRow(cells=[TableCell(content=[Text(content="Row 2")])]),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "table_rowspan.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestCommentModes:
    """Tests for comment rendering modes."""

    def test_comment_mode_ignore(self, tmp_path):
        """Test that comments are ignored when comment_mode is 'ignore'."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Visible text")]),
                Comment(content="This should be ignored", metadata={"author": "Test"}),
            ]
        )
        options = PdfRendererOptions(comment_mode="ignore")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "comment_ignore.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Visible text" in text
            # Comment should not appear
            assert "This should be ignored" not in text

    def test_comment_mode_visible(self, tmp_path):
        """Test that comments are visible when comment_mode is 'visible'."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(
                    content="Visible comment",
                    metadata={"author": "Author", "date": "2025-01-20"},
                )
            ]
        )
        options = PdfRendererOptions(comment_mode="visible")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "comment_visible.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Visible comment" in text

    def test_comment_with_label(self, tmp_path):
        """Test comment with label metadata."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(
                    content="Labeled comment",
                    metadata={"author": "Author", "label": "1", "date": "2025-01-20"},
                )
            ]
        )
        options = PdfRendererOptions(comment_mode="visible")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "comment_label.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestInlineComments:
    """Tests for inline comment rendering."""

    def test_inline_comment_ignore(self, tmp_path):
        """Test inline comment is ignored when comment_mode is 'ignore'."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Before "),
                        CommentInline(content="ignored", metadata={}),
                        Text(content=" after"),
                    ]
                )
            ]
        )
        options = PdfRendererOptions(comment_mode="ignore")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "inline_ignore.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_inline_comment_visible(self, tmp_path):
        """Test inline comment is visible when comment_mode is 'visible'."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(
                            content="visible inline",
                            metadata={"author": "Test Author", "label": "1"},
                        ),
                    ]
                )
            ]
        )
        options = PdfRendererOptions(comment_mode="visible")
        renderer = PdfRenderer(options)
        output_file = tmp_path / "inline_visible.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestInlineFormattingAdvanced:
    """Additional tests for inline formatting."""

    def test_underline(self, tmp_path):
        """Test underline rendering."""
        from all2md.ast import Underline

        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = PdfRenderer()
        output_file = tmp_path / "underline.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_superscript(self, tmp_path):
        """Test superscript rendering."""
        from all2md.ast import Superscript

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="E = mc"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "superscript.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_subscript(self, tmp_path):
        """Test subscript rendering."""
        from all2md.ast import Subscript

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="H"),
                        Subscript(content=[Text(content="2")]),
                        Text(content="O"),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "subscript.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestCustomHeadingFonts:
    """Tests for custom heading font settings."""

    def test_heading_fonts_option(self, tmp_path):
        """Test custom heading fonts option."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Custom H1")]),
                Heading(level=2, content=[Text(content="Custom H2")]),
            ]
        )
        options = PdfRendererOptions(heading_fonts={1: ("Helvetica-Bold", 20), 2: ("Helvetica-Bold", 16)})
        renderer = PdfRenderer(options)
        output_file = tmp_path / "heading_fonts.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Custom H1" in text
            assert "Custom H2" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestEmptyTable:
    """Tests for empty table handling."""

    def test_empty_table_no_rows(self, tmp_path):
        """Test table with no rows is handled gracefully."""
        doc = Document(children=[Table(rows=[])])
        renderer = PdfRenderer()
        output_file = tmp_path / "empty_table.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestFootnoteDefinitionContent:
    """Tests for different footnote definition content types."""

    def test_footnote_with_code_block(self, tmp_path):
        """Test footnote definition containing code block."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Reference"), FootnoteReference(identifier="code")]),
                FootnoteDefinition(identifier="code", content=[CodeBlock(content="print('hello')")]),
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "footnote_code.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
@pytest.mark.pdf
class TestDefinitionListAdvanced:
    """Advanced tests for definition list rendering."""

    def test_definition_list_with_paragraph_content(self, tmp_path):
        """Test definition list where content is wrapped in Paragraph."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="API")]),
                            [
                                DefinitionDescription(
                                    content=[Paragraph(content=[Text(content="Application Programming Interface")])]
                                )
                            ],
                        )
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "deflist_para.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "API" in text
            assert "Application Programming Interface" in text

    def test_definition_list_multiple_items(self, tmp_path):
        """Test definition list with multiple terms."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term 1")]),
                            [DefinitionDescription(content=[Text(content="Description 1")])],
                        ),
                        (
                            DefinitionTerm(content=[Text(content="Term 2")]),
                            [DefinitionDescription(content=[Text(content="Description 2")])],
                        ),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "deflist_multi.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Term 1" in text
            assert "Term 2" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestLineBreakInline:
    """Tests for line break in inline content."""

    def test_line_break_processing(self, tmp_path):
        """Test line break in inline content processing."""
        from all2md.ast import LineBreak

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "line_break.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Line 1" in text
            assert "Line 2" in text


@pytest.mark.unit
@pytest.mark.pdf
class TestNestedBlockQuote:
    """Tests for nested blockquote rendering."""

    def test_nested_blockquote(self, tmp_path):
        """Test nested blockquote paragraphs use blockquote style."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="Outer quote")]),
                        BlockQuote(children=[Paragraph(content=[Text(content="Inner quote")])]),
                    ]
                )
            ]
        )
        renderer = PdfRenderer()
        output_file = tmp_path / "nested_bq.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        if PDF_VERIFICATION_AVAILABLE:
            text = get_pdf_text(output_file)
            assert "Outer quote" in text
            assert "Inner quote" in text
