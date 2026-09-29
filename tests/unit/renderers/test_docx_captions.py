"""Figure and table captions survive a round trip through DOCX.

Word marks a caption only by its paragraph style ("Caption", the style Insert Caption
applies); nothing links it to the picture or table beside it. The renderer used to write
captions as plain centered italic paragraphs and dropped ``Table.caption`` outright, and
the parser never built a caption, so PDF -> DOCX kept 0 of the 95 figure captions in the
PMC development corpus as captions (``python -m benchmarks.pmc docx``).
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest

from all2md.ast import Document, Image, Paragraph, Table, TableCell, TableRow, Text
from all2md.ast.nodes import Figure, Node
from all2md.options.docx import DocxRendererOptions
from all2md.parsers.docx import DocxToAstConverter
from all2md.renderers.docx import DocxRenderer

docx = pytest.importorskip("docx")
PIL = pytest.importorskip("PIL.Image")

pytestmark = [pytest.mark.unit, pytest.mark.docx]


def _png() -> bytes:
    buffer = BytesIO()
    PIL.new("RGB", (4, 4)).save(buffer, "PNG")
    return buffer.getvalue()


def _image(alt: str = "alt", caption: str | None = None) -> Image:
    return Image(url="data:image/png;base64," + base64.b64encode(_png()).decode(), alt_text=alt, caption=caption)


def _row(*cells: str) -> TableRow:
    return TableRow(cells=[TableCell(content=[Text(content=cell)]) for cell in cells])


def _render(document: Document, options: DocxRendererOptions | None = None) -> bytes:
    buffer = BytesIO()
    DocxRenderer(options).render(document, buffer)
    return buffer.getvalue()


def _body(data: bytes) -> list[tuple[str, str, str]]:
    """Return the body as (kind, style, text): kind is p, pic (a picture paragraph) or tbl."""
    body = []
    word = docx.Document(BytesIO(data))
    for element in word.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            body.append(("tbl", "", ""))
        elif tag == "p":
            paragraph = docx.text.paragraph.Paragraph(element, word)
            has_picture = bool(element.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/picture}pic"))
            if has_picture or paragraph.text:
                body.append(("pic" if has_picture else "p", paragraph.style.name, paragraph.text))
    return body


def _parse(data: bytes) -> list[Node]:
    return DocxToAstConverter().parse(BytesIO(data)).children


def _shape(nodes: list[Node]) -> list[tuple[str, str | None, int]]:
    return [(type(node).__name__, getattr(node, "caption", None), len(getattr(node, "children", []))) for node in nodes]


class TestRenderer:
    def test_figure_caption_is_a_caption_paragraph_below_the_images(self) -> None:
        figure = Figure(children=[Paragraph(content=[_image()]), Paragraph(content=[_image()])], caption="Figure 1.")
        assert _body(_render(Document(children=[figure]))) == [
            ("pic", "Normal", ""),
            ("pic", "Normal", ""),
            ("p", "Caption", "Figure 1."),
        ]

    def test_table_caption_is_a_caption_paragraph_above_the_table(self) -> None:
        table = Table(header=_row("a"), rows=[_row("1")], caption="Table 1.")
        assert _body(_render(Document(children=[table]))) == [("p", "Caption", "Table 1."), ("tbl", "", "")]

    def test_image_caption_is_written_instead_of_its_alt_text(self) -> None:
        document = Document(children=[Paragraph(content=[_image(alt="a picture", caption="Figure 3.")])])
        assert _body(_render(document)) == [("pic", "Normal", ""), ("p", "Caption", "Figure 3.")]

    def test_an_uncaptioned_image_still_prints_its_alt_text(self) -> None:
        assert _body(_render(Document(children=[Paragraph(content=[_image(alt="a picture")])])))[1][2] == "a picture"

    def test_an_image_carried_as_alt_text_alone_prints_it(self) -> None:
        # attachment_mode="alt_text" yields an Image with no url; Markdown keeps ![A cat]().
        document = Document(children=[Paragraph(content=[Image(url="", alt_text="A cat")])])
        assert _body(_render(document)) == [("p", "Normal", "A cat")]

    def test_an_image_that_fails_to_load_still_prints_its_alt_text(self, tmp_path: Path) -> None:
        document = Document(children=[Paragraph(content=[Image(url=str(tmp_path / "gone.png"), alt_text="A cat")])])
        assert _body(_render(document)) == [("p", "Normal", "A cat")]

    def test_an_image_without_a_picture_still_prints_its_caption(self) -> None:
        document = Document(children=[Paragraph(content=[Image(url="", alt_text="A cat", caption="Figure 5.")])])
        assert _body(_render(document)) == [("p", "Caption", "Figure 5.")]

    def test_an_alt_text_image_in_a_captioned_figure_prints_only_the_caption(self) -> None:
        figure = Figure(children=[Paragraph(content=[Image(url="", alt_text="A cat")])], caption="Figure 6.")
        assert _body(_render(Document(children=[figure]))) == [("p", "Caption", "Figure 6.")]

    def test_alt_text_is_the_picture_description(self) -> None:
        word = docx.Document(BytesIO(_render(Document(children=[Paragraph(content=[_image(alt="a picture")])]))))
        assert word.inline_shapes[0]._inline.docPr.get("descr") == "a picture"

    def test_a_template_without_the_style_gets_an_italic_line(self, tmp_path: Path) -> None:
        template = docx.Document()
        template.styles["Caption"].delete()
        template.save(tmp_path / "template.docx")
        options = DocxRendererOptions(template_path=str(tmp_path / "template.docx"))
        word = docx.Document(BytesIO(_render(Document(children=[Figure(caption="Figure 2.")]), options)))
        caption = next(paragraph for paragraph in word.paragraphs if paragraph.text == "Figure 2.")
        assert caption.style.name == "Normal"
        assert caption.runs[0].italic


class TestRoundTrip:
    def test_every_caption_comes_back_a_caption(self) -> None:
        document = Document(
            children=[
                Paragraph(content=[Text(content="Intro")]),
                Figure(children=[Paragraph(content=[_image()]), Paragraph(content=[_image()])], caption="Figure 1."),
                Table(header=_row("a", "b"), rows=[_row("1", "2")], caption="Table 1."),
                Figure(caption="Figure 2."),
                Paragraph(content=[_image(caption="Figure 3.")]),
                Paragraph(content=[Text(content="End")]),
            ]
        )
        assert _shape(_parse(_render(document))) == [
            ("Paragraph", None, 0),
            ("Figure", "Figure 1.", 2),
            ("Table", "Table 1.", 0),
            ("Figure", "Figure 2.", 0),
            ("Figure", "Figure 3.", 1),
            ("Paragraph", None, 0),
        ]

    def test_alt_text_comes_back(self) -> None:
        figure = _parse(
            _render(Document(children=[Figure(children=[Paragraph(content=[_image("a cat")])], caption="C")]))
        )
        assert isinstance(figure[0], Figure)
        image = figure[0].children[0].content[0]  # type: ignore[attr-defined]
        assert image.alt_text == "a cat"


class TestParserPairing:
    """Captions in a document Word wrote, placed by hand the way people place them."""

    @staticmethod
    def _word(*blocks: str) -> bytes:
        word = docx.Document()
        for block in blocks:
            if block == "IMG":
                word.add_paragraph().add_run().add_picture(BytesIO(_png()))
            elif block == "TBL":
                word.add_table(rows=2, cols=2).cell(0, 0).text = "x"
            elif block.startswith("CAP "):
                word.add_paragraph(block[4:], style="Caption")
            else:
                word.add_paragraph(block)
        buffer = BytesIO()
        word.save(buffer)
        return buffer.getvalue()

    def test_a_caption_below_a_table_is_the_tables(self) -> None:
        assert _shape(_parse(self._word("TBL", "CAP Table 1. Below.")))[0] == ("Table", "Table 1. Below.", 0)

    def test_a_caption_above_an_image_is_the_figures(self) -> None:
        assert _shape(_parse(self._word("CAP Figure 1. Above.", "IMG", "text"))) == [
            ("Figure", "Figure 1. Above.", 1),
            ("Paragraph", None, 0),
        ]

    def test_a_table_label_breaks_the_tie_between_an_image_and_a_table(self) -> None:
        assert _shape(_parse(self._word("IMG", "CAP Table 2. Tie.", "TBL"))) == [
            ("Paragraph", None, 0),
            ("Table", "Table 2. Tie.", 0),
        ]
        assert _shape(_parse(self._word("IMG", "CAP Figure 2. Tie.", "TBL")))[0] == ("Figure", "Figure 2. Tie.", 1)

    def test_images_captioned_below_are_not_claimed_from_above(self) -> None:
        assert _shape(_parse(self._word("CAP Figure 1.", "IMG", "CAP Figure 2."))) == [
            ("Figure", "Figure 1.", 0),
            ("Figure", "Figure 2.", 1),
        ]

    def test_a_caption_with_nothing_beside_it_records_a_figure(self) -> None:
        assert _shape(_parse(self._word("before", "CAP Figure 4. A chart.", "after"))) == [
            ("Paragraph", None, 0),
            ("Figure", "Figure 4. A chart.", 0),
            ("Paragraph", None, 0),
        ]
