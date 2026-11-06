"""Read documents through a private, hidden Word (Windows and a Word install only, hand-run).

``DispatchEx`` starts a Word of our own, so a reading never touches one the user has open.
``win32com`` is imported on entry alone, so importing this module is safe anywhere.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from benchmarks.pdfword.reading import Block, Paragraph, Reading, Table

BODY_TEXT = 10
WD_WITHIN_TABLE = 12
WD_STATISTIC_PAGES = 2
WD_FORMAT_PDF = 17
WD_FORMAT_DOCX = 16
WD_STYLE_TITLE = -63
#: InlineShape types that are a picture or chart: wdInlineShapePicture, Linked, Chart.
INLINE_PICTURES = {3, 4, 12}
#: Shape types that are a picture or chart: msoPicture, msoLinkedPicture, msoChart.
FLOATING_PICTURES = {13, 11, 3}
#: Word's "mixed" answer for a font property over a range.
WD_UNDEFINED = 9999999

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SPACES = re.compile(r"\s+")


def clean(text: Any) -> str:
    """Tidy Word's range text: cell marks and field and note characters go, whitespace collapses."""
    return _SPACES.sub(" ", _CONTROL.sub(" ", str(text or "")).replace("\xa0", " ")).strip()


class Word:
    """A private hidden Word. Use as a context manager."""

    def __init__(self) -> None:
        self.app: Any = None

    def __enter__(self) -> Word:
        import win32com.client

        self.app = win32com.client.DispatchEx("Word.Application")
        self.app.Visible = False
        self.app.DisplayAlerts = 0
        return self

    def __exit__(self, *exc: object) -> None:
        if self.app is not None:
            self.app.Quit(0)
            self.app = None

    def read(self, path: Path, *, render: Path | None = None) -> Reading:
        """Read one DOCX, optionally rendering it to a PDF through Word as well."""
        document = self.app.Documents.Open(str(path.resolve()), False, True, False, Visible=False)
        try:
            if render is not None:
                document.ExportAsFixedFormat(str(render.resolve()), WD_FORMAT_PDF)
            return read_document(document)
        finally:
            document.Close(0)

    def import_pdf(self, pdf: Path, output: Path) -> None:
        """Convert a PDF with Word's own importer and save the result as a DOCX."""
        document = self.app.Documents.Open(
            str(pdf.resolve()), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False, Format=0
        )
        try:
            document.SaveAs2(str(output.resolve()), FileFormat=WD_FORMAT_DOCX)
        finally:
            document.Close(0)


def _table(table: Any) -> Table:
    rows: dict[int, dict[int, str]] = {}
    for cell in table.Range.Cells:
        rows.setdefault(int(cell.RowIndex), {})[int(cell.ColumnIndex)] = clean(cell.Range.Text)
    width = max((max(row) for row in rows.values()), default=0)
    return Table(
        rows=tuple(tuple(rows[r].get(c, "") for c in range(1, width + 1)) for r in sorted(rows)),
    )


def _paragraph(paragraph: Any, title_style: str) -> Paragraph:
    style = str(paragraph.Style.NameLocal)
    outline = int(paragraph.OutlineLevel)
    level = 0 if style == title_style else (outline if outline < BODY_TEXT else None)
    list_format = paragraph.Range.ListFormat
    marker = str(list_format.ListString or "") if int(list_format.ListType) else ""
    return Paragraph(
        text=clean(paragraph.Range.Text),
        style=style,
        level=level,
        marker=marker or None,
        list_level=int(list_format.ListLevelNumber) if marker else None,
    )


def _body_font(document: Any) -> tuple[str, float]:
    """Return the font and size carrying the most body-text characters."""
    fonts: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    for paragraph in document.Paragraphs:
        if int(paragraph.OutlineLevel) < BODY_TEXT or paragraph.Range.Information(WD_WITHIN_TABLE):
            continue
        length = len(str(paragraph.Range.Text))
        name, size = str(paragraph.Range.Font.Name), float(paragraph.Range.Font.Size)
        if name:
            fonts[name] += length
        if size != WD_UNDEFINED:
            sizes[size] += length
    return (
        fonts.most_common(1)[0][0] if fonts else "",
        sizes.most_common(1)[0][0] if sizes else 0.0,
    )


def _story_texts(section_stories: Any) -> list[str]:
    found = []
    for index in (1, 2, 3):  # primary, first page, even pages
        story = section_stories(index)
        if story.Exists:
            text = clean(story.Range.Text)
            if text:
                found.append(text)
    return found


def read_document(document: Any) -> Reading:
    """Read an open document through Word's object model."""
    title_style = str(document.Styles(WD_STYLE_TITLE).NameLocal)
    placed: list[tuple[int, int, Block]] = []
    float_words = 0

    seen_tables = 0
    for table in document.Tables:
        seen_tables += 1
        placed.append((int(table.Range.Start), 0, _table(table)))
    for paragraph in document.Paragraphs:
        if paragraph.Range.Information(WD_WITHIN_TABLE):
            continue
        placed.append((int(paragraph.Range.Start), 1, _paragraph(paragraph, title_style)))

    pictures = sum(1 for shape in document.InlineShapes if int(shape.Type) in INLINE_PICTURES)
    # Text boxes are a separate story, so without this Word's importer would read as losing
    # the text it moved into them. Each is placed at the paragraph it is anchored to.
    for shape in document.Shapes:
        if int(shape.Type) in FLOATING_PICTURES:
            pictures += 1
        frame = shape.TextFrame
        if not frame.HasText:
            continue
        anchor = int(shape.Anchor.Start)
        for paragraph in frame.TextRange.Paragraphs:
            found = _paragraph(paragraph, title_style)
            if found.text:
                float_words += len(found.text.split())
                placed.append((anchor, 2, found))
    for frame in document.Frames:
        float_words += len(clean(frame.Range.Text).split())

    placed.sort(key=lambda item: (item[0], item[1]))
    blocks = tuple(block for _start, _kind, block in placed if not (isinstance(block, Paragraph) and not block.text))

    headers: list[str] = []
    footers: list[str] = []
    columns = 1
    for section in document.Sections:
        columns = max(columns, int(section.PageSetup.TextColumns.Count))
        headers += _story_texts(section.Headers)
        footers += _story_texts(section.Footers)
    setup = document.Sections(1).PageSetup
    font, size = _body_font(document)
    return Reading(
        blocks=blocks,
        footnotes=tuple(clean(note.Range.Text) for note in document.Footnotes),
        headers=tuple(dict.fromkeys(headers)),
        footers=tuple(dict.fromkeys(footers)),
        pictures=pictures,
        pages=int(document.ComputeStatistics(WD_STATISTIC_PAGES)),
        page_width=round(float(setup.PageWidth), 1),
        page_height=round(float(setup.PageHeight), 1),
        margins=(
            round(float(setup.TopMargin), 1),
            round(float(setup.BottomMargin), 1),
            round(float(setup.LeftMargin), 1),
            round(float(setup.RightMargin), 1),
        ),
        columns=columns,
        body_font=font,
        body_size=size,
        float_words=float_words,
    )
