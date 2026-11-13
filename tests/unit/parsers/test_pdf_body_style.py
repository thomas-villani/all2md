#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_body_style.py
"""A PDF's body font, size, line spacing and paragraph spacing carry over to Word.

A PDF converted to Word came out in Calibri 11 with 1.15 lines and 10pt between
paragraphs whatever it was set in, and paginated differently from its source. They are
read from the body text and kept as ``body_style`` metadata the DOCX renderer applies.
"""

from __future__ import annotations

import io
import re
import struct
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Paragraph, Text
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_body_style import (
    KNOWN_LINE_HEIGHTS,
    BodyStyleSampler,
    family_from_postscript,
    font_family,
    font_line_height,
    font_vertical_metrics,
)

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PROSE = "The plant ran three shifts through the winter and met every delivery date"


@pytest.mark.parametrize(
    ("postscript", "family"),
    [
        ("BCDEEE+TimesNewRomanPSMT", "Times New Roman"),
        ("TimesNewRomanPS-BoldMT", "Times New Roman"),
        ("Arial-BoldMT", "Arial"),
        ("Arial,Bold", "Arial"),
        ("Calibri-Light", "Calibri Light"),
        ("ArialNarrow-Bold", "Arial Narrow"),
        ("SegoeUISymbol", "Segoe UI Symbol"),
        ("MS-Gothic", "MS Gothic"),
        ("Helvetica-BoldOblique", "Arial"),
        ("Times-Roman", "Times New Roman"),
        ("FreeMonoBold", "Free Mono"),
    ],
)
def test_a_postscript_name_reads_as_its_family(postscript: str, family: str) -> None:
    assert family_from_postscript(postscript) == family


def _truetype(
    *, units: int, ascender: int, descender: int, gap: int, family: str, win: tuple[int, int] | None = None
) -> bytes:
    """Build just enough of a TrueType font for its head, hhea, name and (with ``win``) OS/2 tables."""
    head = bytearray(54)
    head[18:20] = struct.pack(">H", units)
    hhea = bytearray(36)
    hhea[4:10] = struct.pack(">hhh", ascender, descender, gap)
    encoded = family.encode("utf-16-be")
    name = struct.pack(">HHH", 0, 1, 18) + struct.pack(">HHHHHH", 3, 1, 0x409, 1, len(encoded), 0) + encoded
    tables = [(b"head", bytes(head)), (b"hhea", bytes(hhea)), (b"name", name)]
    if win is not None:
        os2 = bytearray(78)
        os2[74:78] = struct.pack(">HH", *win)
        tables.append((b"OS/2", bytes(os2)))
    offset = 12 + 16 * len(tables)
    directory, data = b"", b""
    for tag, body in tables:
        directory += struct.pack(">4sIII", tag, 0, offset + len(data), len(body))
        data += body
    return b"\x00\x01\x00\x00" + struct.pack(">HHHH", len(tables), 0, 0, 0) + directory + data


def test_the_line_height_and_family_come_from_the_font_file() -> None:
    # Times New Roman's own metrics: Word's "multiple" spacing multiplies 2355/2048.
    font = _truetype(units=2048, ascender=1825, descender=-443, gap=87, family="Times New Roman")
    assert font_line_height(font) == pytest.approx(2355 / 2048)
    assert font_family(font) == "Times New Roman"


def test_a_font_without_tables_has_no_metrics() -> None:
    assert font_line_height(b"%!PS-AdobeFont-1.0") is None
    assert font_family(b"") is None
    assert font_vertical_metrics(b"") is None


def test_word_sets_a_line_by_the_fonts_windows_metrics() -> None:
    # Times New Roman: Windows ascent 1825 above the baseline; below, the Windows descent
    # 443 and the 87 units of line gap the Windows metrics leave out.
    times = _truetype(units=2048, ascender=1825, descender=-443, gap=87, family="Times New Roman", win=(1825, 443))
    assert font_vertical_metrics(times) == pytest.approx((1825 / 2048, 530 / 2048))
    # Calibri: hhea puts 452 units of gap on a 1536 ascender; Windows sets 1950 above.
    calibri = _truetype(units=2048, ascender=1536, descender=-512, gap=452, family="Calibri", win=(1950, 550))
    assert font_vertical_metrics(calibri) == pytest.approx((1950 / 2048, 550 / 2048))
    # No OS/2 table: hhea, its gap below.
    bare = _truetype(units=1000, ascender=800, descender=-200, gap=100, family="Bare")
    assert font_vertical_metrics(bare) == pytest.approx((0.8, 0.3))


def _pdf(tmp_path: Path, *, size: float, multiple: float, after: float, paragraphs: int = 6) -> str:
    """Prose as a word processor sets it: lines ``multiple`` apart, ``after`` between paragraphs.

    The text is in Helvetica, which Word sets as Arial, so the lines are spaced by
    Arial's line height: the multiple is read as the one Word would need.
    """
    pymupdf = pytest.importorskip("pymupdf")
    pitch = KNOWN_LINE_HEIGHTS["Arial"] * size * multiple
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    baseline = 90.0
    for paragraph in range(paragraphs):
        for line in range(3):
            page.insert_text((72, baseline), f"{PROSE} ({paragraph}.{line})", fontsize=size)
            baseline += pitch
        baseline += after
    path = tmp_path / "body.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _style(path: str) -> dict:
    return to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled")).metadata["body_style"]


