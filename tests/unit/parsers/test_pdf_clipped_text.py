"""Text that a clipping path removes from the page must not reach the output.

``Page.get_textbox()`` builds its text page without ``TEXT_CLIP``, so it collects glyphs
that a clipping path or a form XObject ``/BBox`` erases from the rendering -- text that is
printed on no page and that ``get_text()`` will not return. Four extractions in the PDF
parser go through that call: figure captions, the caption-suppression key, table cell text,
and the paragraph a rejected table region falls back to.

The corpus case is a journal proof (PMC9000022) that keeps a superseded, wider typesetting
of each page inside a clipped XObject. Rendering the strip it occupies gives blank paper;
reading a caption region through the unclipped call returned it anyway, cut mid-word at the
region's edges and ahead of the real caption -- ``"...enrichment analysis o roups was
pe..."``. Where the two typesettings line up it doubles the caption instead, which is
harder to notice and no less wrong.

These tests build the same structure the proof does, with `show_pdf_page` clipped to a
strip: the ghost glyphs are in the content stream but outside the XObject's bbox.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.parsers._pdf_images import detect_image_caption
from all2md.parsers._pdf_text import clipped_textbox

pytestmark = [pytest.mark.unit, pytest.mark.pdf]

PRINTED = "Figure 1. Growth of the assay over twelve weeks."
#: Same opening as PRINTED, so the failure is a doubled caption rather than a foreign one.
GHOST = "Figure 1. Growth of the assay over many more twelve weeks superseded"
CAPTION_REGION = (60.0, 240.0, 560.0, 300.0)
IMAGE_RECT = (72.0, 120.0, 400.0, 236.0)


@pytest.fixture
def clipped_page(tmp_path: Path):
    """A page whose only printed caption is PRINTED, with GHOST clipped out of sight."""
    pymupdf = pytest.importorskip("pymupdf")

    source = pymupdf.open()
    source_page = source.new_page()
    # Below the printed caption, so the blank-paper check below samples a band the
    # printed caption does not reach into -- its ascenders would otherwise paint it.
    source_page.insert_text((72, 285), GHOST, fontsize=9)
    source_page.insert_text((72, 700), "visible strip", fontsize=9)

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 258), PRINTED, fontsize=9)
    # The whole source page is drawn into an XObject whose bbox is this strip, so GHOST --
    # at y=285 in source space -- is in the stream and outside the bbox. This is the shape
    # the journal proof has, not an approximation of it.
    strip = pymupdf.Rect(0, 690, 595, 710)
    page.show_pdf_page(strip, source, 0, clip=strip)
    path = tmp_path / "clipped.pdf"
    document.save(path)
    document.close()
    source.close()

    opened = pymupdf.open(path)
    try:
        yield opened[0]
    finally:
        opened.close()


def test_the_ghost_is_not_printed_anywhere(clipped_page) -> None:
    """The premise: it is invisible, so returning it is not a judgement call.

    Without this the other tests only show that two extractions disagree, not which
    one is right.
    """
    pymupdf = pytest.importorskip("pymupdf")

    assert "superseded" not in clipped_page.get_text("text")
    pixmap = clipped_page.get_pixmap(clip=pymupdf.Rect(0, 272, 595, 292), dpi=72)
    painted = {pixmap.pixel(x, y) for x in range(pixmap.width) for y in range(pixmap.height)}
    assert painted == {(255, 255, 255)}, "the ghost's band renders as blank paper"


def test_bare_get_textbox_returns_the_ghost(clipped_page) -> None:
    """Pins the PyMuPDF behaviour this helper exists to correct.

    If a release ever makes ``get_textbox`` honour clips on its own, this fails and the
    helper can go -- which is the only signal that would tell us so.
    """
    pymupdf = pytest.importorskip("pymupdf")

    assert "superseded" in clipped_page.get_textbox(pymupdf.Rect(*CAPTION_REGION))


def test_clipped_textbox_returns_only_printed_text(clipped_page) -> None:
    pymupdf = pytest.importorskip("pymupdf")

    text = clipped_textbox(clipped_page, pymupdf.Rect(*CAPTION_REGION))
    assert text.strip() == PRINTED


def test_a_bound_caption_is_not_doubled_by_the_ghost(clipped_page) -> None:
    """The end of the path: what the figure actually carries."""
    pymupdf = pytest.importorskip("pymupdf")

    class FakeRegion:
        bbox = CAPTION_REGION

    caption = detect_image_caption(clipped_page, pymupdf.Rect(*IMAGE_RECT), [FakeRegion()])
    assert caption == PRINTED
    assert caption.count("Figure 1.") == 1


def test_clipping_still_cuts_a_word_the_rect_crosses(clipped_page) -> None:
    """The helper changes which glyphs exist, not how the rect selects among them.

    Table cells depend on the per-glyph clip: a cell rect is a cell's contents, not the
    whole line it sits on. Switching to a line-preserving extraction would have fixed the
    ghost and broken every grid, so the distinction is load-bearing.
    """
    pymupdf = pytest.importorskip("pymupdf")

    whole = clipped_textbox(clipped_page, pymupdf.Rect(*CAPTION_REGION))
    half = clipped_textbox(clipped_page, pymupdf.Rect(150.0, 240.0, 560.0, 300.0))
    assert whole.startswith("Figure 1. Growth")
    assert not half.startswith("Figure 1. Growth")
    assert half and half in whole
