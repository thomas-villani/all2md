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
    LineBreak,
    Link,
    List,
    ListItem,
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
from all2md.options import RstRendererOptions
from all2md.renderers.rst import RestructuredTextRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic RST rendering."""

    def test_simple_heading(self) -> None:
        """Test rendering a simple heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "Title" in rst
        assert "=====" in rst

    def test_heading_levels(self) -> None:
        """Test rendering different heading levels."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Level 1")]),
                Heading(level=2, content=[Text(content="Level 2")]),
                Heading(level=3, content=[Text(content="Level 3")]),
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Check for different underline characters
        assert "=====" in rst  # Level 1
        assert "-----" in rst  # Level 2
        assert "~~~~~" in rst  # Level 3

    def test_custom_heading_chars(self) -> None:
        """Test rendering with custom heading characters."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        options = RstRendererOptions(heading_chars="#*-^")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # Should use # for level 1
        assert "#####" in rst

    def test_simple_paragraph(self) -> None:
        """Test rendering a simple paragraph."""
        doc = Document(children=[Paragraph(content=[Text(content="This is a paragraph.")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "This is a paragraph." in rst


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting rendering."""

    def test_emphasis(self) -> None:
        """Test rendering emphasis."""
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
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "*italic*" in rst

    def test_strong(self) -> None:
        """Test rendering strong."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text.")]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "**bold**" in rst

    def test_code(self) -> None:
        """Test rendering inline code."""
        doc = Document(
            children=[Paragraph(content=[Text(content="This is "), Code(content="code"), Text(content=" text.")])]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "``code``" in rst


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
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "* Item 1" in rst
        assert "* Item 2" in rst
        assert "* Item 3" in rst

    def test_enumerated_list(self) -> None:
        """Test rendering an enumerated list."""
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
        doc = Document(children=[CodeBlock(content="def hello():\n    print('Hello')", language="python")])
        options = RstRendererOptions(code_directive_style="directive")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert ".. code-block:: python" in rst
        assert "def hello():" in rst

    def test_code_block_with_double_colon(self) -> None:
        """Test rendering code block with :: style."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('Hello')", language=None)])
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
        doc = Document(
            children=[Paragraph(content=[Link(url="https://www.python.org", content=[Text(content="Python")])])]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "`Python <https://www.python.org>`_" in rst


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_image(self) -> None:
        """Test rendering an image."""
        doc = Document(children=[Image(url="example.png", alt_text="Example")])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ".. image:: example.png" in rst
        assert ":alt: Example" in rst


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_grid_table(self) -> None:
        """Test rendering a grid table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="A")]),
                            TableCell(content=[Text(content="B")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="1")]),
                                TableCell(content=[Text(content="2")]),
                            ],
                            is_header=False,
                        ),
                    ],
                )
            ]
        )
        options = RstRendererOptions(table_style="grid")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "+" in rst
        assert "|" in rst
        assert "A" in rst
        assert "B" in rst

    def test_simple_table(self) -> None:
        """Test rendering a simple table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Col1")]),
                            TableCell(content=[Text(content="Col2")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                            ],
                            is_header=False,
                        ),
                    ],
                )
            ]
        )
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
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term 1")]),
                            [DefinitionDescription(content=[Paragraph(content=[Text(content="Definition 1")])])],
                        ),
                        (
                            DefinitionTerm(content=[Text(content="Term 2")]),
                            [DefinitionDescription(content=[Paragraph(content=[Text(content="Definition 2")])])],
                        ),
                    ]
                )
            ]
        )
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
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="This is quoted.")])])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Block quotes in RST are indented
        lines = rst.split("\n")
        quoted_lines = [line for line in lines if "This is quoted." in line]
        assert len(quoted_lines) > 0
        assert any(line.startswith("   ") for line in quoted_lines)


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_transition(self) -> None:
        """Test rendering a thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "----" in rst


