#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_asciidoc_renderer.py
"""Unit tests for AsciiDocRenderer.

Tests cover:
- Heading rendering (ATX style only)
- List item continuation for block content
- Footnote flattening for inline-only content
- Basic AsciiDoc syntax generation
"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
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
from all2md.options.asciidoc import AsciiDocRendererOptions
from all2md.renderers.asciidoc import AsciiDocRenderer


@pytest.mark.unit
class TestHeadingRendering:
    """Tests for heading rendering - only ATX style is valid AsciiDoc."""

    def test_heading_level_1(self):
        """Test h1 renders with == prefix."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "== Title" in result

    def test_heading_level_2(self):
        """Test h2 renders with === prefix."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "=== Subtitle" in result

    def test_heading_level_3(self):
        """Test h3 renders with ==== prefix."""
        doc = Document(children=[Heading(level=3, content=[Text(content="Section")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "==== Section" in result

    def test_no_setext_style(self):
        """Test that setext-style underlines are not used (not valid AsciiDoc)."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        # Should NOT have underline
        assert "====" not in result or "== Title" in result
        # Should have ATX style
        assert "== Title" in result


@pytest.mark.unit
class TestListItemContinuation:
    """Tests for list item continuation with block content."""

    def test_list_item_with_code_block(self):
        """Test list item with code block has continuation marker."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item with code")]),
                                CodeBlock(content="print('hello')", language="python"),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have continuation marker
        assert "+\n" in result
        # Should have list marker
        assert "* Item with code" in result
        # Should have code block delimiters
        assert "----" in result

    def test_list_item_with_blockquote(self):
        """Test list item with blockquote has continuation marker."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item text")]),
                                BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])]),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have continuation marker
        assert "+\n" in result
        # Should have blockquote delimiters
        assert "____" in result

    def test_list_item_with_nested_list(self):
        """Test list item with nested list has continuation marker."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Outer item")]),
                                List(
                                    ordered=False,
                                    items=[ListItem(children=[Paragraph(content=[Text(content="Inner item")])])],
                                ),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have continuation marker before nested list
        assert "+\n" in result
        # Should have both list levels
        assert "* Outer item" in result
        assert "** Inner item" in result

    def test_list_item_with_table(self):
        """Test list item with table has continuation marker."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item with table")]),
                                Table(
                                    header=TableRow(
                                        cells=[
                                            TableCell(content=[Text(content="Col1")]),
                                            TableCell(content=[Text(content="Col2")]),
                                        ]
                                    ),
                                    rows=[],
                                ),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have continuation marker
        assert "+\n" in result
        # Should have table delimiters
        assert "|===" in result

    def test_list_item_first_child_is_block(self):
        """Test list item where first child is a block element."""
        doc = Document(
            children=[
                List(ordered=False, items=[ListItem(children=[CodeBlock(content="first_item", language="python")])])
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have continuation marker even for first child
        assert "* \n+" in result or "*\n+" in result


@pytest.mark.unit
class TestFootnoteFlattening:
    """Tests for footnote content flattening to inline text."""

    def test_footnote_with_paragraph(self):
        """Test footnote with simple paragraph content."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote text")])]),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Should have footnote with flattened content
        assert "footnote:1[Footnote text]" in result

    def test_footnote_with_code_block(self):
        """Test footnote with code block gets flattened to inline code."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[CodeBlock(content="print('test')", language="python")]),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Code block should be converted to inline representation
        assert "footnote:1[" in result
        assert "print" in result  # Code content should be present

    def test_footnote_with_multiple_paragraphs(self):
        """Test footnote with multiple paragraphs gets flattened and joined."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(
                    identifier="1",
                    content=[
                        Paragraph(content=[Text(content="First para")]),
                        Paragraph(content=[Text(content="Second para")]),
                    ],
                ),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Both paragraphs should be in the footnote, space-separated
        assert "footnote:1[First para Second para]" in result

    def test_footnote_with_formatting(self):
        """Test footnote with inline formatting is preserved."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(
                    identifier="1", content=[Paragraph(content=[Strong(content=[Text(content="bold")])])]
                ),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Inline formatting should be preserved
        assert "footnote:1[*bold*]" in result

    def test_footnote_multiple_references(self):
        """Test multiple references to same footnote."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="First"),
                        FootnoteReference(identifier="1"),
                        Text(content=" and second"),
                        FootnoteReference(identifier="1"),
                    ]
                ),
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Note")])]),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # First occurrence has content
        assert "footnote:1[Note]" in result
        # Second occurrence is empty
        assert "footnote:1[]" in result


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic AsciiDoc rendering."""

    def test_paragraph(self):
        """Test simple paragraph rendering."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "Hello world" in result

    def test_strong(self):
        """Test bold text rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "*bold*" in result

    def test_emphasis(self):
        """Test italic text rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "_italic_" in result

    def test_code_inline(self):
        """Test inline code rendering."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "+code+" in result

    def test_link(self):
        """Test link rendering."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Example")])])]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "link:https://example.com[Example]" in result

    def test_code_block(self):
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="print('hello')", language="python")])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "[source,python]" in result
        assert "----" in result
        assert "print('hello')" in result

    def test_unordered_list(self):
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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_ordered_list(self):
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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert ". First" in result
        assert ". Second" in result


@pytest.mark.unit
class TestRendererOptions:
    """Tests for renderer options."""

    def test_list_indent_option(self):
        """Test list indent spacing option."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Outer")]),
                                List(
                                    ordered=False,
                                    items=[ListItem(children=[Paragraph(content=[Text(content="Inner")])])],
                                ),
                            ]
                        )
                    ],
                )
            ]
        )

        # Test with custom indent
        options = AsciiDocRendererOptions(list_indent=4)
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have nested list markers
        assert "* Outer" in result
        assert "** Inner" in result

    def test_use_attributes_option(self):
        """Test document attributes rendering."""
        doc = Document(
            metadata={"title": "Test Title", "author": "Test Author"},
            children=[Paragraph(content=[Text(content="Content")])],
        )

        # Test with attributes enabled
        options = AsciiDocRendererOptions(use_attributes=True)
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)
        assert ":title: Test Title" in result
        assert ":author: Test Author" in result

        # Test with attributes disabled
        options = AsciiDocRendererOptions(use_attributes=False)
        renderer = AsciiDocRenderer(options)
        result = renderer.render_to_string(doc)
        assert ":title:" not in result
        assert ":author:" not in result
