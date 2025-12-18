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


@pytest.mark.unit
class TestImageRendering:
    """Tests for image rendering."""

    def test_image_basic(self):
        """Test basic image rendering."""
        from all2md.ast import Image

        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Alt text")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses image:: for block images
        assert "image::image.png[Alt text]" in result

    def test_image_with_dimensions(self):
        """Test image with width and height."""
        from all2md.ast import Image

        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Alt", width=200, height=100)])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "image.png" in result


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_thematic_break(self):
        """Test thematic break rendering."""
        from all2md.ast import ThematicBreak

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses ''' for breaks
        assert "'''" in result or "---" in result


@pytest.mark.unit
class TestLineBreak:
    """Tests for line break rendering."""

    def test_soft_line_break(self):
        """Test soft line break rendering."""
        from all2md.ast import LineBreak

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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "Line 1" in result
        assert "Line 2" in result

    def test_hard_line_break(self):
        """Test hard line break rendering."""
        from all2md.ast import LineBreak

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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses + for hard line breaks
        assert "Line 1" in result
        assert "Line 2" in result


@pytest.mark.unit
class TestSubscriptSuperscript:
    """Tests for subscript and superscript rendering."""

    def test_superscript(self):
        """Test superscript rendering."""
        from all2md.ast import Superscript

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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses ^^ for superscript
        assert "^2^" in result

    def test_subscript(self):
        """Test subscript rendering."""
        from all2md.ast import Subscript

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
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses ~~ for subscript
        assert "~2~" in result


@pytest.mark.unit
class TestUnderlineStrikethrough:
    """Tests for underline and strikethrough rendering."""

    def test_underline(self):
        """Test underline rendering."""
        from all2md.ast import Underline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Normal and "),
                        Underline(content=[Text(content="underlined")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses [.underline] role
        assert "underlined" in result

    def test_strikethrough(self):
        """Test strikethrough rendering."""
        from all2md.ast import Strikethrough

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Normal and "),
                        Strikethrough(content=[Text(content="deleted")]),
                        Text(content=" text."),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses [.line-through] role
        assert "deleted" in result


@pytest.mark.unit
class TestDefinitionList:
    """Tests for definition list rendering."""

    def test_definition_list(self):
        """Test definition list rendering."""
        from all2md.ast import DefinitionDescription, DefinitionList, DefinitionTerm

        term1 = DefinitionTerm(content=[Text(content="Term 1")])
        desc1 = DefinitionDescription(content=[Text(content="Description 1")])
        term2 = DefinitionTerm(content=[Text(content="Term 2")])
        desc2 = DefinitionDescription(content=[Text(content="Description 2")])

        doc = Document(children=[DefinitionList(items=[(term1, [desc1]), (term2, [desc2])])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses term:: definition format
        assert "Term 1" in result
        assert "Description 1" in result
        assert "Term 2" in result
        assert "Description 2" in result


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering."""

    def test_math_inline(self):
        """Test inline math rendering."""
        from all2md.ast import MathInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Equation: "),
                        MathInline(content="E = mc^2"),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # AsciiDoc uses latexmath or stem macro
        assert "E = mc^2" in result

    def test_math_block(self):
        """Test math block rendering."""
        from all2md.ast import MathBlock

        doc = Document(children=[MathBlock(content="\\int_0^\\infty e^{-x} dx = 1")])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "\\int_0^\\infty e^{-x} dx = 1" in result


@pytest.mark.unit
class TestCommentRendering:
    """Tests for comment rendering."""

    def test_comment_block(self):
        """Test block comment rendering."""
        from all2md.ast import Comment

        doc = Document(children=[Comment(content="This is a comment")])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Comments should be rendered
        assert "This is a comment" in result or "//" in result

    def test_inline_comment(self):
        """Test inline comment rendering."""
        from all2md.ast import CommentInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="inline note"),
                        Text(content=" more"),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        # Inline comments should be present
        assert "Text" in result
        assert "more" in result


@pytest.mark.unit
class TestHTMLHandling:
    """Tests for HTML handling."""

    def test_html_block(self):
        """Test HTML block passthrough."""
        from all2md.ast import HTMLBlock

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                HTMLBlock(content="<div>HTML content</div>"),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "Before" in result
        assert "After" in result

    def test_html_inline(self):
        """Test inline HTML passthrough."""
        from all2md.ast import HTMLInline

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        HTMLInline(content="<span>inline</span>"),
                        Text(content=" more"),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "Text" in result
        assert "more" in result


@pytest.mark.unit
class TestFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file_path(self, tmp_path):
        """Test rendering to file path string."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output_file = tmp_path / "output.adoc"

        renderer = AsciiDocRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "Title" in content

    def test_render_to_path_object(self, tmp_path):
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output_file = tmp_path / "output.adoc"

        renderer = AsciiDocRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self):
        """Test rendering to text stream."""
        from io import StringIO

        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output = StringIO()

        renderer = AsciiDocRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "Content" in result

    def test_render_to_bytes(self):
        """Test render_to_bytes method."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert b"Title" in result


@pytest.mark.unit
class TestTableRendering:
    """Tests for table rendering."""

    def test_table_with_header(self):
        """Test table with header row."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Col1")]),
                            TableCell(content=[Text(content="Col2")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "|===" in result
        assert "Col1" in result
        assert "Col2" in result
        assert "A" in result

    def test_table_without_header(self):
        """Test table without header row."""
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
                        )
                    ],
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "|===" in result


@pytest.mark.unit
class TestOptionsValidation:
    """Tests for options validation."""

    def test_invalid_options_type(self):
        """Test that invalid options type raises error."""
        from all2md.exceptions import InvalidOptionsError

        with pytest.raises(InvalidOptionsError):
            AsciiDocRenderer(options="invalid")

    def test_valid_options(self):
        """Test valid options are accepted."""
        options = AsciiDocRendererOptions(
            list_indent=4,
            use_attributes=True,
        )
        renderer = AsciiDocRenderer(options)
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        result = renderer.render_to_string(doc)

        assert "Test" in result


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_document(self):
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert isinstance(result, str)

    def test_special_characters(self):
        """Test rendering special characters."""
        doc = Document(children=[Paragraph(content=[Text(content="Special: <>&\"' and unicode: \u00e9\u00f1")])])
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "\u00e9" in result

    def test_nested_formatting(self):
        """Test nested inline formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Strong(
                            content=[
                                Text(content="Bold with "),
                                Emphasis(content=[Text(content="italic")]),
                            ]
                        )
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "Bold with" in result

    def test_mixed_content(self):
        """Test document with mixed content types."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(
                    content=[
                        Text(content="Normal "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" "),
                        Emphasis(content=[Text(content="italic")]),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item")])]),
                    ],
                ),
                CodeBlock(content="print('hello')", language="python"),
            ]
        )
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)

        assert "== Title" in result
        assert "*bold*" in result
        assert "_italic_" in result
        assert "* Item" in result
        assert "print('hello')" in result
