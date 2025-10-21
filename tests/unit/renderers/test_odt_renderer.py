#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_odt_renderer.py
"""Unit tests for OdtRenderer.

Tests cover:
- Rendering all node types to ODT
- Document structure and styles
- Table formatting
- Image handling
- Edge cases and nested structures

Note: These tests require odfpy to be installed.

"""

from io import BytesIO

import pytest

try:
    from odf.opendocument import load as odf_load

    ODFPY_AVAILABLE = True
except ImportError:
    ODFPY_AVAILABLE = False

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
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
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
from all2md.options import OdtRendererOptions

if ODFPY_AVAILABLE:
    from all2md.renderers.odt import OdtRenderer

pytestmark = pytest.mark.skipif(not ODFPY_AVAILABLE, reason="odfpy not installed")


@pytest.mark.unit
class TestBasicRendering:
    """Tests for basic ODT rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = OdtRenderer()
        output_file = tmp_path / "empty.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()
        odt_doc = odf_load(str(output_file))
        assert odt_doc is not None

    def test_render_text_only(self, tmp_path):
        """Test rendering plain text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "text.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()
        odt_doc = odf_load(str(output_file))
        # Check that document has text content
        from odf.text import P

        paragraphs = odt_doc.getElementsByType(P)
        assert len(paragraphs) >= 1

    def test_render_multiple_paragraphs(self, tmp_path):
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "paras.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import P

        paragraphs = odt_doc.getElementsByType(P)
        assert len(paragraphs) >= 2

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = OdtRenderer()
        output = BytesIO()
        renderer.render(doc, output)

        output.seek(0)
        assert len(output.read()) > 0


@pytest.mark.unit
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1(self, tmp_path):
        """Test rendering h1."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "h1.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import H

        headings = odt_doc.getElementsByType(H)
        assert len(headings) >= 1

    def test_heading_level_2(self, tmp_path):
        """Test rendering h2."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "h2.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import H

        headings = odt_doc.getElementsByType(H)
        assert len(headings) >= 1

    def test_heading_with_formatting(self, tmp_path):
        """Test heading with inline formatting."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Bold "), Strong(content=[Text(content="title")])])]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "h_format.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import H

        headings = odt_doc.getElementsByType(H)
        assert len(headings) >= 1


@pytest.mark.unit
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_strong(self, tmp_path):
        """Test bold text rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = OdtRenderer()
        output_file = tmp_path / "bold.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_emphasis(self, tmp_path):
        """Test italic text rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = OdtRenderer()
        output_file = tmp_path / "italic.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_code(self, tmp_path):
        """Test inline code rendering."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "code.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_strikethrough(self, tmp_path):
        """Test strikethrough rendering."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = OdtRenderer()
        output_file = tmp_path / "strike.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_underline(self, tmp_path):
        """Test underline rendering."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = OdtRenderer()
        output_file = tmp_path / "underline.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_nested_formatting(self, tmp_path):
        """Test nested inline formatting."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "nested.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestLinkRendering:
    """Tests for hyperlink rendering."""

    def test_simple_link(self, tmp_path):
        """Test basic hyperlink rendering."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="Visit "), Link(url="https://example.com", content=[Text(content="Example")])]
                )
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "link.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import A

        links = odt_doc.getElementsByType(A)
        assert len(links) >= 1

    def test_link_with_formatting(self, tmp_path):
        """Test hyperlink with nested formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Link(url="https://example.com", content=[Strong(content=[Text(content="Bold Link")])])]
                )
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "link_formatted.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestListRendering:
    """Tests for list rendering."""

    def test_unordered_list(self, tmp_path):
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
        renderer = OdtRenderer()
        output_file = tmp_path / "ul.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import List as OdfList

        lists = odt_doc.getElementsByType(OdfList)
        assert len(lists) >= 1

    def test_ordered_list(self, tmp_path):
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
        renderer = OdtRenderer()
        output_file = tmp_path / "ol.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import List as OdfList

        lists = odt_doc.getElementsByType(OdfList)
        assert len(lists) >= 1


@pytest.mark.unit
class TestTableRendering:
    """Tests for table rendering."""

    def test_simple_table(self, tmp_path):
        """Test basic table rendering."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[TableCell(content=[Text(content="Name")]), TableCell(content=[Text(content="Age")])]
                    ),
                    rows=[
                        TableRow(
                            cells=[TableCell(content=[Text(content="Alice")]), TableCell(content=[Text(content="30")])]
                        )
                    ],
                )
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "table.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.table import Table as OdfTable

        tables = odt_doc.getElementsByType(OdfTable)
        assert len(tables) >= 1

    def test_table_without_header(self, tmp_path):
        """Test table without header row."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(cells=[TableCell(content=[Text(content="A")]), TableCell(content=[Text(content="B")])])
                    ]
                )
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "table_no_header.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.table import Table as OdfTable

        tables = odt_doc.getElementsByType(OdfTable)
        assert len(tables) >= 1


@pytest.mark.unit
class TestBlockElements:
    """Tests for block-level elements."""

    def test_code_block(self, tmp_path):
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('world')", language="python")])
        renderer = OdtRenderer()
        output_file = tmp_path / "codeblock.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_blockquote(self, tmp_path):
        """Test blockquote rendering with indentation."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Normal text")]),
                BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])]),
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "blockquote.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_thematic_break(self, tmp_path):
        """Test horizontal rule rendering."""
        doc = Document(children=[ThematicBreak()])
        renderer = OdtRenderer()
        output_file = tmp_path / "hr.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        from odf.text import P

        paragraphs = odt_doc.getElementsByType(P)
        assert len(paragraphs) >= 1


