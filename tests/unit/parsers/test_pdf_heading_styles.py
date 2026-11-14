#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_heading_styles.py
"""A PDF's heading sizes, fonts, weights and colors carry over to Word, level by level.

Word's built-in headings are 14pt and 13pt; a lease headed in 20pt came out with 14pt
headings and ran a page short.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Heading, Paragraph, Text
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_body_style import _Line
from all2md.parsers._pdf_heading_styles import heading_font, measure_heading_styles

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PROSE = "The plant ran three shifts through the winter and met every delivery date on time."


def test_a_lines_look_is_its_commonest_span() -> None:
    spans = [
        {"text": "4.", "size": 11.0, "font": "Arial", "flags": 0, "color": 0},
        {"text": "Indemnification", "size": 16.0, "font": "Arial-BoldMT", "flags": 16, "color": 0x2F5496},
    ]
    assert heading_font(spans) == {"size": 16.0, "font": "Arial-BoldMT", "bold": True, "color": 0x2F5496}


def test_a_lines_look_records_where_it_sits() -> None:
    spans = [
        {"text": "Rent", "size": 20.0, "font": "Arial", "origin": (72.0, 210.1), "bbox": (72.0, 190.0, 118.4, 215.0)}
    ]
    look = heading_font(spans)
    assert look is not None
    assert (look["baseline"], look["x0"], look["x1"]) == (210.1, 72.0, 118.4)


def test_each_level_takes_the_look_most_of_its_headings_share() -> None:
    looks = [
        (1, {"size": 28.0, "font": "CalibriLight", "bold": False, "color": 0}),
        (2, {"size": 20.0, "font": "CalibriLight", "bold": False, "color": 0x2F5496}),
        (2, {"size": 20.0, "font": "CalibriLight", "bold": False, "color": 0x2F5496}),
        (2, {"size": 16.0, "font": "CalibriLight", "bold": False, "color": 0x2F5496}),
        # A bold title at the body size takes the body's size and font.
        (3, {"bold": True}),
    ]
    styles = measure_heading_styles(looks, {"font": "Garamond", "size": 12.0}, lambda name: f"{name}!")
    assert styles == {
        "1": {"size": 28.0, "font": "CalibriLight!", "bold": False},
        "2": {"size": 20.0, "font": "CalibriLight!", "bold": False, "color": "2F5496"},
        "3": {"size": 12.0, "font": "Garamond", "bold": True},
    }


#: Shares of the size above and below the baseline: a 20pt heading font, a 12pt body font.
METRICS = {"Head": (0.95, 0.27), "Body": (0.86, 0.26)}


def _line(baseline: float, size: float = 12.0, font: str = "Body") -> _Line:
    return _Line(block=0, characters=40, size=size, font=font, baseline=baseline, x0=72.0, x1=540.0)


def _spaced(lines: list[_Line], body: dict, baseline: float = 210.0) -> dict:
    look = {"size": 20.0, "font": "Head", "bold": False, "color": 0, "baseline": baseline, "x0": 72.0, "x1": 300.0}
    styles = measure_heading_styles([(1, look, lines)], body, lambda name: name, METRICS.get)
    return styles["1"]


def test_the_space_around_a_heading_is_read_as_word_would_set_it() -> None:
    body = {"font": "Body", "size": 12.0, "line_spacing": 1.0, "space_after": 8.0}
    # Above: the body line's descent (3.12), 18pt before, the heading's ascent (19).
    # Below: the heading's descent (5.4), 4pt after, the body line's ascent (10.32).
    lines = [_line(210.0 - 3.12 - 18.0 - 19.0), _line(210.0 + 5.4 + 4.0 + 10.32)]
    style = _spaced(lines, body)
    assert (style["space_before"], style["space_after"]) == (18.0, 4.0)


def test_word_leaves_the_larger_space_not_the_sum() -> None:
    body = {"font": "Body", "size": 12.0, "line_spacing": 1.0, "space_after": 8.0}
    # Under 8pt between the body and the heading: the body's own space after shows,
    # and the heading's space before is read as the same.
    style = _spaced([_line(210.0 - 3.12 - 6.0 - 19.0)], body)
    assert style["space_before"] == 8.0


def test_the_bodys_line_spacing_extra_sits_under_its_text() -> None:
    body = {"font": "Body", "size": 12.0, "line_spacing": 1.5, "space_after": 0.0}
    # A 1.5-line body line carries half its 13.44pt line height under it.
    extra = 0.5 * (0.86 + 0.26) * 12.0
    style = _spaced([_line(210.0 - 3.12 - extra - 12.0 - 19.0)], body)
    assert style["space_before"] == 12.0


def test_a_neighbor_that_is_not_body_text_says_nothing() -> None:
    body = {"font": "Body", "size": 12.0, "line_spacing": 1.0, "space_after": 8.0}
    # A heading's second line is skipped; a caption-sized line below says nothing.
    lines = [_line(210.0 + 24.0, size=20.0, font="Head"), _line(270.0, size=9.0)]
    style = _spaced(lines, body)
    assert "space_before" not in style and "space_after" not in style


def test_headings_are_read_from_the_pdf(tmp_path: Path) -> None:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for number in range(1, 4):
        page = doc.new_page(width=612, height=792)
        baseline = 90.0
        for section in range(2):
            page.insert_text(
                (72, baseline), f"Section {number}.{section} Overview", fontsize=18, color=(0.18, 0.33, 0.59)
            )
            baseline += 30
            for line in range(6):
                page.insert_text((72, baseline), f"{PROSE} ({number}.{section}.{line})", fontsize=11)
                baseline += 14
            baseline += 20
    path = tmp_path / "headings.pdf"
    doc.save(str(path))
    doc.close()
    styles = to_ast(str(path), parser_options=PdfOptions(layout_analysis_mode="disabled")).metadata["heading_styles"]
    (look,) = styles.values()
    assert look["size"] == 18.0
    assert look["font"] == "Arial"
    assert look["color"] == "2E5496"
    # Set 30pt above the first body line and 34 below the last: some space either side.
    assert look["space_before"] > 0 and look["space_after"] > 0


def _styles_xml(metadata: dict, *children, **options) -> str:
    pytest.importorskip("docx")
    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    out = io.BytesIO()
    DocxRenderer(DocxRendererOptions(**options)).render(Document(children=list(children), metadata=metadata), out)
    return zipfile.ZipFile(out).read("word/styles.xml").decode("utf-8")


def _style(xml: str, style_id: str) -> str:
    match = re.search(rf'<w:style [^>]*w:styleId="{style_id}".*?</w:style>', xml, re.S)
    assert match is not None
    return match.group()


STYLES = {
    "1": {"size": 28.0, "font": "Calibri Light", "bold": False},
    "2": {"size": 20.0, "font": "Calibri Light", "bold": False, "color": "2F5496"},
}


def test_the_docx_renderer_styles_the_headings() -> None:
    # Two top-level headings: no title is promoted, so level 1 is Heading 1.
    xml = _styles_xml(
        {"heading_styles": STYLES},
        Heading(level=1, content=[Text(content="Lease")]),
        Heading(level=1, content=[Text(content="Exhibit A")]),
        Heading(level=2, content=[Text(content="Rent")]),
    )
    first, second = _style(xml, "Heading1"), _style(xml, "Heading2")
    assert '<w:sz w:val="56"/>' in first and 'w:ascii="Calibri Light"' in first
    assert "asciiTheme" not in first
    assert '<w:b w:val="0"/>' in first
    assert '<w:sz w:val="40"/>' in second and 'w:val="2F5496"' in second


def test_a_promoted_title_takes_the_first_levels_style() -> None:
    xml = _styles_xml(
        {"heading_styles": STYLES},
        Heading(level=1, content=[Text(content="Lease")]),
        Paragraph(content=[Text(content="Body")]),
        Heading(level=2, content=[Text(content="Rent")]),
    )
    assert '<w:sz w:val="56"/>' in _style(xml, "Title")
    assert '<w:sz w:val="40"/>' in _style(xml, "Heading1")


def test_the_docx_renderer_sets_the_space_around_headings() -> None:
    styles = {
        "1": {**STYLES["1"], "space_after": 4.0},
        "2": {**STYLES["2"], "space_before": 18.0, "space_after": 8.0},
    }
    xml = _styles_xml(
        {"heading_styles": styles},
        Heading(level=1, content=[Text(content="Lease")]),
        Paragraph(content=[Text(content="Body")]),
        Heading(level=2, content=[Text(content="Rent")]),
    )
    title, heading = _style(xml, "Title"), _style(xml, "Heading1")
    assert 'w:after="80"' in title
    # Word's Title draws a rule under itself; the PDF's title had none.
    assert "w:pBdr" not in title
    assert 'w:before="360"' in heading and 'w:after="160"' in heading and 'w:line="240"' in heading


def test_a_reference_template_keeps_its_own_heading_styles(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    from docx import Document as WordDocument

    template = tmp_path / "template.docx"
    WordDocument().save(str(template))
    xml = _styles_xml(
        {"heading_styles": STYLES}, Heading(level=2, content=[Text(content="Rent")]), template_path=str(template)
    )
    assert "Calibri Light" not in xml


@pytest.mark.parametrize(
    ("color", "named"),
    [(0xFFFFFF, False), (0x231F20, False), (0x000000, False), (0x2F5496, True), (0xBF311A, True)],
)
def test_a_heading_color_is_named_only_when_it_reads_on_white(color: int, named: bool) -> None:
    # White headings sat on a shaded band Word does not draw; print's rich black is black.
    styles = measure_heading_styles([(1, {"size": 20.0, "font": "Arial", "color": color})], None, str)
    assert ("color" in styles["1"]) is named
