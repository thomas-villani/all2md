"""What `detect_image_caption` will and will not call a caption.

The detector had no tests at all, which is some of how it drifted to accepting any text
under 200 characters that began with a capital -- on a journal page that is a running head,
an author list, or an ordinary sentence. Measured against JATS figure captions over 12 PMC
articles it returned 32 strings of which 19 were captions; the rules here return 31 of which
27 are, when the layout model is available.

The layout tests pass regions in directly rather than running the model, so they exercise
the binding rule on every platform -- `pymupdf-layout` is an optional extra and is not
installed in the unit lane.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from all2md.parsers._pdf_images import detect_image_caption

pytestmark = [pytest.mark.unit, pytest.mark.pdf, pytest.mark.image]

CAPTION = "Figure 1. Growth of the assay over twelve weeks."
#: A column-spanning figure, so the fallback band is wide enough to hold CAPTION whole.
#: A *narrower* figure clips it -- see `test_a_caption_wider_than_the_band_is_clipped`.
IMAGE_RECT = (72.0, 120.0, 400.0, 240.0)


@dataclass(frozen=True)
class FakeRegion:
    """Stands in for a `LayoutPrediction`; the detector only reads ``bbox``."""

    bbox: tuple[float, float, float, float]


def _page(tmp_path: Path, lines: dict[float, str], *, name: str = "page.pdf"):
    """A one-page PDF with an image at IMAGE_RECT and text at the given baselines."""
    pymupdf = pytest.importorskip("pymupdf")
    source = pymupdf.open()
    source_page = source.new_page()
    source_page.draw_rect(pymupdf.Rect(0, 0, 100, 100), fill=(0.5, 0.5, 0.5))
    pixmap = source_page.get_pixmap(dpi=36)
    source.close()

    document = pymupdf.open()
    page = document.new_page()
    page.insert_image(pymupdf.Rect(*IMAGE_RECT), pixmap=pixmap)
    for baseline, text in lines.items():
        page.insert_text((72, baseline), text, fontsize=9)
    path = tmp_path / name
    document.save(path)
    document.close()

    opened = pymupdf.open(path)
    return opened, opened[0], pymupdf.Rect(*IMAGE_RECT)


class TestTheCue:
    """With no layout regions, only a figure cue counts."""

    def test_a_cue_below_the_image_is_the_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {250.0: CAPTION})
        try:
            assert detect_image_caption(page, bbox) == CAPTION
        finally:
            document.close()

    def test_a_cue_above_the_image_is_the_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {110.0: CAPTION})
        try:
            assert detect_image_caption(page, bbox) == CAPTION
        finally:
            document.close()

    def test_ordinary_prose_below_the_image_is_not_a_caption(self, tmp_path: Path) -> None:
        """The rule this replaces returned this string, because it is short and capitalised."""
        document, page, bbox = _page(tmp_path, {250.0: "The assay was repeated in triplicate."})
        try:
            assert detect_image_caption(page, bbox) is None
        finally:
            document.close()

    def test_a_running_head_is_not_a_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {110.0: "APPELLETTI ET AL."})
        try:
            assert detect_image_caption(page, bbox) is None
        finally:
            document.close()

    def test_text_beyond_the_band_is_not_a_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {700.0: CAPTION})
        try:
            assert detect_image_caption(page, bbox) is None
        finally:
            document.close()

    def test_a_caption_wider_than_the_band_is_clipped(self, tmp_path: Path) -> None:
        """A known limit of the cue path, pinned rather than hidden.

        The band is the image's width plus a small overhang, so a caption set to the
        column width under a narrow figure loses its tail. The layout region does not
        have this problem, because the model draws the box around the caption itself.
        """
        pymupdf = pytest.importorskip("pymupdf")
        document, page, _ = _page(tmp_path, {250.0: CAPTION}, name="narrow.pdf")
        try:
            narrow = pymupdf.Rect(72.0, 120.0, 220.0, 240.0)
            clipped = detect_image_caption(page, narrow)
            assert clipped is not None
            assert CAPTION.startswith(clipped)
            assert clipped != CAPTION

            region = [FakeRegion((72.0, 244.0, 400.0, 256.0))]
            assert detect_image_caption(page, narrow, region) == CAPTION
        finally:
            document.close()

    def test_an_empty_band_yields_no_caption_rather_than_crashing(self, tmp_path: Path) -> None:
        """A whitespace-only band used to reach ``text[0]`` and raise IndexError.

        The caller wraps image extraction in ``except Exception: continue``, so the crash
        did not surface -- it silently dropped the whole image, 1 in 70 on the PMC corpus.
        """
        document, page, bbox = _page(tmp_path, {250.0: "   "})
        try:
            assert detect_image_caption(page, bbox) is None
        finally:
            document.close()


class TestTheLayoutRegion:
    """A `caption` region beats the cue, and is not required to carry one."""

    def test_a_caption_region_below_the_image_wins(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {250.0: "Growth over twelve weeks, by cohort."})
        try:
            regions = [FakeRegion((72.0, 244.0, 320.0, 256.0))]
            # No figure cue anywhere: the cue-only path returns nothing here, so this
            # asserts the region is what recovered it.
            assert detect_image_caption(page, bbox) is None
            assert detect_image_caption(page, bbox, regions) == "Growth over twelve weeks, by cohort."
        finally:
            document.close()

    def test_a_region_in_the_next_column_is_not_this_figures_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {250.0: CAPTION})
        try:
            regions = [FakeRegion((420.0, 244.0, 560.0, 256.0))]
            assert detect_image_caption(page, bbox, regions) == CAPTION  # falls back to the cue
        finally:
            document.close()

    def test_a_distant_region_is_not_this_figures_caption(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {600.0: "Growth over twelve weeks, by cohort."})
        try:
            regions = [FakeRegion((72.0, 594.0, 320.0, 606.0))]
            assert detect_image_caption(page, bbox, regions) is None
        finally:
            document.close()

    def test_the_nearer_region_wins_when_two_are_in_range(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {250.0: "Nearest below.", 290.0: "Further below."})
        try:
            regions = [
                FakeRegion((72.0, 284.0, 320.0, 296.0)),
                FakeRegion((72.0, 244.0, 320.0, 256.0)),
            ]
            assert detect_image_caption(page, bbox, regions) == "Nearest below."
        finally:
            document.close()

    def test_below_beats_above_at_equal_distance(self, tmp_path: Path) -> None:
        """A figure's caption is set below it; a table's above. This is the figure rule."""
        document, page, bbox = _page(tmp_path, {110.0: "Above the figure.", 250.0: "Below the figure."})
        try:
            regions = [
                FakeRegion((72.0, 104.0, 320.0, 116.0)),
                FakeRegion((72.0, 244.0, 320.0, 256.0)),
            ]
            assert detect_image_caption(page, bbox, regions) == "Below the figure."
        finally:
            document.close()

    def test_an_empty_region_falls_through_to_the_cue(self, tmp_path: Path) -> None:
        document, page, bbox = _page(tmp_path, {250.0: CAPTION})
        try:
            regions = [FakeRegion((400.0, 400.0, 500.0, 420.0))]
            assert detect_image_caption(page, bbox, regions) == CAPTION
        finally:
            document.close()
