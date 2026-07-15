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
from all2md.options import MarkdownRendererOptions
from all2md.renderers.markdown import MarkdownRenderer
from all2md.utils.flavors import GFMFlavor


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
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Hello world"

    def test_render_multiple_paragraphs(self):
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "First paragraph\n\nSecond paragraph"


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering options."""

    def test_inline_math_default_latex(self) -> None:
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = MarkdownRenderer(MarkdownRendererOptions(flavor="gfm"))
        result = renderer.render_to_string(doc)
        assert "$x^2$" in result

    def test_inline_math_mathml_option(self) -> None:
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        MathInline(
                            content="x^2",
                            notation="latex",
                            representations={"mathml": "<math><msup><mi>x</mi><mn>2</mn></msup></math>"},
                        )
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer(MarkdownRendererOptions(math_mode="mathml"))
        result = renderer.render_to_string(doc)
        assert '<span class="math math-inline" data-notation="mathml">' in result

    def test_inline_math_commonmark_html_fallback(self) -> None:
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = MarkdownRenderer(MarkdownRendererOptions(flavor="commonmark"))
        result = renderer.render_to_string(doc)
        assert '<span class="math math-inline" data-notation="latex">' in result

    def test_block_math_mathml_mode(self) -> None:
        doc = Document(
            children=[
                MathBlock(
                    content="x^2",
                    notation="latex",
                    representations={"mathml": "<math><msup><mi>x</mi><mn>2</mn></msup></math>"},
                )
            ]
        )
        renderer = MarkdownRenderer(MarkdownRendererOptions(math_mode="mathml"))
        result = renderer.render_to_string(doc)
        assert '<div class="math math-block" data-notation="mathml">' in result


@pytest.mark.unit
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1_hash(self):
        """Test rendering h1 with hash style."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "# Title"

    def test_heading_level_2_hash(self):
        """Test rendering h2 with hash style."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "## Subtitle"

    def test_heading_setext_h1(self):
        """Test rendering h1 with setext style."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "Title\n====="

    def test_heading_setext_h2(self):
        """Test rendering h2 with setext style."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        options = MarkdownRendererOptions(use_hash_headings=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "Subtitle\n--------"

    def test_heading_with_formatting(self):
        """Test rendering heading with inline formatting."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Welcome "), Strong(content=[Text(content="Home")])])]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "# Welcome **Home**"


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting nodes."""

    def test_emphasis(self):
        """Test rendering emphasis (italic)."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic text")])])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "*italic text*"

    def test_emphasis_with_underscore(self):
        """Test rendering emphasis with underscore symbol."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        options = MarkdownRendererOptions(emphasis_symbol="_")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "_italic_"

    def test_strong(self):
        """Test rendering strong (bold)."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold text")])])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "**bold text**"

    def test_code_inline(self):
        """Test rendering inline code."""
        doc = Document(children=[Paragraph(content=[Code(content="print()")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "`print()`"

    def test_code_with_backticks(self):
        """Test rendering inline code containing backticks."""
        doc = Document(children=[Paragraph(content=[Code(content="`tick`")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```tick```"

    def test_combined_formatting(self):
        """Test rendering combined inline formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content="."),
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "This is **bold** and *italic*."


@pytest.mark.unit
class TestExtendedInlineFormatting:
    """Tests for extended inline formatting."""

    def test_strikethrough_gfm(self):
        """Test strikethrough with GFM flavor."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        options = MarkdownRendererOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "~~deleted~~"

    def test_strikethrough_commonmark(self):
        """Test strikethrough fallback with CommonMark."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        options = MarkdownRendererOptions(flavor="commonmark")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<del>deleted</del>"

    def test_underline_html_mode(self):
        """Test underline with HTML mode."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        options = MarkdownRendererOptions(underline_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<u>underlined</u>"

    def test_superscript_html_mode(self):
        """Test superscript with HTML mode."""
        doc = Document(children=[Paragraph(content=[Superscript(content=[Text(content="2")])])])
        options = MarkdownRendererOptions(superscript_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<sup>2</sup>"

    def test_subscript_html_mode(self):
        """Test subscript with HTML mode."""
        doc = Document(children=[Paragraph(content=[Subscript(content=[Text(content="0")])])])
        options = MarkdownRendererOptions(subscript_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert result == "<sub>0</sub>"


@pytest.mark.unit
class TestLinks:
    """Tests for link rendering."""

    def test_simple_link(self):
        """Test rendering a simple link."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Example")])])]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "[Example](https://example.com)"

    def test_link_with_title(self):
        """Test rendering a link with title."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Link(url="https://example.com", content=[Text(content="Example")], title="Example Site")]
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == '[Example](https://example.com "Example Site")'


@pytest.mark.unit
class TestImages:
    """Tests for image rendering."""

    def test_simple_image(self):
        """Test rendering a simple image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="An image")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "![An image](image.png)"

    def test_image_with_title(self):
        """Test rendering an image with title."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="An image", title="Image Title")])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == '![An image](image.png "Image Title")'


@pytest.mark.unit
class TestCodeBlocks:
    """Tests for code block rendering."""

    def test_code_block_simple(self):
        """Test rendering a simple code block."""
        doc = Document(children=[CodeBlock(content="print('hello')")])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```\nprint('hello')\n```"

    def test_code_block_with_language(self):
        """Test rendering a code block with language."""
        doc = Document(children=[CodeBlock(content="x = 1", language="python")])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "```python\nx = 1\n```"


@pytest.mark.unit
class TestBlockQuotes:
    """Tests for block quote rendering."""

    def test_simple_blockquote(self):
        """Test rendering a simple block quote."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])])])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "> Quoted text"

    def test_multi_paragraph_blockquote(self):
        """Test rendering a block quote with multiple paragraphs."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[Paragraph(content=[Text(content="First")]), Paragraph(content=[Text(content="Second")])]
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        assert all(line.startswith(">") for line in lines)


@pytest.mark.unit
class TestLists:
    """Tests for list rendering."""

    def test_unordered_list(self):
        """Test rendering an unordered list."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="One")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Two")])]),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "* One\n* Two"

    def test_ordered_list(self):
        """Test rendering an ordered list."""
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
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "1. First\n2. Second"

    def test_ordered_list_with_start(self):
        """Test rendering an ordered list with custom start."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=5,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Fifth")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Sixth")])]),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "5. Fifth\n6. Sixth"

    def test_task_list_gfm(self):
        """Test rendering task lists with GFM flavor."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Done")])], task_status="checked"),
                        ListItem(children=[Paragraph(content=[Text(content="Todo")])], task_status="unchecked"),
                    ],
                )
            ]
        )
        options = MarkdownRendererOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "* [x]" in result
        assert "* [ ]" in result

    def test_nested_unordered_list(self):
        """Test rendering nested unordered lists with proper indentation."""
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
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")]), nested_list]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        # First item should not be indented
        assert lines[0] == "* Item 1"
        # Nested items should be indented by 2 spaces (marker "* " is 2 chars)
        assert lines[1] == "  - Nested 1"
        assert lines[2] == "  - Nested 2"
        # Second top-level item should not be indented
        assert lines[3] == "* Item 2"

    def test_nested_ordered_list(self):
        """Test rendering nested ordered lists with proper indentation."""
        nested_list = List(
            ordered=True,
            items=[
                ListItem(children=[Paragraph(content=[Text(content="Nested A")])]),
                ListItem(children=[Paragraph(content=[Text(content="Nested B")])]),
            ],
        )
        doc = Document(
            children=[
                List(
                    ordered=True,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")]), nested_list]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        assert lines[0] == "1. First"
        # Nested items indented by 3 spaces (marker "1. " is 3 chars)
        assert lines[1] == "   1. Nested A"
        assert lines[2] == "   2. Nested B"
        assert lines[3] == "2. Second"

    def test_multi_paragraph_list_item(self):
        """Test rendering list items with multiple paragraphs."""
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="First paragraph")]),
                                Paragraph(content=[Text(content="Second paragraph")]),
                            ]
                        ),
                        ListItem(children=[Paragraph(content=[Text(content="Next item")])]),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        assert lines[0] == "* First paragraph"
        # Second paragraph indented by 2 spaces to align with first
        assert lines[1] == "  Second paragraph"
        assert lines[2] == "* Next item"

    def test_soft_wrapped_paragraph_indented_in_item(self):
        """A multi-line (soft-wrapped) paragraph in a list item keeps its indent.

        The continuation line was emitted at column zero, so on reparse it became a
        lazy continuation that collapsed the wrapped lines into one; a nested item
        broke apart entirely.
        """
        from all2md import convert

        opts = MarkdownRendererOptions(flavor="gfm")
        source = "* a line that\n  wraps here\n"
        once = convert(source, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)

        assert once == twice, "soft-wrapped list item is not idempotent"
        # Continuation aligned under the marker's content column, not at column zero.
        assert "* a line that\n  wraps here" in once
        assert "\nwraps here" not in once

    def test_nested_list_as_first_child_not_double_indented(self):
        """A nested list that is a list item's first child must not double-indent.

        The first-child branch cleared the indent stack but left ``_in_list`` set, so a
        nested list added its own indent level on top of the marker -- rendering the item
        as ``1.     - x`` (five stray spaces) instead of ``1. - x``.
        """
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=1,
                    items=[
                        ListItem(
                            children=[
                                List(
                                    ordered=False,
                                    items=[ListItem(children=[Paragraph(content=[Text(content="alpha")])])],
                                )
                            ]
                        )
                    ],
                )
            ]
        )
        result = MarkdownRenderer().render_to_string(doc)
        assert result.splitlines()[0] == "1. - alpha"

    def test_ordered_task_multiline_roundtrips(self):
        """The Part 6 shape: an ordered item wrapping a multi-line task item."""
        from all2md import convert

        opts = MarkdownRendererOptions(flavor="gfm")
        source = "1. - [x] first line\n     second line\n"
        once = convert(source, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)

        assert once == twice, "ordered>task>multiline is not idempotent"
        # Clean marker (no stray padding) and the continuation aligned under the content.
        assert once.startswith("1. - [x] first line\n")
        assert "\nsecond line" not in once  # never at column zero

    def test_deeply_nested_list(self):
        """Test rendering deeply nested lists (3 levels)."""
        level3_list = List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Level 3")])])])
        level2_list = List(
            ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Level 2")]), level3_list])]
        )
        doc = Document(
            children=[
                List(
                    ordered=False,
                    items=[ListItem(children=[Paragraph(content=[Text(content="Level 1")]), level2_list])],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        assert lines[0] == "* Level 1"
        assert lines[1] == "  - Level 2"
        # Level 3 indented by 4 spaces (2 for level 1 + 2 for level 2)
        assert lines[2] == "    + Level 3"

    def test_ordered_list_varying_marker_widths(self):
        """Test rendering ordered lists with varying marker widths (1-9, 10-99)."""
        doc = Document(
            children=[
                List(
                    ordered=True,
                    start=8,
                    tight=False,
                    items=[
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 8")]),
                                Paragraph(content=[Text(content="Continuation 8")]),
                            ]
                        ),
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 9")]),
                                Paragraph(content=[Text(content="Continuation 9")]),
                            ]
                        ),
                        ListItem(
                            children=[
                                Paragraph(content=[Text(content="Item 10")]),
                                Paragraph(content=[Text(content="Continuation 10")]),
                            ]
                        ),
                    ],
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        lines = result.split("\n")
        # Markers are aligned by width, and because the list is loose the two
        # paragraphs inside each item are separated by a blank line (rendering
        # them adjacent would lazily merge them into one paragraph on reparse).
        assert lines[0] == "8. Item 8"
        assert lines[1] == ""
        assert lines[2] == "   Continuation 8"  # 3 spaces (marker "8. ")
        assert lines[3] == ""  # blank line between items
        assert lines[4] == "9. Item 9"
        assert lines[5] == ""
        assert lines[6] == "   Continuation 9"  # 3 spaces (marker "9. ")
        assert lines[7] == ""  # blank line
        assert lines[8] == "10. Item 10"
        assert lines[9] == ""
        assert lines[10] == "    Continuation 10"  # 4 spaces (marker "10. ")

    def test_loose_multiparagraph_list_roundtrips_without_collapsing(self):
        """A loose list item with two paragraphs must survive a reparse.

        Regression: the parser read the loose/tight flag only from ``attrs``,
        where mistune 3.x never puts it, so every list was treated as tight and
        the renderer emitted the item's second paragraph on the immediately
        following line. On reparse that line is a lazy continuation, silently
        merging the two paragraphs into one.
        """
        from all2md import convert, to_ast

        source = "1. first\n\n   second para\n\n2. next\n"
        opts = MarkdownRendererOptions(flavor="pandoc")

        once = convert(source, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)
        assert once == twice, "loose multi-paragraph list is not idempotent"

        # The two paragraphs stay separated by a blank line, never collapsed.
        assert "first\n\n   second para" in once
        assert "first\nsecond para" not in once

        # The AST still carries a loose list whose first item has two paragraphs.
        ast = to_ast(source, source_format="markdown")
        lists = [c for c in ast.children if isinstance(c, List)]
        assert lists and lists[0].tight is False
        first_item_paragraphs = [c for c in lists[0].items[0].children if isinstance(c, Paragraph)]
        assert len(first_item_paragraphs) == 2

    def test_list_item_block_children_stay_indented_on_roundtrip(self):
        """A code block or quote inside a list item must not break out.

        The code-block and block-quote renderers ignored the current
        indentation, so as a later child of a list item they landed at column
        zero. On reparse they became siblings of the list rather than children
        of the item, dropping the trailing paragraph out of the item too.
        """
        from all2md import convert, to_ast

        opts = MarkdownRendererOptions(flavor="pandoc")
        for source in (
            "- a\n\n  ```\n  x\n  ```\n\n  after\n",  # para, code, para
            "- item\n\n  > quoted\n",  # para then block quote
        ):
            once = convert(source, source_format="markdown", target_format="markdown", renderer_options=opts)
            twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)
            assert once == twice, f"list item with a block child is not idempotent: {source!r}"

            # The block child stays inside the single list, not beside it.
            ast = to_ast(once, source_format="markdown")
            assert sum(isinstance(c, List) for c in ast.children) == 1
            assert len(ast.children) == 1

    def test_task_list_item_continuation_is_not_indented_as_code(self):
        """A task item's second paragraph must reparse as a paragraph.

        The checkbox ("[ ] ") was counted into the marker width, so a
        continuation paragraph indented six spaces and reparsed as an indented
        code block. Continuations indent to the base marker width instead.
        """
        from all2md import convert, to_ast
        from all2md.ast import CodeBlock

        opts = MarkdownRendererOptions(flavor="pandoc")
        source = "- [ ] task\n\n  more detail\n"

        once = convert(source, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)
        assert once == twice, "task-list continuation is not idempotent"

        ast = to_ast(once, source_format="markdown")
        item = [c for c in ast.children if isinstance(c, List)][0].items[0]
        assert item.task_status
        assert not any(isinstance(c, CodeBlock) for c in item.children)
        assert sum(isinstance(c, Paragraph) for c in item.children) == 2


@pytest.mark.unit
class TestTables:
    """Tests for table rendering."""

    def test_simple_table_gfm(self):
        """Test rendering a simple table with GFM."""
        header = TableRow(
            cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])], is_header=True
        )

        row1 = TableRow(cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])])

        table = Table(header=header, rows=[row1], alignments=["left", "right"])

        doc = Document(children=[table])
        options = MarkdownRendererOptions(flavor=GFMFlavor())
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        assert "Name" in result
        assert "Alice" in result
        assert "|" in result

    def test_table_fallback_commonmark(self):
        """Test table fallback to HTML with CommonMark."""
        header = TableRow(cells=[TableCell(content=[Text(content="Header")])], is_header=True)

        table = Table(header=header, rows=[])

        doc = Document(children=[table])
        options = MarkdownRendererOptions(flavor="commonmark")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        assert "<table>" in result
        assert "<th>Header</th>" in result


@pytest.mark.unit
class TestThematicBreak:
    """Tests for thematic break rendering."""

    def test_thematic_break(self):
        """Test rendering a thematic break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "---" in result


@pytest.mark.unit
class TestHTMLNodes:
    """Tests for HTML node rendering."""

    def test_html_block(self):
        """Test rendering an HTML block."""
        doc = Document(children=[HTMLBlock(content="<div>Custom HTML</div>")])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "&lt;div&gt;Custom HTML&lt;/div&gt;"

        renderer = MarkdownRenderer(MarkdownRendererOptions(html_passthrough_mode="pass-through"))
        result = renderer.render_to_string(doc)
        assert result == "<div>Custom HTML</div>"

    def test_html_inline(self):
        """Test rendering inline HTML."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        HTMLInline(content="<span>HTML</span>"),
                        Text(content=" inline"),
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert result == "Text with &lt;span&gt;HTML&lt;/span&gt; inline"

        renderer = MarkdownRenderer(MarkdownRendererOptions(html_passthrough_mode="pass-through"))
        result = renderer.render_to_string(doc)
        assert result == "Text with <span>HTML</span> inline"


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_soft_line_break(self):
        """Test rendering a soft line break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First line"), LineBreak(soft=True), Text(content="Second line")])
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "First line\nSecond line" in result

    def test_hard_line_break(self):
        """Test rendering a hard line break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First line"), LineBreak(soft=False), Text(content="Second line")])
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "First line  \nSecond line" in result


@pytest.mark.unit
class TestComplexDocuments:
    """Tests for complex nested documents."""

    def test_document_with_mixed_content(self):
        """Test rendering a document with mixed content types."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(
                    content=[
                        Text(content="A paragraph with "),
                        Strong(content=[Text(content="bold")]),
                        Text(content=" and "),
                        Emphasis(content=[Text(content="italic")]),
                        Text(content="."),
                    ]
                ),
                List(
                    ordered=False,
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                ),
                CodeBlock(content="code here", language="python"),
            ]
        )

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
        doc = Document(children=[Paragraph(content=[Text(content="*asterisks* and [brackets]")])])
        options = MarkdownRendererOptions(escape_special=True)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "\\*" in result
        assert "\\[" in result

    def test_no_escape_when_disabled(self):
        """Test that escaping can be disabled."""
        doc = Document(children=[Paragraph(content=[Text(content="*asterisks*")])])
        options = MarkdownRendererOptions(escape_special=False)
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        assert "\\*" not in result
        assert "*asterisks*" in result


@pytest.mark.unit
class TestFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_roundtrips_under_default_flavor(self):
        """Footnotes must roundtrip as Markdown under the default (GFM) flavor.

        The default ``unsupported_inline_mode='html'`` made GFM emit a raw
        ``<sup>`` reference and ``<div id="fn-...">`` definition, which the
        default html_passthrough policy then escaped to ``&lt;sup&gt;`` on the
        next pass -- output the renderer's own parser corrupts.
        """
        from all2md import convert

        source = "Text with a note.[^1]\n\n[^1]: The footnote body.\n"
        once = convert(source, source_format="markdown", target_format="markdown")
        twice = convert(once, source_format="markdown", target_format="markdown")

        assert once == twice, "footnote roundtrip is not idempotent"
        assert "[^1]" in once
        assert "[^1]: The footnote body." in once
        assert "<sup>" not in once
        assert "fn-1" not in once

    def test_multiparagraph_footnote_definition_does_not_collapse(self):
        """A multi-paragraph footnote definition keeps both paragraphs on reparse."""
        from all2md import convert, to_ast
        from all2md.ast.nodes import FootnoteDefinition, Paragraph

        source = "See note.[^1]\n\n[^1]: First paragraph.\n\n    Second paragraph.\n"
        once = convert(source, source_format="markdown", target_format="markdown")
        twice = convert(once, source_format="markdown", target_format="markdown")

        assert once == twice
        doc = to_ast(once, source_format="markdown")
        defs = [n for n in doc.children if isinstance(n, FootnoteDefinition)]
        assert len(defs) == 1
        assert sum(1 for c in defs[0].content if isinstance(c, Paragraph)) == 2

    def test_footnote_explicit_html_mode_still_emits_html(self):
        """An explicit ``unsupported_inline_mode='html'`` is still honored."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Body")])]),
            ]
        )
        options = MarkdownRendererOptions(flavor="gfm", unsupported_inline_mode="html")
        result = MarkdownRenderer(options).render_to_string(doc)
        assert "<sup>1</sup>" in result
        assert '<div id="fn-1">' in result

    def test_footnote_reference_pandoc_flavor(self):
        """Test footnote reference with Pandoc flavor (supports footnotes)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")]),
                FootnoteDefinition(identifier="1", content=[Text(content="Footnote text")]),
            ]
        )
        options = MarkdownRendererOptions(flavor="pandoc")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        assert "[^1]" in result
        assert "[^1]: Footnote text" in result

    def test_footnote_unsupported_flavor_uses_correct_option(self):
        """Test that unsupported footnote definition uses unsupported_inline_mode (bug fix)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="note1")]),
                FootnoteDefinition(identifier="note1", content=[Text(content="Footnote text")]),
            ]
        )
        # CommonMark doesn't support footnotes
        options = MarkdownRendererOptions(flavor="commonmark", unsupported_inline_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Reference should use HTML
        assert "<sup>note1</sup>" in result
        # Definition should use HTML (not drop it)
        assert '<div id="fn-note1">' in result or "Footnote text" in result

    def test_footnote_definition_drop_mode(self):
        """Test footnote definition with drop mode for unsupported flavors."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text")]),
                FootnoteDefinition(identifier="note1", content=[Text(content="Footnote text")]),
            ]
        )
        # CommonMark doesn't support footnotes
        options = MarkdownRendererOptions(flavor="commonmark", unsupported_inline_mode="drop")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Definition should be dropped
        assert "Footnote text" not in result


