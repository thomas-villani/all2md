"""A run-in heading runs on into its text in Word, through the style separator.

The PDF parser splits a bold run-in title from its sentence (``**5. Indemnification.**
The Company shall ...``, #688), so the title is a heading. In Word it used to become a
heading on a line of its own, which the source never had. The renderer now hides the
heading's paragraph mark (``w:vanish`` + ``w:specVanish``), Word's style separator: Word
draws the heading and its text as one line and keeps the heading in the outline.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Heading, List, ListItem, Paragraph, Table, TableCell, TableRow, Text
from all2md.options.pdf import PdfOptions
from all2md.renderers.docx import DocxRenderer

docx = pytest.importorskip("docx")

pytestmark = [pytest.mark.unit, pytest.mark.docx]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _run_in(title: str = "5. Indemnification", stop: str = ".") -> Heading:
    return Heading(level=2, content=[Text(content=title)], metadata={"run_in": True, "run_in_stop": stop})


def _body(text: str = "The Company shall indemnify the Purchaser.") -> Paragraph:
    return Paragraph(content=[Text(content=text)])


def _paragraphs(document: Document) -> list:
    buffer = BytesIO()
    DocxRenderer().render(document, buffer)
    return docx.Document(BytesIO(buffer.getvalue())).paragraphs


def _separated(paragraph) -> bool:
    mark = paragraph._p.find(f"{_W}pPr/{_W}rPr")
    return mark is not None and mark.find(f"{_W}vanish") is not None and mark.find(f"{_W}specVanish") is not None


class TestARunInHeadingRunsOn:
    def test_its_mark_is_a_style_separator_and_its_stop_comes_back(self) -> None:
        heading, body = _paragraphs(Document(children=[_run_in(), _body()]))
        assert _separated(heading)
        assert heading.text == "5. Indemnification. "
        assert heading.style.name == "Heading 2"
        assert not _separated(body)
        assert body.text.startswith("The Company shall")

    def test_a_title_cut_at_a_colon_gets_its_colon_back(self) -> None:
        heading, _ = _paragraphs(Document(children=[_run_in("(b) Territory", ":"), _body()]))
        assert heading.text == "(b) Territory: "

    def test_a_title_that_had_no_stop_gets_only_a_space(self) -> None:
        heading, _ = _paragraphs(Document(children=[_run_in("9.6 Expiration of Agreement", ""), _body()]))
        assert heading.text == "9.6 Expiration of Agreement "


class TestARunInHeadingStaysOnItsOwnLine:
    def test_an_ordinary_heading(self) -> None:
        plain = Heading(level=2, content=[Text(content="Definitions")])
        heading, _ = _paragraphs(Document(children=[plain, _body()]))
        assert not _separated(heading)
        assert heading.text == "Definitions"

    def test_at_the_end_of_the_document(self) -> None:
        (heading,) = _paragraphs(Document(children=[_run_in()]))
        assert not _separated(heading)
        assert heading.text == "5. Indemnification"

    def test_before_another_heading(self) -> None:
        heading, _ = _paragraphs(Document(children=[_run_in(), Heading(level=2, content=[Text(content="6. Term")])]))
        assert not _separated(heading)

    def test_before_a_table(self) -> None:
        table = Table(rows=[TableRow(cells=[TableCell(content=[Text(content="cell")])])])
        heading = _paragraphs(Document(children=[_run_in(), table]))[0]
        assert not _separated(heading)

    def test_before_a_list(self) -> None:
        items = List(ordered=False, items=[ListItem(children=[_body("an item")])])
        heading = _paragraphs(Document(children=[_run_in(), items]))[0]
        assert not _separated(heading)

    def test_before_a_paragraph_that_opens_a_page(self) -> None:
        body = _body()
        body.metadata["page_break_before"] = True
        heading, _ = _paragraphs(Document(children=[_run_in(), body]))
        assert not _separated(heading)


def test_the_pdf_parser_keeps_the_stop_it_cut(tmp_path: Path) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    regular, bold = pymupdf.Font("helv"), pymupdf.Font("hebo")
    writer = pymupdf.TextWriter(page.rect)
    lines = [
        [("5.1 Indemnification.", True), (" The Company shall indemnify the Purchaser from any and all", False)],
        [("losses, claims and damages arising out of a breach of this Agreement.", False)],
    ]
    for row, runs in enumerate(lines):
        x = 72.0
        for text, is_bold in runs:
            font = bold if is_bold else regular
            writer.append((x, 60.0 + 14.0 * row), text, font=font, fontsize=11.0)
            x += font.text_length(text, fontsize=11.0)
    writer.write_text(page)
    path = tmp_path / "run_in.pdf"
    doc.save(str(path))
    doc.close()
    parsed = to_ast(str(path), parser_options=PdfOptions(layout_analysis_mode="disabled"))
    (heading,) = [node for node in parsed.children if isinstance(node, Heading)]
    assert heading.metadata["run_in"] is True
    assert heading.metadata["run_in_stop"] == "."
