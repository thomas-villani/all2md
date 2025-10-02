#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pdf2markdown.py
"""PDF to Markdown conversion module.

This module provides advanced PDF parsing with table detection using PyMuPDF.
It extracts text content, handles complex layouts, and converts them to
well-formatted Markdown with support for headers, tables, links, and code blocks.

The conversion process identifies document structure including headers based on
font sizes, preserves table layouts using PyMuPDF's table detection, and
maintains formatting for code blocks, emphasis, and links.

Key Features
------------
- Advanced table detection and Markdown formatting
- Header identification based on font size analysis
- Link extraction and Markdown link formatting
- Code block detection for monospace fonts
- Page-by-page processing with customizable page ranges
- Password-protected PDF support
- Image embedding as base64 data URLs

Dependencies
------------
- PyMuPDF (fitz) v1.24.0 or later for PDF processing
- Required for all PDF operations including text extraction and table detection

Examples
--------
Basic PDF conversion:

    >>> from all2md.parsers.pdf2markdown import pdf_to_markdown
    >>> markdown_content = pdf_to_markdown("document.pdf")

Convert specific pages with options:

    >>> from all2md.options import PdfOptions
    >>> options = PdfOptions(pages=[0, 1, 2])
    >>> content = pdf_to_markdown("document.pdf", options=options)

Convert from file-like object:

    >>> from io import BytesIO
    >>> with open("document.pdf", "rb") as f:
    ...     content = pdf_to_markdown(BytesIO(f.read()))

Original from pdf4llm package, modified by Tom Villani to improve table processing.
"""

import re
import string
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, Union

if TYPE_CHECKING:
    import fitz

from all2md.constants import (
    DEFAULT_OVERLAP_THRESHOLD_PERCENT,
    DEFAULT_OVERLAP_THRESHOLD_PX,
    PDF_MIN_PYMUPDF_VERSION,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError, PasswordProtectedError
from all2md.options import MarkdownOptions, PdfOptions
from all2md.utils.attachments import create_attachment_sequencer, process_attachment
from all2md.utils.inputs import (
    escape_markdown_special,
    format_markdown_heading,
    validate_and_convert_input,
    validate_page_range,
)
from all2md.utils.metadata import (
    PDF_FIELD_MAPPING,
    DocumentMetadata,
    extract_dict_metadata,
    prepend_metadata_if_enabled,
)

# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf", "application/x-pdf"],
    magic_bytes=[
        (b"%PDF", 0),  # PDF signature
    ],
    converter_module="all2md.parsers.pdf2markdown",
    converter_function="pdf_to_markdown",
    required_packages=[("pymupdf", "fitz", ">=1.26.4")],
    optional_packages=[],
    import_error_message=(
        "PDF conversion requires 'pymupdf' version 1.26.4 or later. "
        "Install with: pip install 'pymupdf>=1.26.4'"
    ),
    options_class="PdfOptions",
    description="Convert PDF documents to Markdown with advanced table detection",
    priority=10
)


