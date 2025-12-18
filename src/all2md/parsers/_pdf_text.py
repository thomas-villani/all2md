#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_text.py
"""PDF text processing utilities.

This private module contains functions for processing text from PDF documents,
including handling rotated text and resolving hyperlinks.

"""

from __future__ import annotations

from typing import TYPE_CHECKING

from all2md.constants import DEFAULT_OVERLAP_THRESHOLD_PERCENT
from all2md.options.markdown import MarkdownRendererOptions
from all2md.utils.inputs import escape_markdown_special

if TYPE_CHECKING:
    pass

__all__ = ["handle_rotated_text", "resolve_links"]


def handle_rotated_text(line: dict, md_options: MarkdownRendererOptions | None = None) -> str:
    """Process rotated text blocks and convert to readable format.

    Handles text that is rotated 90°, 180°, or 270° by extracting the text
    and marking it appropriately for inclusion in the markdown output.

    Parameters
    ----------
    line : dict
        Line dictionary from PyMuPDF containing direction and span information
    md_options : MarkdownRendererOptions or None, optional
        Markdown formatting options for escaping special characters

    Returns
    -------
    str
        Processed text from the rotated line, with rotation indicator

    """
    # Extract text from all spans in the rotated line
    text_parts = []
    for span in line.get("spans", []):
        span_text = span.get("text", "").strip()
        if span_text:
            if md_options and md_options.escape_special:
                span_text = escape_markdown_special(span_text)
            text_parts.append(span_text)

    if not text_parts:
        return ""

    combined_text = " ".join(text_parts)

    # Determine rotation type based on direction vector
    dir_x, dir_y = line.get("dir", (1, 0))

    if abs(dir_x) < 0.1 and abs(dir_y) > 0.9:
        # Vertical text (90° or 270°)
        if dir_y > 0:
            rotation_note = " *[rotated 90° clockwise]*"
        else:
            rotation_note = " *[rotated 90° counter-clockwise]*"
    elif abs(dir_x) > 0.9 and abs(dir_y) < 0.1:
        if dir_x < 0:
            rotation_note = " *[rotated 180°]*"
        else:
            rotation_note = ""  # Normal horizontal text
    else:
        # Arbitrary angle rotation
        rotation_note = " *[rotated text]*"

    return combined_text + rotation_note if rotation_note else combined_text


def resolve_links(
    links: list, span: dict, md_options: MarkdownRendererOptions | None = None, overlap_threshold: float | None = None
) -> str | None:
    """Accept a span bbox and return a markdown link string.

    Enhanced to handle partial overlaps and multiple links within a span
    by using character-level bbox analysis when needed.

    Parameters
    ----------
    links : list
        List of link dictionaries from page.get_links()
    span : dict
        Text span dictionary containing bbox and text information
    md_options : MarkdownRendererOptions or None, optional
        Markdown formatting options for escaping special characters
    overlap_threshold : float or None, optional
        Percentage overlap required for link detection (0-100). If None, uses DEFAULT_OVERLAP_THRESHOLD_PERCENT.

    Returns
    -------
    str or None
        Formatted markdown link string if overlap detected, None otherwise

    Notes
    -----
    The overlap_threshold parameter allows tuning link detection sensitivity:
    - Higher values (e.g., 80-90) reduce false positives but may miss valid links
    - Lower values (e.g., 50-60) catch more links but may incorrectly link non-link text
    - Default (70) provides a good balance for most PDFs

    """
    if not links or not span.get("text"):
        return None

    import fitz

    bbox = fitz.Rect(span["bbox"])  # span bbox
    span_text = span["text"]

    # Use provided threshold or fall back to default
    threshold_percent = overlap_threshold if overlap_threshold is not None else DEFAULT_OVERLAP_THRESHOLD_PERCENT

    # Find all links that overlap with this span
    overlapping_links = []
    for link in links:
        hot = link.get("from")  # the hot area of the link
        if hot is None:
            continue  # Skip links without valid hot area
        overlap = hot & bbox
        if abs(overlap) > 0:
            overlapping_links.append((link, overlap))

    if not overlapping_links:
        return None

    # If single link covers most of the span, use simple approach
    if len(overlapping_links) == 1:
        link, overlap = overlapping_links[0]
        bbox_area = (threshold_percent / 100.0) * abs(bbox)
        if abs(overlap) >= bbox_area:
            uri = link.get("uri")
            if not uri:
                return None  # Skip links without valid URI
            link_text = span_text.strip()
            if md_options and md_options.escape_special:
                link_text = escape_markdown_special(link_text, md_options.bullet_symbols)
            return f"[{link_text}]({uri})"

    # Handle multiple or partial links by character-level analysis
    # Estimate character positions based on bbox width
    if len(span_text) == 0:
        return None

    char_width = bbox.width / len(span_text)
    result_parts = []
    last_end = 0

    # Sort links by their x-coordinate
    overlapping_links.sort(key=lambda x: x[1].x0)

    for link, overlap in overlapping_links:
        # Check if this link meets the threshold
        bbox_area = (threshold_percent / 100.0) * abs(bbox)
        if abs(overlap) < bbox_area:
            # This link doesn't meet the threshold, skip it
            continue

        # Calculate character range for this link
        start_char = max(0, int((overlap.x0 - bbox.x0) / char_width))
        end_char = min(len(span_text), int((overlap.x1 - bbox.x0) / char_width))

        if start_char >= end_char:
            continue

        # Add non-link text before this link
        if start_char > last_end:
            text_before = span_text[last_end:start_char]
            if md_options and md_options.escape_special:
                text_before = escape_markdown_special(text_before, md_options.bullet_symbols)
            result_parts.append(text_before)

        # Add link text
        link_text = span_text[start_char:end_char].strip()
        if link_text:
            if md_options and md_options.escape_special:
                link_text = escape_markdown_special(link_text, md_options.bullet_symbols)
            result_parts.append(f"[{link_text}]({link['uri']})")
            last_end = end_char

    # Add remaining non-link text
    if last_end < len(span_text):
        text_after = span_text[last_end:]
        if md_options and md_options.escape_special:
            text_after = escape_markdown_special(text_after, md_options.bullet_symbols)
        result_parts.append(text_after)

    # Return combined result if any links were found
    if result_parts:
        return "".join(result_parts)

    return None
