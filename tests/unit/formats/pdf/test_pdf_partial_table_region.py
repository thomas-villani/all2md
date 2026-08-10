#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_partial_table_region.py
"""A table region covering part of a block must not take the rest of the block with it.

Blocks that a table region covers are withheld from the text stream, because the region is
emitted separately -- as a table, or as a paragraph when the grid is rejected -- and emitting
both would duplicate it. That withholding was decided per *block*, on a majority-area test:
a region covering more than half of a block removed the whole block.

"More than half" is not "all of it". PyMuPDF returns a full-height journal column as a single
block, so a region predicted over the lower half of one clears the bar for the entire column,
and the upper half is deleted -- carried out with the block, and absent from the region whose
text is re-emitted. On page 16 of PMC7500012 that silently removed nine reference entries;
the layout model predicted a table over y=380-733 of a column spanning y=90-733, which is
54.8% of it, and references 19-27 above the region were never emitted by anything.

The *observed* loss came from a layout-predicted region, but the filter is fed by ordinary
``find_tables()`` detections too, so this path is reached with or without ``pymupdf-layout``.
The tests drive the filter directly rather than through either detector, which keeps them
honest on the unit lane's install (no ``pdf_layout`` extra) and keeps them from silently
depending on what a model happens to predict this release.

One consequence is worth stating because it was missed once: rescuing lines *adds* blocks the
parser previously discarded, so it can change output on documents that have nothing to do
with the original bug. The PDF golden snapshots are the instrument for that, and they run on
Linux only -- passing ``tests/golden`` on Windows says nothing about them.
"""

from __future__ import annotations

import pytest

from all2md.parsers.pdf import _block_outside_table_regions

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.table]


def _line(y0: float, y1: float, text: str, x0: float = 50.0, x1: float = 300.0) -> dict:
    return {"bbox": (x0, y0, x1, y1), "spans": [{"text": text}]}


def _block(*lines: dict) -> dict:
    xs0 = min(line["bbox"][0] for line in lines)
    ys0 = min(line["bbox"][1] for line in lines)
    xs1 = max(line["bbox"][2] for line in lines)
    ys1 = max(line["bbox"][3] for line in lines)
    return {"bbox": (xs0, ys0, xs1, ys1), "lines": list(lines), "type": 0}


def _text_of(block: dict | None) -> str:
    if block is None:
        return ""
    return " ".join(span["text"] for line in block["lines"] for span in line["spans"])


class TestBlockOutsideTableRegions:
    """The unit that decides what survives a partially-covering region."""

    def test_keeps_the_lines_above_a_region_covering_the_lower_half(self):
        import fitz

        block = _block(
            _line(90, 100, "reference nineteen"),
            _line(100, 110, "reference twenty"),
            _line(400, 410, "cell one"),
            _line(410, 420, "cell two"),
        )
        region = fitz.Rect(50, 380, 300, 430)

        remainder = _block_outside_table_regions(block, [region])

        assert remainder is not None
        assert _text_of(remainder) == "reference nineteen reference twenty"

    def test_tightens_the_bbox_to_what_survives(self):
        import fitz

        block = _block(_line(90, 100, "kept"), _line(400, 410, "covered"))

        remainder = _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)])

        assert remainder is not None
        # A stale bbox would still claim the region's rows, and reading order is decided by
        # sorting on it -- the surviving text would sort below the table it precedes.
        assert remainder["bbox"][1] == 90
        assert remainder["bbox"][3] == 100

    def test_returns_none_when_the_region_covers_every_line(self):
        import fitz

        block = _block(_line(400, 410, "cell one"), _line(410, 420, "cell two"))

        assert _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)]) is None

    def test_does_not_mutate_the_original_block(self):
        import fitz

        block = _block(_line(90, 100, "kept"), _line(400, 410, "covered"))

        _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)])

        assert len(block["lines"]) == 2
        assert block["bbox"][3] == 410

    def test_a_line_straddling_the_boundary_is_assigned_not_duplicated(self):
        import fitz

        # Mostly below the region edge, so it belongs to the region and must not also appear
        # in the remainder; the alternative is the same words emitted twice.
        block = _block(_line(90, 100, "prose"), _line(374, 390, "straddler"))

        remainder = _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)])

        assert _text_of(remainder) == "prose"

    def test_a_line_mostly_outside_the_region_survives(self):
        import fitz

        block = _block(_line(90, 100, "prose"), _line(370, 386, "straddler"))

        remainder = _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)])

        assert _text_of(remainder) == "prose straddler"

    def test_several_regions_are_all_honoured(self):
        import fitz

        block = _block(
            _line(90, 100, "top prose"),
            _line(200, 210, "first table"),
            _line(300, 310, "middle prose"),
            _line(500, 510, "second table"),
        )
        regions = [fitz.Rect(50, 195, 300, 215), fitz.Rect(50, 495, 300, 515)]

        remainder = _block_outside_table_regions(block, regions)

        assert _text_of(remainder) == "top prose middle prose"

    def test_whitespace_only_survivors_are_not_rescued(self):
        import fitz

        # The lines bordering a table region are routinely blank or a single space. Rescuing
        # those turns a dropped block into an empty paragraph, which shows up as a stray gap
        # in the output -- caught by the PDF golden snapshot, which only runs on Linux.
        block = _block(_line(90, 100, " "), _line(400, 410, "cell one"))

        assert _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)]) is None

    def test_real_text_beside_whitespace_still_survives(self):
        import fitz

        block = _block(_line(90, 100, " "), _line(100, 110, "prose"), _line(400, 410, "cell"))

        remainder = _block_outside_table_regions(block, [fitz.Rect(50, 380, 300, 430)])

        assert _text_of(remainder) == "  prose"

    def test_a_block_without_lines_yields_nothing(self):
        import fitz

        # Image blocks carry no lines; there is no prose to rescue and the caller's existing
        # decision to drop them stands.
        assert _block_outside_table_regions({"bbox": (0, 0, 10, 10), "type": 1}, [fitz.Rect(0, 0, 10, 10)]) is None


