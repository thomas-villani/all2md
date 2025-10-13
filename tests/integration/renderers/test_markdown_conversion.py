#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/integration/renderers/test_markdown_conversion.py
"""Integration tests for Markdown renderer.

Tests cover:
- End-to-end Markdown rendering workflows
- Different Markdown flavors (GFM, CommonMark)
- Complete document conversion
- Markdown-specific options

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
from all2md.options import MarkdownOptions
from all2md.renderers import MarkdownRenderer


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
class TestMarkdownRendering:
    """Integration tests for Markdown rendering."""

    def test_full_document_to_markdown(self):
        """Test rendering complete document to Markdown."""
        doc = create_sample_document()
        renderer = MarkdownRenderer(MarkdownOptions())
        result = renderer.render_to_string(doc)

        # Verify all major elements are present
        assert "# Document Title" in result
        assert "**bold text**" in result
        assert "[link](https://example.com)" in result
        assert "* First item" in result
        assert "```python" in result
        assert "| Name" in result
        assert "> This is a blockquote" in result

    def test_markdown_different_flavors(self):
        """Test rendering with different Markdown flavors."""
        doc = create_sample_document()

        # GFM
        gfm_renderer = MarkdownRenderer(MarkdownOptions(flavor="gfm"))
        gfm_result = gfm_renderer.render_to_string(doc)
        assert "| Name" in gfm_result  # Tables supported in GFM

        # CommonMark
        cm_renderer = MarkdownRenderer(MarkdownOptions(
            flavor="commonmark",
            unsupported_table_mode="html"
        ))
        cm_result = cm_renderer.render_to_string(doc)
        # Tables as HTML in CommonMark
        assert "<table>" in cm_result
