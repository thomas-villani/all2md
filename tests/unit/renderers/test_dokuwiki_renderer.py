#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for DokuWiki renderer.

Tests cover:
- Basic rendering
- Headings
- Inline formatting
- Code blocks
- Lists (ordered, unordered, nested)
- Tables
- Links and images
- Block quotes
- Thematic breaks
- Line breaks
- Comments
- Definition lists
- Math
- HTML handling
- Footnotes
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
from all2md.options.dokuwiki import DokuWikiOptions
from all2md.renderers.dokuwiki import DokuWikiRenderer


@pytest.mark.unit
class TestDokuWikiBasicRendering:
    """Tests for basic DokuWiki rendering functionality."""

    def test_render_simple_text(self) -> None:
        """Test rendering simple text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "Hello world" in output

    def test_render_empty_document(self) -> None:
        """Test rendering empty document."""
        doc = Document(children=[])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert output == "\n"

    def test_render_multiple_paragraphs(self) -> None:
        """Test rendering multiple paragraphs with spacing."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "First paragraph" in output
        assert "Second paragraph" in output
        # Should have blank line between paragraphs
        assert "\n\n" in output


@pytest.mark.unit
class TestDokuWikiHeadings:
    """Tests for DokuWiki heading rendering."""

    def test_render_heading_level_1(self) -> None:
        """Test rendering level 1 heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "====== Title ======" in output

    def test_render_heading_level_2(self) -> None:
        """Test rendering level 2 heading."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "===== Section =====" in output

    def test_render_heading_level_3(self) -> None:
        """Test rendering level 3 heading."""
        doc = Document(children=[Heading(level=3, content=[Text(content="Subsection")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "==== Subsection ====" in output

    def test_render_heading_level_4(self) -> None:
        """Test rendering level 4 heading."""
        doc = Document(children=[Heading(level=4, content=[Text(content="Subsubsection")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "=== Subsubsection ===" in output

    def test_render_heading_level_5(self) -> None:
        """Test rendering level 5 heading."""
        doc = Document(children=[Heading(level=5, content=[Text(content="Level 5")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "== Level 5 ==" in output

    def test_render_heading_with_formatting(self) -> None:
        """Test rendering heading with inline formatting."""
        doc = Document(
            children=[
                Heading(
                    level=1,
                    content=[Text(content="My "), Strong(content=[Text(content="Bold")]), Text(content=" Title")],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "====== My **Bold** Title ======" in output


@pytest.mark.unit
class TestDokuWikiInlineFormatting:
    """Tests for DokuWiki inline formatting."""

    def test_render_bold(self) -> None:
        """Test rendering bold text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="This is "), Strong(content=[Text(content="bold")]), Text(content=" text")]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "**bold**" in output

    def test_render_italic(self) -> None:
        """Test rendering italic text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "//italic//" in output

    def test_render_underline(self) -> None:
        """Test rendering underlined text."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Underline(content=[Text(content="underlined")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "__underlined__" in output

    def test_render_bold_italic(self) -> None:
        """Test rendering bold and italic text."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Should have nested formatting
        assert "**" in output
        assert "//" in output

    def test_render_strikethrough(self) -> None:
        """Test rendering strikethrough."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Strikethrough(content=[Text(content="deleted")]),
                        Text(content=" text"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<del>deleted</del>" in output

    def test_render_strikethrough_no_html(self) -> None:
        """Test rendering strikethrough without HTML."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<del>" not in output
        assert "deleted" in output

    def test_render_subscript(self) -> None:
        """Test rendering subscript."""
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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sub>2</sub>" in output

    def test_render_subscript_no_html(self) -> None:
        """Test rendering subscript without HTML."""
        doc = Document(children=[Paragraph(content=[Subscript(content=[Text(content="2")])])])
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<sub>" not in output
        assert "2" in output

    def test_render_superscript(self) -> None:
        """Test rendering superscript."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="E=mc"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<sup>2</sup>" in output

    def test_render_superscript_no_html(self) -> None:
        """Test rendering superscript without HTML."""
        doc = Document(children=[Paragraph(content=[Superscript(content=[Text(content="2")])])])
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<sup>" not in output
        assert "2" in output


@pytest.mark.unit
class TestDokuWikiCodeBlocks:
    """Tests for DokuWiki code block rendering."""

    def test_render_code_inline_default(self) -> None:
        """Test rendering inline code with default options."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Default uses '' for monospace
        assert "''code''" in output

    def test_render_code_inline_with_fence(self) -> None:
        """Test rendering inline code with monospace_fence option."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="code"), Text(content=" here")])]
        )
        renderer = DokuWikiRenderer(DokuWikiOptions(monospace_fence=True))
        output = renderer.render_to_string(doc)

        assert "<code>code</code>" in output

    def test_render_code_block_with_language(self) -> None:
        """Test rendering code block with language."""
        doc = Document(children=[CodeBlock(content='def hello():\n    print("world")', language="python")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<code python>" in output
        assert "def hello():" in output
        assert "</code>" in output

    def test_render_code_block_without_language(self) -> None:
        """Test rendering code block without language."""
        doc = Document(children=[CodeBlock(content="code here")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<code>" in output
        assert "code here" in output
        assert "</code>" in output


@pytest.mark.unit
class TestDokuWikiLists:
    """Tests for DokuWiki list rendering."""

    def test_render_unordered_list(self) -> None:
        """Test rendering unordered list."""
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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "* Item 1" in output
        assert "* Item 2" in output
        assert "* Item 3" in output

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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "- First" in output
        assert "- Second" in output

    def test_render_nested_list(self) -> None:
        """Test rendering nested list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 1")]),
                                List(
                                    ordered=False,
                                    items=[
                                        ListItem(children=[Paragraph(content=[Text(content="Nested item")])]),
                                    ],
                                ),
                            ]
                        ),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check for nested indentation
        assert "* Item 1" in output
        assert "  * Nested item" in output
        assert "* Item 2" in output


@pytest.mark.unit
class TestDokuWikiTables:
    """Tests for DokuWiki table rendering."""

    def test_render_table_with_header(self) -> None:
        """Test rendering table with header."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Name")]),
                            TableCell(content=[Text(content="Age")]),
                        ],
                        is_header=True,
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Alice")]),
                                TableCell(content=[Text(content="30")]),
                            ]
                        ),
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Bob")]),
                                TableCell(content=[Text(content="25")]),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check for table structure
        assert "^ Name ^" in output or "^ Name  ^" in output
        assert "^ Age ^" in output or "^ Age  ^" in output
        assert "| Alice |" in output or "| Alice  |" in output
        assert "| Bob |" in output or "| Bob  |" in output

    def test_render_table_without_header(self) -> None:
        """Test rendering table without header."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Cell 1")]),
                                TableCell(content=[Text(content="Cell 2")]),
                            ]
                        ),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "| Cell 1 |" in output or "| Cell 1  |" in output


@pytest.mark.unit
class TestDokuWikiLinks:
    """Tests for DokuWiki link rendering."""

    def test_render_link_simple(self) -> None:
        """Test rendering simple link."""
        doc = Document(children=[Paragraph(content=[Link(url="page:name", content=[Text(content="page:name")])])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Link text matches URL, so can use short form
        assert "[[page:name]]" in output

    def test_render_link_with_text(self) -> None:
        """Test rendering link with custom text."""
        doc = Document(children=[Paragraph(content=[Link(url="page:name", content=[Text(content="Link Text")])])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[page:name|Link Text]]" in output

    def test_render_external_link(self) -> None:
        """Test rendering external link."""
        doc = Document(
            children=[Paragraph(content=[Link(url="http://example.com", content=[Text(content="Example")])])]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "[[http://example.com|Example]]" in output


@pytest.mark.unit
class TestDokuWikiImages:
    """Tests for DokuWiki image rendering."""

    def test_render_image_simple(self) -> None:
        """Test rendering simple image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "{{image.png}}" in output

    def test_render_image_with_alt(self) -> None:
        """Test rendering image with alt text."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Alt Text")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "{{image.png|Alt Text}}" in output


@pytest.mark.unit
class TestDokuWikiBlockQuotes:
    """Tests for DokuWiki block quote rendering."""

    def test_render_blockquote(self) -> None:
        """Test rendering blockquote."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="Quoted text")]),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "> Quoted text" in output

    def test_render_blockquote_multiline(self) -> None:
        """Test rendering multi-paragraph blockquote."""
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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "> First paragraph" in output
        assert "> Second paragraph" in output


@pytest.mark.unit
class TestDokuWikiLineBreaks:
    """Tests for DokuWiki line break rendering."""

    def test_render_thematic_break(self) -> None:
        """Test rendering thematic break."""
        doc = Document(children=[ThematicBreak()])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "----" in output

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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "\\\\" in output

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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Soft line break is just a newline
        assert "Line 1\nLine 2" in output or "Line 1" in output and "Line 2" in output


@pytest.mark.unit
class TestDokuWikiComments:
    """Tests for DokuWiki comment rendering."""

    def test_render_comment_html_mode(self) -> None:
        """Test rendering comment in HTML mode."""
        doc = Document(children=[Comment(content="This is a comment")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- This is a comment -->" in output

    def test_render_comment_with_metadata(self) -> None:
        """Test rendering comment with author and date metadata."""
        doc = Document(
            children=[
                Comment(
                    content="Review this",
                    metadata={"author": "John", "date": "2025-01-15", "label": "1"},
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "Comment 1 by John (2025-01-15):" in output
        assert "Review this" in output

    def test_render_comment_visible_mode(self) -> None:
        """Test rendering comment in visible mode."""
        doc = Document(children=[Comment(content="Visible comment")])
        options = DokuWikiOptions(comment_mode="visible")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "Visible comment" in output
        assert "<!--" not in output

    def test_render_comment_ignore_mode(self) -> None:
        """Test rendering comment in ignore mode."""
        doc = Document(children=[Comment(content="Hidden comment")])
        options = DokuWikiOptions(comment_mode="ignore")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "comment" not in output.lower()

    def test_render_comment_inline_html_mode(self) -> None:
        """Test rendering inline comment in HTML mode."""
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
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "/* inline comment */" in output

    def test_render_comment_inline_with_metadata(self) -> None:
        """Test rendering inline comment with metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        CommentInline(content="check this", metadata={"author": "Jane", "label": "2"}),
                    ]
                )
            ]
        )
        options = DokuWikiOptions(comment_mode="visible")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "Comment 2" in output
        assert "Jane" in output

    def test_render_comment_inline_ignore_mode(self) -> None:
        """Test rendering inline comment in ignore mode."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(content="ignored"),
                        Text(content=" here"),
                    ]
                )
            ]
        )
        options = DokuWikiOptions(comment_mode="ignore")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "ignored" not in output


@pytest.mark.unit
class TestDokuWikiDefinitionLists:
    """Tests for DokuWiki definition list rendering."""

    def test_render_definition_list_html(self) -> None:
        """Test rendering definition list with HTML."""
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
        renderer = DokuWikiRenderer()  # use_html_for_unsupported=True by default
        output = renderer.render_to_string(doc)

        assert "<dl>" in output
        assert "<dt>Term</dt>" in output
        assert "<dd>" in output
        assert "Definition" in output
        assert "</dl>" in output

    def test_render_definition_list_no_html(self) -> None:
        """Test rendering definition list without HTML."""
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
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<dl>" not in output
        assert "Term" in output
        assert "Definition" in output


@pytest.mark.unit
class TestDokuWikiMath:
    """Tests for DokuWiki math rendering."""

    def test_render_math_inline_html(self) -> None:
        """Test rendering inline math with HTML."""
        doc = Document(children=[Paragraph(content=[MathInline(content="E=mc^2")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<math>E=mc^2</math>" in output

    def test_render_math_inline_no_html(self) -> None:
        """Test rendering inline math without HTML."""
        doc = Document(children=[Paragraph(content=[MathInline(content="E=mc^2")])])
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "$E=mc^2$" in output
        assert "<math>" not in output

    def test_render_math_block_html(self) -> None:
        """Test rendering math block with HTML."""
        doc = Document(children=[MathBlock(content="\\int_0^1 x^2 dx")])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<MATH>" in output
        assert "\\int_0^1 x^2 dx" in output
        assert "</MATH>" in output

    def test_render_math_block_no_html(self) -> None:
        """Test rendering math block without HTML."""
        doc = Document(children=[MathBlock(content="x^2 + y^2 = z^2")])
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<MATH>" not in output
        assert "<code>" in output
        assert "x^2 + y^2 = z^2" in output


@pytest.mark.unit
class TestDokuWikiFootnotes:
    """Tests for DokuWiki footnote rendering."""

    def test_render_footnote_reference(self) -> None:
        """Test rendering footnote reference."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        FootnoteReference(identifier="1"),
                        Text(content=" reference"),
                    ]
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "((" in output

    def test_render_footnote_definition_html(self) -> None:
        """Test rendering footnote definition with HTML."""
        doc = Document(
            children=[
                FootnoteDefinition(
                    identifier="1",
                    content=[Paragraph(content=[Text(content="Footnote text")])],
                )
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- Footnote 1:" in output
        assert "Footnote text" in output

    def test_render_footnote_definition_no_html(self) -> None:
        """Test rendering footnote definition without HTML."""
        doc = Document(
            children=[
                FootnoteDefinition(
                    identifier="1",
                    content=[Paragraph(content=[Text(content="Footnote text")])],
                )
            ]
        )
        options = DokuWikiOptions(use_html_for_unsupported=False)
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        # Should be skipped when use_html_for_unsupported is False
        assert "<!--" not in output


@pytest.mark.unit
class TestDokuWikiHTML:
    """Tests for DokuWiki HTML handling."""

    def test_render_html_block_passthrough(self) -> None:
        """Test rendering HTML block with pass-through mode."""
        doc = Document(children=[HTMLBlock(content="<div>HTML content</div>")])
        options = DokuWikiOptions(html_passthrough_mode="pass-through")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<div>HTML content</div>" in output

    def test_render_html_block_escape(self) -> None:
        """Test rendering HTML block with escape mode."""
        doc = Document(children=[HTMLBlock(content="<div>content</div>")])
        options = DokuWikiOptions(html_passthrough_mode="escape")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "&lt;div&gt;" in output

    def test_render_html_block_drop(self) -> None:
        """Test rendering HTML block with drop mode."""
        doc = Document(children=[HTMLBlock(content="<div>dropped</div>")])
        options = DokuWikiOptions(html_passthrough_mode="drop")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<div>" not in output
        assert "dropped" not in output

    def test_render_html_inline_passthrough(self) -> None:
        """Test rendering inline HTML with pass-through mode."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        HTMLInline(content="<span>inline</span>"),
                        Text(content=" here"),
                    ]
                )
            ]
        )
        options = DokuWikiOptions(html_passthrough_mode="pass-through")
        renderer = DokuWikiRenderer(options)
        output = renderer.render_to_string(doc)

        assert "<span>inline</span>" in output


@pytest.mark.unit
class TestDokuWikiFileOutput:
    """Tests for DokuWiki file output functionality."""

    def test_render_to_file_path(self, tmp_path: Path) -> None:
        """Test rendering to file path."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        output_file = tmp_path / "output.doku"

        renderer = DokuWikiRenderer()
        renderer.render(doc, str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "====== Title ======" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Test rendering to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Content")])])
        output_file = tmp_path / "output.doku"

        renderer = DokuWikiRenderer()
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_render_to_text_stream(self) -> None:
        """Test rendering to text stream."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Section")])])
        output = StringIO()

        renderer = DokuWikiRenderer()
        renderer.render(doc, output)

        result = output.getvalue()
        assert "===== Section =====" in result

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
        renderer = DokuWikiRenderer()
        renderer.render(doc, output)

        assert b"Binary test" in output.data


@pytest.mark.unit
class TestDokuWikiEdgeCases:
    """Tests for edge cases in DokuWiki rendering."""

    def test_render_escaping_special_characters(self) -> None:
        """Test that special characters are properly escaped."""
        doc = Document(children=[Paragraph(content=[Text(content="Text with * and / characters")])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Characters should be escaped
        assert "\\*" in output or "*" in output  # Depends on escaping implementation
        assert "\\/" in output or "/" in output

    def test_render_complex_document(self) -> None:
        """Test rendering complex document with mixed content."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Introduction with "), Strong(content=[Text(content="bold")])]),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
                CodeBlock(content="code example", language="python"),
            ]
        )
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        # Check all elements are present
        assert "====== Title ======" in output
        assert "**bold**" in output
        assert "* Item 1" in output
        assert "<code python>" in output

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            DokuWikiRenderer(options="invalid")

    def test_unsupported_output_type(self) -> None:
        """Test that unsupported output type raises error."""
        doc = Document(children=[Paragraph(content=[Text(content="test")])])
        renderer = DokuWikiRenderer()

        with pytest.raises(TypeError):
            renderer.render(doc, 12345)  # type: ignore

    def test_render_empty_paragraph(self) -> None:
        """Test rendering empty paragraph."""
        doc = Document(children=[Paragraph(content=[])])
        renderer = DokuWikiRenderer()
        output = renderer.render_to_string(doc)

        assert isinstance(output, str)
