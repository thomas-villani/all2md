#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/parsers/test_pdf_page_setup.py
"""A PDF's paper size, orientation and margins carry over to Word.

A PDF converted to Word came out on portrait US Letter with one-inch margins whatever it
was printed on. The size is exact in the PDF; the margins are read from where the body
text starts and stops, and kept as ``page_setup`` metadata the DOCX renderer applies.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

import pytest

from all2md import to_ast
from all2md.ast import Document, Paragraph, Text
from all2md.options.pdf import PdfOptions
from all2md.parsers._pdf_page_setup import measure_page_setup

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

LINE = "The plant ran three shifts through the winter and met every delivery date on time."


def _pdf(tmp_path: Path, *, width: float, height: float, margin: float, pages: int = 3, header: float = 27.0) -> str:
    pymupdf = pytest.importorskip("pymupdf")
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        page = doc.new_page(width=width, height=height)
        page.insert_text((margin, header + 10), "Kestrel Ridge Manufacturing", fontsize=9)
        # Line by line, as a word processor sets text: the first line's top at the top
        # margin, the last line's bottom at the bottom one. (insert_textbox reports a
        # block reaching past its own box, below the footer.)
        baseline = margin + 12.0
        while baseline + 3.0 <= height - margin:
            page.insert_text((margin, baseline), f"{LINE} ({n})", fontsize=11)
            baseline += 14.0
        page.insert_text((margin, height - header - 3), f"Quarterly review, page {n}", fontsize=9)
    path = tmp_path / "setup.pdf"
    doc.save(str(path))
    doc.close()
    return str(path)


def _setup(path: str) -> dict:
    return to_ast(path, parser_options=PdfOptions(layout_analysis_mode="disabled")).metadata["page_setup"]


def test_a4_with_narrow_margins_is_measured(tmp_path: Path) -> None:
    setup = _setup(_pdf(tmp_path, width=595.3, height=841.9, margin=54.0))
    assert (setup["width"], setup["height"]) == (595.3, 841.9)
    assert "orientation" not in setup
    assert setup["margin_left"] == 54.0
    assert setup["margin_top"] == 54.0
    assert setup["margin_right"] == 54.0
    assert setup["margin_bottom"] == 54.0
    assert setup["header_distance"] == 27.0
    assert setup["footer_distance"] == 27.0


def test_landscape_is_recorded(tmp_path: Path) -> None:
    setup = _setup(_pdf(tmp_path, width=792.0, height=612.0, margin=72.0))
    assert setup["orientation"] == "landscape"
    assert setup["margin_left"] == 72.0


def test_a_single_page_records_its_size_only(tmp_path: Path) -> None:
    # Its header cannot be told from the body, so the top margin would land on it.
    setup = _setup(_pdf(tmp_path, width=595.3, height=841.9, margin=54.0, pages=1))
    assert setup == {"width": 595.3, "height": 841.9}


def _block(bbox: tuple[float, float, float, float], text: str = "Body text here", size: float = 11.0) -> dict:
    return {"type": 0, "bbox": bbox, "lines": [{"bbox": bbox, "spans": [{"text": text, "size": size}]}]}


def test_a_large_heading_at_the_top_still_reads_as_the_margin() -> None:
    # A 20pt heading's glyphs start about 4pt below its line, and so below the margin.
    pages = [([_block((72, 76.1, 300, 96), "Next Steps", 20.0), _block((72, 110, 540, 700))], 612.0, 792.0)] * 2
    setup = measure_page_setup([(612.0, 792.0)] * 2, pages, None)
    assert setup is not None
    assert setup["margin_top"] == 72.0


def test_justified_lines_that_overshoot_the_right_margin_snap_back() -> None:
    pages = [([_block((72, 63, 560.5, 700))], 612.0, 792.0)] * 2
    setup = measure_page_setup([(612.0, 792.0)] * 2, pages, None)
    assert setup is not None
    assert setup["margin_right"] == 54.0
    assert setup["margin_top"] == 63.0


def _render(metadata: dict, **options) -> str:
    pytest.importorskip("docx")
    from all2md.options.docx import DocxRendererOptions
    from all2md.renderers.docx import DocxRenderer

    out = io.BytesIO()
    doc = Document(children=[Paragraph(content=[Text(content="Body")])], metadata=metadata)
    DocxRenderer(DocxRendererOptions(**options)).render(doc, out)
    return zipfile.ZipFile(out).read("word/document.xml").decode("utf-8")


def test_the_docx_renderer_applies_the_page_setup() -> None:
    body = _render(
        {
            "page_setup": {
                "width": 792.0,
                "height": 612.0,
                "orientation": "landscape",
                "margin_top": 54.0,
                "margin_bottom": 54.0,
                "margin_left": 63.0,
                "margin_right": 63.0,
                "header_distance": 27.0,
                "footer_distance": 27.0,
            }
        }
    )
    size = re.search(r"<w:pgSz[^>]*/>", body)
    margins = re.search(r"<w:pgMar[^>]*/>", body)
    assert size is not None and margins is not None
    assert 'w:w="15840"' in size.group() and 'w:h="12240"' in size.group()
    assert 'w:orient="landscape"' in size.group()
    for attribute, twips in (("top", 1080), ("bottom", 1080), ("left", 1260), ("right", 1260), ("header", 540)):
        assert f'w:{attribute}="{twips}"' in margins.group()


def test_a_reference_template_keeps_its_own_page_setup(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    from docx import Document as WordDocument

    template = tmp_path / "template.docx"
    WordDocument().save(str(template))
    body = _render({"page_setup": {"width": 595.3, "height": 841.9}}, template_path=str(template))
    size = re.search(r"<w:pgSz[^>]*/>", body)
    assert size is not None
    assert 'w:w="11906"' not in size.group()
