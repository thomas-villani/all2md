#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_pdf_conversion.py
"""Integration tests for PDF renderer.

Tests cover:
- End-to-end PDF rendering workflows
- Different page sizes
- Custom font settings
- Complete document conversion

"""


import pytest

try:
    from reportlab.platypus import SimpleDocTemplate  # noqa: F401
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from all2md.ast import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.options import PdfRendererOptions

if REPORTLAB_AVAILABLE:
    from all2md.renderers.pdf import PdfRenderer


def create_sample_document():
    """Create a sample AST document for testing.

    Returns
    -------
    Document
        A sample document with various elements for testing.

    """
    return Document(
        metadata={"title": "Sample Document", "author": "Test Author"},
        children=[
            Heading(level=1, content=[Text(content="Document Title")]),
            Paragraph(content=[
                Text(content="This is a paragraph with "),
                Strong(content=[Text(content="bold text")]),
                Text(content=" and a "),
                Link(url="https://example.com", content=[Text(content="link")]),
                Text(content=".")
            ]),
            Heading(level=2, content=[Text(content="Lists")]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                ListItem(children=[Paragraph(content=[Text(content="Third item")])])
            ]),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='def hello():\n    print("Hello, world!")', language="python"),
            Heading(level=2, content=[Text(content="Table")]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Value")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alpha")]),
                        TableCell(content=[Text(content="1")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="Beta")]),
                        TableCell(content=[Text(content="2")])
                    ])
                ]
            ),
            Heading(level=2, content=[Text(content="Quote")]),
            BlockQuote(children=[
                Paragraph(content=[Text(content="This is a blockquote.")])
            ])
        ]
    )


@pytest.mark.integration
@pytest.mark.skipif(not REPORTLAB_AVAILABLE, reason="reportlab not installed")
@pytest.mark.pdf
class TestPdfRendering:
    """Integration tests for PDF rendering."""

    def test_full_document_to_pdf(self, tmp_path):
        """Test rendering complete document to PDF."""
        doc = create_sample_document()
        renderer = PdfRenderer()
        output_file = tmp_path / "full_document.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0

    def test_pdf_page_sizes(self, tmp_path):
        """Test PDF rendering with different page sizes."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])

        # Letter
        letter_renderer = PdfRenderer(PdfRendererOptions(page_size="letter"))
        letter_file = tmp_path / "letter.pdf"
        letter_renderer.render(doc, letter_file)
        assert letter_file.exists()

        # A4
        a4_renderer = PdfRenderer(PdfRendererOptions(page_size="a4"))
        a4_file = tmp_path / "a4.pdf"
        a4_renderer.render(doc, a4_file)
        assert a4_file.exists()

        # Legal
        legal_renderer = PdfRenderer(PdfRendererOptions(page_size="legal"))
        legal_file = tmp_path / "legal.pdf"
        legal_renderer.render(doc, legal_file)
        assert legal_file.exists()

    def test_pdf_with_custom_fonts(self, tmp_path):
        """Test PDF with custom font settings."""
        doc = create_sample_document()
        options = PdfRendererOptions(
            font_name="Times-Roman",
            font_size=12,
            code_font="Courier"
        )
        renderer = PdfRenderer(options)
        output_file = tmp_path / "custom_fonts.pdf"
        renderer.render(doc, output_file)

        assert output_file.exists()
