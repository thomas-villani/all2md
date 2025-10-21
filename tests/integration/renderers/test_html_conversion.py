#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_html_conversion.py
"""Integration tests for HTML renderer.

Tests cover:
- End-to-end HTML rendering workflows
- Standalone vs fragment rendering
- Table of contents generation
- CSS styling options
- Complete document conversion

"""

import pytest

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
from all2md.options import HtmlRendererOptions
from all2md.renderers.html import HtmlRenderer


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
            Paragraph(
                content=[
                    Text(content="This is a paragraph with "),
                    Strong(content=[Text(content="bold text")]),
                    Text(content=" and a "),
                    Link(url="https://example.com", content=[Text(content="link")]),
                    Text(content="."),
                ]
            ),
            Heading(level=2, content=[Text(content="Lists")]),
            List(
                ordered=False,
                items=[
                    ListItem(children=[Paragraph(content=[Text(content="First item")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Second item")])]),
                    ListItem(children=[Paragraph(content=[Text(content="Third item")])]),
                ],
            ),
            Heading(level=2, content=[Text(content="Code Example")]),
            CodeBlock(content='def hello():\n    print("Hello, world!")', language="python"),
            Heading(level=2, content=[Text(content="Table")]),
            Table(
                header=TableRow(
                    cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Value")])]
                ),
                rows=[
                    TableRow(
                        cells=[TableCell(content=[Text(content="Alpha")]), TableCell(content=[Text(content="1")])]
                    ),
                    TableRow(cells=[TableCell(content=[Text(content="Beta")]), TableCell(content=[Text(content="2")])]),
                ],
            ),
            Heading(level=2, content=[Text(content="Quote")]),
            BlockQuote(children=[Paragraph(content=[Text(content="This is a blockquote.")])]),
        ],
    )


@pytest.mark.integration
class TestHtmlRendering:
    """Integration tests for HTML rendering."""

    def test_full_document_to_html_standalone(self):
        """Test rendering complete document to standalone HTML."""
        doc = create_sample_document()
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True))
        result = renderer.render_to_string(doc)

        # Verify HTML structure
        assert "<!DOCTYPE html>" in result
        assert "<html" in result
        assert "<head>" in result
        assert "<body>" in result
        assert "</html>" in result

        # Verify content
        assert "<h1" in result
        assert "Document Title" in result
        assert "<strong>bold text</strong>" in result
        assert '<a href="https://example.com">link</a>' in result
        assert "<ul>" in result
        assert "<table>" in result
        assert "<blockquote>" in result

    def test_full_document_to_html_fragment(self):
        """Test rendering complete document to HTML fragment."""
        doc = create_sample_document()
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)

        # Should not have document structure
        assert "<!DOCTYPE html>" not in result
        assert "<html" not in result

        # But should have content
        assert "<h1" in result
        assert "<p>" in result

    def test_html_with_toc(self):
        """Test HTML rendering with table of contents."""
        doc = create_sample_document()
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, include_toc=True))
        result = renderer.render_to_string(doc)

        assert '<nav id="table-of-contents">' in result
        assert "Document Title" in result
        assert "Lists" in result
        assert "Table" in result

    def test_html_css_options(self):
        """Test different CSS styling options."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])

        # Embedded CSS
        embedded_renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, css_style="embedded"))
        embedded_result = embedded_renderer.render_to_string(doc)
        assert "<style>" in embedded_result

        # No CSS
        no_css_renderer = HtmlRenderer(HtmlRendererOptions(standalone=True, css_style="none"))
        no_css_result = no_css_renderer.render_to_string(doc)
        assert "<style>" not in no_css_result