def test_the_body_style_is_measured(tmp_path: Path) -> None:
    # PyMuPDF keeps a paragraph's lines in one block only while they touch, so the
    # fixture is single-spaced; wider spacing is measured on the sampler's own tests.
    style = _style(_pdf(tmp_path, size=11.0, multiple=1.0, after=6.0))
    assert style == {"font": "Arial", "size": 11.0, "line_spacing": 1.0, "space_after": 6.0}


def _line(text: str, x0: float, x1: float, baseline: float, size: float = 10.0) -> dict:
    span = {"text": text, "size": size, "font": "Body", "origin": (x0, baseline), "ascender": 0.9, "descender": -0.3}
    return {"dir": (1.0, 0.0), "bbox": (x0, baseline - size, x1, baseline + 2), "spans": [span]}


def _block(*lines: dict) -> dict:
    return {"type": 0, "lines": list(lines)}


def test_a_borderless_tables_cells_do_not_outvote_the_prose() -> None:
    # Prose at double spacing (24pt), and a two-column key-terms grid at single (12pt)
    # with more line pairs but far fewer characters.
    sampler = BodyStyleSampler()
    prose = _block(*(_line("x" * 90, 72, 540, 100 + 24 * n) for n in range(4)))
    cells = [_block(*(_line("Rent", x, x + 40, 300 + 12 * n) for n in range(6))) for x in (72, 300)]
    sampler.add([prose, *cells])
    style = sampler.measure(None)
    assert style is not None
    assert style["line_spacing"] == 2.0


def test_table_of_contents_leaders_are_not_body_text() -> None:
    sampler = BodyStyleSampler()
    prose = _block(*(_line("x" * 60, 72, 540, 100 + 12 * n) for n in range(4)))
    contents = [_block(_line(f"Section {n} " + "." * 80 + " 3", 72, 540, 200 + 17 * n)) for n in range(8)]
    later = _block(*(_line("x" * 60, 72, 540, 400 + 12 * n) for n in range(4)))
    sampler.add([prose, *contents, later])
    style = sampler.measure(None)
    assert style is not None
    assert "space_after" not in style


def test_paragraphs_set_flush_have_no_space_after() -> None:
    sampler = BodyStyleSampler()
    paragraphs = [_block(*(_line("x" * 80, 72, 540, 100 + 36 * p + 12 * n) for n in range(3))) for p in range(4)]
    sampler.add(paragraphs)
    style = sampler.measure(None)
    assert style is not None
    assert style["space_after"] == 0.0


def test_too_little_text_says_nothing() -> None:
    sampler = BodyStyleSampler()
    sampler.add([_block(_line("Invoice", 72, 120, 100))])
    assert sampler.measure(None) is None


def _render(metadata: dict, **options) -> tuple[str, str]:
    pytest.importorskip("docx")
    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    out = io.BytesIO()
    doc = Document(children=[Paragraph(content=[Text(content="Body")])], metadata=metadata)
    DocxRenderer(DocxRendererOptions(**options)).render(doc, out)
    archive = zipfile.ZipFile(out)
    return archive.read("word/styles.xml").decode("utf-8"), archive.read("word/document.xml").decode("utf-8")


def _normal(styles: str) -> str:
    match = re.search(r'<w:style [^>]*w:styleId="Normal".*?</w:style>', styles, re.S)
    assert match is not None
    return match.group()


def _default_spacing(styles: str) -> str:
    match = re.search(r"<w:pPrDefault>.*?<w:spacing[^>]*/>", styles, re.S)
    assert match is not None
    return match.group()


BODY_STYLE = {"font": "Garamond", "size": 12.0, "line_spacing": 1.1583, "space_after": 8.0}


def test_the_docx_renderer_applies_the_body_style() -> None:
    styles, _ = _render({"body_style": BODY_STYLE})
    normal = _normal(styles)
    assert 'w:ascii="Garamond"' in normal
    assert '<w:sz w:val="24"/>' in normal
    spacing = _default_spacing(styles)
    assert 'w:after="160"' in spacing and 'w:line="278"' in spacing and 'w:lineRule="auto"' in spacing
    # On Normal the spacing would beat a table style's single spacing in every cell.
    assert "<w:spacing" not in normal


def test_a_font_the_caller_names_wins() -> None:
    styles, _ = _render({"body_style": BODY_STYLE}, default_font="Georgia", default_font_size=10)
    normal = _normal(styles)
    assert 'w:ascii="Georgia"' in normal and '<w:sz w:val="20"/>' in normal
    assert 'w:line="278"' in _default_spacing(styles)


def test_a_reference_template_keeps_its_own_body_style(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    from docx import Document as WordDocument

    template = tmp_path / "template.docx"
    WordDocument().save(str(template))
    styles, _ = _render({"body_style": BODY_STYLE}, template_path=str(template))
    assert "Garamond" not in styles
    assert 'w:line="278"' not in styles
