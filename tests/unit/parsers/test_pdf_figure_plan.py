#  Copyright (c) 2025 Tom Villani, Ph.D.
"""The PDF parser plans figures: panel grouping, caption rescue, and vector figures (#338).

``_plan_page_figures`` is the step between image extraction and node emission. It
decides what becomes a ``Figure`` container: images grouped by a layout ``picture``
region or an identical detected caption, a region-level caption rescued for panels
whose own bbox sits too far from the caption line, and -- for a ``picture`` region
holding no raster at all -- a caption-only container, because a vector-drawn
figure's caption is the only record the figure exists.

The planner tests drive the method directly with synthetic geometry and a fake
page, so they run wherever ``pymupdf`` does; the layout *model* is never needed.
The end-to-end test patches the model boundary (``predict_page_layout``) for the
same reason: CI's unit lane installs no ``pdf_layout`` extra.
"""

from __future__ import annotations

import pytest

pymupdf = pytest.importorskip("pymupdf")

from all2md.api import to_ast, to_markdown  # noqa: E402
from all2md.ast import Figure  # noqa: E402
from all2md.ast.extraction import collect_figures  # noqa: E402
from all2md.options import PdfOptions  # noqa: E402
from all2md.parsers import pdf as pdf_module  # noqa: E402
from all2md.parsers._pdf_layout import LayoutPrediction, PageLayoutPredictions  # noqa: E402
from all2md.parsers.pdf import PdfToAstConverter  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

_CAPTION = "Figure 1. Two panels of the same assay."
_OTHER_CAPTION = "Figure 2. An unrelated diagram."

#: A picture region spanning two panel bboxes, and the caption region below it.
_PICTURE = LayoutPrediction(72.0, 100.0, 400.0, 300.0, "picture")
_CAPTION_REGION = LayoutPrediction(72.0, 310.0, 400.0, 330.0, "caption")
_TOP_PANEL = pymupdf.Rect(80, 110, 390, 195)
_BOTTOM_PANEL = pymupdf.Rect(80, 205, 390, 290)


class _FakePage:
    """Answers ``get_textbox`` from a rect->text map; everywhere else is blank."""

    def __init__(self, texts: dict[tuple[float, float, float, float], str]) -> None:
        self._texts = texts

    def get_textbox(self, rect: "pymupdf.Rect") -> str:
        return self._texts.get((rect.x0, rect.y0, rect.x1, rect.y1), "")


def _plan(page_images, predictions=None, table_info=(), texts=None):
    layout = PageLayoutPredictions(predictions=list(predictions)) if predictions is not None else None
    page = _FakePage(texts or {})
    converter = PdfToAstConverter(PdfOptions())
    return converter._plan_page_figures(page, page_images, layout, list(table_info))


def _image(bbox, caption=None):
    return {"bbox": bbox, "result": {}, "caption": caption}


class TestPanelGrouping:
    def test_two_panels_in_one_picture_region_are_one_figure(self) -> None:
        """The region caption is rescued for panels whose own search could not reach it.

        The bottom panel's below-band would find the caption; the top panel's finds
        the bottom panel. The region's extent is what actually ends above the caption.
        """
        plan = _plan(
            [_image(_TOP_PANEL), _image(_BOTTOM_PANEL)],
            predictions=[_PICTURE, _CAPTION_REGION],
            texts={_CAPTION_REGION.bbox: _CAPTION},
        )

        assert len(plan) == 1
        assert plan[0]["caption"] == _CAPTION
        assert [img["bbox"] for img in plan[0]["images"]] == [_TOP_PANEL, _BOTTOM_PANEL]

    def test_a_member_caption_wins_without_a_region_lookup(self) -> None:
        """When a panel already bound the caption, the group inherits it as-is."""
        plan = _plan(
            [_image(_TOP_PANEL), _image(_BOTTOM_PANEL, caption=_CAPTION)],
            predictions=[_PICTURE, _CAPTION_REGION],
            texts={},
        )

        assert len(plan) == 1
        assert plan[0]["caption"] == _CAPTION
        assert len(plan[0]["images"]) == 2

    def test_conflicting_captions_dissolve_the_region(self) -> None:
        """Two captioned figures under one region means the region is wrong, not the captions."""
        plan = _plan(
            [_image(_TOP_PANEL, caption=_CAPTION), _image(_BOTTOM_PANEL, caption=_OTHER_CAPTION)],
            predictions=[_PICTURE, _CAPTION_REGION],
            texts={_CAPTION_REGION.bbox: _CAPTION},
        )

        assert sorted(item["caption"] for item in plan) == sorted([_CAPTION, _OTHER_CAPTION])
        assert all(len(item["images"]) == 1 for item in plan)

    def test_an_identical_caption_groups_panels_without_any_layout(self) -> None:
        plan = _plan([_image(_TOP_PANEL, caption=_CAPTION), _image(_BOTTOM_PANEL, caption=_CAPTION)])

        assert len(plan) == 1
        assert plan[0]["caption"] == _CAPTION
        assert len(plan[0]["images"]) == 2

    def test_panels_in_separate_picture_regions_sharing_a_caption_fold_into_one_figure(self) -> None:
        """One printed caption is one figure, even across layout regions (#410).

        The layout model can draw one region per panel of a multi-panel figure;
        each region then binds the same caption and the caption prints once per
        panel. The fold at the end of the planner is what makes the docstring's
        promise -- identical caption, one figure -- hold on the region path too.
        """
        top_region = LayoutPrediction(72.0, 100.0, 400.0, 200.0, "picture")
        bottom_region = LayoutPrediction(72.0, 201.0, 400.0, 300.0, "picture")
        plan = _plan(
            [_image(_TOP_PANEL, caption=_CAPTION), _image(_BOTTOM_PANEL, caption=_CAPTION)],
            predictions=[top_region, bottom_region, _CAPTION_REGION],
        )

        assert len(plan) == 1
        assert plan[0]["caption"] == _CAPTION
        assert [img["bbox"] for img in plan[0]["images"]] == [_TOP_PANEL, _BOTTOM_PANEL]

    def test_regions_with_distinct_captions_stay_separate_figures(self) -> None:
        top_region = LayoutPrediction(72.0, 100.0, 400.0, 200.0, "picture")
        bottom_region = LayoutPrediction(72.0, 201.0, 400.0, 300.0, "picture")
        plan = _plan(
            [_image(_TOP_PANEL, caption=_CAPTION), _image(_BOTTOM_PANEL, caption=_OTHER_CAPTION)],
            predictions=[top_region, bottom_region],
        )

        assert [item["caption"] for item in plan] == [_CAPTION, _OTHER_CAPTION]
        assert all(len(item["images"]) == 1 for item in plan)

    def test_a_region_item_and_a_loose_image_sharing_a_caption_fold_together(self) -> None:
        """The fold is path-blind: region-grouped and loose images with one caption merge."""
        top_region = LayoutPrediction(72.0, 100.0, 400.0, 200.0, "picture")
        loose_panel = pymupdf.Rect(80, 500, 200, 560)
        plan = _plan(
            [_image(_TOP_PANEL, caption=_CAPTION), _image(loose_panel, caption=_CAPTION)],
            predictions=[top_region],
        )

        assert len(plan) == 1
        assert [img["bbox"] for img in plan[0]["images"]] == [_TOP_PANEL, loose_panel]

    def test_uncaptioned_images_stay_bare(self) -> None:
        """No caption anywhere means no container: the paragraphs they always were."""
        plan = _plan([_image(_TOP_PANEL), _image(_BOTTOM_PANEL)])

        assert [item["caption"] for item in plan] == [None, None]
        assert all(len(item["images"]) == 1 for item in plan)

    def test_items_come_out_in_top_of_page_order(self) -> None:
        low = _image(pymupdf.Rect(80, 500, 200, 560), caption=_OTHER_CAPTION)
        high = _image(_TOP_PANEL, caption=_CAPTION)
        plan = _plan([low, high])

        assert [item["caption"] for item in plan] == [_CAPTION, _OTHER_CAPTION]