@pytest.mark.unit
class TestHTMLSanitization:
    """Tests for HTML sanitization options."""

    def test_html_block_escape_default(self):
        """Test that HTML blocks are escaped by default (secure-by-default)."""
        doc = Document(children=[HTMLBlock(content="<script>alert('xss')</script>")])
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        # Should be escaped
        assert "&lt;script&gt;" in result
        assert "&lt;/script&gt;" in result
        # Should not contain raw HTML
        assert "<script>" not in result

    def test_html_inline_escape_default(self):
        """Test that inline HTML is escaped by default (secure-by-default)."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        HTMLInline(content="<img src=x onerror=alert(1)>"),
                        Text(content=" inline"),
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        # Should be escaped
        assert "&lt;img" in result
        assert "&gt;" in result
        # Should not contain raw HTML
        assert "<img" not in result

    def test_html_sanitization_pass_through_mode(self):
        """Test HTML pass-through mode (allows raw HTML)."""
        doc = Document(children=[HTMLBlock(content="<div class='custom'>Content</div>")])
        options = MarkdownRendererOptions(html_passthrough_mode="pass-through")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Should pass through unchanged
        assert "<div class='custom'>Content</div>" in result

    def test_html_sanitization_escape_mode(self):
        """Test HTML escape mode (shows HTML as text)."""
        doc = Document(children=[HTMLBlock(content="<script>dangerous()</script>")])
        options = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Should be HTML-escaped
        assert "&lt;script&gt;dangerous()&lt;/script&gt;" in result
        assert "<script>" not in result

    def test_html_sanitization_drop_mode(self):
        """Test HTML drop mode (removes HTML entirely)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                HTMLBlock(content="<div>Removed content</div>"),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        options = MarkdownRendererOptions(html_passthrough_mode="drop")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # HTML content should be removed
        assert "Removed content" not in result
        assert "<div>" not in result
        # Other content should remain
        assert "Before" in result
        assert "After" in result

    def test_html_sanitization_sanitize_mode(self):
        """Test HTML sanitize mode (removes dangerous elements)."""
        doc = Document(children=[HTMLBlock(content="<p>Safe paragraph</p><script>alert('bad')</script>")])
        options = MarkdownRendererOptions(html_passthrough_mode="sanitize")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Safe HTML should be preserved
        assert "<p>" in result or "Safe paragraph" in result
        # Dangerous script tag should be removed (text content may remain, which is expected)
        assert "<script>" not in result
        assert "</script>" not in result

    def test_html_inline_sanitization_modes(self):
        """Test that inline HTML respects all sanitization modes."""
        html_content = "<span onclick='bad()'>Text</span>"

        # Escape mode
        doc_escape = Document(children=[Paragraph(content=[HTMLInline(content=html_content)])])
        options_escape = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer_escape = MarkdownRenderer(options_escape)
        result_escape = renderer_escape.render_to_string(doc_escape)
        assert "&lt;span" in result_escape

        # Drop mode
        doc_drop = Document(
            children=[
                Paragraph(content=[Text(content="Before "), HTMLInline(content=html_content), Text(content=" After")])
            ]
        )
        options_drop = MarkdownRendererOptions(html_passthrough_mode="drop")
        renderer_drop = MarkdownRenderer(options_drop)
        result_drop = renderer_drop.render_to_string(doc_drop)
        assert "Before  After" in result_drop or "Before After" in result_drop
        assert "<span" not in result_drop

    def test_html_sanitization_does_not_affect_code_blocks(self):
        """Test that HTML sanitization does NOT affect code blocks."""
        doc = Document(children=[CodeBlock(content="<script>alert('This is code')</script>", language="html")])
        # Even with escape mode, code blocks should render their content unchanged
        options = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Code block should contain the raw HTML (not escaped)
        assert "```html\n<script>alert('This is code')</script>\n```" in result

    def test_html_sanitization_does_not_affect_inline_code(self):
        """Test that HTML sanitization does NOT affect inline code."""
        doc = Document(children=[Paragraph(content=[Text(content="Example: "), Code(content="<div>code</div>")])])
        # Even with escape mode, inline code should render their content unchanged
        options = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Inline code should contain the raw HTML (not escaped)
        assert "`<div>code</div>`" in result

    def test_html_sanitization_multiple_html_blocks(self):
        """Test HTML sanitization with multiple HTML blocks."""
        doc = Document(
            children=[
                HTMLBlock(content="<div>Block 1</div>"),
                Paragraph(content=[Text(content="Regular text")]),
                HTMLBlock(content="<script>evil()</script>"),
            ]
        )
        options = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Both HTML blocks should be escaped
        assert "&lt;div&gt;Block 1&lt;/div&gt;" in result
        assert "&lt;script&gt;evil()&lt;/script&gt;" in result
        # Regular text unaffected
        assert "Regular text" in result

    def test_html_sanitization_empty_html_block(self):
        """Test HTML sanitization with empty HTML content."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                HTMLBlock(content=""),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        options = MarkdownRendererOptions(html_passthrough_mode="escape")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)
        # Should not produce errors
        assert "Before" in result
        assert "After" in result


@pytest.mark.unit
class TestDefinitionListRendering:
    """Tests for definition list rendering with smart fallback behavior."""

    def test_gfm_default_uses_pandoc_syntax(self):
        """Test that GFM flavor with default settings uses Pandoc-style syntax."""
        # GFM doesn't support definition lists, but with default settings,
        # should use force mode (Pandoc syntax) instead of HTML
        term = DefinitionTerm(content=[Text(content="Python")])
        description = DefinitionDescription(
            content=[Paragraph(content=[Text(content="A high-level programming language")])]
        )
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        # Default GFM options (no explicit unsupported_inline_mode)
        options = MarkdownRendererOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should use Pandoc syntax, NOT HTML tags
        assert "Python\n:" in result or "Python\n :" in result
        assert "A high-level programming language" in result
        assert "<dl>" not in result
        assert "<dt>" not in result
        assert "<dd>" not in result

    def test_explicit_html_mode_preserved(self):
        """Test that explicit HTML mode is respected for backward compatibility."""
        term = DefinitionTerm(content=[Text(content="Python")])
        description = DefinitionDescription(content=[Paragraph(content=[Text(content="A programming language")])])
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        # Explicitly set HTML mode
        options = MarkdownRendererOptions(flavor="gfm", unsupported_inline_mode="html")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should use HTML tags when explicitly requested
        assert "<dl>" in result
        assert "<dt>" in result
        assert "Python" in result
        assert "<dd>" in result
        assert "A programming language" in result

    def test_explicit_force_mode(self):
        """Test that explicit force mode uses Pandoc syntax."""
        term = DefinitionTerm(content=[Text(content="Ruby")])
        description = DefinitionDescription(content=[Paragraph(content=[Text(content="Another programming language")])])
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        # Explicitly set force mode
        options = MarkdownRendererOptions(flavor="gfm", unsupported_inline_mode="force")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should use Pandoc syntax
        assert "Ruby\n:" in result or "Ruby\n :" in result
        assert "Another programming language" in result
        assert "<dl>" not in result

    def test_explicit_plain_mode(self):
        """Test that explicit plain mode strips structure."""
        term = DefinitionTerm(content=[Text(content="JavaScript")])
        description = DefinitionDescription(content=[Paragraph(content=[Text(content="A scripting language")])])
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        # Explicitly set plain mode
        options = MarkdownRendererOptions(flavor="gfm", unsupported_inline_mode="plain")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should output plain text without structure
        assert "JavaScript" in result
        assert "A scripting language" in result
        assert ":" not in result  # No colon from Pandoc syntax
        assert "<dl>" not in result  # No HTML

    def test_pandoc_flavor_uses_native_syntax(self):
        """Test that Pandoc flavor (which supports definition lists) uses native syntax."""
        term = DefinitionTerm(content=[Text(content="Rust")])
        description = DefinitionDescription(
            content=[Paragraph(content=[Text(content="A systems programming language")])]
        )
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        # Pandoc flavor supports definition lists natively
        options = MarkdownRendererOptions(flavor="pandoc")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should use Pandoc syntax (native support)
        assert "Rust\n:" in result or "Rust\n :" in result
        assert "A systems programming language" in result
        assert "<dl>" not in result

    def test_complex_inline_formatting_in_term(self):
        """Test definition list with complex inline formatting in term."""
        term = DefinitionTerm(content=[Code(content="ALL2MD_CONFIG"), Text(content=" variable")])
        description = DefinitionDescription(content=[Paragraph(content=[Text(content="Configuration file path")])])
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        options = MarkdownRendererOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should preserve inline formatting
        assert "`ALL2MD_CONFIG`" in result
        assert "variable" in result
        assert "Configuration file path" in result

    def test_multiple_descriptions_per_term(self):
        """Test definition list with multiple descriptions for one term."""
        term = DefinitionTerm(content=[Text(content="HTTP")])
        desc1 = DefinitionDescription(content=[Paragraph(content=[Text(content="HyperText Transfer Protocol")])])
        desc2 = DefinitionDescription(
            content=[Paragraph(content=[Text(content="The foundation of web communication")])]
        )
        definition_list = DefinitionList(items=[(term, [desc1, desc2])])
        doc = Document(children=[definition_list])

        options = MarkdownRendererOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have multiple `: ` prefixes
        assert "HTTP" in result
        assert "HyperText Transfer Protocol" in result
        assert "The foundation of web communication" in result
        assert result.count(":") >= 2  # At least 2 colons for 2 descriptions

    def test_multiline_description_with_code_block(self):
        """Test definition list with multiline description containing code block."""
        term = DefinitionTerm(content=[Text(content="Example")])
        description = DefinitionDescription(
            content=[
                Paragraph(content=[Text(content="Here's how to use it:")]),
                CodeBlock(content="code example", language="bash"),
            ]
        )
        definition_list = DefinitionList(items=[(term, [description])])
        doc = Document(children=[definition_list])

        options = MarkdownRendererOptions(flavor="gfm")
        renderer = MarkdownRenderer(options)
        result = renderer.render_to_string(doc)

        # Should have proper structure
        assert "Example" in result
        assert "Here's how to use it:" in result
        assert "code example" in result

    def test_definition_list_roundtrips_without_collapsing(self):
        """Multi-paragraph descriptions and multiple terms survive a roundtrip.

        Two regressions in one place: a description's paragraphs were joined by
        a single newline (so the second lazily merged into the first on
        reparse), and consecutive term/description groups were separated by a
        single newline (so the next term merged into the previous description).
        Both need a blank-line separator; continuation lines are indented four
        spaces.
        """
        from all2md import convert, to_ast
        from all2md.ast import DefinitionList

        opts = MarkdownRendererOptions(flavor="pandoc")
        markdown = "term one\n\n:   first para\n\n    second para\n\nterm two\n\n:   only para\n"

        once = convert(markdown, source_format="markdown", target_format="markdown", renderer_options=opts)
        twice = convert(once, source_format="markdown", target_format="markdown", renderer_options=opts)
        assert once == twice, "definition list is not idempotent"

        # Blank line kept between the two paragraphs of the first description.
        assert "first para\n\n    second para" in once

        # Both terms survive as two separate definition items.
        ast = to_ast(once, source_format="markdown")
        dls = [n for n in ast.children if isinstance(n, DefinitionList)]
        assert len(dls) == 1
        assert len(dls[0].items) == 2
