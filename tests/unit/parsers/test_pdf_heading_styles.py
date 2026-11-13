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
from all2md.parsers._pdf_heading_styles import heading_font, measure_heading_styles

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PROSE = "The plant ran three shifts through the winter and met every delivery date on time."


def test_a_lines_look_is_its_commonest_span() -> None:
    spans = [
        {"text": "4.", "size": 11.0, "font": "Arial", "flags": 0, "color": 0},
        {"text": "Indemnification", "size": 16.0, "font": "Arial-BoldMT", "flags": 16, "color": 0x2F5496},
    ]
    assert heading_font(spans) == {"size": 16.0, "font": "Arial-BoldMT", "bold": True, "color": 0x2F5496}


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
