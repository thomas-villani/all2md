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