@pytest.mark.unit
class TestMetadata:
    """Tests for metadata rendering."""

    def test_docinfo_rendering(self) -> None:
        """Test rendering metadata as docinfo."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"author": "John Doe", "creation_date": "2025-01-01"},
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


@pytest.mark.unit
class TestTextEscaping:
    """Tests for special character escaping in text content."""

    def test_escape_asterisks(self) -> None:
        """Test that asterisks are escaped in text."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with *asterisks* here")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Asterisks should be escaped with backslashes
        assert r"\*asterisks\*" in rst
        assert "*asterisks*" not in rst or r"\*" in rst

    def test_escape_underscores(self) -> None:
        """Test that underscores are escaped in text."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with _underscores_ here")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Underscores should be escaped
        assert r"\_underscores\_" in rst

    def test_escape_backticks(self) -> None:
        """Test that backticks are escaped in text."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with `backticks` here")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Backticks should be escaped
        assert r"\`backticks\`" in rst

    def test_escape_brackets(self) -> None:
        """Test that square brackets are escaped in text."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with [brackets] here")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Brackets should be escaped
        assert r"\[brackets\]" in rst

    def test_escape_pipes(self) -> None:
        """Test that pipes are escaped in text."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with |pipes| here")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Pipes should be escaped
        assert r"\|pipes\|" in rst

    def test_escape_multiple_special_chars(self) -> None:
        """Test escaping multiple special characters together."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Special chars: *bold* _italic_ `code` [ref] |sub| <url>")])]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # All special chars should be escaped
        assert r"\*bold\*" in rst
        assert r"\_italic\_" in rst
        assert r"\`code\`" in rst
        assert r"\[ref\]" in rst
        assert r"\|sub\|" in rst
        assert r"\<url\>" in rst


@pytest.mark.unit
class TestUnsupportedFeatures:
    """Tests for RST unsupported feature fallbacks."""

    def test_strikethrough_renders_as_plain_text(self) -> None:
        """Test that strikethrough content renders as plain text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Strikethrough(content=[Text(content="struck through")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should contain the text but without any strikethrough markup
        assert "struck through" in rst
        # Should not have any special formatting
        assert "~~" not in rst
        assert "This is struck through text." in rst

    def test_underline_renders_as_plain_text(self) -> None:
        """Test that underline content renders as plain text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Underline(content=[Text(content="underlined")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should contain the text but without any underline markup
        assert "underlined" in rst
        # Should not have any special formatting
        assert "This is underlined text." in rst

    def test_superscript_uses_role_syntax(self) -> None:
        """Test that superscript uses :sup: role syntax."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="x"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should use :sup: role
        assert ":sup:`2`" in rst

    def test_subscript_uses_role_syntax(self) -> None:
        """Test that subscript uses :sub: role syntax."""
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
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should use :sub: role
        assert ":sub:`2`" in rst


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_soft_line_break_renders_as_space(self) -> None:
        """Test that soft line breaks render as spaces."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Soft breaks should render as space
        assert "Line 1 Line 2" in rst

    def test_hard_line_break_uses_line_block_syntax(self) -> None:
        """Test that hard line breaks use line block syntax."""
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
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Hard breaks should use line block syntax (newline + pipe + space)
        assert "\n| " in rst
        assert "Line 1" in rst
        assert "Line 2" in rst

    def test_multiple_hard_breaks(self) -> None:
        """Test multiple hard line breaks."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                        LineBreak(soft=False),
                        Text(content="Line 3"),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should have multiple line block markers
        assert rst.count("\n| ") >= 2


@pytest.mark.unit
class TestTableLimitations:
    """Tests for table rendering limitations."""

    def test_grid_table_single_line_cells(self) -> None:
        """Test that grid tables render single-line cells correctly."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Header 1")]),
                            TableCell(content=[Text(content="Header 2")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Cell 1")]),
                                TableCell(content=[Text(content="Cell 2")]),
                            ],
                            is_header=False,
                        ),
                    ],
                )
            ]
        )
        options = RstRendererOptions(table_style="grid")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # Should render as grid table
        assert "+" in rst
        assert "|" in rst
        assert "Header 1" in rst
        assert "Cell 1" in rst

    def test_simple_table_single_line_cells(self) -> None:
        """Test that simple tables render single-line cells correctly."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Col1")]),
                            TableCell(content=[Text(content="Col2")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                            ],
                            is_header=False,
                        ),
                    ],
                )
            ]
        )
        options = RstRendererOptions(table_style="simple")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # Should render as simple table
        assert "====" in rst
        assert "Col1" in rst
        assert "A" in rst

    def test_table_with_complex_inline_content(self) -> None:
        """Test table cells with complex inline content (emphasis, code)."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Header")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(
                                    content=[
                                        Text(content="Text with "),
                                        Emphasis(content=[Text(content="emphasis")]),
                                        Text(content=" and "),
                                        Code(content="code"),
                                    ]
                                ),
                            ],
                            is_header=False,
                        ),
                    ],
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Should render inline formatting within cells
        assert "*emphasis*" in rst
        assert "``code``" in rst


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering."""

    def test_math_inline(self) -> None:
        """Test rendering inline math."""
        from all2md.ast import MathInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="The equation "),
                        MathInline(content="E = mc^2"),
                        Text(content=" is famous."),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":math:`E = mc^2`" in rst

    def test_math_block(self) -> None:
        """Test rendering math block."""
        from all2md.ast import MathBlock

        doc = Document(
            children=[
                MathBlock(content="\\int_0^\\infty e^{-x} dx = 1"),
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ".. math::" in rst
        assert "\\int_0^\\infty e^{-x} dx = 1" in rst


@pytest.mark.unit
class TestFootnoteRendering:
    """Tests for footnote rendering."""

    def test_footnote_reference(self) -> None:
        """Test rendering footnote reference."""
        from all2md.ast import FootnoteReference

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with footnote"),
                        FootnoteReference(identifier="1"),
                        Text(content="."),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Uses [id]_ format
        assert "[1]_" in rst

    def test_footnote_definition(self) -> None:
        """Test rendering footnote definition."""
        from all2md.ast import FootnoteDefinition

        doc = Document(
            children=[
                FootnoteDefinition(
                    identifier="1",
                    content=[Paragraph(content=[Text(content="Footnote content")])],
                ),
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # Uses .. [id] format
        assert ".. [1]" in rst
        assert "Footnote content" in rst


@pytest.mark.unit
class TestCommentRendering:
    """Tests for comment rendering modes."""

    def test_comment_rst_mode(self) -> None:
        """Test comment in RST native mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(content="This is a comment"),
            ]
        )
        options = RstRendererOptions(comment_mode="rst")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # RST mode uses .. directive format with indented content
        assert ".." in rst
        assert "This is a comment" in rst

    def test_comment_visible_mode(self) -> None:
        """Test comment in visible mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(content="Visible comment"),
            ]
        )
        options = RstRendererOptions(comment_mode="visible")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "Visible comment" in rst

    def test_comment_ignore_mode(self) -> None:
        """Test comment in ignore mode."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(content="Ignored comment"),
            ]
        )
        options = RstRendererOptions(comment_mode="ignore")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "Ignored comment" not in rst

    def test_comment_with_metadata(self) -> None:
        """Test comment with author metadata."""
        from all2md.ast import Comment

        doc = Document(
            children=[
                Comment(
                    content="Comment with author",
                    metadata={"author": "John", "date": "2025-01-01"},
                ),
            ]
        )
        options = RstRendererOptions(comment_mode="visible")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        assert "Comment with author" in rst

    def test_inline_comment(self) -> None:
        """Test inline comment rendering."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="inline note"),
                        Text(content=" more text."),
                    ]
                )
            ]
        )
        options = RstRendererOptions(comment_mode="visible")
        renderer = RestructuredTextRenderer(options)
        rst = renderer.render_to_string(doc)

        # Inline comments should appear in visible mode
        assert "inline note" in rst


