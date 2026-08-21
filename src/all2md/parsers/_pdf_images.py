#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_images.py
"""PDF image extraction utilities.

This private module contains functions for extracting images from PDF pages
and detecting image captions.

"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable

from all2md.constants import (
    PDF_CAPTION_BAND_HEIGHT,
    PDF_CAPTION_BAND_OVERHANG,
    PDF_CAPTION_MAX_LENGTH,
    PDF_CAPTION_SEARCH_GAP,
)
from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import generate_attachment_filename, process_attachment

if TYPE_CHECKING:
    import pymupdf

__all__ = ["extract_page_images", "detect_image_caption"]


def _bbox_in_any_region(bbox: Any, regions: list[Any], coverage: float = 0.7) -> bool:
    """Return True if ``bbox`` is mostly inside any of the given regions.

    Uses fractional coverage of the image rect rather than full containment so
    images that overlap the boundary of a header/footer band by a few points
    still get filtered.
    """
    bbox_area = abs(bbox)
    if bbox_area <= 0:
        return False
    for region in regions:
        intersection = bbox & region
        if abs(intersection) >= coverage * bbox_area:
            return True
    return False


#: Openings that mark a line as a figure caption rather than body text. Used only when the
#: layout model is unavailable, where there is nothing better to go on.
_CAPTION_KEYWORD = re.compile(
    r"^(Figure|Fig\.?|Image|Picture|Photo|Illustration|Scheme|Chart|Graph|Table)",
    re.IGNORECASE,
)
#: What may follow the keyword: a run of digits (optionally separated by punctuation or
#: whitespace), or a single uppercase letter set off by real whitespace. Deliberately *not*
#: case-insensitive -- under IGNORECASE, a bare ``[A-Z]`` also matches the trailing "s" of a
#: plural sentence opener, so mandatory whitespace plus a case-sensitive letter class is what
#: keeps "Figures in this study" and "Tables 1 and 2" from reading as captions.
_CAPTION_LOCATOR = re.compile(r"(?:\s*\.?\s*\d|\s+[A-Z]\b)")


def _matches_caption_cue(text: str) -> bool:
    """Return True if ``text`` opens like "Figure 3" / "Fig. 2b" rather than ordinary prose."""
    keyword_match = _CAPTION_KEYWORD.match(text)
    return bool(keyword_match and _CAPTION_LOCATOR.match(text, keyword_match.end()))


def _region_text(page: "pymupdf.Page", rect: Any) -> str:
    """Return the text inside a rect as a single whitespace-collapsed line.

    Deliberately not clipped to ``PDF_CAPTION_MAX_LENGTH``: that cap belongs to the
    cue *matcher*, not the stored caption. Clipping the caption itself cut real
    captions mid-sentence -- the figure then carried a 500-character prefix while
    the body copy kept the full text, so the copies could never match and the
    caption printed twice (#410).
    """
    return " ".join(page.get_textbox(rect).split())


def _caption_from_layout(
    page: "pymupdf.Page",
    image_bbox: "pymupdf.Rect",
    caption_regions: list[Any],
) -> str | None:
    """Return the text of the layout ``caption`` region bound to this image, if any.

    Below beats above at equal distance, which is the convention for figures -- and the
    opposite of a table's, whose caption is set above it. Ties are broken by distance so a
    page with two figures does not give both the same caption.
    """
    import pymupdf

    best: tuple[float, str] | None = None
    for region in caption_regions:
        rect = pymupdf.Rect(region.bbox)
        # A caption sits under the figure it belongs to, not beside it in the next column.
        if min(image_bbox.x1, rect.x1) - max(image_bbox.x0, rect.x0) <= 0:
            continue
        if rect.y0 >= image_bbox.y1 - 2:
            gap, rank = rect.y0 - image_bbox.y1, rect.y0 - image_bbox.y1
        elif rect.y1 <= image_bbox.y0 + 2:
            # Ranked behind every below-candidate by adding a whole gap's worth.
            gap = image_bbox.y0 - rect.y1
            rank = gap + PDF_CAPTION_SEARCH_GAP
        else:
            continue
        if gap > PDF_CAPTION_SEARCH_GAP:
            continue
        text = _region_text(page, rect)
        if text and (best is None or rank < best[0]):
            best = (rank, text)
    return best[1] if best else None


def detect_image_caption(
    page: "pymupdf.Page",
    image_bbox: "pymupdf.Rect",
    caption_regions: list[Any] | None = None,
) -> str | None:
    """Detect the caption belonging to an image.

    Prefers the layout model's ``caption`` regions, which are what the model was trained to
    find, and falls back to matching a figure cue (``Figure 3``, ``Fig. 2b``) against a
    fixed band above and below the image when the model is unavailable.

    The fallback is deliberately narrower than the band search it replaces. That search also
    accepted *any* text under 200 characters beginning with a capital, which on a journal
    page means running heads, author names and ordinary sentences: measured against JATS
    figure captions over 12 PMC articles, it returned 32 strings of which 19 were captions.
    The rules here return 31 of which 27 are captions with the model, and 19 of which 15 are
    with only the cue. Requiring the cue *on top of* a layout region was tried and rejected:
    it bought 0.9 points of precision for 8.8 points of recall, because real captions do not
    all open with the word "Figure".

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page containing the image.
    image_bbox : PyMuPDF Rect
        Bounding box of the image.
    caption_regions : list of LayoutPrediction or None
        The page's layout regions labelled ``caption``. Empty or None falls back to the cue.

    Returns
    -------
    str or None
        The caption text, or None when nothing near the image looks like one.

    """
    import pymupdf

    if caption_regions:
        found = _caption_from_layout(page, image_bbox, caption_regions)
        if found:
            return found

    below = pymupdf.Rect(
        image_bbox.x0 - PDF_CAPTION_BAND_OVERHANG,
        image_bbox.y1,
        image_bbox.x1 + PDF_CAPTION_BAND_OVERHANG,
        image_bbox.y1 + PDF_CAPTION_BAND_HEIGHT,
    )
    above = pymupdf.Rect(
        image_bbox.x0 - PDF_CAPTION_BAND_OVERHANG,
        image_bbox.y0 - PDF_CAPTION_BAND_HEIGHT,
        image_bbox.x1 + PDF_CAPTION_BAND_OVERHANG,
        image_bbox.y0,
    )
    for search_rect in (below, above):
        # The cue pattern sees at most PDF_CAPTION_MAX_LENGTH characters, so it
        # never matches against an unbounded string; the *returned* caption stays
        # whole (#410). A whitespace-only band collapses to "" and is skipped --
        # it used to reach `text[0]` and raise IndexError, which the caller swallowed
        # as "skip this image", silently deleting 1 image in 70 on the PMC corpus.
        text = _region_text(page, search_rect)
        if text and _matches_caption_cue(text[:PDF_CAPTION_MAX_LENGTH]):
            return text

    return None


def extract_page_images(
    page: "pymupdf.Page",
    page_num: int,
    options: PdfOptions | None = None,
    base_filename: str = "document",
    attachment_sequencer: Callable | None = None,
    excluded_regions: list[Any] | None = None,
    caption_regions: list[Any] | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Extract images from a PDF page with their positions.

    Extracts all images from the page and optionally saves them to disk
    or converts to base64 data URIs for embedding in Markdown. Under
    ``attachment_mode="alt_text"`` no pixmap is ever decoded: the pass records
    geometry and detected captions only, and returns just the figures that carry
    a caption -- a captioned figure with no URL is meaningful output, an
    uncaptioned ``![alt]()`` placeholder is not (#338).

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page to extract images from
    page_num : int
        Page number for naming extracted images
    options : PdfOptions or None, optional
        PDF options containing image extraction settings
    base_filename : str, default "document"
        Base filename stem for generating standardized image names
    attachment_sequencer : object, optional
        Sequencer for generating unique attachment names
    excluded_regions : list of pymupdf.Rect, optional
        Regions on the page where images should be skipped (e.g. page-header
        and page-footer zones from layout analysis). An image is dropped if
        its bbox is mostly contained in any excluded region.
    caption_regions : list of LayoutPrediction, optional
        The page's layout regions labelled ``caption``. When absent, caption detection
        falls back to matching a figure cue near the image.

    Returns
    -------
    tuple[list[dict], dict[str, str]]
        Tuple containing:
            - List of dictionaries with image info:
                - 'bbox': Image bounding box
                - 'path': Path to saved image or data URI
                - 'caption': Detected caption text (if any)
            - Dictionary of footnote definitions (label -> content) collected during processing


    Notes
    -----
    For large PDFs with many images, use skip_image_extraction=True in PdfOptions
    to avoid memory pressure from decoding images on every page.

    """
    # Track footnotes collected during this function
    collected_footnotes: dict[str, str] = {}

    # Skip image extraction entirely if requested (performance optimization for large PDFs)
    if options and options.skip_image_extraction:
        return [], collected_footnotes

    if not options or options.attachment_mode == "skip":
        return [], collected_footnotes

    # In alt_text mode there are no bytes to embed, so what is worth emitting is a
    # *captioned* figure: the caption is meaningful page content, while an uncaptioned
    # URL-less ``![alt]()`` placeholder is just noise (#338, #340). The pass below
    # detects geometry and captions without ever decoding a pixmap; with caption
    # detection off there is nothing it could emit, so skip it entirely.
    # ``image_placement_markers`` remains meaningful for ``save`` / ``base64``.
    caption_only = options.attachment_mode == "alt_text"
    if caption_only and not options.include_image_captions:
        return [], collected_footnotes

    import pymupdf

    min_dim = float(options.min_image_dimension or 0.0)
    exclusion_rects = list(excluded_regions or [])

    images = []
    image_list = page.get_images()

    for img_idx, img in enumerate(image_list):
        # Initialize pixmap references for proper cleanup in finally block
        pix = None
        pix_rgb = None
        try:
            # Get image data
            xref = img[0]

            # Get image position on page (cheap; do this before decoding the
            # pixmap so tiny / excluded images can be skipped without paying
            # the decode cost).
            img_rects = page.get_image_rects(xref)
            if not img_rects:
                continue

            bbox = img_rects[0]  # Use first occurrence

            # Filter out tiny decorations (logo strokes, signature artifacts).
            if min_dim > 0 and (bbox.width < min_dim or bbox.height < min_dim):
                continue

            # Filter out images that sit inside layout-detected page-header /
            # page-footer regions.
            if exclusion_rects and _bbox_in_any_region(bbox, exclusion_rects):
                continue

            if caption_only:
                # Captioned figures survive the default mode; uncaptioned ones stay
                # suppressed as noise. No pixmap is ever decoded on this path, and
                # ``process_attachment`` with no data reduces to the alt-text result,
                # so footnote-style alt text keeps working.
                caption = detect_image_caption(page, bbox, caption_regions)
                if not caption:
                    continue
                result = process_attachment(
                    attachment_data=None,
                    attachment_name=f"{base_filename}-page{page_num + 1}-img{img_idx + 1}",
                    alt_text=f"Image from page {page_num + 1}",
                    attachment_mode="alt_text",
                    is_image=True,
                    alt_text_mode=options.alt_text_mode,
                )
                if result.get("footnote_label") and result.get("footnote_content"):
                    collected_footnotes[result["footnote_label"]] = result["footnote_content"]
                images.append({"bbox": bbox, "result": result, "caption": caption})
                continue

            pix = pymupdf.Pixmap(page.parent, xref)

            # Convert to RGB if needed
            if pix.n - pix.alpha < 4:  # GRAY or RGB
                pix_rgb = pix
            else:
                pix_rgb = pymupdf.Pixmap(pymupdf.csRGB, pix)

            # Determine image format and convert pixmap to bytes
            img_format = options.image_format if options.image_format else "png"
            img_extension = img_format  # "png" or "jpeg"

            if img_format == "jpeg":
                # Use JPEG with specified quality
                quality = options.image_quality if options.image_quality else 90
                img_bytes = pix_rgb.tobytes("jpeg", jpg_quality=quality)
            else:
                # Default to PNG
                img_bytes = pix_rgb.tobytes("png")

            # Use sequencer if available, otherwise fall back to manual indexing
            if attachment_sequencer is not None:
                img_filename, _ = attachment_sequencer(
                    base_stem=base_filename,
                    format_type="pdf",
                    page_num=page_num + 1,  # Convert to 1-based
                    extension=img_extension,
                )
            else:
                img_filename = generate_attachment_filename(
                    base_stem=base_filename,
                    format_type="pdf",
                    page_num=page_num + 1,  # Convert to 1-based
                    sequence_num=img_idx + 1,
                    extension=img_extension,
                )

            result = process_attachment(
                attachment_data=img_bytes,
                attachment_name=img_filename,
                alt_text=f"Image from page {page_num + 1}",
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=True,
                alt_text_mode=options.alt_text_mode,
            )

            # Collect footnote info if present
            if result.get("footnote_label") and result.get("footnote_content"):
                collected_footnotes[result["footnote_label"]] = result["footnote_content"]

            # Try to detect caption
            caption = None
            if options.include_image_captions:
                caption = detect_image_caption(page, bbox, caption_regions)

            # Store the process_attachment result dict instead of just markdown string
            images.append({"bbox": bbox, "result": result, "caption": caption})

        except Exception:
            # Skip problematic images
            continue
        finally:
            # Clean up pixmap resources to prevent memory leaks
            # This is critical for long-running operations and batch processing
            if pix_rgb is not None and pix_rgb != pix:
                pix_rgb = None
            if pix is not None:
                pix = None

    return images, collected_footnotes
