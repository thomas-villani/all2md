#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_docx_conversion.py
"""Integration tests for DOCX renderer.

Tests cover:
- End-to-end DOCX rendering workflows
- Custom styles and fonts
- Metadata handling
- Complete document conversion

"""


import pytest

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

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
from all2md.options import DocxRendererOptions

if DOCX_AVAILABLE:
    from all2md.renderers.docx import DocxRenderer


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
@pytest.mark.skipif(not DOCX_AVAILABLE, reason="python-docx not installed")
@pytest.mark.docx
class TestDocxRendering:
    """Integration tests for DOCX rendering."""

    def test_full_document_to_docx(self, tmp_path):
        """Test rendering complete document to DOCX."""
        doc = create_sample_document()
        renderer = DocxRenderer()
        output_file = tmp_path / "full_document.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()

        # Verify DOCX content
        docx_doc = DocxDocument(str(output_file))

        # Check for tables
        assert len(docx_doc.tables) >= 1

        # Check for content in paragraphs
        all_text = " ".join(p.text for p in docx_doc.paragraphs)
        assert "Document Title" in all_text
        assert "bold text" in all_text
        assert "First item" in all_text

    def test_docx_with_custom_styles(self, tmp_path):
        """Test DOCX rendering with custom styles."""
        doc = create_sample_document()
        options = DocxRendererOptions(
            default_font="Arial",
            default_font_size=12,
            code_font="Consolas"
        )
        renderer = DocxRenderer(options)
        output_file = tmp_path / "custom_styles.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_docx_metadata(self, tmp_path):
        """Test DOCX metadata handling."""
        doc = create_sample_document()
        renderer = DocxRenderer()
        output_file = tmp_path / "with_metadata.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert docx_doc.core_properties.title == "Sample Document"
        assert docx_doc.core_properties.author == "Test Author"