@pytest.mark.unit
class TestDocumentMetadata:
    """Tests for document metadata."""

    def test_metadata_properties(self, tmp_path):
        """Test document properties from metadata."""
        doc = Document(
            metadata={"title": "Test Document", "author": "Test Author", "subject": "Testing"},
            children=[Paragraph(content=[Text(content="Content")])],
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "metadata.odt"
        renderer.render(doc, output_file)

        odt_doc = odf_load(str(output_file))
        # Verify metadata was set
        meta = odt_doc.meta
        assert meta is not None


@pytest.mark.unit
class TestDefinitionLists:
    """Tests for definition list rendering."""

    def test_definition_list(self, tmp_path):
        """Test definition list rendering."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term")]),
                            [DefinitionDescription(content=[Text(content="Description")])],
                        )
                    ]
                )
            ]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "deflist.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestRendererOptions:
    """Tests for renderer options."""

    def test_custom_fonts(self, tmp_path):
        """Test custom font settings."""
        doc = Document(children=[Paragraph(content=[Text(content="Custom font")])])
        options = OdtRendererOptions(default_font="Liberation Serif", default_font_size=14)
        renderer = OdtRenderer(options)
        output_file = tmp_path / "custom_font.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_code_font_option(self, tmp_path):
        """Test code font option."""
        doc = Document(children=[CodeBlock(content="code here")])
        options = OdtRendererOptions(code_font="Courier")
        renderer = OdtRenderer(options)
        output_file = tmp_path / "code_font.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestMathRendering:
    """Tests for math rendering."""

    def test_inline_math(self, tmp_path):
        """Test inline math rendering."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "math_inline.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_block_math(self, tmp_path):
        """Test block math rendering."""
        doc = Document(children=[MathBlock(content="E = mc^2", notation="latex")])
        renderer = OdtRenderer()
        output_file = tmp_path / "math_block.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_reference(self, tmp_path):
        """Test footnote reference rendering."""
        doc = Document(children=[Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "footnote_ref.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()

    def test_footnote_definition(self, tmp_path):
        """Test footnote definition rendering."""
        doc = Document(children=[FootnoteDefinition(identifier="1", content=[Text(content="Footnote text")])])
        renderer = OdtRenderer()
        output_file = tmp_path / "footnote_def.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()


@pytest.mark.unit
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_hard_line_break(self, tmp_path):
        """Test hard line break rendering."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=False), Text(content="Line 2")])]
        )
        renderer = OdtRenderer()
        output_file = tmp_path / "linebreak.odt"
        renderer.render(doc, output_file)

        assert output_file.exists()
