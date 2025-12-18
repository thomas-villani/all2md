#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Textile renderer.

Tests cover:
- Basic rendering
- Headings
- Paragraphs
- Code blocks
- Block quotes
- Lists (ordered, unordered, nested)
- Tables
- Inline formatting
- Links and images
- Math
- Footnotes
- Comments
- Definition lists
- HTML handling
- File output
- Edge cases

"""

from io import StringIO
from pathlib import Path

import pytest

from all2md.ast import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
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
from all2md.exceptions import InvalidOptionsError
from all2md.options.textile import TextileRendererOptions
from all2md.renderers.textile import TextileRenderer


@pytest.mark.unit
class TestTextileBasicRendering:
    """Tests for basic Textile rendering functionality."""

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert result == "\n"

    def test_render_simple_paragraph(self) -> None:
        """Test rendering a simple paragraph."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello, world!")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "Hello, world!" in result

    def test_render_multiple_paragraphs(self) -> None:
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph.")]),
                Paragraph(content=[Text(content="Second paragraph.")]),
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "First paragraph." in result
        assert "Second paragraph." in result


@pytest.mark.unit
class TestTextileHeadings:
    """Tests for Textile heading rendering."""

    def test_render_h1(self) -> None:
        """Test rendering level 1 heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h1. Title" in result

    def test_render_h2(self) -> None:
        """Test rendering level 2 heading."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h2. Subtitle" in result

    def test_render_h6(self) -> None:
        """Test rendering level 6 heading."""
        doc = Document(children=[Heading(level=6, content=[Text(content="Deep heading")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h6. Deep heading" in result

    def test_render_heading_with_emphasis(self) -> None:
        """Test rendering heading with emphasis."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[
                        Text(content="My "),
                        Emphasis(content=[Text(content="Emphasized")]),
                        Text(content=" Title"),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h1. My _Emphasized_ Title" in result


@pytest.mark.unit
class TestTextileCodeBlocks:
    """Tests for Textile code block rendering."""

    def test_render_code_block_extended(self) -> None:
        """Test rendering code block with extended blocks enabled."""
        doc = Document(children=[CodeBlock(content="print('hello')", language="python")])
        options = TextileRendererOptions(use_extended_blocks=True)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "bc. print('hello')" in result

    def test_render_code_block_non_extended(self) -> None:
        """Test rendering code block without extended blocks."""
        doc = Document(children=[CodeBlock(content="code", language="")])
        options = TextileRendererOptions(use_extended_blocks=False)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "@code@" in result

    def test_render_multiline_code_block(self) -> None:
        """Test rendering multiline code block."""
        doc = Document(children=[CodeBlock(content="line1\nline2\nline3", language="text")])
        options = TextileRendererOptions(use_extended_blocks=True)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "bc. line1" in result
        assert "line2" in result
        assert "line3" in result


@pytest.mark.unit
class TestTextileBlockQuotes:
    """Tests for Textile block quote rendering."""

    def test_render_block_quote_extended(self) -> None:
        """Test rendering block quote with extended blocks enabled."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="A quote")])])])
        options = TextileRendererOptions(use_extended_blocks=True)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "bq. " in result
        assert "A quote" in result

    def test_render_block_quote_non_extended(self) -> None:
        """Test rendering block quote without extended blocks."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="A quote")])])])
        options = TextileRendererOptions(use_extended_blocks=False)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "A quote" in result

    def test_render_nested_block_quote(self) -> None:
        """Test rendering block quote with multiple paragraphs."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="First paragraph")]),
                        Paragraph(content=[Text(content="Second paragraph")]),
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "First paragraph" in result
        assert "Second paragraph" in result


@pytest.mark.unit
class TestTextileLists:
    """Tests for Textile list rendering."""

    def test_render_unordered_list(self) -> None:
        """Test rendering unordered list."""
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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "* Item 1" in result
        assert "* Item 2" in result

    def test_render_ordered_list(self) -> None:
        """Test rendering ordered list."""
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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "# First" in result
        assert "# Second" in result

    def test_render_nested_list(self) -> None:
        """Test rendering nested list."""
        nested_list = List(
            ordered=False,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="Nested 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Nested 2")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Top")]), nested_list]),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "* Top" in result
        assert "** Nested 1" in result
        assert "** Nested 2" in result


@pytest.mark.unit
class TestTextileTables:
    """Tests for Textile table rendering."""

    def test_render_simple_table(self) -> None:
        """Test rendering a simple table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Name")]),
                            TableCell(content=[Text(content="Age")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Alice")]),
                                TableCell(content=[Text(content="30")]),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "|_.Name|" in result
        assert "|_.Age|" in result
        assert "|Alice|" in result
        assert "|30|" in result

    def test_render_table_without_header(self) -> None:
        """Test rendering table without header."""
        doc = Document(
            children=[
                Table(
                    header=None,
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "|A|" in result
        assert "|B|" in result

    def test_render_table_with_colspan(self) -> None:
        """Test rendering table with colspan."""
        doc = Document(
            children=[
                Table(
                    header=None,
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Spans two")], colspan=2),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "\\2. Spans two" in result

    def test_render_table_with_rowspan(self) -> None:
        """Test rendering table with rowspan."""
        doc = Document(
            children=[
                Table(
                    header=None,
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Spans rows")], rowspan=2),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "/2. Spans rows" in result


@pytest.mark.unit
class TestTextileInlineFormatting:
    """Tests for Textile inline formatting."""

    def test_render_emphasis(self) -> None:
        """Test rendering emphasis."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "_italic_" in result

    def test_render_strong(self) -> None:
        """Test rendering strong."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "*bold*" in result

    def test_render_inline_code(self) -> None:
        """Test rendering inline code."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "@code@" in result

    def test_render_strikethrough(self) -> None:
        """Test rendering strikethrough."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "-deleted-" in result

    def test_render_underline(self) -> None:
        """Test rendering underline."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "+underlined+" in result

    def test_render_superscript(self) -> None:
        """Test rendering superscript."""
        doc = Document(children=[Paragraph(content=[Superscript(content=[Text(content="2")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "^2^" in result

    def test_render_subscript(self) -> None:
        """Test rendering subscript."""
        doc = Document(children=[Paragraph(content=[Subscript(content=[Text(content="2")])])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "~2~" in result


@pytest.mark.unit
class TestTextileLinks:
    """Tests for Textile link rendering."""

    def test_render_simple_link(self) -> None:
        """Test rendering simple link."""
        doc = Document(
            children=[Paragraph(content=[Link(url="http://example.com", content=[Text(content="Example")])])]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert '"Example":http://example.com' in result

    def test_render_link_with_formatting(self) -> None:
        """Test rendering link with formatted text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Link(
                            url="http://example.com",
                            content=[Strong(content=[Text(content="Bold Link")])],
                        )
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert '"*Bold Link*":http://example.com' in result


@pytest.mark.unit
class TestTextileImages:
    """Tests for Textile image rendering."""

    def test_render_image_simple(self) -> None:
        """Test rendering simple image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "!image.png!" in result

    def test_render_image_with_alt(self) -> None:
        """Test rendering image with alt text."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="A picture")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "!image.png(A picture)!" in result


@pytest.mark.unit
class TestTextileLineBreaks:
    """Tests for Textile line break rendering."""

    def test_render_hard_line_break(self) -> None:
        """Test rendering hard line break."""
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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "Line 1\nLine 2" in result

    def test_render_soft_line_break(self) -> None:
        """Test rendering soft line break."""
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
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "Line 1 Line 2" in result


@pytest.mark.unit
class TestTextileThematicBreak:
    """Tests for Textile thematic break rendering."""

    def test_render_thematic_break(self) -> None:
        """Test rendering thematic break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "<hr />" in result
        assert "Before" in result
        assert "After" in result


@pytest.mark.unit
class TestTextileMath:
    """Tests for Textile math rendering."""

    def test_render_math_inline(self) -> None:
        """Test rendering inline math."""
        doc = Document(children=[Paragraph(content=[MathInline(content="E=mc^2")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "@E=mc^2@" in result

    def test_render_math_block(self) -> None:
        """Test rendering math block."""
        doc = Document(children=[MathBlock(content="\\int_0^1 x^2 dx")])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "bc. \\int_0^1 x^2 dx" in result


@pytest.mark.unit
class TestTextileFootnotes:
    """Tests for Textile footnote rendering."""

    def test_render_footnote_reference(self) -> None:
        """Test rendering footnote reference."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Some text"),
                        FootnoteReference(identifier="1"),
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "^[1]^" in result

    def test_render_footnote_definition(self) -> None:
        """Test rendering footnote definition."""
        doc = Document(
            children=[
                FootnoteDefinition(
                    identifier="1",
                    content=[Paragraph(content=[Text(content="Footnote text")])],
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "*[1]*" in result
        assert "Footnote text" in result


@pytest.mark.unit
class TestTextileDefinitionLists:
    """Tests for Textile definition list rendering."""

    def test_render_definition_list(self) -> None:
        """Test rendering definition list."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term")]),
                            [DefinitionDescription(content=[Paragraph(content=[Text(content="Definition")])])],
                        )
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "*Term*" in result
        assert "Definition" in result


@pytest.mark.unit
class TestTextileComments:
    """Tests for Textile renderer comment support."""

    def test_render_comment_block(self) -> None:
        """Test rendering block-level comment."""
        doc = Document(children=[Comment(content="This is a comment")])
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- This is a comment -->" in output

    def test_render_comment_block_with_metadata(self) -> None:
        """Test rendering block-level comment with author and date metadata."""
        doc = Document(
            children=[
                Comment(
                    content="This is a comment",
                    metadata={"author": "John Doe", "date": "2025-01-15", "label": "1"},
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- Comment 1 by John Doe (2025-01-15): This is a comment -->" in output

    def test_render_comment_inline(self) -> None:
        """Test rendering inline comment."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Some text "),
                        CommentInline(content="inline comment"),
                        Text(content=" more text"),
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- inline comment -->" in output
        assert "Some text" in output
        assert "more text" in output

    def test_render_comment_inline_with_metadata(self) -> None:
        """Test rendering inline comment with author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Some text "),
                        CommentInline(content="needs review", metadata={"author": "Jane Smith"}),
                        Text(content=" more text"),
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- [Comment by Jane Smith: needs review] -->" in output

    def test_render_comment_blockquote_mode(self) -> None:
        """Test rendering comment in blockquote mode."""
        doc = Document(children=[Comment(content="A comment")])
        options = TextileRendererOptions(comment_mode="blockquote")
        renderer = TextileRenderer(options)
        output = renderer.render_to_string(doc)

        assert "bq. A comment" in output

    def test_render_comment_ignore_mode(self) -> None:
        """Test rendering comment in ignore mode."""
        doc = Document(children=[Comment(content="A comment")])
        options = TextileRendererOptions(comment_mode="ignore")
        renderer = TextileRenderer(options)
        output = renderer.render_to_string(doc)

        assert "comment" not in output.lower()


@pytest.mark.unit
class TestTextileHTML:
    """Tests for Textile HTML handling."""

    def test_render_html_block(self) -> None:
        """Test rendering HTML block."""
        doc = Document(children=[HTMLBlock(content="<div>HTML content</div>")])
        options = TextileRendererOptions(html_passthrough_mode="pass-through")
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<div>HTML content</div>" in result

    def test_render_html_inline(self) -> None:
        """Test rendering inline HTML."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        HTMLInline(content="<span>inline</span>"),
                        Text(content=" HTML"),
                    ]
                )
            ]
        )
        options = TextileRendererOptions(html_passthrough_mode="pass-through")
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<span>inline</span>" in result

    def test_render_html_escape_mode(self) -> None:
        """Test HTML escape mode."""
        doc = Document(children=[HTMLBlock(content="<script>alert('xss')</script>")])
        options = TextileRendererOptions(html_passthrough_mode="escape")
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<script>" not in result

    def test_render_html_drop_mode(self) -> None:
        """Test HTML drop mode."""
        doc = Document(children=[HTMLBlock(content="<div>dropped</div>")])
        options = TextileRendererOptions(html_passthrough_mode="drop")
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<div>" not in result


@pytest.mark.unit
class TestTextileLineWrapping:
    """Tests for Textile line wrapping option."""

    def test_render_with_line_wrapping(self) -> None:
        """Test rendering with line length wrapping."""
        long_text = "This is a very long paragraph that should be wrapped at a specific line length."
        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])
        options = TextileRendererOptions(line_length=30)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        # Lines should be wrapped
        lines = result.strip().split("\n")
        assert len(lines) > 1
        for line in lines:
            assert len(line) <= 35  # Allow some flexibility for word boundaries

    def test_render_without_line_wrapping(self) -> None:
        """Test rendering without line wrapping (line_length=0)."""
        long_text = "This is a long line that should not be wrapped."
        doc = Document(children=[Paragraph(content=[Text(content=long_text)])])
        options = TextileRendererOptions(line_length=0)
        renderer = TextileRenderer(options)
        result = renderer.render_to_string(doc)

        assert long_text in result


@pytest.mark.unit
class TestTextileFileOutput:
    """Tests for Textile file output functionality."""

    def test_render_to_file_path(self, tmp_path: Path) -> None:
        """Test rendering to file path."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output_file = tmp_path / "output.textile"

        renderer = TextileRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "h1. Title" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output_file = tmp_path / "output.textile"

        renderer = TextileRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Heading")])])
        output = StringIO()

        renderer = TextileRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "h2. Heading" in result

    def test_render_to_binary_stream(self) -> None:
        """Test rendering to binary stream."""
        doc = Document(children=[Paragraph(content=[Text(content="Binary test")])])

        class BinaryStream:
            def __init__(self):
                self.data = b""
                self.mode = "wb"

            def write(self, data):
                self.data = data

        output = BinaryStream()
        renderer = TextileRenderer()
        renderer.render(doc, output)

        assert b"Binary test" in output.data


@pytest.mark.unit
class TestTextileEdgeCases:
    """Tests for edge cases in Textile rendering."""

    def test_render_nested_formatting(self) -> None:
        """Test rendering nested inline formatting."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "*_bold italic_*" in result

    def test_render_empty_paragraph(self) -> None:
        """Test rendering empty paragraph."""
        doc = Document(children=[Paragraph(content=[])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_render_special_characters(self) -> None:
        """Test rendering special characters."""
        doc = Document(children=[Paragraph(content=[Text(content="Special: <>&\"'")])])
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        # Textile passes through special chars
        assert "Special:" in result

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            TextileRenderer(options="invalid")

    def test_unsupported_output_type(self) -> None:
        """Test that unsupported output type raises error."""
        doc = Document(children=[Paragraph(content=[Text(content="test")])])
        renderer = TextileRenderer()

        with pytest.raises(TypeError):
            renderer.render(doc, 12345)  # type: ignore

    def test_render_complex_document(self) -> None:
        """Test rendering complex document with multiple elements."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Document")]),
                Paragraph(
                    content=[
                        Text(content="A paragraph with "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text."),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Header")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Value")])])],
                ),
            ]
        )
        renderer = TextileRenderer()
        result = renderer.render_to_string(doc)

        assert "h1. Document" in result
        assert "*bold*" in result
        assert "_italic_" in result
        assert "* Item 1" in result
        assert "|_.Header|" in result
        assert "|Value|" in result