def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    MarkdownConversionError
        If PyMuPDF version is too old
    """
    try:
        import fitz
        min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split(".")))
        if fitz.pymupdf_version_tuple < min_version:
            raise ImportError(
                f"PyMuPDF version {PDF_MIN_PYMUPDF_VERSION} or later is required, "
                f"but {'.'.join(map(str, fitz.pymupdf_version_tuple))} is installed."
            )
    except ImportError as e:
        if "fitz" in str(e) or "No module" in str(e):
            from all2md.exceptions import DependencyError
            raise DependencyError(
                converter_name="pdf",
                missing_packages=[("pymupdf", f">={PDF_MIN_PYMUPDF_VERSION}")],
            ) from e
        raise


SPACES = set(string.whitespace)  # used to check relevance of text pieces


class IdentifyHeaders:
    """Compute data for identifying header text based on font size analysis.

    This class analyzes font sizes across document pages to identify which
    font sizes should be treated as headers versus body text. It creates
    a mapping from font sizes to Markdown header levels (# ## ### etc.).

    Parameters
    ----------
    doc : fitz.Document
        PDF document to analyze
    pages : list[int], range, or None, optional
        Pages to analyze for font size distribution. If None, analyzes all pages.
    body_limit : float or None, optional
        Font size threshold below which text is considered body text.
        If None, uses the most frequent font size as body text baseline.
    options : PdfOptions or None, optional
        PDF conversion options containing header detection parameters.

    Attributes
    ----------
    header_id : dict[int, str]
        Mapping from font size to markdown header prefix string
    options : PdfOptions
        PDF conversion options used for header detection
    """

    def __init__(
            self,
            doc,  # PyMuPDF Document object
            pages: list[int] | range | None = None,
            body_limit: float | None = None,
            options: PdfOptions | None = None,
    ) -> None:
        """Initialize header identification by analyzing font sizes.

        Reads all text spans from specified pages and builds a frequency
        distribution of font sizes. Uses this to determine which font sizes
        should be treated as headers versus body text.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to analyze
        pages : list[int], range, or None, optional
            Pages to analyze for font size distribution. If None, analyzes all pages.
        body_limit : float or None, optional
            Font size threshold below which text is considered body text.
            If None, uses the most frequent font size as body text baseline.
        options : PdfOptions or None, optional
            PDF conversion options containing header detection parameters.
        """
        self.options = options or PdfOptions()

        # Determine pages to sample for header analysis
        if self.options.header_sample_pages is not None:
            if isinstance(self.options.header_sample_pages, int):
                # Sample first N pages
                pages_to_sample = list(range(min(self.options.header_sample_pages, doc.page_count)))
            else:
                # Use specific page list
                pages_to_sample = [p for p in self.options.header_sample_pages if p < doc.page_count]
        elif pages is not None:
            pages_to_sample = pages if isinstance(pages, list) else list(pages)
        else:
            pages_to_sample = list(range(doc.page_count))

        pages_to_use: list[int] = pages_to_sample
        fontsizes: dict[int, int] = {}
        fontweight_sizes: dict[int, int] = {}  # Track bold font sizes
        allcaps_sizes: dict[int, int] = {}  # Track all-caps text sizes
        import fitz
        for pno in pages_to_use:
            page = doc[pno]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            for span in [  # look at all non-empty horizontal spans
                s
                for b in blocks
                for line in b["lines"]
                for s in line["spans"]
                if not SPACES.issuperset(s["text"]) and line["dir"] == (1, 0)
            ]:
                fontsz = round(span["size"])
                text = span["text"].strip()
                text_len = len(text)

                # Track font size occurrences
                count = fontsizes.get(fontsz, 0) + text_len
                fontsizes[fontsz] = count

                # Track bold text if enabled
                if self.options.header_use_font_weight and (span["flags"] & 16):  # Bold flag
                    fontweight_sizes[fontsz] = fontweight_sizes.get(fontsz, 0) + text_len

                # Track all-caps text if enabled
                if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                    allcaps_sizes[fontsz] = allcaps_sizes.get(fontsz, 0) + text_len

        # maps a fontsize to a string of multiple # header tag characters
        self.header_id = {}
        self.bold_header_sizes = set()  # Track which sizes are headers due to bold
        self.allcaps_header_sizes = set()  # Track which sizes are headers due to all-caps

        # Apply allowlist/denylist filters
        if self.options.header_size_denylist:
            for size in self.options.header_size_denylist:
                fontsizes.pop(round(size), None)

        # Filter by minimum occurrences
        if self.options.header_min_occurrences > 0:
            fontsizes = {k: v for k, v in fontsizes.items() if v >= self.options.header_min_occurrences}

        # If not provided, choose the most frequent font size as body text.
        # If no text at all on all pages, just use 12
        if body_limit is None:
            temp = sorted(
                fontsizes.items(),
                key=lambda i: i[1],
                reverse=True,
            )
            body_limit = temp[0][0] if temp else 12

        # Get header sizes based on percentile threshold and minimum font size ratio
        if self.options.header_percentile_threshold and fontsizes:
            sorted_sizes = sorted(fontsizes.keys(), reverse=True)
            percentile_idx = int(len(sorted_sizes) * (1 - self.options.header_percentile_threshold / 100))
            percentile_threshold = sorted_sizes[max(0, percentile_idx - 1)] if percentile_idx > 0 else sorted_sizes[0]
            # Apply both percentile and font size ratio filters
            min_header_size = body_limit * self.options.header_font_size_ratio
            sizes = [s for s in sorted_sizes if s >= percentile_threshold and s >= min_header_size]
        else:
            # Apply font size ratio filter even without percentile threshold
            min_header_size = body_limit * self.options.header_font_size_ratio
            sizes = sorted([f for f in fontsizes if f >= min_header_size], reverse=True)

        # Add sizes from allowlist
        if self.options.header_size_allowlist:
            for size in self.options.header_size_allowlist:
                rounded_size = round(size)
                if rounded_size not in sizes and rounded_size > body_limit:
                    sizes.append(rounded_size)
            sizes = sorted(sizes, reverse=True)

        # Add bold and all-caps sizes as potential headers (but still respect font size ratio)
        min_header_size = body_limit * self.options.header_font_size_ratio
        if self.options.header_use_font_weight:
            for size in fontweight_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.bold_header_sizes.add(size)

        if self.options.header_use_all_caps:
            for size in allcaps_sizes:
                if size not in sizes and size >= min_header_size:
                    sizes.append(size)
                    self.allcaps_header_sizes.add(size)

        sizes = sorted(set(sizes), reverse=True)

        # make the header tag dictionary
        for i, size in enumerate(sizes):
            level = min(i + 1, 6)  # Limit to h6
            # Store level information for later formatting
            self.header_id[size] = level

    def get_header_level(self, span: dict) -> int:
        """Return header level for a text span, or 0 if not a header.

        Analyzes the font size of a text span and returns the corresponding
        header level (1-6) or 0 if the span should be treated as body text.
        Includes content-based validation to reduce false positives.

        Parameters
        ----------
        span : dict
            Text span dictionary from PyMuPDF extraction containing 'size' key

        Returns
        -------
        int
            Header level (1-6) or 0 if not a header
        """
        fontsize = round(span["size"])  # compute fontsize
        level = self.header_id.get(fontsize, 0)

        # Check for additional header indicators if no size-based header found
        if not level and self.options:
            text = span.get("text", "").strip()

            # Check for bold header
            if self.options.header_use_font_weight and (span.get("flags", 0) & 16):
                if fontsize in self.bold_header_sizes:
                    level = self.header_id.get(fontsize, 0)

            # Check for all-caps header
            if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                if fontsize in self.allcaps_header_sizes:
                    level = self.header_id.get(fontsize, 0)

        # Apply content-based validation if we detected a potential header
        if level > 0:
            text = span.get("text", "").strip()

            # Skip if text is too long to be a realistic header
            if len(text) > self.options.header_max_line_length:
                return 0

            # Skip if text is mostly whitespace or empty
            if not text or len(text.strip()) == 0:
                return 0

            # Skip if text looks like a paragraph (ends with typical sentence punctuation and is long)
            if len(text) > 50 and text.endswith(('.', '!', '?')):
                return 0

        return level


def detect_columns(blocks: list, column_gap_threshold: float = 20) -> list[list[dict]]:
    """Detect multi-column layout in text blocks.

    Analyzes the x-coordinates of text blocks to identify column boundaries
    and groups blocks into columns based on their horizontal positions.

    Parameters
    ----------
    blocks : list
        List of text blocks from PyMuPDF page extraction
    column_gap_threshold : float, default 20
        Minimum gap between columns in points

    Returns
    -------
    list[list[dict]]
        List of columns, where each column is a list of blocks
    """
    if not blocks:
        return [blocks]

    # Extract x-coordinates (left edge) for each block
    x_coords = []
    for block in blocks:
        if "bbox" in block:
            x_coords.append(block["bbox"][0])

    if len(x_coords) < 2:
        return [blocks]

    # Sort x-coordinates and find significant gaps
    sorted_x = sorted(set(x_coords))
    column_boundaries = [sorted_x[0]]

    for i in range(1, len(sorted_x)):
        gap = sorted_x[i] - sorted_x[i - 1]
        if gap >= column_gap_threshold:
            column_boundaries.append(sorted_x[i])

    # If no significant gaps found, treat as single column
    if len(column_boundaries) <= 1:
        return [blocks]

    # Check if we have overlapping blocks that suggest single column
    # Calculate the width coverage for each potential column
    block_ranges = []
    for block in blocks:
        if "bbox" in block:
            x0, x1 = block["bbox"][0], block["bbox"][2]
            block_ranges.append((x0, x1))

    # If most blocks overlap significantly, it's likely single column
    if len(block_ranges) >= 3:
        # Find the median width to determine if blocks are mostly full-width
        widths = [x1 - x0 for x0, x1 in block_ranges]
        median_width = sorted(widths)[len(widths) // 2]

        # Find overall page bounds
        min_x = min(x0 for x0, x1 in block_ranges)
        max_x = max(x1 for x0, x1 in block_ranges)
        page_width = max_x - min_x

        # If median block width is > 60% of page width, likely single column
        if median_width > 0.6 * page_width:
            return [blocks]

    # Group blocks into columns based on boundaries
    columns = [[] for _ in range(len(column_boundaries))]

    for block in blocks:
        if "bbox" not in block:
            columns[0].append(block)  # Default to first column
            continue

        x0 = block["bbox"][0]

        # Find which column this block belongs to
        assigned = False
        for i in range(len(column_boundaries) - 1):
            if column_boundaries[i] <= x0 < column_boundaries[i + 1]:
                columns[i].append(block)
                assigned = True
                break

        if not assigned:
            # Assign to last column
            columns[-1].append(block)

    # Sort blocks within each column by y-coordinate (top to bottom)
    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    # Remove empty columns
    columns = [col for col in columns if col]

    return columns


def handle_rotated_text(line: dict, md_options: MarkdownOptions | None = None) -> str:
    """Process rotated text blocks and convert to readable format.

    Handles text that is rotated 90°, 180°, or 270° by extracting the text
    and marking it appropriately for inclusion in the markdown output.

    Parameters
    ----------
    line : dict
        Line dictionary from PyMuPDF containing direction and span information
    md_options : MarkdownOptions or None, optional
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


def resolve_links(links: list, span: dict, md_options: MarkdownOptions | None = None) -> str | None:
    """Accept a span bbox and return a markdown link string.

    Enhanced to handle partial overlaps and multiple links within a span
    by using character-level bbox analysis when needed.

    Parameters
    ----------
    links : list
        List of link dictionaries from page.get_links()
    span : dict
        Text span dictionary containing bbox and text information
    md_options : MarkdownOptions or None, optional
        Markdown formatting options for escaping special characters

    Returns
    -------
    str or None
        Formatted markdown link string if overlap detected, None otherwise
    """
    if not links or not span.get("text"):
        return None

    import fitz
    bbox = fitz.Rect(span["bbox"])  # span bbox
    span_text = span["text"]

    # Find all links that overlap with this span
    overlapping_links = []
    for link in links:
        hot = link["from"]  # the hot area of the link
        overlap = hot & bbox
        if abs(overlap) > 0:
            overlapping_links.append((link, overlap))

    if not overlapping_links:
        return None

    # If single link covers most of the span, use simple approach
    if len(overlapping_links) == 1:
        link, overlap = overlapping_links[0]
        bbox_area = (DEFAULT_OVERLAP_THRESHOLD_PERCENT / 100.0) * abs(bbox)
        if abs(overlap) >= bbox_area:
            link_text = span_text.strip()
            if md_options and md_options.escape_special:
                link_text = escape_markdown_special(link_text, md_options.bullet_symbols)
            return f"[{link_text}]({link['uri']})"

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


def extract_page_images(
        page: "fitz.Page", page_num: int, options: PdfOptions | None = None, base_filename: str = "document",
        attachment_sequencer=None
) -> list[dict]:
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

    Returns
    -------
    list[dict]
        List of dictionaries containing image info:
        - 'bbox': Image bounding box
        - 'path': Path to saved image or data URI
        - 'caption': Detected caption text (if any)
    """
    if not options or options.attachment_mode == "skip":
        return []

    # For alt_text mode, only extract if we need image placement markers
    if options.attachment_mode == "alt_text" and not options.image_placement_markers:
        return []

    import fitz
    images = []
    image_list = page.get_images()

    for img_idx, img in enumerate(image_list):
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
            if attachment_sequencer:
                img_filename, _ = attachment_sequencer(
                    base_stem=base_filename,
                    format_type="pdf",
                    page_num=page_num + 1,  # Convert to 1-based
                    extension=img_extension
                )
            else:
                from all2md.utils.attachments import generate_attachment_filename
                img_filename = generate_attachment_filename(
                    base_stem=base_filename,
                    format_type="pdf",
                    page_num=page_num + 1,  # Convert to 1-based
                    sequence_num=img_idx + 1,
                    extension=img_extension
                )

            image_path = process_attachment(
                attachment_data=img_bytes,
                attachment_name=img_filename,
                alt_text=f"Image from page {page_num + 1}",
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=True,
                alt_text_mode=options.alt_text_mode,
            )

            # Try to detect caption
            caption = None
            if options.include_image_captions:
                caption = detect_image_caption(page, bbox)

            images.append({"bbox": bbox, "path": image_path, "caption": caption})

            # Clean up
            if pix_rgb != pix:
                pix_rgb = None
            pix = None

        except Exception:
            # Skip problematic images
            continue

    return images


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
            # Check if text matches caption pattern
            for pattern in caption_patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    return text

            # Also check for short text that might be a caption
            if len(text) < 200 and text[0].isupper():
                return text

    return None


def detect_tables_by_ruling_lines(page: "fitz.Page", threshold: float = 0.5) -> list["fitz.Rect"]:
    """Fallback table detection using ruling lines and text alignment.

    Uses page drawing commands to detect horizontal and vertical lines
    that form table structures, useful when PyMuPDF's table detection fails.

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page to analyze for tables
    threshold : float, default 0.5
        Minimum line length ratio relative to page size for ruling lines

    Returns
    -------
    list[PyMuPDF Rect]
        List of bounding boxes for detected tables
    """
    # Get page dimensions
    page_rect = page.rect
    min_hline_len = page_rect.width * threshold
    min_vline_len = page_rect.height * threshold * 0.3  # Lower threshold for vertical lines

    # Extract drawing commands to find lines
    drawings = page.get_drawings()

    h_lines = []
    v_lines = []

    import fitz

    for item in drawings:
        if "items" not in item:
            continue

        for drawing in item["items"]:
            if drawing[0] == "l":  # Line command
                p1, p2 = drawing[1], drawing[2]

                # Check if horizontal line
                if abs(p1.y - p2.y) < 2:  # Nearly horizontal
                    line_len = abs(p2.x - p1.x)
                    if line_len >= min_hline_len:
                        h_lines.append((min(p1.x, p2.x), p1.y, max(p1.x, p2.x), p2.y))

                # Check if vertical line
                elif abs(p1.x - p2.x) < 2:  # Nearly vertical
                    line_len = abs(p2.y - p1.y)
                    if line_len >= min_vline_len:
                        v_lines.append((p1.x, min(p1.y, p2.y), p2.x, max(p1.y, p2.y)))

    # Find table regions by grouping intersecting lines
    table_rects: list["fitz.Rect"] = []

    # Group horizontal lines by proximity
    h_lines.sort(key=lambda line: line[1])  # Sort by y-coordinate

    if len(h_lines) >= 2 and len(v_lines) >= 2:
        # Look for regions with multiple h_lines and v_lines
        for i in range(len(h_lines) - 1):
            for j in range(i + 1, min(i + 10, len(h_lines))):  # Check next few h_lines
                y1 = h_lines[i][1]
                y2 = h_lines[j][1]

                # Find v_lines that span between these h_lines
                spanning_vlines = [v for v in v_lines if v[1] <= y1 + 5 and v[3] >= y2 - 5]

                if len(spanning_vlines) >= 2:
                    # Found a potential table
                    x_min = min(min(h_lines[i][0], h_lines[j][0]), min(v[0] for v in spanning_vlines))
                    x_max = max(max(h_lines[i][2], h_lines[j][2]), max(v[2] for v in spanning_vlines))

                    table_rect = fitz.Rect(x_min, y1, x_max, y2)

                    # Check for overlap with existing tables
                    overlaps = False
                    for existing in table_rects:
                        if abs(existing & table_rect) > abs(table_rect) * 0.5:
                            overlaps = True
                            break

                    if not overlaps and not table_rect.is_empty:
                        table_rects.append(table_rect)

    return table_rects


def _parse_pdf_date(date_str: str) -> str:
    """Parse PDF date format into a readable string.

    Parameters
    ----------
    date_str : str
        PDF date string (e.g., "D:20210315120000Z")

    Returns
    -------
    str
        Parsed date or original string if parsing fails
    """
    if not date_str or not date_str.startswith('D:'):
        return date_str

    try:
        from datetime import datetime
        # Remove D: prefix and parse
        clean_date = date_str[2:]
        if 'Z' in clean_date:
            clean_date = clean_date.replace('Z', '+0000')
        # Basic parsing - format is YYYYMMDDHHmmSS
        if len(clean_date) >= 8:
            year = int(clean_date[0:4])
            month = int(clean_date[4:6])
            day = int(clean_date[6:8])
            return datetime(year, month, day)
    except (ValueError, IndexError):
        pass
    return date_str


def extract_pdf_metadata(doc: "fitz.Document") -> DocumentMetadata:
    """Extract metadata from PDF document.

    Parameters
    ----------
    doc : fitz.Document
        PyMuPDF document object

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    # PyMuPDF provides metadata as a dictionary
    pdf_meta = doc.metadata if hasattr(doc, 'metadata') else {}

    if not pdf_meta:
        return DocumentMetadata()

    # Create custom handlers for PDF-specific field processing
    def handle_pdf_dates(meta_dict: dict[str, Any], field_names: list[str]) -> Any:
        """Handle PDF date fields with special parsing."""
        for field_name in field_names:
            if field_name in meta_dict:
                date_val = meta_dict[field_name]
                if date_val and str(date_val).strip():
                    return _parse_pdf_date(str(date_val).strip())
        return None

    # Custom field mapping for PDF dates
    pdf_mapping = PDF_FIELD_MAPPING.copy()
    pdf_mapping.update({
        'creation_date': ['creationDate', 'CreationDate'],
        'modification_date': ['modDate', 'ModDate'],
    })

    # Custom handlers for special fields
    custom_handlers = {
        'creation_date': handle_pdf_dates,
        'modification_date': handle_pdf_dates,
    }

    # Use the utility function for standard extraction
    metadata = extract_dict_metadata(pdf_meta, pdf_mapping)

    # Apply custom handlers for date fields
    for field_name, handler in custom_handlers.items():
        if field_name in pdf_mapping:
            value = handler(pdf_meta, pdf_mapping[field_name])
            if value:
                setattr(metadata, field_name, value)

    # Store any additional PDF-specific metadata in custom fields
    processed_keys = set()
    for field_names in pdf_mapping.values():
        if isinstance(field_names, list):
            processed_keys.update(field_names)
        else:
            processed_keys.add(field_names)

    # Skip internal PDF fields
    internal_fields = {'format', 'trapped', 'encryption'}

    for key, value in pdf_meta.items():
        if key not in processed_keys and key not in internal_fields:
            if value and str(value).strip():
                metadata.custom[key] = value

    return metadata


def parse_page_ranges(page_spec: str, total_pages: int) -> list[int]:
    """Parse page range specification into list of 0-based page indices.

    Supports various formats:
    - "1-3" → [0, 1, 2]
    - "5" → [4]
    - "10-" → [9, 10, ..., total_pages-1]
    - "1-3,5,10-" → combined ranges

    Parameters
    ----------
    page_spec : str
        Page range specification
    total_pages : int
        Total number of pages in document

    Returns
    -------
    list of int
        0-based page indices

    Examples
    --------
    >>> parse_page_ranges("1-3,5", 10)
    [0, 1, 2, 4]
    >>> parse_page_ranges("8-", 10)
    [7, 8, 9]

    """
    pages = set()

    # Split by comma to handle multiple ranges
    parts = page_spec.split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Handle range (e.g., "1-3" or "10-")
        if '-' in part:
            range_parts = part.split('-', 1)
            start_str = range_parts[0].strip()
            end_str = range_parts[1].strip()

            # Parse start (1-based to 0-based)
            if start_str:
                start = int(start_str) - 1
            else:
                start = 0

            # Parse end (1-based to 0-based, or use total_pages if empty)
            if end_str:
                end = int(end_str) - 1
            else:
                end = total_pages - 1

            # Add all pages in range
            for p in range(start, end + 1):
                if 0 <= p < total_pages:
                    pages.add(p)
        else:
            # Single page (1-based to 0-based)
            page = int(part) - 1
            if 0 <= page < total_pages:
                pages.add(page)

    # Return sorted list
    return sorted(pages)


def _expand_page_separators(markdown: str, options: PdfOptions) -> str:
    """Expand PAGE_SEP markers with page separator template.

    Replaces HTML comment markers like <!-- PAGE_SEP:1/10 --> with the
    actual page separator template, expanding {page_num} and {total_pages} placeholders.

    Parameters
    ----------
    markdown : str
        Markdown text containing PAGE_SEP markers
    options : PdfOptions
        PDF options containing page_separator_template

    Returns
    -------
    str
        Markdown with expanded page separators

    """
    import re

    # Pattern to match <!-- PAGE_SEP:N/T -->
    pattern = r'<!-- PAGE_SEP:(\d+)/(\d+) -->'

    def replace_sep(match):
        page_num = match.group(1)
        total_pages = match.group(2)

        # Get template from options
        template = options.page_separator_template

        # Expand placeholders
        separator = template.replace("{page_num}", page_num)
        separator = separator.replace("{total_pages}", total_pages)

        # If include_page_numbers is True and template doesn't have placeholders,
        # append page numbers automatically
        if options.include_page_numbers and "{page_num}" not in template and "{total_pages}" not in template:
            separator = f"{separator}\nPage {page_num}/{total_pages}"

        return f"\n{separator}\n"

    return re.sub(pattern, replace_sep, markdown)


def pdf_to_markdown(input_data: Union[str, Path, IO[bytes], "fitz.Document"], options: PdfOptions | None = None) -> str:
    """Convert PDF document to Markdown format.

    This function processes PDF documents and converts them to well-formatted
    Markdown with support for headers, tables, links, and code blocks. It uses
    PyMuPDF's advanced table detection and preserves document structure.

    Parameters
    ----------
    input_data : str, Path, IO[bytes], or fitz.Document
        PDF document to convert. Can be:
        - String or Path to PDF file
        - Binary file object containing PDF data
        - Already opened PyMuPDF Document object
    options : PdfOptions or None, default None
        Configuration options for PDF conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown-formatted text content of the PDF document.

    Raises
    ------
    InputError
        If input type is not supported or page numbers are invalid
    PasswordProtectedError
        If PDF is password-protected and no/incorrect password provided
    MarkdownConversionError
        If document cannot be processed or PyMuPDF version is too old

    Notes
    -----
    - Tables may occasionally appear out of order compared to original layout
    - Complex tables can sometimes break into multiple separate tables
    - Headers are identified based on font size analysis
    - Code blocks are detected using monospace font analysis

    Examples
    --------
    Basic conversion:

        >>> markdown_text = pdf_to_markdown("document.pdf")

    Convert specific pages with base64 images:

        >>> from all2md.options import PdfOptions
        >>> options = PdfOptions(pages=[0, 1, 2])
        >>> content = pdf_to_markdown("document.pdf", options=options)

    Convert from file object with password:

        >>> from io import BytesIO
        >>> with open("encrypted.pdf", "rb") as f:
        ...     data = BytesIO(f.read())
        >>> options = PdfOptions(password="secret123")
        >>> content = pdf_to_markdown(data, options=options)
    """
    _check_pymupdf_version()

    import fitz

    # Handle backward compatibility and merge options
    if options is None:
        options = PdfOptions()

    # Validate and convert input
    doc_input, input_type = validate_and_convert_input(
        input_data, supported_types=["path-like", "file-like (BytesIO)", "fitz.Document objects"]
    )

    # Open document based on input type
    try:
        if input_type == "path":
            doc = fitz.open(filename=str(doc_input))
        elif input_type in ("file", "bytes"):
            # Handle different file-like object types
            if hasattr(doc_input, 'name') and hasattr(doc_input, 'read'):
                # For file objects that have a name attribute (like BufferedReader from open()),
                # use the filename approach which is more memory efficient
                doc = fitz.open(filename=doc_input.name)
            elif hasattr(doc_input, 'read'):
                # For file-like objects without name (like BytesIO), read the content
                doc = fitz.open(stream=doc_input.read(), filetype="pdf")
            else:
                # For bytes objects
                doc = fitz.open(stream=doc_input)
        elif input_type == "object":
            if isinstance(doc_input, fitz.Document) or (
                    hasattr(doc_input, "page_count") and hasattr(doc_input, "__getitem__")
            ):
                doc = doc_input
            else:
                raise InputError(
                    f"Expected fitz.Document object, got {type(doc_input).__name__}",
                    parameter_name="input_data",
                    parameter_value=doc_input,
                )
        else:
            raise InputError(
                f"Unsupported input type: {input_type}", parameter_name="input_data", parameter_value=doc_input
            )
    except Exception as e:
        if "password" in str(e).lower() or "encrypt" in str(e).lower():
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            raise PasswordProtectedError(filename=filename) from e
        else:
            raise MarkdownConversionError(
                f"Failed to open PDF document: {str(e)}", conversion_stage="document_opening", original_error=e
            ) from e

    # Validate page range
    try:
        validated_pages = validate_page_range(options.pages, doc.page_count)
        pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
    except Exception as e:
        raise InputError(
            f"Invalid page range: {str(e)}", parameter_name="pages", parameter_value=options.pages
        ) from e

    # Extract base filename for standardized attachment naming
    if input_type == "path" and isinstance(doc_input, (str, Path)):
        base_filename = Path(doc_input).stem
    else:
        # For non-file inputs, use a default name
        base_filename = "document"

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_pdf_metadata(doc)

    # Get Markdown options (create default if not provided)
    md_options = options.markdown_options or MarkdownOptions()

    # Create header identifier for font-based header detection
    hdr_identifier = IdentifyHeaders(doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=options)

    # Create attachment sequencer for consistent filename generation
    attachment_sequencer = create_attachment_sequencer()

    # Use new AST-based conversion path
    from all2md.parsers.pdf import PdfToAstConverter
    from all2md.ast import MarkdownRenderer

    # Convert PDF to AST
    ast_converter = PdfToAstConverter(
        options=options,
        doc=doc,
        base_filename=base_filename,
        attachment_sequencer=attachment_sequencer,
        hdr_identifier=hdr_identifier,
    )
    ast_document = ast_converter.convert_to_ast(doc, pages_to_use)

    # Render AST to markdown using MarkdownOptions
    renderer = MarkdownRenderer(md_options)
    markdown = renderer.render(ast_document)

    # Post-process page separators: expand PAGE_SEP markers with template
    markdown = _expand_page_separators(markdown, options)

    # Prepend metadata if enabled
    markdown = prepend_metadata_if_enabled(markdown, metadata, options.extract_metadata)

    return markdown