class TestPageKeepsProseAboveAPartialRegion:
    """The same defect through the page pipeline, on a PDF built to reproduce it.

    The region is injected by stubbing table detection rather than by running the layout
    model, so this covers the filtering behaviour on installs without ``pymupdf-layout``
    -- which is where the unit lane runs.
    """

    @staticmethod
    def _column_page(tmp_path, name: str) -> str:
        """Write a page holding one tall column: prose on top, a small grid at the bottom.

        The lines are packed tightly enough that PyMuPDF returns them as a *single* block,
        which is the precondition for the bug -- a region over the bottom rows then clears
        the majority-area bar for the whole column.
        """
        import fitz

        doc = fitz.open()
        page = doc.new_page(width=300, height=500)
        writer = fitz.TextWriter(page.rect)
        font = fitz.Font("helv")
        # One uninterrupted 10pt cadence across both halves. A wider gap at the join makes
        # PyMuPDF start a second block, and two blocks cannot reproduce this at all.
        for idx in range(10):
            writer.append((50, 60 + idx * 10), f"prose line {idx} of the column", font=font, fontsize=8)
        for idx in range(20):
            writer.append((50, 160 + idx * 10), f"grid {idx}    value {idx}", font=font, fontsize=8)
        writer.write_text(page)
        path = tmp_path / name
        doc.save(str(path))
        doc.close()
        return str(path)

    def test_prose_above_the_region_survives(self, tmp_path, monkeypatch):
        import fitz

        from all2md.options.pdf import PdfOptions
        from all2md.parsers.pdf import PdfToAstConverter

        path = self._column_page(tmp_path, "column.pdf")
        doc = fitz.open(path)
        page = doc[0]

        block = next(b for b in page.get_text("dict")["blocks"] if b.get("type") == 0)
        # Precondition: one block spanning both halves. If PyMuPDF ever splits these, the
        # fixture stops testing the thing it was built for and should be rebuilt, not
        # loosened.
        assert block["bbox"][1] < 100 and block["bbox"][3] > 300

        region = fitz.Rect(40, 155, 290, 360)
        assert abs(region & fitz.Rect(block["bbox"])) > 0.5 * abs(fitz.Rect(block["bbox"]))

        converter = PdfToAstConverter(options=PdfOptions())
        monkeypatch.setattr(
            PdfToAstConverter,
            "_detect_page_tables",
            lambda self, page, page_num, total: (
                [{"bbox": region, "idx": 0, "type": "layout", "lines": ([], [])}],
                [],
                [],
            ),
        )

        nodes = converter._process_page_to_ast(page, 0, "doc", lambda a, b: (a, 0), doc.page_count)
        from all2md.ast.nodes import Text
        from all2md.ast.transforms import NodeCollector

        collector = NodeCollector(lambda n: isinstance(n, Text))
        for node in nodes:
            node.accept(collector)
        text = " ".join(t.content for t in collector.collected)
        doc.close()

        assert "prose line 0 of the column" in text
        assert "prose line 9 of the column" in text
