#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_docx_renderer.py
"""Unit tests for DocxRenderer.

Tests cover:
- Rendering all node types to DOCX
- Document structure and styles
- Table formatting
- Image handling
- Edge cases and nested structures

Note: These tests require python-docx to be installed.

"""

from io import BytesIO

import pytest

try:
    from docx import Document as DocxDocument
    from docx.oxml.ns import qn

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

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
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.options import DocxRendererOptions

if DOCX_AVAILABLE:
    from all2md.renderers.docx import DocxRenderer

pytestmark = pytest.mark.skipif(not DOCX_AVAILABLE, reason="python-docx not installed")

_MATH = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"

# A 1x1 white PNG.
_PNG_1PX = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC"


@pytest.mark.unit
@pytest.mark.docx
class TestBasicRendering:
    """Tests for basic DOCX rendering."""

    def test_render_empty_document(self, tmp_path):
        """Test rendering an empty document."""
        doc = Document()
        renderer = DocxRenderer()
        output_file = tmp_path / "empty.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        # Empty document still has default styles
        assert docx_doc is not None

    def test_render_text_only(self, tmp_path):
        """Test rendering plain text."""
        doc = Document(children=[Paragraph(content=[Text(content="Hello world")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "text.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.paragraphs) >= 1
        assert "Hello world" in docx_doc.paragraphs[0].text

    def test_render_multiple_paragraphs(self, tmp_path):
        """Test rendering multiple paragraphs."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="First paragraph")]),
                Paragraph(content=[Text(content="Second paragraph")]),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "paras.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        paragraphs = [p for p in docx_doc.paragraphs if p.text.strip()]
        assert len(paragraphs) >= 2
        assert "First paragraph" in paragraphs[0].text
        assert "Second paragraph" in paragraphs[1].text

    def test_render_to_bytes_io(self):
        """Test rendering to BytesIO."""
        doc = Document(children=[Paragraph(content=[Text(content="Test")])])
        renderer = DocxRenderer()
        output = BytesIO()
        renderer.render(doc, output)

        output.seek(0)
        docx_doc = DocxDocument(output)
        assert len(docx_doc.paragraphs) >= 1


@pytest.mark.unit
@pytest.mark.docx
class TestHeadingRendering:
    """Tests for heading rendering."""

    def test_heading_level_1(self, tmp_path):
        """Test rendering h1."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Title")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "h1.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Find heading paragraph
        heading_para = None
        for para in docx_doc.paragraphs:
            if para.text == "Title":
                heading_para = para
                break
        assert heading_para is not None

    def test_heading_level_2(self, tmp_path):
        """Test rendering h2."""
        doc = Document(children=[Heading(level=2, content=[Text(content="Subtitle")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "h2.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        found = False
        for para in docx_doc.paragraphs:
            if "Subtitle" in para.text:
                found = True
                break
        assert found

    def test_heading_with_formatting(self, tmp_path):
        """Test heading with inline formatting."""
        doc = Document(
            children=[Heading(level=1, content=[Text(content="Bold "), Strong(content=[Text(content="title")])])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "h_format.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        found = False
        for para in docx_doc.paragraphs:
            if "Bold" in para.text and "title" in para.text:
                found = True
                break
        assert found


@pytest.mark.unit
@pytest.mark.docx
class TestInlineFormatting:
    """Tests for inline formatting."""

    def test_strong(self, tmp_path):
        """Test bold text rendering."""
        doc = Document(children=[Paragraph(content=[Strong(content=[Text(content="bold")])])])
        renderer = DocxRenderer()
        output_file = tmp_path / "bold.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "bold" in para.text
        # Check if any run is bold
        has_bold = any(run.bold for run in para.runs)
        assert has_bold

    def test_emphasis(self, tmp_path):
        """Test italic text rendering."""
        doc = Document(children=[Paragraph(content=[Emphasis(content=[Text(content="italic")])])])
        renderer = DocxRenderer()
        output_file = tmp_path / "italic.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "italic" in para.text
        # Check if any run is italic
        has_italic = any(run.italic for run in para.runs)
        assert has_italic

    def test_code(self, tmp_path):
        """Test inline code rendering."""
        doc = Document(children=[Paragraph(content=[Code(content="code")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "code.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "code" in para.text

    def test_strikethrough(self, tmp_path):
        """Test strikethrough rendering."""
        doc = Document(children=[Paragraph(content=[Strikethrough(content=[Text(content="deleted")])])])
        renderer = DocxRenderer()
        output_file = tmp_path / "strike.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "deleted" in para.text

    def test_underline(self, tmp_path):
        """Test underline rendering."""
        doc = Document(children=[Paragraph(content=[Underline(content=[Text(content="underlined")])])])
        renderer = DocxRenderer()
        output_file = tmp_path / "underline.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "underlined" in para.text

    def test_nested_formatting(self, tmp_path):
        """Test nested inline formatting."""
        doc = Document(
            children=[Paragraph(content=[Strong(content=[Emphasis(content=[Text(content="bold italic")])])])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "nested.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "bold italic" in para.text


@pytest.mark.unit
@pytest.mark.docx
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
        renderer = DocxRenderer()
        output_file = tmp_path / "link.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "Visit" in para.text
        assert "Example" in para.text

        # Check that hyperlink exists in XML structure
        from docx.oxml.ns import qn

        hyperlinks = para._element.findall(qn("w:hyperlink"))
        assert len(hyperlinks) > 0, "No hyperlinks found in paragraph XML"

        # Verify the hyperlink has proper w:r and w:t structure
        hyperlink = hyperlinks[0]
        runs = hyperlink.findall(qn("w:r"))
        assert len(runs) > 0, "Hyperlink has no w:r elements"

        # Check that text is in w:t element (not directly in w:r)
        text_elements = runs[0].findall(qn("w:t"))
        assert len(text_elements) > 0, "Run has no w:t element - text not properly structured"
        assert text_elements[0].text == "Example", f"Expected 'Example' but got '{text_elements[0].text}'"

    def test_link_with_formatting(self, tmp_path):
        """Test hyperlink with nested formatting."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Link(url="https://example.com", content=[Strong(content=[Text(content="Bold Link")])])]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "link_formatted.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "Bold Link" in para.text


@pytest.mark.unit
@pytest.mark.docx
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
        renderer = DocxRenderer()
        output_file = tmp_path / "ul.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        paragraphs = docx_doc.paragraphs
        text_content = [p.text for p in paragraphs]
        assert "Item 1" in text_content
        assert "Item 2" in text_content

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
        renderer = DocxRenderer()
        output_file = tmp_path / "ol.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        paragraphs = docx_doc.paragraphs
        text_content = [p.text for p in paragraphs]
        assert "First" in text_content
        assert "Second" in text_content


def _template_lacking_list_styles(tmp_path, *, drop_numbering_part: bool):
    """Build a template with no List Bullet/List Number styles.

    Real-world templates omit these styles; some also ship without a numbering part
    at all, which exercises a different branch of ``_ensure_list_styles``.
    """
    import re
    import zipfile

    template = tmp_path / "template.docx"
    doc = DocxDocument()
    for name in ("List Bullet", "List Number"):
        doc.styles[name].delete()
    doc.save(str(template))

    if not drop_numbering_part:
        return template

    stripped = tmp_path / "template_no_numbering.docx"
    with zipfile.ZipFile(template) as zin, zipfile.ZipFile(stripped, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "word/numbering.xml":
                continue
            data = zin.read(item.filename)
            if item.filename == "[Content_Types].xml":
                data = re.sub(rb"<Override PartName=\"/word/numbering\.xml\"[^/]*/>", b"", data)
            elif item.filename == "word/_rels/document.xml.rels":
                data = re.sub(rb"<Relationship [^>]*Target=\"numbering\.xml\"[^>]*/>", b"", data)
            zout.writestr(item, data)
    return stripped


@pytest.mark.unit
@pytest.mark.docx
@pytest.mark.parametrize("drop_numbering_part", [False, True], ids=["existing-numbering", "no-numbering"])
def test_template_numbering_keeps_schema_element_order(tmp_path, drop_numbering_part):
    """Regression: interleaved w:abstractNum/w:num silently killed bullets in Word.

    CT_Numbering is a strict sequence -- every w:abstractNum must precede every
    w:num.  Word does not reject an out-of-order part; it mis-associates the stray
    definition, so bulleted lists render as plain paragraphs.
    """
    from docx.oxml.ns import qn

    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    template = _template_lacking_list_styles(tmp_path, drop_numbering_part=drop_numbering_part)
    doc = Document(
        children=[
            List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Bullet")])])]),
            List(ordered=True, items=[ListItem(children=[Paragraph(content=[Text(content="Number")])])]),
        ]
    )
    output_file = tmp_path / "out.docx"
    DocxRenderer(options=DocxRendererOptions(template_path=str(template))).render(doc, output_file)

    rendered = DocxDocument(str(output_file))
    numbering = rendered.part.numbering_part._element
    order = [child.tag.split("}")[-1] for child in numbering if child.tag in (qn("w:abstractNum"), qn("w:num"))]
    assert "abstractNum" in order and "num" in order
    last_abstract = len(order) - 1 - order[::-1].index("abstractNum")
    assert last_abstract < order.index("num"), f"w:num precedes a w:abstractNum: {order}"

    # Each recreated style must resolve to a numbering definition that exists.
    styles = {s.name for s in rendered.styles}
    assert {"List Bullet", "List Number"} <= styles

    defined_num_ids = {int(n.get(qn("w:numId"))) for n in numbering.findall(qn("w:num"))}
    for style_name in ("List Bullet", "List Number"):
        num_pr = rendered.styles[style_name]._element.find(qn("w:pPr")).find(qn("w:numPr"))
        num_id = int(num_pr.find(qn("w:numId")).get(qn("w:val")))
        assert num_id in defined_num_ids, f"{style_name} references undefined numId {num_id}"


@pytest.mark.unit
@pytest.mark.docx
def test_template_bullet_uses_symbol_font_codepoint(tmp_path):
    """The Symbol font's bullet is U+F0B7; U+00B7 renders as the wrong glyph."""
    from docx.oxml.ns import qn

    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    template = _template_lacking_list_styles(tmp_path, drop_numbering_part=True)
    doc = Document(
        children=[List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content="Bullet")])])])]
    )
    output_file = tmp_path / "out.docx"
    DocxRenderer(options=DocxRendererOptions(template_path=str(template))).render(doc, output_file)

    numbering = DocxDocument(str(output_file)).part.numbering_part._element
    bullet_lvl = next(
        lvl
        for lvl in numbering.iter(qn("w:lvl"))
        if lvl.find(qn("w:numFmt")) is not None and lvl.find(qn("w:numFmt")).get(qn("w:val")) == "bullet"
    )
    assert bullet_lvl.find(qn("w:lvlText")).get(qn("w:val")) == ""


@pytest.mark.unit
@pytest.mark.docx
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
        renderer = DocxRenderer()
        output_file = tmp_path / "table.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.tables) >= 1
        table = docx_doc.tables[0]

        # Check table has correct dimensions
        assert len(table.rows) == 2
        assert len(table.rows[0].cells) == 2

        # Check header content
        assert "Name" in table.rows[0].cells[0].text
        assert "Age" in table.rows[0].cells[1].text

        # Check body content
        assert "Alice" in table.rows[1].cells[0].text
        assert "30" in table.rows[1].cells[1].text

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
        renderer = DocxRenderer()
        output_file = tmp_path / "table_no_header.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.tables) >= 1

    @staticmethod
    def _one_cell_table(text, caption=None):
        return Table(rows=[TableRow(cells=[TableCell(content=[Text(content=text)])])], caption=caption)

    @staticmethod
    def _body_shape(result):
        from docx.oxml.ns import qn

        body = DocxDocument(BytesIO(result)).element.body
        names = {qn("w:tbl"): "tbl", qn("w:p"): "p"}
        return [
            names[child.tag] + ("" if child.tag != qn("w:p") or "".join(child.itertext()).strip() else "(empty)")
            for child in body
            if child.tag in names
        ]

    def test_adjacent_tables_keep_a_paragraph_between_them(self):
        """Word reads two tables with nothing between them as one table."""
        from all2md import to_ast

        doc = Document(children=[self._one_cell_table("first"), self._one_cell_table("second")])
        result = DocxRenderer().render_to_bytes(doc)
        assert self._body_shape(result) == ["tbl", "p(empty)", "tbl"]
        # The separator is not content: the parser drops it and reads two tables back.
        children = to_ast(result, source_format="docx").children
        assert [type(child).__name__ for child in children] == ["Table", "Table"]

    @pytest.mark.parametrize(
        "between",
        [Paragraph(content=[Text(content="prose")]), None],
        ids=["prose", "caption"],
    )
    def test_tables_already_apart_get_no_extra_paragraph(self, between):
        second = self._one_cell_table("second", caption=None if between else "Table 2. Second")
        children = [self._one_cell_table("first")] + ([between] if between else []) + [second]
        result = DocxRenderer().render_to_bytes(Document(children=children))
        assert self._body_shape(result) == ["tbl", "p", "tbl"]


@pytest.mark.unit
@pytest.mark.docx
class TestBlockElements:
    """Tests for block-level elements."""

    def test_code_block(self, tmp_path):
        """Test code block rendering."""
        doc = Document(children=[CodeBlock(content="def hello():\n    print('world')", language="python")])
        renderer = DocxRenderer()
        output_file = tmp_path / "codeblock.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        found = False
        for para in docx_doc.paragraphs:
            if "def hello()" in para.text:
                found = True
                break
        assert found

    def test_blockquote(self, tmp_path):
        """Test blockquote rendering uses Word's Quote style (#71)."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Normal text")]),
                BlockQuote(children=[Paragraph(content=[Text(content="Quoted text")])]),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "blockquote.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))

        # Find the quoted paragraph
        quoted_para = None
        normal_para = None
        for para in docx_doc.paragraphs:
            if "Quoted text" in para.text:
                quoted_para = para
            elif "Normal text" in para.text:
                normal_para = para

        assert quoted_para is not None, "Quoted text not found"
        assert normal_para is not None, "Normal text not found"

        # The quote paragraph carries the Quote style (not a bare left indent, which the
        # parser would misread as a list); the normal paragraph does not.
        assert quoted_para.style.name == "Quote"
        assert normal_para.style.name != "Quote"
        # A single-level quote relies on the style for its indent, so it must not set a
        # direct left indent -- that is exactly what got mistaken for list nesting.
        assert quoted_para.paragraph_format.left_indent is None

    def test_nested_blockquote(self, tmp_path):
        """Test nested blockquote rendering with increased indentation (#71)."""
        doc = Document(
            children=[
                BlockQuote(
                    children=[
                        Paragraph(content=[Text(content="Level 1")]),
                        BlockQuote(children=[Paragraph(content=[Text(content="Level 2")])]),
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "nested_blockquote.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))

        # Find both paragraphs
        level1_para = None
        level2_para = None
        for para in docx_doc.paragraphs:
            if "Level 1" in para.text:
                level1_para = para
            elif "Level 2" in para.text:
                level2_para = para

        assert level1_para is not None, "Level 1 text not found"
        assert level2_para is not None, "Level 2 text not found"

        # Both levels use the Quote style; the style supplies level 1's indent, and the
        # deeper level adds a direct indent on top so nesting is still visible in Word.
        assert level1_para.style.name == "Quote"
        assert level2_para.style.name == "Quote"
        assert level1_para.paragraph_format.left_indent is None
        assert level2_para.paragraph_format.left_indent is not None
        assert level2_para.paragraph_format.left_indent > 0

    def test_thematic_break(self, tmp_path):
        """Test horizontal rule rendering."""
        doc = Document(children=[ThematicBreak()])
        renderer = DocxRenderer()
        output_file = tmp_path / "hr.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # An empty paragraph with a bottom border, as Word draws "---"; not a line of text.
        (rule,) = docx_doc.paragraphs
        assert rule.text == ""
        assert rule._p.pPr.find(f"{_W}pBdr/{_W}bottom").get(f"{_W}val") == "single"

    def test_thematic_break_round_trips(self):
        doc = Document(
            children=[
                Paragraph(content=[Text(content="above")]),
                ThematicBreak(),
                Paragraph(content=[Text(content="below")]),
            ]
        )
        assert _round_trip(doc) == "above\n\n---\n\nbelow"


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _round_trip(doc: Document) -> str:
    """Render to DOCX and convert back to Markdown."""
    from all2md import to_markdown

    buffer = BytesIO()
    DocxRenderer().render(doc, buffer)
    return to_markdown(buffer.getvalue(), source_format="docx").strip()


def _alert(kind: str, text: str, title: str | None = None) -> BlockQuote:
    metadata = {"admonition_type": kind} | ({"admonition_title": title} if title else {})
    return BlockQuote(children=[Paragraph(content=[Text(content=text)])], metadata=metadata)


def _left_bar(paragraph) -> str | None:
    """The color of a paragraph's left border, or None without one."""
    properties = paragraph._p.pPr
    left = properties.find(f"{_W}pBdr/{_W}left") if properties is not None else None
    return left.get(f"{_W}color") if left is not None else None


@pytest.mark.unit
@pytest.mark.docx
class TestAlerts:
    """GitHub alerts and admonitions: a colored bold label and a bar down the left."""

    def render(self, *children) -> list:
        buffer = BytesIO()
        DocxRenderer().render(Document(children=list(children)), buffer)
        return DocxDocument(buffer).paragraphs

    def test_label_and_bar(self):
        label, body = self.render(_alert("warning", "Mind the gap."))
        assert label.text == "Warning"
        assert label.runs[0].bold
        assert str(label.runs[0].font.color.rgb) == "9A6700"
        assert body.text == "Mind the gap."
        assert _left_bar(label) == _left_bar(body) == "9A6700"

    def test_a_custom_title_is_the_label(self):
        label, _ = self.render(_alert("note", "Body.", title="Read this first"))
        assert label.text == "Read this first"

    @pytest.mark.parametrize(("kind", "color"), [("danger", "CF222E"), ("hint", "1A7F37"), ("unheard-of", "0969DA")])
    def test_other_kinds_take_the_nearest_alert_color(self, kind, color):
        label, body = self.render(_alert(kind, "Body."))
        assert _left_bar(body) == color

    def test_a_plain_quote_has_no_bar_and_no_label(self):
        (quote,) = self.render(BlockQuote(children=[Paragraph(content=[Text(content="Quoted.")])]))
        assert quote.text == "Quoted."
        assert _left_bar(quote) is None

    def test_only_the_alerts_paragraphs_get_the_bar(self):
        before, label, body, after = self.render(
            Paragraph(content=[Text(content="before")]),
            _alert("tip", "Body."),
            Paragraph(content=[Text(content="after")]),
        )
        assert _left_bar(before) is None and _left_bar(after) is None
        assert _left_bar(label) == _left_bar(body) == "1A7F37"

    def test_alerts_round_trip_one_by_one(self):
        doc = Document(children=[_alert("note", "First."), _alert("caution", "Second.")])
        assert _round_trip(doc) == "> [!NOTE]\n> First.\n\n> [!CAUTION]\n> Second."

    def test_a_custom_title_reads_back_as_a_bold_line(self):
        """Only the five GitHub labels are recognized; a title could be any bold text."""
        markdown = _round_trip(Document(children=[_alert("note", "Body.", title="Heads up")]))
        assert markdown == "> **Heads up**\n> \n> Body."


@pytest.mark.unit
@pytest.mark.docx
class TestDocumentMetadata:
    """Tests for document metadata."""

    def test_metadata_properties(self, tmp_path):
        """Test document properties from metadata."""
        doc = Document(
            metadata={"title": "Test Document", "author": "Test Author", "subject": "Testing"},
            children=[Paragraph(content=[Text(content="Content")])],
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "metadata.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert docx_doc.core_properties.title == "Test Document"
        assert docx_doc.core_properties.author == "Test Author"
        assert docx_doc.core_properties.subject == "Testing"


def _compat_settings(docx_doc):
    """Return ``{name: val}`` of the ``w:compatSetting`` elements in a document's settings."""
    from docx.oxml.ns import qn

    compat = docx_doc.settings.element.find(qn("w:compat"))
    if compat is None:
        return {}
    return {el.get(qn("w:name")): el.get(qn("w:val")) for el in compat.findall(qn("w:compatSetting"))}


@pytest.mark.unit
@pytest.mark.docx
class TestCompatibilityMode:
    """Word opens a document naming no compatibility mode as a Word 2010 one."""

    def test_default_render_replaces_the_default_templates_word_2010_mode(self):
        from docx.oxml.ns import qn

        result = DocxRenderer().render_to_bytes(Document(children=[Paragraph(content=[Text(content="x")])]))
        docx_doc = DocxDocument(BytesIO(result))
        assert _compat_settings(docx_doc)["compatibilityMode"] == "15"

        # Word refuses settings children out of schema order: nothing before w:compat may be
        # one the schema puts after it.
        children = [child.tag for child in docx_doc.settings.element]
        successors = {qn(tag) for tag in DocxRenderer._COMPAT_SUCCESSORS}
        assert not successors & set(children[: children.index(qn("w:compat"))])

    @pytest.mark.parametrize(("existing", "expected"), [("14", "14"), (None, "15")])
    def test_a_template_mode_is_kept_and_a_missing_one_added(self, tmp_path, existing, expected):
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        template_doc = DocxDocument()
        settings = template_doc.settings.element
        compat = OxmlElement("w:compat")
        legacy = OxmlElement("w:doNotExpandShiftReturn")
        compat.append(legacy)
        if existing is not None:
            setting = OxmlElement("w:compatSetting")
            setting.set(qn("w:name"), "compatibilityMode")
            setting.set(qn("w:uri"), "http://schemas.microsoft.com/office/word")
            setting.set(qn("w:val"), existing)
            compat.append(setting)
        existing_compat = settings.find(qn("w:compat"))
        settings.replace(existing_compat, compat)
        template = tmp_path / "template.docx"
        template_doc.save(str(template))

        doc = Document(children=[Paragraph(content=[Text(content="x")])])
        result = DocxRenderer(options=DocxRendererOptions(template_path=str(template))).render_to_bytes(doc)
        docx_doc = DocxDocument(BytesIO(result))
        assert _compat_settings(docx_doc) == {"compatibilityMode": expected}
        rendered = docx_doc.settings.element.find(qn("w:compat"))
        assert rendered.find(qn("w:doNotExpandShiftReturn")) is not None

    def test_a_template_without_compat_gets_it_in_schema_order(self, tmp_path):
        from docx.oxml.ns import qn

        template_doc = DocxDocument()
        settings = template_doc.settings.element
        settings.remove(settings.find(qn("w:compat")))
        template = tmp_path / "template.docx"
        template_doc.save(str(template))

        doc = Document(children=[Paragraph(content=[Text(content="x")])])
        result = DocxRenderer(options=DocxRendererOptions(template_path=str(template))).render_to_bytes(doc)
        docx_doc = DocxDocument(BytesIO(result))
        assert _compat_settings(docx_doc) == {"compatibilityMode": "15"}
        children = [child.tag for child in docx_doc.settings.element]
        successors = {qn(tag) for tag in DocxRenderer._COMPAT_SUCCESSORS}
        assert not successors & set(children[: children.index(qn("w:compat"))])
        assert successors & set(children[children.index(qn("w:compat")) + 1 :])


@pytest.mark.unit
@pytest.mark.docx
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
        renderer = DocxRenderer()
        output_file = tmp_path / "deflist.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "Term" in text_content
        assert "Description" in text_content


@pytest.mark.unit
@pytest.mark.docx
class TestRendererOptions:
    """Tests for renderer options."""

    def test_custom_fonts(self, tmp_path):
        """Test custom font settings."""
        doc = Document(children=[Paragraph(content=[Text(content="Custom font")])])
        options = DocxRendererOptions(default_font="Arial", default_font_size=14)
        renderer = DocxRenderer(options)
        output_file = tmp_path / "custom_font.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None

    def test_code_font_option(self, tmp_path):
        """Test code font option."""
        doc = Document(children=[CodeBlock(content="code here")])
        options = DocxRendererOptions(code_font="Monaco")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "code_font.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None


@pytest.mark.unit
@pytest.mark.docx
class TestMathRendering:
    """Tests for math rendering."""

    def test_inline_math(self, tmp_path):
        """Inline math is a Word equation (m:oMath) by default."""
        doc = Document(children=[Paragraph(content=[MathInline(content="x^2", notation="latex")])])
        output_file = tmp_path / "math_inline.docx"
        DocxRenderer().render(doc, output_file)

        body = DocxDocument(str(output_file)).element.body
        assert body.find(f".//{_MATH}oMath/{_MATH}sSup") is not None

    def test_block_math(self, tmp_path):
        """Display math is an equation paragraph (m:oMathPara) by default."""
        doc = Document(children=[MathBlock(content="E = mc^2", notation="latex")])
        output_file = tmp_path / "math_block.docx"
        DocxRenderer().render(doc, output_file)

        body = DocxDocument(str(output_file)).element.body
        assert body.find(f".//{_MATH}oMathPara/{_MATH}oMath") is not None

    def test_latex_mode_writes_the_source(self, tmp_path):
        """math_mode="latex" keeps the LaTeX as text: inline between $ signs, display as a code block."""
        doc = Document(
            children=[
                Paragraph(content=[MathInline(content="x^2", notation="latex")]),
                MathBlock(content="E = mc^2", notation="latex"),
            ]
        )
        output_file = tmp_path / "math_latex.docx"
        DocxRenderer(DocxRendererOptions(math_mode="latex")).render(doc, output_file)

        text = [para.text for para in DocxDocument(str(output_file)).paragraphs]
        assert any("$x^2$" in line for line in text)
        assert any("E = mc^2" in line for line in text)


@pytest.mark.unit
@pytest.mark.docx
class TestFootnotes:
    """Tests for footnote rendering."""

    def test_footnote_reference(self, tmp_path):
        """Test footnote reference rendering."""
        doc = Document(children=[Paragraph(content=[Text(content="Text"), FootnoteReference(identifier="1")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "footnote_ref.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Footnote reference is rendered as superscript
        text_content = "".join(p.text for p in docx_doc.paragraphs)
        assert "Text" in text_content

    def test_footnote_definition(self, tmp_path):
        """Test footnote definition rendering."""
        doc = Document(children=[FootnoteDefinition(identifier="1", content=[Text(content="Footnote text")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "footnote_def.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = "".join(p.text for p in docx_doc.paragraphs)
        assert "Footnote text" in text_content


@pytest.mark.unit
@pytest.mark.docx
class TestLineBreaks:
    """Tests for line break rendering."""

    def test_hard_line_break(self, tmp_path):
        """Test hard line break renders as a <w:br/> element."""
        doc = Document(
            children=[Paragraph(content=[Text(content="Line 1"), LineBreak(soft=False), Text(content="Line 2")])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "linebreak.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "Line 1" in para.text
        assert "Line 2" in para.text
        assert "<w:br/>" in para._p.xml

    def test_soft_line_break_renders_as_space(self, tmp_path):
        """Test soft line break renders as a space, not a hard line break."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Bold text"), LineBreak(soft=True), Text(content="continues here")])
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "soft_linebreak.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert para.text == "Bold text continues here"
        assert "<w:br/>" not in para._p.xml


@pytest.mark.unit
@pytest.mark.docx
class TestCodeBlockStyle:
    """Tests for CodeBlock style creation."""

    def test_code_block_style_created(self, tmp_path):
        """Test that CodeBlock style is created when code blocks are present."""
        doc = Document(children=[CodeBlock(content="print('hello')", language="python")])
        renderer = DocxRenderer()
        output_file = tmp_path / "codeblock_style.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Check that CodeBlock style exists
        style_names = [s.name for s in docx_doc.styles]
        assert "CodeBlock" in style_names

    def test_no_code_block_style_when_no_code_blocks(self, tmp_path):
        """Test that CodeBlock style is not created when no code blocks are present."""
        doc = Document(children=[Paragraph(content=[Text(content="No code here")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "no_codeblock.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Check that CodeBlock style does not exist
        style_names = [s.name for s in docx_doc.styles]
        assert "CodeBlock" not in style_names

    def test_code_block_uses_style(self, tmp_path):
        """Test that code blocks use the CodeBlock style."""
        doc = Document(children=[CodeBlock(content="def foo():\n    pass", language="python")])
        renderer = DocxRenderer()
        output_file = tmp_path / "codeblock_uses_style.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Find the code block paragraph
        code_para = None
        for para in docx_doc.paragraphs:
            if "def foo()" in para.text:
                code_para = para
                break

        assert code_para is not None
        assert code_para.style.name == "CodeBlock"


@pytest.mark.unit
@pytest.mark.docx
class TestHeadingFormattingWithoutStyles:
    """Tests for heading rendering with use_styles=False."""

    def test_heading_bold_without_styles(self, tmp_path):
        """Test that headings are bold when use_styles=False."""
        doc = Document(children=[Heading(level=1, content=[Text(content="Test Heading")])])
        options = DocxRendererOptions(use_styles=False)
        renderer = DocxRenderer(options)
        output_file = tmp_path / "heading_no_styles.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Find the heading paragraph
        heading_para = None
        for para in docx_doc.paragraphs:
            if "Test Heading" in para.text:
                heading_para = para
                break

        assert heading_para is not None, "Heading not found"
        # At least one run should be bold
        has_bold = any(run.bold for run in heading_para.runs)
        assert has_bold, "Heading should have bold formatting when use_styles=False"

    def test_heading_font_size_without_styles(self, tmp_path):
        """Test that custom heading font sizes are applied when use_styles=False."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Large Heading")]),
                Heading(level=2, content=[Text(content="Medium Heading")]),
            ]
        )

        # Custom font sizes for headings
        options = DocxRendererOptions(use_styles=False, heading_font_sizes={1: 24, 2: 18})
        renderer = DocxRenderer(options)
        output_file = tmp_path / "heading_custom_sizes.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))

        # Find h1
        h1_para = None
        h2_para = None
        for para in docx_doc.paragraphs:
            if "Large Heading" in para.text:
                h1_para = para
            elif "Medium Heading" in para.text:
                h2_para = para

        assert h1_para is not None, "H1 not found"
        assert h2_para is not None, "H2 not found"

        # Check font sizes are applied
        h1_sizes = [run.font.size for run in h1_para.runs if run.font.size]
        h2_sizes = [run.font.size for run in h2_para.runs if run.font.size]

        # Import Pt for comparison
        from docx.shared import Pt

        assert any(size == Pt(24) for size in h1_sizes), "H1 should have 24pt font size"
        assert any(size == Pt(18) for size in h2_sizes), "H2 should have 18pt font size"

    def test_heading_with_formatting_without_styles(self, tmp_path):
        """Test heading with inline formatting when use_styles=False."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Normal "), Emphasis(content=[Text(content="emphasized")])])
            ]
        )
        options = DocxRendererOptions(use_styles=False)
        renderer = DocxRenderer(options)
        output_file = tmp_path / "heading_formatted_no_styles.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        heading_para = None
        for para in docx_doc.paragraphs:
            if "Normal" in para.text and "emphasized" in para.text:
                heading_para = para
                break

        assert heading_para is not None, "Heading not found"
        # Should have both regular and italic runs, all bold
        has_italic = any(run.italic for run in heading_para.runs)
        all_bold = all(run.bold for run in heading_para.runs if run.text.strip())
        assert has_italic, "Should have italic formatting"
        assert all_bold, "All runs should be bold (heading-level formatting)"


@pytest.mark.unit
@pytest.mark.docx
class TestHyperlinkWhitespace:
    """Tests for hyperlink whitespace preservation."""

    def test_hyperlink_with_leading_space(self, tmp_path):
        """Test hyperlink text with leading space is preserved."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content=" Link Text")])])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "link_leading_space.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]

        # Check hyperlink element in XML
        from docx.oxml.ns import qn

        hyperlinks = para._element.findall(qn("w:hyperlink"))
        assert len(hyperlinks) > 0, "No hyperlinks found"

        hyperlink = hyperlinks[0]
        runs = hyperlink.findall(qn("w:r"))
        text_elements = runs[0].findall(qn("w:t"))

        # Verify xml:space="preserve" is present
        space_attr = text_elements[0].get(qn("xml:space"))
        assert space_attr == "preserve", "xml:space='preserve' attribute should be present"

        # Verify text has leading space
        assert text_elements[0].text == " Link Text", "Leading space should be preserved"

    def test_hyperlink_with_trailing_space(self, tmp_path):
        """Test hyperlink text with trailing space is preserved."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Link Text ")])])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "link_trailing_space.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]

        # Check hyperlink element in XML
        from docx.oxml.ns import qn

        hyperlinks = para._element.findall(qn("w:hyperlink"))
        text_elements = hyperlinks[0].findall(qn("w:r"))[0].findall(qn("w:t"))

        # Verify xml:space="preserve" is present
        space_attr = text_elements[0].get(qn("xml:space"))
        assert space_attr == "preserve", "xml:space='preserve' attribute should be present"

        # Verify text has trailing space
        assert text_elements[0].text == "Link Text ", "Trailing space should be preserved"

    def test_hyperlink_with_multiple_spaces(self, tmp_path):
        """Test hyperlink text with multiple consecutive spaces is preserved."""
        doc = Document(
            children=[Paragraph(content=[Link(url="https://example.com", content=[Text(content="Link  Text")])])]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "link_multiple_spaces.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]

        # Check hyperlink element in XML
        from docx.oxml.ns import qn

        hyperlinks = para._element.findall(qn("w:hyperlink"))
        text_elements = hyperlinks[0].findall(qn("w:r"))[0].findall(qn("w:t"))

        # Verify xml:space="preserve" is present
        space_attr = text_elements[0].get(qn("xml:space"))
        assert space_attr == "preserve", "xml:space='preserve' attribute should be present"

        # Verify double space is preserved
        assert text_elements[0].text == "Link  Text", "Multiple spaces should be preserved"


@pytest.mark.unit
@pytest.mark.docx
class TestComments:
    """Tests for comment rendering."""

    def test_block_comment_with_author(self, tmp_path):
        """Test block comment with author metadata."""
        doc = Document(
            children=[
                Comment(
                    content="This is a review comment",
                    metadata={"author": "John Doe", "date": "2025-01-20", "comment_type": "docx_review"},
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "block_comment.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        # Comment should be rendered (either as native comment or fallback)
        assert docx_doc is not None

    def test_block_comment_without_author(self, tmp_path):
        """Test block comment without author metadata."""
        doc = Document(children=[Comment(content="Anonymous comment", metadata={"comment_type": "generic"})])
        renderer = DocxRenderer()
        output_file = tmp_path / "block_comment_no_author.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None

    def test_inline_comment_with_author(self, tmp_path):
        """Test inline comment with author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="This is text "),
                        CommentInline(
                            content="Needs clarification",
                            metadata={"author": "Jane Smith", "comment_type": "docx_review"},
                        ),
                        Text(content=" more text."),
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "inline_comment.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        # Comment should be rendered
        para = docx_doc.paragraphs[0]
        assert "This is text" in para.text
        assert "more text" in para.text

    def test_inline_comment_without_author(self, tmp_path):
        """Test inline comment without author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        CommentInline(content="anonymous comment", metadata={}),
                        Text(content=" here."),
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "inline_comment_no_author.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "Text with" in para.text

    def test_comment_with_label(self, tmp_path):
        """Test comment with label metadata."""
        doc = Document(
            children=[
                Comment(
                    content="Important review note",
                    metadata={"author": "Reviewer", "label": "1", "date": "2025-01-20"},
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "comment_with_label.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None

    def test_multiple_comments(self, tmp_path):
        """Test multiple comments in document."""
        doc = Document(
            children=[
                Comment(content="First comment", metadata={"author": "User 1"}),
                Paragraph(content=[Text(content="Text here")]),
                Comment(content="Second comment", metadata={"author": "User 2"}),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "multiple_comments.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.paragraphs) >= 1

    def test_comment_initials_generation(self, tmp_path):
        """Test automatic generation of initials from author name."""
        doc = Document(
            children=[
                Comment(content="Test comment", metadata={"author": "John David Smith", "comment_type": "docx_review"})
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "comment_initials.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        # Initials should be generated as "JDS" from "John David Smith"
        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None

    def test_comment_with_explicit_initials(self, tmp_path):
        """Test comment with explicitly provided initials."""
        doc = Document(
            children=[
                Comment(
                    content="Test comment",
                    metadata={"author": "John Smith", "initials": "JS", "comment_type": "docx_review"},
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "comment_explicit_initials.docx"
        renderer.render(doc, output_file)

        assert output_file.exists()
        docx_doc = DocxDocument(str(output_file))
        assert docx_doc is not None


@pytest.mark.unit
@pytest.mark.docx
class TestCommentModes:
    """Tests for comment rendering modes."""

    def test_comment_mode_ignore(self, tmp_path):
        """Test that comments are ignored when comment_mode is 'ignore'."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Visible text")]),
                Comment(content="This should be ignored", metadata={"author": "Test"}),
            ]
        )
        options = DocxRendererOptions(comment_mode="ignore")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "comment_ignore.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "Visible text" in text_content
        # Comment should not appear in text
        assert "This should be ignored" not in text_content

    def test_comment_mode_visible(self, tmp_path):
        """Test that comments are visible when comment_mode is 'visible'."""
        doc = Document(
            children=[
                Comment(
                    content="Visible comment",
                    metadata={"author": "Author", "date": "2025-01-20", "comment_type": "review"},
                )
            ]
        )
        options = DocxRendererOptions(comment_mode="visible")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "comment_visible.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "Visible comment" in text_content
        assert "Author" in text_content

    def test_inline_comment_mode_ignore(self, tmp_path):
        """Test inline comment is ignored when comment_mode is 'ignore'."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Before "),
                        CommentInline(content="ignored inline", metadata={}),
                        Text(content=" after"),
                    ]
                )
            ]
        )
        options = DocxRendererOptions(comment_mode="ignore")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "inline_ignore.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "Before" in para.text
        assert "after" in para.text
        assert "ignored inline" not in para.text

    def test_inline_comment_mode_visible(self, tmp_path):
        """Test inline comment is visible when comment_mode is 'visible'."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text "),
                        CommentInline(
                            content="visible inline",
                            metadata={"author": "Test Author", "date": "2025-01-20", "label": "1"},
                        ),
                    ]
                )
            ]
        )
        options = DocxRendererOptions(comment_mode="visible")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "inline_visible.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "visible inline" in para.text
        assert "Test Author" in para.text


@pytest.mark.unit
@pytest.mark.docx
class TestRenderToBytes:
    """Tests for render_to_bytes method."""

    def test_render_to_bytes_simple(self):
        """Test render_to_bytes returns valid DOCX bytes."""
        doc = Document(children=[Paragraph(content=[Text(content="Byte content")])])
        renderer = DocxRenderer()
        result = renderer.render_to_bytes(doc)

        assert isinstance(result, bytes)
        assert len(result) > 0

        # Verify it's a valid DOCX by loading it
        from io import BytesIO

        docx_doc = DocxDocument(BytesIO(result))
        assert "Byte content" in docx_doc.paragraphs[0].text


@pytest.mark.unit
@pytest.mark.docx
class TestMetadataKeywords:
    """Tests for document metadata with keywords."""

    def test_keywords_as_list(self, tmp_path):
        """Test keywords metadata when provided as a list."""
        doc = Document(
            metadata={"title": "Test", "keywords": ["keyword1", "keyword2", "keyword3"]},
            children=[Paragraph(content=[Text(content="Content")])],
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "keywords_list.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert "keyword1" in docx_doc.core_properties.keywords
        assert "keyword2" in docx_doc.core_properties.keywords
        assert "keyword3" in docx_doc.core_properties.keywords

    def test_keywords_as_string(self, tmp_path):
        """Test keywords metadata when provided as a string."""
        doc = Document(
            metadata={"keywords": "single keyword string"},
            children=[Paragraph(content=[Text(content="Content")])],
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "keywords_string.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert docx_doc.core_properties.keywords == "single keyword string"


@pytest.mark.unit
@pytest.mark.docx
class TestTableSpanning:
    """Tests for table colspan and rowspan."""

    def test_table_with_colspan(self, tmp_path):
        """Test table with column spanning."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(
                        cells=[
                            TableCell(content=[Text(content="Merged Header")], colspan=2),
                            TableCell(content=[Text(content="Single")]),
                        ]
                    ),
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="A")]),
                                TableCell(content=[Text(content="B")]),
                                TableCell(content=[Text(content="C")]),
                            ]
                        )
                    ],
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "table_colspan.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.tables) == 1
        table = docx_doc.tables[0]
        assert len(table.rows) == 2

    def test_table_with_rowspan(self, tmp_path):
        """Test table with row spanning."""
        doc = Document(
            children=[
                Table(
                    rows=[
                        TableRow(
                            cells=[
                                TableCell(content=[Text(content="Merged")], rowspan=2),
                                TableCell(content=[Text(content="Row 1")]),
                            ]
                        ),
                        TableRow(cells=[TableCell(content=[Text(content="Row 2")])]),
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "table_rowspan.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.tables) == 1


@pytest.mark.unit
@pytest.mark.docx
class TestSubscriptSuperscript:
    """Tests for subscript and superscript rendering."""

    def test_superscript(self, tmp_path):
        """Test superscript rendering."""
        from all2md.ast import Superscript

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="E = mc"),
                        Superscript(content=[Text(content="2")]),
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "superscript.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        assert "E = mc" in para.text
        assert "2" in para.text
        # Check that some run has superscript
        has_superscript = any(run.font.superscript for run in para.runs if run.text == "2")
        assert has_superscript

    def test_subscript(self, tmp_path):
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
        renderer = DocxRenderer()
        output_file = tmp_path / "subscript.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        para = docx_doc.paragraphs[0]
        text = para.text
        assert "H" in text
        assert "2" in text
        assert "O" in text


@pytest.mark.unit
@pytest.mark.docx
class TestListInstances:
    """Each list gets a restarting numbering instance, so Word sees one list per AST list."""

    @staticmethod
    def _bullets(*texts):
        return List(ordered=False, items=[ListItem(children=[Paragraph(content=[Text(content=t)])]) for t in texts])

    def test_adjacent_bullet_lists_read_back_as_two(self):
        from all2md import to_ast

        doc = Document(children=[self._bullets("a", "b"), self._bullets("c")])
        result = DocxRenderer().render_to_bytes(doc)
        lists = [child for child in to_ast(result, source_format="docx").children if isinstance(child, List)]
        assert [(lst.ordered, len(lst.items)) for lst in lists] == [(False, 2), (False, 1)]

    def test_each_bullet_list_has_its_own_restarting_instance(self):
        from docx.oxml.ns import qn

        doc = Document(children=[self._bullets("a"), Paragraph(content=[Text(content="between")]), self._bullets("b")])
        docx_doc = DocxDocument(BytesIO(DocxRenderer().render_to_bytes(doc)))
        num_ids = [
            p._p.pPr.numPr.numId.val for p in docx_doc.paragraphs if p._p.pPr is not None and p._p.pPr.numPr is not None
        ]
        assert len(num_ids) == 2 and num_ids[0] != num_ids[1]
        numbering = docx_doc.part.numbering_part.element
        for num_id in num_ids:
            (num,) = [el for el in numbering.findall(qn("w:num")) if el.get(qn("w:numId")) == str(num_id)]
            assert num.find(qn("w:lvlOverride")) is not None


@pytest.mark.unit
@pytest.mark.docx
class TestNestedLists:
    """Tests for nested list rendering."""

    def test_nested_unordered_list(self, tmp_path):
        """Test nested unordered list."""
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
                                        ListItem(children=[Paragraph(content=[Text(content="Nested 1.1")])]),
                                        ListItem(children=[Paragraph(content=[Text(content="Nested 1.2")])]),
                                    ],
                                ),
                            ]
                        ),
                        ListItem(children=[Paragraph(content=[Text(content="Item 2")])]),
                    ],
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "nested_list.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        paragraphs = docx_doc.paragraphs
        text_content = [p.text for p in paragraphs]
        assert "Item 1" in text_content
        assert "Nested 1.1" in text_content
        assert "Item 2" in text_content

    def test_multi_paragraph_list_item(self, tmp_path):
        """Test list item with multiple paragraphs."""
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
                        )
                    ],
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "multi_para_list.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "First paragraph" in text_content
        assert "Second paragraph" in text_content


@pytest.mark.unit
@pytest.mark.docx
class TestBlockquoteWithElements:
    """Tests for blockquote with different element types."""

    def test_blockquote_with_heading(self, tmp_path):
        """Test heading inside blockquote has indentation."""
        doc = Document(children=[BlockQuote(children=[Heading(level=2, content=[Text(content="Quoted Heading")])])])
        renderer = DocxRenderer()
        output_file = tmp_path / "bq_heading.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        heading_para = None
        for para in docx_doc.paragraphs:
            if "Quoted Heading" in para.text:
                heading_para = para
                break

        assert heading_para is not None
        assert heading_para.paragraph_format.left_indent is not None

    def test_blockquote_with_code_block(self, tmp_path):
        """Test code block inside blockquote has indentation."""
        doc = Document(children=[BlockQuote(children=[CodeBlock(content="code inside quote", language="python")])])
        renderer = DocxRenderer()
        output_file = tmp_path / "bq_code.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        code_para = None
        for para in docx_doc.paragraphs:
            if "code inside quote" in para.text:
                code_para = para
                break

        assert code_para is not None
        assert code_para.paragraph_format.left_indent is not None


@pytest.mark.unit
@pytest.mark.docx
class TestTableStyle:
    """Tests for table style option."""

    def test_table_with_custom_style(self, tmp_path):
        """Test table with custom table style."""
        doc = Document(
            children=[
                Table(
                    header=TableRow(cells=[TableCell(content=[Text(content="Header")])]),
                    rows=[TableRow(cells=[TableCell(content=[Text(content="Data")])])],
                )
            ]
        )
        options = DocxRendererOptions(table_style="Table Grid")
        renderer = DocxRenderer(options)
        output_file = tmp_path / "table_style.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        assert len(docx_doc.tables) == 1
        # Table should exist and have content
        assert "Header" in docx_doc.tables[0].rows[0].cells[0].text


@pytest.mark.unit
@pytest.mark.docx
class TestEmptyTable:
    """Tests for empty table handling."""

    def test_empty_table_no_rows(self, tmp_path):
        """Test table with no rows is handled gracefully."""
        doc = Document(children=[Table(rows=[])])
        renderer = DocxRenderer()
        output_file = tmp_path / "empty_table.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Empty table should not be created
        assert len(docx_doc.tables) == 0


@pytest.mark.unit
@pytest.mark.docx
class TestDefinitionListAdvanced:
    """Advanced tests for definition list rendering."""

    def test_definition_list_with_paragraph_content(self, tmp_path):
        """Test definition list where content is wrapped in Paragraph."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="API")]),
                            [
                                DefinitionDescription(
                                    content=[Paragraph(content=[Text(content="Application Programming Interface")])]
                                )
                            ],
                        )
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "deflist_para.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "API" in text_content
        assert "Application Programming Interface" in text_content

    def test_definition_list_multiple_descriptions(self, tmp_path):
        """Test term with multiple descriptions."""
        doc = Document(
            children=[
                DefinitionList(
                    items=[
                        (
                            DefinitionTerm(content=[Text(content="Term")]),
                            [
                                DefinitionDescription(content=[Text(content="First description")]),
                                DefinitionDescription(content=[Text(content="Second description")]),
                            ],
                        )
                    ]
                )
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "deflist_multi_desc.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        text_content = " ".join(p.text for p in docx_doc.paragraphs)
        assert "Term" in text_content
        assert "First description" in text_content
        assert "Second description" in text_content


@pytest.mark.unit
@pytest.mark.docx
class TestTitlePromotion:
    """Tests for H1-to-Title promotion in DOCX rendering."""

    def test_leading_h1_uses_title_style(self, tmp_path):
        """Test that a leading H1 is rendered with Word's Title style."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="My Title")]),
                Heading(level=2, content=[Text(content="Section One")]),
                Paragraph(content=[Text(content="Body text")]),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "title.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        # Find the title paragraph
        title_para = None
        for para in docx_doc.paragraphs:
            if para.text == "My Title":
                title_para = para
                break
        assert title_para is not None
        assert title_para.style.name == "Title"

    def test_subsequent_headings_promoted(self, tmp_path):
        """Test that H2 becomes Heading 1 after title promotion."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="My Title")]),
                Heading(level=2, content=[Text(content="Section One")]),
                Heading(level=3, content=[Text(content="Subsection")]),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "promoted.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        section_para = None
        subsection_para = None
        for para in docx_doc.paragraphs:
            if para.text == "Section One":
                section_para = para
            elif para.text == "Subsection":
                subsection_para = para

        assert section_para is not None
        assert section_para.style.name == "Heading 1"
        assert subsection_para is not None
        assert subsection_para.style.name == "Heading 2"

    @pytest.mark.parametrize(
        "leading",
        [
            # PMC10000026.1: a second H1 used to be written as "Heading 1" beside the H2s.
            [Heading(level=1, content=[Text(content="animals")]), Heading(level=1, content=[Text(content="Article")])],
            # PMC8000039.1: a logo ahead of the H1 left every heading a level too high.
            [
                Paragraph(content=[Image(url="data:image/png;base64," + _PNG_1PX, alt_text="")]),
                Heading(level=1, content=[Text(content="microorganisms")]),
            ],
        ],
        ids=["two h1", "image first"],
    )
    def test_heading_levels_survive_a_docx_round_trip(self, leading):
        from all2md import from_ast, to_ast

        doc = Document(
            children=[
                *leading,
                Heading(level=2, content=[Text(content="1. Introduction")]),
                Heading(level=3, content=[Text(content="1.1. Scope")]),
            ]
        )

        back = to_ast(BytesIO(from_ast(doc, "docx")), source_format="docx")

        def levels(document):
            return [
                (h.level, "".join(t.content for t in h.content)) for h in document.children if isinstance(h, Heading)
            ]

        assert levels(back) == levels(doc)

    def test_promote_title_false_keeps_h1(self, tmp_path):
        """Test that promote_title=False keeps H1 as Heading 1."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="My Title")]),
                Heading(level=2, content=[Text(content="Section")]),
            ]
        )
        options = DocxRendererOptions(promote_title=False)
        renderer = DocxRenderer(options=options)
        output_file = tmp_path / "no_promote.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        title_para = None
        section_para = None
        for para in docx_doc.paragraphs:
            if para.text == "My Title":
                title_para = para
            elif para.text == "Section":
                section_para = para

        assert title_para is not None
        assert title_para.style.name == "Heading 1"
        assert section_para is not None
        assert section_para.style.name == "Heading 2"

    def test_no_h1_no_title_style(self, tmp_path):
        """Test that documents without a leading H1 are unaffected."""
        doc = Document(
            children=[
                Heading(level=2, content=[Text(content="Section")]),
                Paragraph(content=[Text(content="Body")]),
            ]
        )
        renderer = DocxRenderer()
        output_file = tmp_path / "no_title.docx"
        renderer.render(doc, output_file)

        docx_doc = DocxDocument(str(output_file))
        section_para = None
        for para in docx_doc.paragraphs:
            if para.text == "Section":
                section_para = para
                break
        assert section_para is not None
        assert section_para.style.name == "Heading 2"


def _georgia_template(tmp_path, *, suffix: str = ".docx"):
    """Build a template whose Normal style is Georgia 12; ``.dotx`` declares the template type."""
    import zipfile

    from docx.shared import Pt

    template_doc = DocxDocument()
    template_doc.styles["Normal"].font.name = "Georgia"
    template_doc.styles["Normal"].font.size = Pt(12)
    docx_path = tmp_path / "template.docx"
    template_doc.save(str(docx_path))
    if suffix == ".docx":
        return docx_path
    dotx_path = tmp_path / "template.dotx"
    with zipfile.ZipFile(docx_path) as zin, zipfile.ZipFile(dotx_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "[Content_Types].xml":
                data = data.replace(b"wordprocessingml.document.main+xml", b"wordprocessingml.template.main+xml")
            zout.writestr(info, data)
    return dotx_path


def _normal_font(docx_bytes: bytes) -> tuple:
    font = DocxDocument(BytesIO(docx_bytes)).styles["Normal"].font
    return font.name, font.size.pt if font.size else None


@pytest.mark.unit
@pytest.mark.docx
class TestTemplateFont:
    """A template's body font is the reason to pass the template, so it is kept."""

    doc = Document(children=[Paragraph(content=[Text(content="Body")])])

    def test_a_blank_document_gets_calibri_11(self):
        assert _normal_font(DocxRenderer().render_to_bytes(self.doc)) == ("Calibri", 11)

    def test_a_template_keeps_its_own_font(self, tmp_path):
        """It used to be overwritten with Calibri 11, the defaults, on every render."""
        options = DocxRendererOptions(template_path=str(_georgia_template(tmp_path)))

        assert _normal_font(DocxRenderer(options).render_to_bytes(self.doc)) == ("Georgia", 12)

    def test_a_named_font_still_wins_over_the_template(self, tmp_path):
        options = DocxRendererOptions(
            template_path=str(_georgia_template(tmp_path)), default_font="Arial", default_font_size=14
        )

        assert _normal_font(DocxRenderer(options).render_to_bytes(self.doc)) == ("Arial", 14)

    def test_a_named_size_alone_keeps_the_templates_face(self, tmp_path):
        options = DocxRendererOptions(template_path=str(_georgia_template(tmp_path)), default_font_size=10)

        assert _normal_font(DocxRenderer(options).render_to_bytes(self.doc)) == ("Georgia", 10)

    def test_a_dotx_template_is_accepted(self, tmp_path):
        """python-docx refuses the template content type; the renderer reads it anyway."""
        template = _georgia_template(tmp_path, suffix=".dotx")
        before = template.read_bytes()

        result = DocxRenderer(DocxRendererOptions(template_path=str(template))).render_to_bytes(self.doc)

        assert _normal_font(result) == ("Georgia", 12)
        assert "Body" in [p.text for p in DocxDocument(BytesIO(result)).paragraphs]
        assert template.read_bytes() == before


def _pandoc_like_template(path) -> str:
    """A reference document with pandoc's style names and no Word ``Quote``.

    Its code, link and quote styles have their own look, so a test can tell
    whether the renderer used them or wrote over them with direct formatting.
    """
    from docx.enum.style import WD_STYLE_TYPE
    from docx.shared import Pt, RGBColor

    template_doc = DocxDocument()
    styles = template_doc.styles
    for name in ("Quote", "Light Grid Accent 1"):
        element = styles[name].element
        element.getparent().remove(element)
    source = styles.add_style("Source Code", WD_STYLE_TYPE.PARAGRAPH)
    source.font.name = "Consolas"
    source.font.size = Pt(9)
    verbatim = styles.add_style("Verbatim Char", WD_STYLE_TYPE.CHARACTER)
    verbatim.font.name = "Consolas"
    styles.add_style("Block Text", WD_STYLE_TYPE.PARAGRAPH).font.italic = True
    styles.add_style("Hyperlink", WD_STYLE_TYPE.CHARACTER).font.color.rgb = RGBColor(0, 0x80, 0)
    styles.add_style("Table", WD_STYLE_TYPE.TABLE)
    template_doc.save(str(path))
    return str(path)


_SAMPLE = Document(
    children=[
        Paragraph(
            content=[
                Link(url="https://example.com", content=[Text(content="site")]),
                Text(content=" and "),
                Code(content="code"),
            ]
        ),
        CodeBlock(content="print(1)"),
        BlockQuote(children=[Paragraph(content=[Text(content="quoted")])]),
        Table(
            header=TableRow(cells=[TableCell(content=[Text(content="a")])]),
            rows=[TableRow(cells=[TableCell(content=[Text(content="1")])])],
        ),
    ]
)


def _render(options: DocxRendererOptions | None = None):
    return DocxDocument(BytesIO(DocxRenderer(options).render_to_bytes(_SAMPLE)))


def _runs(docx_doc, text: str) -> list:
    return [run for paragraph in docx_doc.paragraphs for run in paragraph.runs if run.text.strip() == text]


@pytest.mark.unit
@pytest.mark.docx
class TestTemplateStyles:
    """A template's own styles are used, not written over with direct formatting."""

    def test_links_are_blue_and_underlined_without_a_template(self):
        """python-docx's blank document has no Hyperlink style, so links printed as plain text."""
        style = _render().styles["Hyperlink"]
        assert str(style.font.color.rgb) == "0563C1"
        assert style.font.underline

    def test_a_templates_hyperlink_style_is_kept(self, tmp_path):
        docx_doc = _render(DocxRendererOptions(template_path=_pandoc_like_template(tmp_path / "ref.docx")))
        assert str(docx_doc.styles["Hyperlink"].font.color.rgb) == "008000"

    def test_code_is_styled_without_direct_formatting(self):
        docx_doc = _render()
        (block,) = [p for p in docx_doc.paragraphs if p.text == "print(1)"]
        assert block.style.name == "CodeBlock"
        assert block.runs[0].font.name is None
        assert block._p.pPr.find(qn("w:shd")) is None
        style = docx_doc.styles["CodeBlock"]
        assert (style.font.name, style.font.size.pt) == ("Courier New", 10)
        assert style.element.pPr.find(qn("w:shd")).get(qn("w:fill")) == "F0F0F0"
        (inline,) = _runs(docx_doc, "code")
        assert inline.style.name == "Verbatim Char"
        assert inline.font.name is None

    def test_a_templates_code_styles_keep_their_font(self, tmp_path):
        docx_doc = _render(DocxRendererOptions(template_path=_pandoc_like_template(tmp_path / "ref.docx")))
        (block,) = [p for p in docx_doc.paragraphs if p.text == "print(1)"]
        assert block.style.name == "Source Code"
        assert block.runs[0].font.name is None
        assert docx_doc.styles["Source Code"].font.name == "Consolas"
        assert docx_doc.styles["Verbatim Char"].font.name == "Consolas"
        assert "CodeBlock" not in [style.name for style in docx_doc.styles]

    def test_a_named_code_font_is_set_on_the_templates_styles(self, tmp_path):
        template = _pandoc_like_template(tmp_path / "ref.docx")
        docx_doc = _render(DocxRendererOptions(template_path=template, code_font="Menlo", code_font_size=8))
        for name in ("Source Code", "Verbatim Char"):
            assert (docx_doc.styles[name].font.name, docx_doc.styles[name].font.size.pt) == ("Menlo", 8)

    def test_without_styles_code_is_formatted_directly(self):
        docx_doc = _render(DocxRendererOptions(use_styles=False))
        (block,) = [p for p in docx_doc.paragraphs if p.text == "print(1)"]
        assert (block.runs[0].font.name, block.runs[0].font.size.pt) == ("Courier New", 10)
        shading = block._p.pPr.find(qn("w:shd"))
        assert (shading.get(qn("w:val")), shading.get(qn("w:fill"))) == ("clear", "F0F0F0")
        (inline,) = _runs(docx_doc, "code")
        assert inline.font.name == "Courier New"

    def test_pandoc_quote_and_table_styles_are_used(self, tmp_path):
        docx_doc = _render(DocxRendererOptions(template_path=_pandoc_like_template(tmp_path / "ref.docx")))
        (quote,) = [p for p in docx_doc.paragraphs if p.text == "quoted"]
        assert quote.style.name == "Block Text"
        assert docx_doc.tables[0].style.name == "Table"

    def test_a_missing_table_style_falls_back_to_table_grid(self):
        docx_doc = _render(DocxRendererOptions(table_style="No Such Style"))
        assert docx_doc.tables[0].style.name == "Table Grid"

    def test_the_pandoc_template_round_trips(self, tmp_path):
        from all2md import to_markdown

        options = DocxRendererOptions(template_path=_pandoc_like_template(tmp_path / "ref.docx"))
        markdown = to_markdown(DocxRenderer(options).render_to_bytes(_SAMPLE), source_format="docx")
        assert "[site](https://example.com) and `code`" in markdown
        assert "```\nprint(1)\n```" in markdown
        assert "> quoted" in markdown
