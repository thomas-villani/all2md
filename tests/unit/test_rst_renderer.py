#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_rst_renderer.py
"""Unit tests for reStructuredText renderer.

Tests cover:
- Rendering headings with underlines
- Rendering inline formatting
- Rendering lists (bullet and enumerated)
- Rendering tables (grid and simple)
- Rendering code blocks
- Rendering links and images
- Rendering definition lists
- Configuration options

"""

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
)
from all2md.options import RstRendererOptions
from all2md.renderers.rst import RestructuredTextRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic RST rendering."""

    def test_simple_heading(self) -> None:
        """Test rendering a simple heading."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "Title" in rst
        assert "=====" in rst

    def test_heading_levels(self) -> None:
        """Test rendering different heading levels."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Level 1")]),
            Heading(level=2, content=[Text(content="Level 2")]),
            Heading(level=3, content=[Text(content="Level 3")]),
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Check for different underline characters
        assert "=====" in rst  # Level 1
        assert "-----" in rst  # Level 2
        assert "~~~~~" in rst  # Level 3

    def test_custom_heading_chars(self) -> None:
        """Test rendering with custom heading characters."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        options = RstRendererOptions(heading_chars="#*-^")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # Should use # for level 1
        assert "#####" in rst

    def test_simple_paragraph(self) -> None:
        """Test rendering a simple paragraph."""
        doc = Document(children=[
            Paragraph(content=[Text(content="This is a paragraph.")])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "This is a paragraph." in rst


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting rendering."""

    def test_emphasis(self) -> None:
        """Test rendering emphasis."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" text.")
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "*italic*" in rst

    def test_strong(self) -> None:
        """Test rendering strong."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text.")
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "**bold**" in rst

    def test_code(self) -> None:
        """Test rendering inline code."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="This is "),
                Code(content="code"),
                Text(content=" text.")
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "``code``" in rst


@pytest.mark.unit
class TestLists:
    """Tests for list rendering."""

    def test_bullet_list(self) -> None:
        """Test rendering a bullet list."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 3")])]),
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "* Item 1" in rst
        assert "* Item 2" in rst
        assert "* Item 3" in rst

    def test_enumerated_list(self) -> None:
        """Test rendering an enumerated list."""
        doc = Document(children=[
            List(ordered=True, start=1, items=[
                ListItem(children=[Paragraph(content=[Text(content="First")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                ListItem(children=[Paragraph(content=[Text(content="Third")])]),
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "1. First" in rst
        assert "2. Second" in rst
        assert "3. Third" in rst


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block rendering."""

    def test_code_block_with_directive(self) -> None:
        """Test rendering code block with directive style."""
        doc = Document(children=[
            CodeBlock(content="def hello():\n    print('Hello')", language="python")
        ])
        options = RstRendererOptions(code_directive_style="directive")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert ".. code-block:: python" in rst
        assert "def hello():" in rst

    def test_code_block_with_double_colon(self) -> None:
        """Test rendering code block with :: style."""
        doc = Document(children=[
            CodeBlock(content="def hello():\n    print('Hello')", language=None)
        ])
        options = RstRendererOptions(code_directive_style="double_colon")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "::" in rst
        assert "def hello():" in rst


@pytest.mark.unit
class TestLinks:
    """Tests for link rendering."""

    def test_external_link(self) -> None:
        """Test rendering an external link."""
        doc = Document(children=[
            Paragraph(content=[
                Link(
                    url="https://www.python.org",
                    content=[Text(content="Python")]
                )
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "`Python <https://www.python.org>`_" in rst


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_image(self) -> None:
        """Test rendering an image."""
        doc = Document(children=[
            Image(url="example.png", alt_text="Example")
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ".. image:: example.png" in rst
        assert ":alt: Example" in rst


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_grid_table(self) -> None:
        """Test rendering a grid table."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="A")]),
                    TableCell(content=[Text(content="B")]),
                ], is_header=True),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="1")]),
                        TableCell(content=[Text(content="2")]),
                    ], is_header=False),
                ]
            )
        ])
        options = RstRendererOptions(table_style="grid")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "+" in rst
        assert "|" in rst
        assert "A" in rst
        assert "B" in rst

    def test_simple_table(self) -> None:
        """Test rendering a simple table."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")]),
                ], is_header=True),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")]),
                    ], is_header=False),
                ]
            )
        ])
        options = RstRendererOptions(table_style="simple")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "====" in rst
        assert "Col1" in rst
        assert "Col2" in rst


@pytest.mark.unit
class TestDefinitionLists:
    """Tests for definition list rendering."""

    def test_definition_list(self) -> None:
        """Test rendering a definition list."""
        doc = Document(children=[
            DefinitionList(items=[
                (
                    DefinitionTerm(content=[Text(content="Term 1")]),
                    [DefinitionDescription(content=[
                        Paragraph(content=[Text(content="Definition 1")])
                    ])]
                ),
                (
                    DefinitionTerm(content=[Text(content="Term 2")]),
                    [DefinitionDescription(content=[
                        Paragraph(content=[Text(content="Definition 2")])
                    ])]
                ),
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "Term 1" in rst
        assert "Term 2" in rst
        assert "Definition 1" in rst
        assert "Definition 2" in rst


@pytest.mark.unit
class TestBlockQuote:
    """Tests for block quote rendering."""

    def test_block_quote(self) -> None:
        """Test rendering a block quote."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="This is quoted.")])
            ])
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Block quotes in RST are indented
        lines = rst.split('\n')
        quoted_lines = [line for line in lines if "This is quoted." in line]
        assert len(quoted_lines) > 0
        assert any(line.startswith('   ') for line in quoted_lines)


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_transition(self) -> None:
        """Test rendering a thematic break."""
        doc = Document(children=[
            ThematicBreak()
        ])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "----" in rst


@pytest.mark.unit
class TestMetadata:
    """Tests for metadata rendering."""

    def test_docinfo_rendering(self) -> None:
        """Test rendering metadata as docinfo."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Content")])
            ],
            metadata={
                'author': 'John Doe',
                'creation_date': '2025-01-01'
            }
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Author: John Doe" in rst
        assert ":Date: 2025-01-01" in rst


@pytest.mark.unit
class TestRoundTrip:
    """Tests for round-trip conversion."""

    def test_heading_round_trip(self) -> None:
        """Test round-trip of heading through AST."""
        from all2md.parsers.rst import RestructuredTextParser

        original_rst = """
Title
=====
"""
        parser = RestructuredTextParser()
        doc = parser.parse(original_rst.strip())

        renderer = RestructuredTextRenderer()
        generated_rst = renderer.render_to_string(doc)

        assert "Title" in generated_rst
        assert "=====" in generated_rst

    def test_paragraph_round_trip(self) -> None:
        """Test round-trip of paragraph through AST."""
        from all2md.parsers.rst import RestructuredTextParser

        original_rst = "This is a **bold** statement with *italic* text."

        parser = RestructuredTextParser()
        doc = parser.parse(original_rst)

        renderer = RestructuredTextRenderer()
        generated_rst = renderer.render_to_string(doc)

        assert "**bold**" in generated_rst
        assert "*italic*" in generated_rst