@pytest.mark.unit
class TestHTMLHandling:
    """Tests for HTML node handling."""

    def test_html_inline_rendered(self) -> None:
        """Test that inline HTML is passed through."""
        from all2md.ast import HTMLInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        HTMLInline(content="<span>inline</span>"),
                        Text(content=" more."),
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # HTML is passed through in RST
        assert "Text" in rst
        assert "more" in rst

    def test_html_block_rendered(self) -> None:
        """Test that HTML blocks are passed through."""
        from all2md.ast import HTMLBlock

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                HTMLBlock(content="<div>HTML content</div>"),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        # HTML blocks are passed through
        assert "Before" in rst
        assert "After" in rst


@pytest.mark.unit
class TestFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file_path(self, tmp_path) -> None:
        """Test rendering to file path string."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output_file = tmp_path / "output.rst"

        renderer = RestructuredTextRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "Title" in content
        assert "=====" in content

    def test_render_to_path_object(self, tmp_path) -> None:
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output_file = tmp_path / "output.rst"

        renderer = RestructuredTextRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        from io import StringIO

        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output = StringIO()

        renderer = RestructuredTextRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "Content" in result

    def test_render_to_bytes(self) -> None:
        """Test render_to_bytes method."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = RestructuredTextRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert b"Title" in result


