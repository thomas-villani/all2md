#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_markdown_renderer.py
"""Unit tests for MarkdownRenderer.

Tests cover:
- Rendering all node types to markdown
- Different markdown flavors (CommonMark, GFM, MarkdownPlus)
- Render options (emphasis symbols, bullet symbols, etc.)
- Edge cases and complex nested structures

"""

import pytest

from all2md.options import MarkdownOptions
from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    CommonMarkFlavor,
    Document,
    Emphasis,
    GFMFlavor,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MarkdownRenderer,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic node rendering."""

    def test_render_empty_document(self):
        """Test rendering an empty document."""
        doc = Document()
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == ""

    def test_render_text_only(self):
        """Test rendering plain text."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello world")])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Hello world"

    def test_render_multiple_paragraphs(self):
        """Test rendering multiple paragraphs."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First paragraph")]),
            Paragraph(content=[Text(content="Second paragraph")])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "First paragraph\n\nSecond paragraph"


@pytest.mark.unit
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1_hash(self):
        """Test rendering h1 with hash style."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "# Title"

    def test_heading_level_2_hash(self):
        """Test rendering h2 with hash style."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Subtitle")])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "## Subtitle"

    def test_heading_setext_h1(self):
        """Test rendering h1 with setext style."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "Title\n====="

    def test_heading_setext_h2(self):
        """Test rendering h2 with setext style."""
        doc = Document(children=[
            Heading(level=2, content=[Text(content="Subtitle")])
        ])
        options = MarkdownOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "Subtitle\n--------"

    def test_heading_with_formatting(self):
        """Test rendering heading with inline formatting."""
        doc = Document(children=[
            Heading(level=1, content=[
                Text(content="Welcome "),
                Strong(content=[Text(content="Home")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "# Welcome **Home**"


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting nodes."""

    def test_emphasis(self):
        """Test rendering emphasis (italic)."""
        doc = Document(children=[
            Paragraph(content=[
                Emphasis(content=[Text(content="italic text")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "*italic text*"

    def test_emphasis_with_underscore(self):
        """Test rendering emphasis with underscore symbol."""
        doc = Document(children=[
            Paragraph(content=[
                Emphasis(content=[Text(content="italic")])
            ])
        ])
        options = MarkdownOptions(emphasis_symbol="_")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "_italic_"

    def test_strong(self):
        """Test rendering strong (bold)."""
        doc = Document(children=[
            Paragraph(content=[
                Strong(content=[Text(content="bold text")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "**bold text**"

    def test_code_inline(self):
        """Test rendering inline code."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="print()")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "`print()`"

    def test_code_with_backticks(self):
        """Test rendering inline code containing backticks."""
        doc = Document(children=[
            Paragraph(content=[
                Code(content="`tick`")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```tick```"

    def test_combined_formatting(self):
        """Test rendering combined inline formatting."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=".")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "This is **bold** and *italic*."


@pytest.mark.unit
class TestExtendedInlineFormatting:
    """Tests for extended inline formatting."""

    def test_strikethrough_gfm(self):
        """Test strikethrough with GFM flavor."""
        doc = Document(children=[
            Paragraph(content=[
                Strikethrough(content=[Text(content="deleted")])
            ])
        ])
        options = MarkdownOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "~~deleted~~"

    def test_strikethrough_commonmark(self):
        """Test strikethrough fallback with CommonMark."""
        doc = Document(children=[
            Paragraph(content=[
                Strikethrough(content=[Text(content="deleted")])
            ])
        ])
        options = MarkdownOptions(flavor="commonmark")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<del>deleted</del>"

    def test_underline_html_mode(self):
        """Test underline with HTML mode."""
        doc = Document(children=[
            Paragraph(content=[
                Underline(content=[Text(content="underlined")])
            ])
        ])
        options = MarkdownOptions(underline_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<u>underlined</u>"

    def test_superscript_html_mode(self):
        """Test superscript with HTML mode."""
        doc = Document(children=[
            Paragraph(content=[
                Superscript(content=[Text(content="2")])
            ])
        ])
        options = MarkdownOptions(superscript_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<sup>2</sup>"

    def test_subscript_html_mode(self):
        """Test subscript with HTML mode."""
        doc = Document(children=[
            Paragraph(content=[
                Subscript(content=[Text(content="0")])
            ])
        ])
        options = MarkdownOptions(subscript_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<sub>0</sub>"


@pytest.mark.unit
class TestLinks:
    """Tests for link rendering."""

    def test_simple_link(self):
        """Test rendering a simple link."""
        doc = Document(children=[
            Paragraph(content=[
                Link(url="https://example.com", content=[Text(content="Example")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "[Example](https://example.com)"

    def test_link_with_title(self):
        """Test rendering a link with title."""
        doc = Document(children=[
            Paragraph(content=[
                Link(
                    url="https://example.com",
                    content=[Text(content="Example")],
                    title="Example Site"
                )
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == '[Example](https://example.com "Example Site")'


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_simple_image(self):
        """Test rendering a simple image."""
        doc = Document(children=[
            Paragraph(content=[
                Image(url="image.png", alt_text="An image")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "![An image](image.png)"

    def test_image_with_title(self):
        """Test rendering an image with title."""
        doc = Document(children=[
            Paragraph(content=[
                Image(url="image.png", alt_text="An image", title="Image Title")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == '![An image](image.png "Image Title")'


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block rendering."""

    def test_code_block_simple(self):
        """Test rendering a simple code block."""
        doc = Document(children=[
            CodeBlock(content="print('hello')")
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```\nprint('hello')\n```"

    def test_code_block_with_language(self):
        """Test rendering a code block with language."""
        doc = Document(children=[
            CodeBlock(content="x = 1", language="python")
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```python\nx = 1\n```"


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote rendering."""

    def test_simple_blockquote(self):
        """Test rendering a simple block quote."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="Quoted text")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "> Quoted text"

    def test_multi_paragraph_blockquote(self):
        """Test rendering a block quote with multiple paragraphs."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="First")]),
                Paragraph(content=[Text(content="Second")])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split('\n')
        assert all(line.startswith('>') for line in lines)


@pytest.mark.unit
class TestLists:
    """Tests for list rendering."""

    def test_unordered_list(self):
        """Test rendering an unordered list."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="One")])]),
                ListItem(children=[Paragraph(content=[Text(content="Two")])])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "* One\n* Two"

    def test_ordered_list(self):
        """Test rendering an ordered list."""
        doc = Document(children=[
            List(ordered=True, items=[
                ListItem(children=[Paragraph(content=[Text(content="First")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second")])])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "1. First\n2. Second"

    def test_ordered_list_with_start(self):
        """Test rendering an ordered list with custom start."""
        doc = Document(children=[
            List(ordered=True, start=5, items=[
                ListItem(children=[Paragraph(content=[Text(content="Fifth")])]),
                ListItem(children=[Paragraph(content=[Text(content="Sixth")])])
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "5. Fifth\n6. Sixth"

    def test_task_list_gfm(self):
        """Test rendering task lists with GFM flavor."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(
                    children=[Paragraph(content=[Text(content="Done")])],
                    task_status='checked'
                ),
                ListItem(
                    children=[Paragraph(content=[Text(content="Todo")])],
                    task_status='unchecked'
                )
            ])
        ])
        options = MarkdownOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "* [x]" in result
        assert "* [ ]" in result


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_simple_table_gfm(self):
        """Test rendering a simple table with GFM."""
        header = TableRow(cells=[
            TableCell(content=[Text(content="Name")]),
            TableCell(content=[Text(content="Age")])
        ], is_header=True)

        row1 = TableRow(cells=[
            TableCell(content=[Text(content="Alice")]),
            TableCell(content=[Text(content="30")])
        ])

        table = Table(header=header, rows=[row1], alignments=['left', 'right'])

        doc = Document(children=[table])
        options = MarkdownOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Name" in result
        assert "Alice" in result
        assert "|" in result

    def test_table_fallback_commonmark(self):
        """Test table fallback to HTML with CommonMark."""
        header = TableRow(cells=[
            TableCell(content=[Text(content="Header")])
        ], is_header=True)

        table = Table(header=header, rows=[])

        doc = Document(children=[table])
        options = MarkdownOptions(flavor="commonmark")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<table>" in result
        assert "<th>Header</th>" in result


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_thematic_break(self):
        """Test rendering a thematic break."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="After")])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "---" in result


@pytest.mark.unit
class TestHTMLNodes:
    """Tests for HTML node rendering."""

    def test_html_block(self):
        """Test rendering an HTML block."""
        doc = Document(children=[
            HTMLBlock(content="<div>Custom HTML</div>")
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "<div>Custom HTML</div>"

    def test_html_inline(self):
        """Test rendering inline HTML."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Text with "),
                HTMLInline(content="<span>HTML</span>"),
                Text(content=" inline")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Text with <span>HTML</span> inline"


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_soft_line_break(self):
        """Test rendering a soft line break."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="First line"),
                LineBreak(soft=True),
                Text(content="Second line")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "First line\nSecond line" in result

    def test_hard_line_break(self):
        """Test rendering a hard line break."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="First line"),
                LineBreak(soft=False),
                Text(content="Second line")
            ])
        ])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "First line  \nSecond line" in result


@pytest.mark.unit
class TestComplexDocuments:
    """Tests for complex nested documents."""

    def test_document_with_mixed_content(self):
        """Test rendering a document with mixed content types."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[
                Text(content="A paragraph with "),
                Strong(content=[Text(content="bold")]),
                Text(content=" and "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=".")
            ]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ]),
            CodeBlock(content="code here", language="python")
        ])

        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)

        assert "# Title" in result
        assert "**bold**" in result
        assert "*italic*" in result
        assert "* Item 1" in result
        assert "```python" in result


@pytest.mark.unit
class TestEscaping:
    """Tests for markdown character escaping."""

    def test_escape_special_characters(self):
        """Test escaping special markdown characters."""
        doc = Document(children=[
            Paragraph(content=[Text(content="*asterisks* and [brackets]")])
        ])
        options = MarkdownOptions(escape_special=True)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "\\*" in result
        assert "\\[" in result

    def test_no_escape_when_disabled(self):
        """Test that escaping can be disabled."""
        doc = Document(children=[
            Paragraph(content=[Text(content="*asterisks*")])
        ])
        options = MarkdownOptions(escape_special=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "\\*" not in result
        assert "*asterisks*" in result
