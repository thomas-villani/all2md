"""Unit tests for the RtfRenderer."""

from pathlib import Path

import pytest

try:
    from pyth.plugins.rtf15 import writer  # noqa: F401

    RTF_AVAILABLE = True
except Exception:  # pragma: no cover - dependency guard
    RTF_AVAILABLE = False

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
from all2md.options import RtfRendererOptions

if RTF_AVAILABLE:
    from all2md.renderers.rtf import RtfRenderer

pytestmark = pytest.mark.skipif(not RTF_AVAILABLE, reason="pyth3 with six not installed")


@pytest.mark.unit
class TestRtfRendererBasic:
    """Smoke tests for the RTF renderer."""

    def test_render_empty_document_to_string(self) -> None:
        """Render an empty document and ensure RTF header is present."""
        renderer = RtfRenderer()
        output = renderer.render_to_string(Document())
        assert "\\rtf1" in output

    def test_render_formatted_paragraph(self) -> None:
        """Ensure formatted inline nodes appear in the output payload."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Hello "),
                        Strong(content=[Text(content="world")]),
                        Emphasis(content=[Text(content="!")]),
                    ]
                )
            ]
        )
        renderer = RtfRenderer(RtfRendererOptions(font_family="swiss"))
        rtf_output = renderer.render_to_string(doc)
        assert "Hello" in rtf_output
        assert "world" in rtf_output
        assert "!" in rtf_output

    def test_render_block_comment_basic(self) -> None:
        """Render a basic block-level comment."""
        doc = Document(children=[Comment(content="This is a block comment", metadata={})])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "This is a block comment" in rtf_output

    def test_render_block_comment_with_metadata(self) -> None:
        """Render a block-level comment with author and date metadata."""
        doc = Document(
            children=[
                Comment(
                    content="Review this section", metadata={"author": "John Doe", "date": "2025-01-15", "label": "1"}
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Review this section" in rtf_output
        assert "John Doe" in rtf_output
        assert "2025-01-15" in rtf_output

    def test_render_block_comment_drop_mode(self) -> None:
        """Render a block-level comment with ignore mode (drops comment)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before comment")]),
                Comment(content="This should be dropped"),
                Paragraph(content=[Text(content="After comment")]),
            ]
        )
        renderer = RtfRenderer(options=RtfRendererOptions(comment_mode="ignore"))
        rtf_output = renderer.render_to_string(doc)
        assert "Before comment" in rtf_output
        assert "After comment" in rtf_output
        assert "This should be dropped" not in rtf_output

    def test_render_inline_comment_basic(self) -> None:
        """Render a basic inline comment."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Before "),
                        CommentInline(content="inline comment", metadata={}),
                        Text(content=" after"),
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Before" in rtf_output
        assert "inline comment" in rtf_output
        assert "after" in rtf_output

    def test_render_inline_comment_with_metadata(self) -> None:
        """Render an inline comment with author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        CommentInline(content="annotated section", metadata={"author": "Jane Smith", "label": "2"}),
                        Text(content=" here"),
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "annotated section" in rtf_output
        assert "Jane Smith" in rtf_output

    def test_render_inline_comment_drop_mode(self) -> None:
        """Render an inline comment with ignore mode (drops comment)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Start "), CommentInline(content="dropped"), Text(content="end")])
            ]
        )
        renderer = RtfRenderer(options=RtfRendererOptions(comment_mode="ignore"))
        rtf_output = renderer.render_to_string(doc)
        assert "Start" in rtf_output
        assert "end" in rtf_output
        assert "dropped" not in rtf_output


@pytest.mark.unit
class TestRtfRendererHeadings:
    """Tests for heading rendering."""

    def test_render_heading_level_1(self) -> None:
        """Render a level 1 heading."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Chapter Title")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Chapter Title" in rtf_output

    def test_render_heading_with_bold_option(self) -> None:
        """Render heading with bold styling enabled."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Bold Heading")])])
        renderer = RtfRenderer(RtfRendererOptions(bold_headings=True))
        rtf_output = renderer.render_to_string(doc)
        assert "Bold Heading" in rtf_output

    def test_render_heading_with_inline_formatting(self) -> None:
        """Render heading with nested inline formatting."""
        doc = Document(
            children=[
                Heading(
                    level=2,
                    content=[
                        Text(content="Section with "),
                        Emphasis(content=[Text(content="emphasis")]),
                    ],
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Section with" in rtf_output
        assert "emphasis" in rtf_output

    def test_render_empty_heading(self) -> None:
        """Render an empty heading returns None."""
        doc = Document(children=[Heading(level=1, content=[])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        # Should still produce valid RTF
        assert "\\rtf1" in rtf_output


@pytest.mark.unit
class TestRtfRendererCodeBlocks:
    """Tests for code block rendering."""

    def test_render_code_block(self) -> None:
        """Render a code block."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('hi')", language="python")])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "def hello" in rtf_output
        assert "print" in rtf_output

    def test_render_inline_code(self) -> None:
        """Render inline code."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Use "), Code(content="print()"), Text(content=" function")])]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "print()" in rtf_output


@pytest.mark.unit
class TestRtfRendererLists:
    """Tests for list rendering."""

    def test_render_unordered_list(self) -> None:
        """Render an unordered list."""
        doc = Document(
            children=[
                List(
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Item 1")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                    ordered=False,
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Item 1" in rtf_output
        assert "Item 2" in rtf_output

    def test_render_ordered_list(self) -> None:
        """Render an ordered list."""
        doc = Document(
            children=[
                List(
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="First")])]),
                        ListItem(children=[Paragraph(content=[Text(content="Second")])]),
                    ],
                    ordered=True,
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "First" in rtf_output
        assert "Second" in rtf_output

    def test_render_task_list_checked(self) -> None:
        """Render a checked task list item."""
        doc = Document(
            children=[
                List(
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Done task")])], task_status="checked"),
                    ],
                    ordered=False,
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Done task" in rtf_output
        assert "[x]" in rtf_output

    def test_render_task_list_unchecked(self) -> None:
        """Render an unchecked task list item."""
        doc = Document(
            children=[
                List(
                    items=[
                        ListItem(children=[Paragraph(content=[Text(content="Pending")])], task_status="unchecked"),
                    ],
                    ordered=False,
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Pending" in rtf_output
        assert "[ ]" in rtf_output

    def test_render_empty_list_item(self) -> None:
        """Render an empty list item."""
        doc = Document(
            children=[
                List(
                    items=[ListItem(children=[])],
                    ordered=False,
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "\\rtf1" in rtf_output


@pytest.mark.unit
class TestRtfRendererTables:
    """Tests for table rendering."""

    def test_render_simple_table(self) -> None:
        """Render a simple table."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]
                        ),
                    ],
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Name" in rtf_output
        assert "Age" in rtf_output
        assert "Alice" in rtf_output

    def test_render_table_with_colspan(self) -> None:
        """Render a table with colspan."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Merged")], colspan=2)]),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])]
                        ),
                    ],
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Merged" in rtf_output

    def test_render_table_with_caption(self) -> None:
        """Render a table with caption."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Col")])]),
                    rows=[],
                    caption="Table 1: Sample",
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Table 1: Sample" in rtf_output


