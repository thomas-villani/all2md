#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/formats/pdf/test_pdf_layout_line_labels.py
"""Layout labels have to reach the lines they describe, not just the blocks.

``match_predictions_to_blocks`` assigns a label to a *block* when the two overlap by
IoU >= 0.3. That is a reasonable test when a block is one semantic unit and a hopeless one
when it is not: PyMuPDF hands back a whole journal column as a single block, so a two-line
section heading inside it scores an IoU near 0.03 against its own block and its label is
thrown away. Measured on the PMC born-digital corpus, 54% of ``section-header`` predictions
never reached any block, and the median miss was a block 38x the prediction's area.

``annotate_lines_with_layout`` asks the question the matcher meant to ask -- did the model
draw a box around *this text* -- by containment rather than IoU, because a line inside a
correct region has a low IoU with it by construction.

These tests drive the annotator directly rather than through the model, so they run on the
unit lane, which installs without the ``pdf_layout`` extra.
"""

from __future__ import annotations

import pytest

from all2md.parsers._pdf_layout import LayoutPrediction, annotate_lines_with_layout

pytestmark = [pytest.mark.unit, pytest.mark.pdf]


def _line(y0: float, y1: float, text: str, x0: float = 50.0, x1: float = 300.0) -> dict:
    return {"bbox": (x0, y0, x1, y1), "spans": [{"text": text}]}


def _block(*lines: dict) -> dict:
    return {
        "bbox": (
            min(line["bbox"][0] for line in lines),
            min(line["bbox"][1] for line in lines),
            max(line["bbox"][2] for line in lines),
            max(line["bbox"][3] for line in lines),
        ),
        "lines": list(lines),
        "type": 0,
    }


def _pred(y0: float, y1: float, label: str, x0: float = 45.0, x1: float = 305.0) -> LayoutPrediction:
    return LayoutPrediction(x0=x0, y0=y0, x1=x1, y1=y1, label=label)


class TestLinesInsideAColumnKeepTheirLabel:
    def test_a_heading_inside_a_full_column_block_is_labelled(self):
        # The case the block matcher cannot serve: one block spanning the column, with a
        # heading two lines tall inside it.
        block = _block(
            _line(100, 110, "Materials and Methods"),
            *[_line(y, y + 10, f"body line at {y}") for y in range(120, 700, 10)],
        )

        stamped = annotate_lines_with_layout([block], [_pred(98, 112, "section-header")])

        assert stamped == 1
        assert block["lines"][0]["_layout_label"] == "section-header"
        assert "_layout_label" not in block["lines"][1]

    def test_body_lines_under_a_text_prediction_are_labelled_text(self):
        block = _block(_line(100, 110, "Results"), _line(120, 130, "prose"), _line(130, 140, "more prose"))
        predictions = [_pred(98, 112, "section-header"), _pred(118, 142, "text")]

        annotate_lines_with_layout([block], predictions)

        labels = [line.get("_layout_label") for line in block["lines"]]
        assert labels == ["section-header", "text", "text"]

    def test_a_line_the_model_did_not_cover_is_left_alone(self):
        block = _block(_line(100, 110, "labelled"), _line(400, 410, "untouched"))

        annotate_lines_with_layout([block], [_pred(98, 112, "section-header")])

        assert "_layout_label" not in block["lines"][1]

    def test_majority_coverage_is_required(self):
        # A prediction clipping the top 20% of a line has not identified that line.
        block = _block(_line(100, 110, "mostly outside"))

        stamped = annotate_lines_with_layout([block], [_pred(98, 102, "section-header")])

        assert stamped == 0
        assert "_layout_label" not in block["lines"][0]

    def test_the_prediction_covering_most_of_the_line_wins(self):
        block = _block(_line(100, 110, "contested"))
        # 'text' covers 60%, 'section-header' covers 90% -- the larger share decides, not
        # the order predictions happen to arrive in.
        predictions = [_pred(94, 106, "text"), _pred(99, 110, "section-header")]

        annotate_lines_with_layout([block], predictions)

        assert block["lines"][0]["_layout_label"] == "section-header"

    def test_no_predictions_is_a_no_op(self):
        block = _block(_line(100, 110, "unlabelled"))

        assert annotate_lines_with_layout([block], []) == 0
        assert "_layout_label" not in block["lines"][0]

    def test_blocks_without_lines_are_skipped(self):
        image_block = {"bbox": (0, 0, 10, 10), "type": 1}

        assert annotate_lines_with_layout([image_block], [_pred(0, 10, "picture")]) == 0

    def test_a_degenerate_line_bbox_is_not_divided_by(self):
        block = {"bbox": (50, 100, 300, 100), "lines": [{"bbox": (50, 100, 300, 100), "spans": []}], "type": 0}

        assert annotate_lines_with_layout([block], [_pred(90, 110, "section-header")]) == 0


class TestPageEmitsAHeadingInsideAColumn:
    """The same defect through the page pipeline, with predictions injected by hand.

    The layout model is not run: the unit lane installs without ``pymupdf-layout``, and a
    test that depended on what the model predicts this release would be measuring the model
    rather than the plumbing.
    """

    @staticmethod
    def _column_page(tmp_path):
        import pymupdf

        doc = pymupdf.open()
        page = doc.new_page(width=300, height=500)
        writer = pymupdf.TextWriter(page.rect)
        font = pymupdf.Font("helv")
        # A uniform cadence and one font size throughout, so the font heuristic has nothing
        # to go on and only the layout label can promote the heading. A larger heading font
        # would let the existing heuristic pass the test without the fix.
        writer.append((50, 60), "Materials and Methods", font=font, fontsize=9)
        for idx in range(30):
            writer.append((50, 70 + idx * 10), f"body line {idx} of this column", font=font, fontsize=9)
        writer.write_text(page)
        path = tmp_path / "column.pdf"
        doc.save(str(path))
        doc.close()
        return str(path)

    def test_the_heading_line_becomes_a_heading(self, tmp_path, monkeypatch):
        import pymupdf

        from all2md.ast.nodes import Heading
        from all2md.ast.transforms import NodeCollector
        from all2md.ast.utils import extract_text
        from all2md.options.pdf import PdfOptions
        from all2md.parsers import pdf as pdf_module
        from all2md.parsers.pdf import PdfToAstConverter

        path = self._column_page(tmp_path)
        doc = pymupdf.open(path)
        page = doc[0]

        blocks = [b for b in page.get_text("dict")["blocks"] if b.get("type") == 0]
        # Precondition: one block holding heading and body alike. If PyMuPDF ever splits
        # them the fixture stops testing this at all and should be rebuilt, not loosened.
        assert len(blocks) == 1

        heading_rect = blocks[0]["lines"][0]["bbox"]
        monkeypatch.setattr(
            pdf_module,
            "predict_page_layout",
            lambda page, feature_set: [
                LayoutPrediction(
                    x0=heading_rect[0] - 2,
                    y0=heading_rect[1] - 1,
                    x1=heading_rect[2] + 2,
                    y1=heading_rect[3] + 1,
                    label="section-header",
                )
            ],
        )

        converter = PdfToAstConverter(options=PdfOptions(layout_analysis_mode="enabled"))
        converter._use_layout = True
        nodes = converter._process_page_to_ast(page, 0, "doc", lambda a, b: (a, 0), doc.page_count)
        doc.close()

        collector = NodeCollector(lambda n: isinstance(n, Heading))
        for node in nodes:
            node.accept(collector)
        assert [extract_text(h).strip() for h in collector.collected] == ["Materials and Methods"]
