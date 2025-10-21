#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_org_renderer.py
"""Unit tests for Org-Mode renderer.

Tests cover:
- Heading rendering with TODO states, priorities, and tags
- Text formatting (bold, italic, code, underline, strikethrough)
- List rendering (bullet and ordered)
- Table rendering
- Code block rendering
- Links and images
- Block quotes
- Metadata rendering

"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options.org import OrgRendererOptions
from all2md.renderers.org import OrgRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic Org rendering."""

    def test_simple_heading(self) -> None:
        """Test rendering a simple heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "* Title" in org

    def test_multiple_heading_levels(self) -> None:
        """Test rendering multiple heading levels."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Level 1")]),
                Heading(level=2, content=[Text(content="Level 2")]),
                Heading(level=3, content=[Text(content="Level 3")]),
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "* Level 1" in org
        assert "** Level 2" in org
        assert "*** Level 3" in org

    def test_simple_paragraph(self) -> None:
        """Test rendering a simple paragraph."""
        doc = Document(children=[Paragraph(content=[Text(content="This is a paragraph.")])])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "This is a paragraph." in org


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text.")]
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "*bold*" in org

    def test_italic(self) -> None:
        """Test rendering italic text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "/italic/" in org

    def test_code(self) -> None:
        """Test rendering code text."""
        doc = Document(
            children=[Paragraph(content=[Text(content="This is "), Code(content="code"), Text(content=" text.")])]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "=code=" in org

    def test_underline(self) -> None:
        """Test rendering underline text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Underline(content=[Text(content="underline")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "_underline_" in org

    def test_strikethrough(self) -> None:
        """Test rendering strikethrough text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Strikethrough(content=[Text(content="strikethrough")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "+strikethrough+" in org


@pytest.mark.unit
class TestTodoHeadings:
    """Tests for TODO heading rendering."""

    def test_todo_heading(self) -> None:
        """Test rendering a TODO heading."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Write documentation")], metadata={"org_todo_state": "TODO"})
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "* TODO Write documentation" in org

    def test_done_heading(self) -> None:
        """Test rendering a DONE heading."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Implement feature")], metadata={"org_todo_state": "DONE"})
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "* DONE Implement feature" in org

    def test_heading_with_priority(self) -> None:
        """Test rendering a heading with priority."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[Text(content="High priority task")],
                    metadata={"org_todo_state": "TODO", "org_priority": "A"},
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "* TODO [#A] High priority task" in org

    def test_heading_with_tags(self) -> None:
        """Test rendering a heading with tags."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Important task")], metadata={"org_tags": ["work", "urgent"]})
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert ":work:urgent:" in org


@pytest.mark.unit
class TestLists:
    """Tests for list rendering."""

    def test_bullet_list(self) -> None:
        """Test rendering a bullet list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
                    ],
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "- Item 1" in org
        assert "- Item 2" in org
        assert "- Item 3" in org

    def test_ordered_list(self) -> None:
        """Test rendering an ordered list."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=1,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Third")])]),
                    ],
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "1. First" in org
        assert "2. Second" in org
        assert "3. Third" in org


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block rendering."""

    def test_code_block_without_language(self) -> None:
        """Test rendering a code block without language."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("Hello")')])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "#+BEGIN_SRC" in org
        assert "#+END_SRC" in org
        assert "def hello()" in org

    def test_code_block_with_language(self) -> None:
        """Test rendering a code block with language."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("Hello")', language="python")])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "#+BEGIN_SRC python" in org
        assert "#+END_SRC" in org


@pytest.mark.unit
class TestLinks:
    """Tests for link rendering."""

    def test_simple_link(self) -> None:
        """Test rendering a simple link."""
        doc = Document(
            children=[
                Paragraph(content=[Link(url="https://example.com", content=[Text(content="https://example.com")])])
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "[[https://example.com]]" in org

    def test_link_with_description(self) -> None:
        """Test rendering a link with description."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Example")])])]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "[[https://example.com][Example]]" in org


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_image(self) -> None:
        """Test rendering an image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="My Image")])])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "[[file:image.png]" in org


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_simple_table(self) -> None:
        """Test rendering a simple table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="1")]), TableCell(content=[Text(content="2")])]
                        ),
                        TableRow(
                            cells=[TableCell(content=[Text(content="3")]), TableCell(content=[Text(content="4")])]
                        ),
                    ],
                )
            ]
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "| A" in org
        assert "| B" in org
        assert "|---" in org or "|--" in org  # Separator line
        assert "| 1" in org
        assert "| 2" in org


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote rendering."""

    def test_block_quote(self) -> None:
        """Test rendering a block quote."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="This is a quote.")])])])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert ": This is a quote." in org


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_thematic_break(self) -> None:
        """Test rendering a thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "-----" in org


@pytest.mark.unit
class TestMetadataRendering:
    """Tests for metadata rendering."""

    def test_file_properties(self) -> None:
        """Test rendering file-level properties."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"title": "My Document", "author": "John Doe"},
        )
        renderer = OrgRenderer()
        org = renderer.render_to_string(doc)

        assert "#+TITLE: My Document" in org
        assert "#+AUTHOR: John Doe" in org


@pytest.mark.unit
class TestOptions:
    """Tests for renderer options."""

    def test_preserve_properties(self) -> None:
        """Test that preserve_properties option works."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[Text(content="Heading")],
                    metadata={"org_properties": {"CUSTOM_ID": "my-id", "CATEGORY": "work"}},
                )
            ]
        )
        options = OrgRendererOptions(preserve_properties=True)
        renderer = OrgRenderer(options)
        org = renderer.render_to_string(doc)

        assert ":PROPERTIES:" in org
        assert ":CUSTOM_ID: my-id" in org or "CUSTOM_ID" in org
        assert ":END:" in org

    def test_preserve_tags_disabled(self) -> None:
        """Test that preserve_tags=False removes tags."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Heading")], metadata={"org_tags": ["work", "urgent"]})]
        )
        options = OrgRendererOptions(preserve_tags=False)
        renderer = OrgRenderer(options)
        org = renderer.render_to_string(doc)

        assert ":work:urgent:" not in org
