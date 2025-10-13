#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_plaintext_renderer.py
"""Unit tests for PlainTextRenderer.

Tests cover:
- Rendering all node types to plain text
- Stripping all formatting (bold, italic, headings, etc.)
- Table rendering with cell separators
- List rendering
- Line wrapping functionality
- Edge cases and complex nested structures

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
from all2md.options import PlainTextOptions
from all2md.renderers.plaintext import PlainTextRenderer


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic node rendering."""

    def test_render_empty_document(self) -> None:
        """Test rendering an empty document."""
        doc = Document()
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == ""

    def test_render_text_only(self) -> None:
        """Test rendering plain text."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Hello world")])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Hello world"

    def test_render_multiple_paragraphs(self) -> None:
        """Test rendering multiple paragraphs."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First paragraph")]),
            Paragraph(content=[Text(content="Second paragraph")])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "First paragraph\n\nSecond paragraph"

    def test_custom_paragraph_separator(self) -> None:
        """Test custom paragraph separator."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First")]),
            Paragraph(content=[Text(content="Second")])
        ])
        options = PlainTextOptions(paragraph_separator="\n")
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "First\nSecond"


@pytest.mark.unit
class TestFormattingStripping:
    """Tests for stripping formatting from text."""

    def test_strip_bold(self) -> None:
        """Test that bold formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Strong(content=[Text(content="bold")]),
                Text(content=" text")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Normal bold text"

    def test_strip_italic(self) -> None:
        """Test that italic formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" text")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Normal italic text"

    def test_strip_strikethrough(self) -> None:
        """Test that strikethrough formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Strikethrough(content=[Text(content="struck")]),
                Text(content=" text")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Normal struck text"

    def test_strip_underline(self) -> None:
        """Test that underline formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Normal "),
                Underline(content=[Text(content="underlined")]),
                Text(content=" text")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Normal underlined text"

    def test_strip_superscript(self) -> None:
        """Test that superscript formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="E = mc"),
                Superscript(content=[Text(content="2")])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "E = mc2"

    def test_strip_subscript(self) -> None:
        """Test that subscript formatting is stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="H"),
                Subscript(content=[Text(content="2")]),
                Text(content="O")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "H2O"

    def test_nested_formatting(self) -> None:
        """Test nested formatting is all stripped."""
        doc = Document(children=[
            Paragraph(content=[
                Strong(content=[
                    Emphasis(content=[
                        Text(content="bold and italic")
                    ])
                ])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "bold and italic"


@pytest.mark.unit
class TestHeadings:
    """Tests for heading rendering."""

    def test_heading_level_1(self) -> None:
        """Test that heading text is extracted without markers."""
        doc = Document(children=[
            Heading(level=1, content=[Text(content="Title")])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Title"

    def test_heading_with_formatting(self) -> None:
        """Test heading with formatting strips formatting."""
        doc = Document(children=[
            Heading(level=2, content=[
                Text(content="Section with "),
                Strong(content=[Text(content="bold")])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Section with bold"


@pytest.mark.unit
class TestLists:
    """Tests for list rendering."""

    def test_unordered_list(self) -> None:
        """Test rendering unordered list."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 3")])])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "- Item 1\n- Item 2\n- Item 3"

    def test_ordered_list(self) -> None:
        """Test rendering ordered list (uses same prefix)."""
        doc = Document(children=[
            List(ordered=True, items=[
                ListItem(children=[Paragraph(content=[Text(content="First")])]),
                ListItem(children=[Paragraph(content=[Text(content="Second")])])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "- First\n- Second"

    def test_custom_list_prefix(self) -> None:
        """Test custom list item prefix."""
        doc = Document(children=[
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ])
        ])
        options = PlainTextOptions(list_item_prefix="* ")
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "* Item 1\n* Item 2"


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_simple_table(self) -> None:
        """Test rendering simple table."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Name")]),
                    TableCell(content=[Text(content="Age")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Alice")]),
                        TableCell(content=[Text(content="30")])
                    ]),
                    TableRow(cells=[
                        TableCell(content=[Text(content="Bob")]),
                        TableCell(content=[Text(content="25")])
                    ])
                ]
            )
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Name | Age\nAlice | 30\nBob | 25"

    def test_table_without_header(self) -> None:
        """Test rendering table without header."""
        doc = Document(children=[
            Table(
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Data1")]),
                        TableCell(content=[Text(content="Data2")])
                    ])
                ]
            )
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Data1 | Data2"

    def test_table_skip_header(self) -> None:
        """Test rendering table with header skipped."""
        doc = Document(children=[
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="Data1")]),
                        TableCell(content=[Text(content="Data2")])
                    ])
                ]
            )
        ])
        options = PlainTextOptions(include_table_headers=False)
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "Data1 | Data2"

    def test_custom_cell_separator(self) -> None:
        """Test custom table cell separator."""
        doc = Document(children=[
            Table(
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")]),
                        TableCell(content=[Text(content="C")])
                    ])
                ]
            )
        ])
        options = PlainTextOptions(table_cell_separator="\t")
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "A\tB\tC"

    def test_table_cell_with_formatting(self) -> None:
        """Test table cells with formatting stripped."""
        doc = Document(children=[
            Table(
                rows=[
                    TableRow(cells=[
                        TableCell(content=[
                            Strong(content=[Text(content="Bold")])
                        ]),
                        TableCell(content=[
                            Emphasis(content=[Text(content="Italic")])
                        ])
                    ])
                ]
            )
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Bold | Italic"


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block rendering."""

    def test_code_block_preserved(self) -> None:
        """Test code block content is preserved."""
        code = """def hello():
    print("world")"""
        doc = Document(children=[
            CodeBlock(content=code, language="python")
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == code.rstrip()

    def test_code_block_not_preserved(self) -> None:
        """Test code block treated as paragraph when not preserved."""
        code = """def hello():
    print("world")"""
        doc = Document(children=[
            CodeBlock(content=code, language="python")
        ])
        options = PlainTextOptions(preserve_code_blocks=False)
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        # Should strip extra whitespace
        assert "def hello():" in result
        assert 'print("world")' in result

    def test_inline_code(self) -> None:
        """Test inline code rendering."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Use "),
                Code(content="print()"),
                Text(content=" here")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Use print() here"


@pytest.mark.unit
class TestLinks:
    """Tests for link rendering."""

    def test_link_text_only(self) -> None:
        """Test link renders text only, not URL."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Visit "),
                Link(
                    content=[Text(content="example")],
                    url="https://example.com"
                )
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Visit example"
        assert "https" not in result


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_image_alt_text(self) -> None:
        """Test image renders alt text only."""
        doc = Document(children=[
            Paragraph(content=[
                Image(alt_text="Photo", url="photo.jpg")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Photo"

    def test_image_without_alt_text(self) -> None:
        """Test image without alt text renders nothing."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Before "),
                Image(alt_text="", url="photo.jpg"),
                Text(content=" after")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Before  after"


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_soft_line_break(self) -> None:
        """Test soft line break renders as space."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="First"),
                LineBreak(soft=True),
                Text(content="Second")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "First Second"

    def test_hard_line_break(self) -> None:
        """Test hard line break renders as newline."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="First"),
                LineBreak(soft=False),
                Text(content="Second")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "First\nSecond"


@pytest.mark.unit
class TestSkippedElements:
    """Tests for elements that are skipped in plain text."""

    def test_html_block_skipped(self) -> None:
        """Test HTML block is skipped."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            HTMLBlock(content="<div>HTML</div>"),
            Paragraph(content=[Text(content="After")])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Before\n\nAfter"
        assert "HTML" not in result
        assert "<div>" not in result

    def test_html_inline_skipped(self) -> None:
        """Test inline HTML is skipped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Before "),
                HTMLInline(content="<span>HTML</span>"),
                Text(content=" after")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Before  after"

    def test_thematic_break_skipped(self) -> None:
        """Test thematic break is skipped."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Before")]),
            ThematicBreak(),
            Paragraph(content=[Text(content="After")])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Before\n\nAfter"

    def test_footnote_reference_skipped(self) -> None:
        """Test footnote reference is skipped."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Text"),
                FootnoteReference(identifier="1")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Text"

    def test_footnote_definition_skipped(self) -> None:
        """Test footnote definition is skipped."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Main text")]),
            FootnoteDefinition(
                identifier="1",
                content=[Paragraph(content=[Text(content="Footnote text")])]
            )
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Main text"


@pytest.mark.unit
class TestMath:
    """Tests for math rendering."""

    def test_inline_math(self) -> None:
        """Test inline math extracts content."""
        doc = Document(children=[
            Paragraph(content=[
                Text(content="Formula: "),
                MathInline(content="x^2 + y^2 = r^2", notation="latex")
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Formula: x^2 + y^2 = r^2"

    def test_math_block(self) -> None:
        """Test math block extracts content."""
        doc = Document(children=[
            MathBlock(content="\\int_{0}^{\\infty} e^{-x} dx = 1", notation="latex")
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert "\\int" in result


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote rendering."""

    def test_block_quote(self) -> None:
        """Test block quote extracts text."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="Quoted text")])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Quoted text"

    def test_nested_block_quotes(self) -> None:
        """Test nested block quotes."""
        doc = Document(children=[
            BlockQuote(children=[
                Paragraph(content=[Text(content="Level 1")]),
                BlockQuote(children=[
                    Paragraph(content=[Text(content="Level 2")])
                ])
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert "Level 1" in result
        assert "Level 2" in result


@pytest.mark.unit
class TestDefinitionLists:
    """Tests for definition list rendering."""

    def test_definition_list(self) -> None:
        """Test definition list rendering."""
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
                )
            ])
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)
        assert "Term 1" in result
        assert "Definition 1" in result
        assert "Term 2" in result
        assert "Definition 2" in result


@pytest.mark.unit
class TestLineWrapping:
    """Tests for line wrapping functionality."""

    def test_no_wrapping_by_default(self) -> None:
        """Test long lines are not wrapped by default (max_line_width=80)."""
        long_text = "This is a very long line of text " * 10
        doc = Document(children=[
            Paragraph(content=[Text(content=long_text)])
        ])
        options = PlainTextOptions(max_line_width=None)
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        # Should not wrap when max_line_width is None
        assert "\n" not in result

    def test_wrapping_enabled(self) -> None:
        """Test line wrapping when enabled."""
        long_text = "This is a very long line of text that should be wrapped at the specified width " * 3
        doc = Document(children=[
            Paragraph(content=[Text(content=long_text)])
        ])
        options = PlainTextOptions(max_line_width=50)
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        # Should wrap, creating multiple lines
        lines = result.split('\n')
        assert len(lines) > 1
        # Each line should be <= 50 characters
        for line in lines:
            assert len(line) <= 50

    def test_wrapping_preserves_paragraphs(self) -> None:
        """Test wrapping preserves paragraph breaks."""
        doc = Document(children=[
            Paragraph(content=[Text(content="First paragraph with some text")]),
            Paragraph(content=[Text(content="Second paragraph with more text")])
        ])
        options = PlainTextOptions(max_line_width=20)
        renderer = PlainTextRenderer(options)
        result = renderer.render_to_string(doc)
        # Should have paragraph separator (double newline)
        assert "\n\n" in result


@pytest.mark.unit
class TestComplexStructures:
    """Tests for complex nested structures."""

    def test_complex_document(self) -> None:
        """Test complex document with multiple element types."""
        doc = Document(children=[
            Heading(level=1, content=[
                Text(content="Title with "),
                Strong(content=[Text(content="bold")])
            ]),
            Paragraph(content=[
                Text(content="Introduction with "),
                Emphasis(content=[Text(content="italic")]),
                Text(content=" and "),
                Link(content=[Text(content="link")], url="http://example.com")
            ]),
            List(ordered=False, items=[
                ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                ListItem(children=[Paragraph(content=[Text(content="Item 2")])])
            ]),
            Table(
                header=TableRow(cells=[
                    TableCell(content=[Text(content="Col1")]),
                    TableCell(content=[Text(content="Col2")])
                ]),
                rows=[
                    TableRow(cells=[
                        TableCell(content=[Text(content="A")]),
                        TableCell(content=[Text(content="B")])
                    ])
                ]
            )
        ])
        renderer = PlainTextRenderer()
        result = renderer.render_to_string(doc)

        # Verify all content is present
        assert "Title with bold" in result
        assert "Introduction with italic and link" in result
        assert "Item 1" in result
        assert "Item 2" in result
        assert "Col1 | Col2" in result
        assert "A | B" in result

        # Verify URLs are not present
        assert "http://" not in result


@pytest.mark.unit
class TestFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file(self, tmp_path) -> None:
        """Test rendering to file."""
        doc = Document(children=[
            Paragraph(content=[Text(content="Test content")])
        ])
        renderer = PlainTextRenderer()

        output_file = tmp_path / "output.txt"
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text(encoding="utf-8")
        assert content == "Test content"
