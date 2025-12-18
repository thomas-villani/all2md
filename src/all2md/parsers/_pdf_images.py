#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_images.py
"""PDF image extraction utilities.

This private module contains functions for extracting images from PDF pages
and detecting image captions.

"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Callable

from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import generate_attachment_filename, process_attachment

if TYPE_CHECKING:
    import fitz

__all__ = ["extract_page_images", "detect_image_caption"]


def detect_image_caption(page: "fitz.Page", image_bbox: "fitz.Rect") -> str | None:
    """Detect caption text near an image.

    Looks for text blocks immediately below or above the image
    that might be captions (e.g., starting with "Figure", "Fig.", etc.).

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page containing the image
    image_bbox : PyMuPDF Rect
        Bounding box of the image

    Returns
    -------
    str or None
        Detected caption text or None if no caption found

    """
    # Define search region below and above image
    caption_patterns = [
        r"^(Figure|Fig\.?|Image|Picture|Photo|Illustration|Table)\s+\d+",
        r"^(Figure|Fig\.?|Image|Picture|Photo|Illustration|Table)\s+[A-Z]\.",
    ]

    import fitz

    # Search below image
    search_below = fitz.Rect(image_bbox.x0 - 20, image_bbox.y1, image_bbox.x1 + 20, image_bbox.y1 + 50)

    # Search above image (less common)
    search_above = fitz.Rect(image_bbox.x0 - 20, image_bbox.y0 - 50, image_bbox.x1 + 20, image_bbox.y0)

    for search_rect in [search_below, search_above]:
        text = page.get_textbox(search_rect)
        if text:
            text = text.strip()
            # Limit text length to prevent ReDoS attacks
            # Captions should be short, so 500 chars is reasonable
            if len(text) > 500:
                text = text[:500]
            # Check if text matches caption pattern
            for pattern in caption_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    return text

            # Also check for short text that might be a caption
            if len(text) < 200 and text[0].isupper():
                return text

    return None


def extract_page_images(
    page: "fitz.Page",
    page_num: int,
    options: PdfOptions | None = None,
    base_filename: str = "document",
    attachment_sequencer: Callable | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Extract images from a PDF page with their positions.

    Extracts all images from the page and optionally saves them to disk
    or converts to base64 data URIs for embedding in Markdown.

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

    # For alt_text mode, only extract if we need image placement markers
    if options.attachment_mode == "alt_text" and not options.image_placement_markers:
        return [], collected_footnotes

    import fitz

    images = []
    image_list = page.get_images()

    for img_idx, img in enumerate(image_list):
        # Initialize pixmap references for proper cleanup in finally block
        pix = None
        pix_rgb = None
        try:
            # Get image data
            xref = img[0]
            pix = fitz.Pixmap(page.parent, xref)

            # Convert to RGB if needed
            if pix.n - pix.alpha < 4:  # GRAY or RGB
                pix_rgb = pix
            else:
                pix_rgb = fitz.Pixmap(fitz.csRGB, pix)

            # Get image position on page
            img_rects = page.get_image_rects(xref)
            if not img_rects:
                continue

            bbox = img_rects[0]  # Use first occurrence

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
                caption = detect_image_caption(page, bbox)

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