@pytest.mark.unit
class TestRtfRendererBlockQuotes:
    """Tests for block quote rendering."""

    def test_render_block_quote(self) -> None:
        """Render a block quote."""
        doc = Document(children=[BlockQuote(children=[Paragraph(content=[Text(content="A wise quote")])])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "A wise quote" in rtf_output
        assert ">" in rtf_output


@pytest.mark.unit
class TestRtfRendererDefinitionLists:
    """Tests for definition list rendering."""

    def test_render_definition_list(self) -> None:
        """Render a definition list."""
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
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Term" in rtf_output
        assert "Definition" in rtf_output


@pytest.mark.unit
class TestRtfRendererInlineFormatting:
    """Tests for inline formatting."""

    def test_render_strikethrough(self) -> None:
        """Render strikethrough text."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "deleted" in rtf_output

    def test_render_underline(self) -> None:
        """Render underlined text."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "underlined" in rtf_output

    def test_render_subscript(self) -> None:
        """Render subscript text."""
        doc = Document(
            children=[Paragraph(content=[Text(content="H"), Subscript(content=[Text(content="2")]), Text(content="O")])]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "H" in rtf_output
        assert "2" in rtf_output
        assert "O" in rtf_output

    def test_render_superscript(self) -> None:
        """Render superscript text."""
        doc = Document(children=[Paragraph(content=[Text(content="x"), Superscript(content=[Text(content="2")])])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "x" in rtf_output


@pytest.mark.unit
class TestRtfRendererLinksAndImages:
    """Tests for link and image rendering."""

    def test_render_link(self) -> None:
        """Render a hyperlink."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Click here")])])]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Click here" in rtf_output

    def test_render_image(self) -> None:
        """Render an image."""
        doc = Document(children=[Paragraph(content=[Image(url="image.png", alt_text="Test image")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Test image" in rtf_output

    def test_render_image_without_alt(self) -> None:
        """Render an image without alt text."""
        doc = Document(children=[Paragraph(content=[Image(url="photo.jpg")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Image" in rtf_output


@pytest.mark.unit
class TestRtfRendererMath:
    """Tests for math rendering."""

    def test_render_inline_math(self) -> None:
        """Render inline math."""
        doc = Document(children=[Paragraph(content=[Text(content="Formula: "), MathInline(content="E=mc^2")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "E=mc^2" in rtf_output

    def test_render_math_block(self) -> None:
        """Render a math block."""
        doc = Document(children=[MathBlock(content="\\int_0^1 x^2 dx")])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "int" in rtf_output


@pytest.mark.unit
class TestRtfRendererFootnotes:
    """Tests for footnote rendering."""

    def test_render_footnote_reference(self) -> None:
        """Render a footnote reference."""
        doc = Document(children=[Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "[^1]" in rtf_output

    def test_render_footnote_definition(self) -> None:
        """Render a footnote definition."""
        doc = Document(
            children=[FootnoteDefinition(identifier="1", content=[Paragraph(content=[Text(content="Footnote text")])])]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Footnote text" in rtf_output


@pytest.mark.unit
class TestRtfRendererMisc:
    """Tests for miscellaneous rendering."""

    def test_render_thematic_break(self) -> None:
        """Render a thematic break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="After")]),
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Before" in rtf_output
        assert "After" in rtf_output
        # Em dash is encoded as Unicode escape in RTF
        assert "8212" in rtf_output or "—" in rtf_output

    def test_render_line_break(self) -> None:
        """Render a line break."""
        doc = Document(children=[Paragraph(content=[Text(content="Line 1"), LineBreak(), Text(content="Line 2")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Line 1" in rtf_output
        assert "Line 2" in rtf_output

    def test_render_html_block(self) -> None:
        """Render an HTML block as literal text."""
        doc = Document(children=[HTMLBlock(content="<div>HTML content</div>")])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "div" in rtf_output

    def test_render_html_inline(self) -> None:
        """Render inline HTML as literal text."""
        doc = Document(children=[Paragraph(content=[HTMLInline(content="<span>inline</span>")])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "span" in rtf_output


@pytest.mark.unit
class TestRtfRendererMetadata:
    """Tests for document metadata handling."""

    def test_render_with_metadata(self) -> None:
        """Render document with title/author metadata."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Content")])],
            metadata={"title": "My Document", "author": "John Doe", "subject": "Testing"},
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Content" in rtf_output


@pytest.mark.unit
class TestRtfRendererFileOutput:
    """Tests for file output functionality."""

    def test_render_to_file(self, tmp_path: Path) -> None:
        """Render to file path."""
        doc = Document(children=[Paragraph(content=[Text(content="File output test")])])
        output_file = tmp_path / "output.rtf"
        renderer = RtfRenderer()
        renderer.render(doc, str(output_file))
        assert output_file.exists()
        content = output_file.read_text()
        assert "File output test" in content

    def test_render_to_path_object(self, tmp_path: Path) -> None:
        """Render to Path object."""
        doc = Document(children=[Paragraph(content=[Text(content="Path test")])])
        output_file = tmp_path / "output.rtf"
        renderer = RtfRenderer()
        renderer.render(doc, output_file)
        assert output_file.exists()


@pytest.mark.unit
class TestRtfRendererEdgeCases:
    """Tests for edge cases."""

    def test_options_validation_wrong_type(self) -> None:
        """Test that wrong options type raises error."""
        with pytest.raises(InvalidOptionsError):
            RtfRenderer(options="invalid")

    def test_render_empty_paragraph(self) -> None:
        """Render an empty paragraph."""
        doc = Document(children=[Paragraph(content=[])])
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "\\rtf1" in rtf_output

    def test_render_nested_formatting(self) -> None:
        """Render nested inline formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Strong(content=[Emphasis(content=[Text(content="bold italic")])]),
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "bold italic" in rtf_output