class TestVectorFigures:
    def test_a_rasterless_picture_region_becomes_a_caption_only_figure(self) -> None:
        plan = _plan(
            [],
            predictions=[_PICTURE, _CAPTION_REGION],
            texts={_CAPTION_REGION.bbox: _CAPTION},
        )

        assert plan == [{"images": [], "caption": _CAPTION}]

    def test_a_region_the_table_detector_claimed_stays_a_table(self) -> None:
        table = {"bbox": pymupdf.Rect(72, 100, 400, 300)}
        plan = _plan(
            [],
            predictions=[_PICTURE, _CAPTION_REGION],
            table_info=[table],
            texts={_CAPTION_REGION.bbox: _CAPTION},
        )

        assert plan == []

    def test_a_caption_already_bound_to_a_raster_is_not_emitted_twice(self) -> None:
        """A raster outside the region bound the same caption; the region must not clone it."""
        outside = _image(pymupdf.Rect(80, 500, 200, 560), caption=_CAPTION)
        plan = _plan(
            [outside],
            predictions=[_PICTURE, _CAPTION_REGION],
            texts={_CAPTION_REGION.bbox: _CAPTION},
        )

        assert len(plan) == 1
        assert plan[0]["images"] == [outside]

    def test_a_captionless_empty_region_emits_nothing(self) -> None:
        """A figure with neither pixels nor a caption carries no information."""
        plan = _plan([], predictions=[_PICTURE], texts={})

        assert plan == []


class TestVectorFigureEndToEnd:
    def test_a_vector_drawn_figure_survives_as_a_captioned_container(self, tmp_path, monkeypatch) -> None:
        """Whole route with the model boundary patched: drawings in, Figure out, caption once."""
        document = pymupdf.open()
        page = document.new_page()
        page.draw_circle(pymupdf.Point(150, 150), 40, color=(1, 0, 0))
        page.draw_line(pymupdf.Point(90, 200), pymupdf.Point(210, 120), color=(0, 0, 1))
        page.insert_text((72, 270), "Figure 1: Sample chart", fontsize=9)
        body = "The chart above summarises the calibration run."
        page.insert_text((72, 340), body, fontsize=9)
        path = tmp_path / "vector.pdf"
        document.save(path)
        document.close()

        predictions = [
            LayoutPrediction(70.0, 100.0, 220.0, 250.0, "picture"),
            LayoutPrediction(70.0, 258.0, 220.0, 278.0, "caption"),
        ]
        monkeypatch.setattr(pdf_module, "is_layout_available", lambda: True)
        monkeypatch.setattr(pdf_module, "predict_page_layout", lambda page, feature_set: predictions)

        options = PdfOptions(layout_analysis_mode="enabled")
        figures = collect_figures(to_ast(path, parser_options=options))
        assert len(figures) == 1
        assert isinstance(figures[0], Figure)
        assert figures[0].children == []
        assert figures[0].caption is not None and figures[0].caption.startswith("Figure 1: Sample chart")

        markdown = to_markdown(path, parser_options=options)
        # Once as the container's caption line; the body copy is suppressed, the prose is not.
        assert markdown.count("Figure 1: Sample chart") == 1
        assert body in markdown