@pytest.mark.unit
class TestNestedContent:
    """Tests for nested content rendering."""

    def test_nested_lists(self) -> None:
        """Test rendering nested lists."""
        inner_list = List(
            ordered=False,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="Inner 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Inner 2")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Outer 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Outer 2")]), inner_list]),
                    ],
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "* Outer 1" in rst
        assert "Inner 1" in rst
        assert "Inner 2" in rst

    def test_nested_ordered_lists(self) -> None:
        """Test rendering nested ordered lists."""
        inner_list = List(
            ordered=True,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="a")])]),
                ListItem(children=[Paragraph(content=[Text(content="b")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="2")]), inner_list]),
                    ],
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "1. 1" in rst
        assert "2. 2" in rst
        assert "1. a" in rst

    def test_nested_block_quotes(self) -> None:
        """Test rendering nested block quotes."""
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
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "Outer quote" in rst
        assert "Inner quote" in rst


@pytest.mark.unit
class TestExtendedMetadata:
    """Tests for extended metadata rendering."""

    def test_metadata_with_title(self) -> None:
        """Test metadata with title field."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"title": "Document Title"},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Title: Document Title" in rst

    def test_metadata_with_source(self) -> None:
        """Test metadata with source field."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"source": "https://example.com"},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Source: https://example.com" in rst

    def test_metadata_with_modification_date(self) -> None:
        """Test metadata with modification date."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"modification_date": "2025-12-01"},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Updated: 2025-12-01" in rst

    def test_metadata_with_keywords_list(self) -> None:
        """Test metadata with keywords as list."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"keywords": ["python", "rst", "docs"]},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Keywords: python, rst, docs" in rst

    def test_metadata_with_language(self) -> None:
        """Test metadata with language field."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"language": "en"},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Language: en" in rst

    def test_metadata_with_category(self) -> None:
        """Test metadata with category field."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"category": "Documentation"},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Category: Documentation" in rst

    def test_metadata_with_custom_fields(self) -> None:
        """Test metadata with custom fields."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"custom": {"version": "1.0", "status": "draft"}},
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert ":Version: 1.0" in rst
        assert ":Status: draft" in rst


@pytest.mark.unit
class TestOptionsValidation:
    """Tests for options validation."""

    def test_invalid_options_type(self) -> None:
        """Test that invalid options type raises error."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            RestructuredTextRenderer(options="invalid")

    def test_valid_options(self) -> None:
        """Test valid options are accepted."""
        options = RstRendererOptions(
            heading_chars="=-~^",
            table_style="simple",
            code_directive_style="double_colon",
        )
        renderer = RestructuredTextRenderer(options)
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        rst = renderer.render_to_string(doc)

        assert "Test" in rst


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert isinstance(rst, str)

    def test_empty_paragraph(self) -> None:
        """Test rendering empty paragraph."""
        doc = Document(children=[Paragraph(content=[])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert isinstance(rst, str)

    def test_deeply_nested_formatting(self) -> None:
        """Test deeply nested inline formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Strong(
                            content=[
                                Text(content="Bold with "),
                                Emphasis(content=[Text(content="italic inside")]),
                            ]
                        )
                    ]
                )
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "**Bold with" in rst or "Bold with" in rst

    def test_special_unicode_characters(self) -> None:
        """Test rendering special unicode characters."""
        doc = Document(children=[Paragraph(content=[Text(content="Unicode: \u00e9\u00f1\u00fc \u4e2d\u6587")])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "\u00e9" in rst
        assert "\u4e2d\u6587" in rst

    def test_very_long_line(self) -> None:
        """Test rendering very long line."""
        long_text = "This is a very long sentence. " * 50
        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "This is a very long sentence" in rst

    def test_mixed_content_document(self) -> None:
        """Test rendering document with mixed content types."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(
                    content=[
                        Text(content="Normal "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" "),
                        Code(content="code"),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item")])]),
                    ],
                ),
                CodeBlock(content="print('hello')", language="python"),
                ThematicBreak(),
            ]
        )
        renderer = RestructuredTextRenderer()
        rst = renderer.render_to_string(doc)

        assert "Title" in rst
        assert "**bold**" in rst
        assert "*italic*" in rst
        assert "``code``" in rst
        assert "* Item" in rst
        assert "----" in rst
