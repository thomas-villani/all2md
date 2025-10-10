#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/pdf.py
"""PDF to AST converter.

This module provides conversion from PDF documents to AST representation.
It replaces direct markdown string generation with structured AST building,
enabling multiple rendering strategies and improved testability.

"""

from __future__ import annotations

import logging
import re
import string
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Optional, Union

from all2md.options.markdown import MarkdownOptions
from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import create_attachment_sequencer, process_attachment

if TYPE_CHECKING:
    import fitz

from all2md.ast import (
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HTMLBlock,
    Image,
    Link,
    Node,
    SourceLocation,
    Strong,
    TableCell,
    TableRow,
    Text,
)
from all2md.ast import (
    Paragraph as AstParagraph,
)
from all2md.ast import (
    Table as AstTable,
)
from all2md.constants import (
    DEFAULT_OVERLAP_THRESHOLD_PERCENT,
    DEFAULT_OVERLAP_THRESHOLD_PX,
    PDF_MIN_PYMUPDF_VERSION,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, PasswordProtectedError, ValidationError
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import escape_markdown_special, validate_and_convert_input, validate_page_range
from all2md.utils.metadata import (
    PDF_FIELD_MAPPING,
    DocumentMetadata,
    extract_dict_metadata,
)

logger = logging.getLogger(__name__)

# Used to check relevance of text pieces
SPACES = set(string.whitespace)

def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    DependencyError
        If PyMuPDF version is too old

    Notes
    -----
    This function assumes fitz is already imported. It should be called
    after dependency checking via the @requires_dependencies decorator.

    """
    import fitz
    min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split(".")))
    if fitz.pymupdf_version_tuple < min_version:
        raise DependencyError(
            converter_name="pdf",
            missing_packages=[],
            version_mismatches=[("pymupdf", PDF_MIN_PYMUPDF_VERSION, ".".join(fitz.pymupdf_version_tuple))],
        )



def _simple_kmeans_1d(values: list[float], k: int, max_iterations: int = 20) -> list[int]:
    """Simple 1D k-means clustering implementation.

    Parameters
    ----------
    values : list of float
        1D values to cluster (e.g., x-coordinates)
    k : int
        Number of clusters
    max_iterations : int, default 20
        Maximum iterations for convergence

    Returns
    -------
    list of int
        Cluster assignment for each value (0 to k-1)

    """
    if not values or k <= 0:
        return []

    if k == 1:
        return [0] * len(values)

    if len(values) < k:
        # Not enough values for k clusters, assign each to its own cluster
        return list(range(len(values)))

    # Initialize centroids by selecting evenly spaced values
    sorted_values = sorted(enumerate(values), key=lambda x: x[1])
    step = len(sorted_values) // k
    initial_indices = [i * step for i in range(k)]
    centroids = [sorted_values[i][1] for i in initial_indices]

    assignments = [0] * len(values)

    for _ in range(max_iterations):
        # Assign each value to nearest centroid
        new_assignments = []
        for val in values:
            distances = [abs(val - centroid) for centroid in centroids]
            new_assignments.append(distances.index(min(distances)))

        # Check for convergence
        if new_assignments == assignments:
            break

        assignments = new_assignments

        # Update centroids
        new_centroids = []
        for cluster_id in range(k):
            cluster_values = [values[i] for i, assign in enumerate(assignments) if assign == cluster_id]
            if cluster_values:
                new_centroids.append(sum(cluster_values) / len(cluster_values))
            else:
                # Empty cluster, keep previous centroid
                new_centroids.append(centroids[cluster_id])

        centroids = new_centroids

    return assignments


def detect_columns(blocks: list, column_gap_threshold: float = 20, use_clustering: bool = False) -> list[list[dict]]:
    """Detect multi-column layout in text blocks with enhanced whitespace analysis.

    Analyzes the x-coordinates of text blocks to identify column boundaries
    and groups blocks into columns based on their horizontal positions. Uses
    whitespace analysis and connected-component grouping for improved accuracy.

    Parameters
    ----------
    blocks : list
        List of text blocks from PyMuPDF page extraction
    column_gap_threshold : float, default 20
        Minimum gap between columns in points
    use_clustering : bool, default False
        Use k-means clustering on x-coordinates for improved robustness

    Returns
    -------
    list[list[dict]]
        List of columns, where each column is a list of blocks

    Notes
    -----
    When use_clustering=True, the function uses k-means clustering to identify
    column groupings based on block center positions. This can be more robust
    for complex layouts but requires estimating the number of columns first.

    """
    if not blocks:
        return [blocks]

    # Extract x-coordinates and build whitespace map
    x_coords = []
    block_ranges = []
    block_centers = []
    for block in blocks:
        if "bbox" in block:
            x0, x1 = block["bbox"][0], block["bbox"][2]
            x_coords.append(x0)
            block_ranges.append((x0, x1))
            block_centers.append((x0 + x1) / 2)

    if len(x_coords) < 2:
        return [blocks]

    # Use k-means clustering if requested
    if use_clustering and block_centers:
        # Estimate number of columns from gap analysis
        sorted_x = sorted(set(x_coords))
        num_columns = 1
        for i in range(1, len(sorted_x)):
            gap = sorted_x[i] - sorted_x[i - 1]
            if gap >= column_gap_threshold:
                num_columns += 1

        # Limit to reasonable number of columns (1-4)
        num_columns = max(1, min(num_columns, 4))

        if num_columns > 1:
            # Apply k-means clustering on block centers
            cluster_assignments = _simple_kmeans_1d(block_centers, num_columns)

            # Group blocks by cluster
            columns_dict: dict[int, list[dict]] = {i: [] for i in range(num_columns)}
            for block_idx, (block, cluster_id) in enumerate(zip(blocks, cluster_assignments)):
                if "bbox" in block:
                    columns_dict[cluster_id].append(block)
                else:
                    # Blocks without bbox go to first cluster
                    columns_dict[0].append(block)

            # Convert dict to sorted list of columns (left to right)
            # Sort clusters by their mean x-coordinate
            cluster_centers = {}
            for cluster_id, cluster_blocks in columns_dict.items():
                if cluster_blocks:
                    centers = [(b["bbox"][0] + b["bbox"][2]) / 2 for b in cluster_blocks if "bbox" in b]
                    if centers:
                        cluster_centers[cluster_id] = sum(centers) / len(centers)
                    else:
                        cluster_centers[cluster_id] = 0
                else:
                    cluster_centers[cluster_id] = 0

            sorted_clusters = sorted(cluster_centers.items(), key=lambda x: x[1])
            columns = [columns_dict[cluster_id] for cluster_id, _ in sorted_clusters if columns_dict[cluster_id]]

            # Sort blocks within each column by y-coordinate (top to bottom)
            for column in columns:
                column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

            return columns

    # Build whitespace map: find gaps between all blocks
    # Sort block ranges by left edge
    sorted_ranges = sorted(block_ranges)

    # Find whitespace gaps (vertical whitespace strips between columns)
    whitespace_gaps = []
    for i in range(len(sorted_ranges) - 1):
        current_right = sorted_ranges[i][1]
        next_left = sorted_ranges[i + 1][0]
        gap_width = next_left - current_right

        if gap_width >= column_gap_threshold:
            # Record the gap
            whitespace_gaps.append({
                'start': current_right,
                'end': next_left,
                'width': gap_width
            })

    # Find consistent gaps that span multiple blocks (likely column separators)
    if whitespace_gaps:
        # Count how many gaps overlap at each position
        gap_frequency: dict[float, int] = {}
        for gap in whitespace_gaps:
            # Round to nearest 5 points to group similar positions
            gap_pos = round((gap['start'] + gap['end']) / 2 / 5) * 5
            gap_frequency[gap_pos] = gap_frequency.get(gap_pos, 0) + 1

        # Find positions with highest frequency (likely column boundaries)
        if gap_frequency:
            max_freq = max(gap_frequency.values())
            # Use gaps that appear in at least 30% of possible positions
            threshold_freq = max(2, max_freq * 0.3)
            column_boundaries = sorted([pos for pos, freq in gap_frequency.items() if freq >= threshold_freq])

            if column_boundaries:
                # Use these boundaries to split columns
                columns: list[list[dict]] = [[] for _ in range(len(column_boundaries) + 1)]

                for block in blocks:
                    if "bbox" not in block:
                        columns[0].append(block)
                        continue

                    x0 = block["bbox"][0]
                    x1 = block["bbox"][2]
                    block_center = (x0 + x1) / 2

                    # Find which column this block belongs to based on center point
                    assigned = False
                    for i, boundary in enumerate(column_boundaries):
                        if block_center < boundary:
                            columns[i].append(block)
                            assigned = True
                            break

                    if not assigned:
                        columns[-1].append(block)

                # Sort blocks within each column by y-coordinate (top to bottom)
                for column in columns:
                    column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

                # Remove empty columns
                columns = [col for col in columns if col]

                if len(columns) > 1:
                    return columns

    # If enhanced detection found no columns, return single column
    # Don't fall back to the simple algorithm as it measures wrong gaps
    if not whitespace_gaps:
        return [blocks]

    # Fallback to original simple gap detection for edge cases
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


def resolve_links(links: list, span: dict, md_options: MarkdownOptions | None = None, overlap_threshold: float | None = None) -> str | None:
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
        hot = link["from"]  # the hot area of the link
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


def extract_page_images(
        page: "fitz.Page", page_num: int, options: PdfOptions | None = None, base_filename: str = "document",
        attachment_sequencer: Callable | None = None
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

            images.append({"bbox": bbox, "path": result.get("markdown", ""), "caption": caption})

            # Clean up
            if pix_rgb != pix:
                pix_rgb = None
            pix = None

        except Exception:
            # Skip problematic images
            continue

    return images, collected_footnotes


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


def detect_tables_by_ruling_lines(page: "fitz.Page", threshold: float = 0.5) -> tuple[list["fitz.Rect"], list[tuple[list[tuple], list[tuple]]]]:
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
    tuple[list[PyMuPDF Rect], list[tuple[list, list]]]
        Tuple containing:
        - List of bounding boxes for detected tables
        - List of (h_lines, v_lines) tuples for each table, where each line
          is a tuple of (x0, y0, x1, y1) coordinates

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

    # Build list of line tuples for each table
    table_lines = []
    for table_rect in table_rects:
        # Find h_lines and v_lines that are part of this table
        table_h_lines = [line for line in h_lines
                        if line[1] >= table_rect.y0 and line[1] <= table_rect.y1]
        table_v_lines = [line for line in v_lines
                        if line[0] >= table_rect.x0 and line[0] <= table_rect.x1]
        table_lines.append((table_h_lines, table_v_lines))

    return table_rects, table_lines


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
        Pages to analyze for font size distribution. If None, samples first 5 pages
        for performance on large PDFs.
    body_limit : float or None, optional
        Font size threshold below which text is considered body text.
        If None, uses the most frequent font size as body text baseline.
    options : PdfOptions or None, optional
        PDF conversion options containing header detection parameters.
        Use options.header_sample_pages to override the default sampling behavior.

    Attributes
    ----------
    header_id : dict[int, str]
        Mapping from font size to markdown header prefix string
    options : PdfOptions
        PDF conversion options used for header detection
    debug_info : dict or None
        Debug information about header detection (if header_debug_output is enabled).
        Contains font size distribution, header sizes, and classification details.

    """

    def __init__(
            self,
            doc: Any,  # PyMuPDF Document object
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
            Pages to analyze for font size distribution. If None, samples first 5 pages.
        body_limit : float or None, optional
            Font size threshold below which text is considered body text.
            If None, uses the most frequent font size as body text baseline.
        options : PdfOptions or None, optional
            PDF conversion options containing header detection parameters.

        """
        self.options = options or PdfOptions()
        self.debug_info: dict[str, Any] | None = None

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
            # Default: sample first 5 pages for performance on large PDFs
            # This provides good header detection accuracy while avoiding O(n) scans
            pages_to_sample = list(range(min(5, doc.page_count)))

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

        # Store debug information if enabled
        if self.options.header_debug_output:
            self.debug_info = {
                "font_size_distribution": fontsizes.copy(),
                "bold_font_sizes": dict(fontweight_sizes),
                "allcaps_font_sizes": dict(allcaps_sizes),
                "body_text_size": body_limit,
                "header_sizes": sizes.copy(),
                "header_id_mapping": self.header_id.copy(),
                "bold_header_sizes": list(self.bold_header_sizes),
                "allcaps_header_sizes": list(self.allcaps_header_sizes),
                "percentile_threshold": self.options.header_percentile_threshold,
                "font_size_ratio": self.options.header_font_size_ratio,
                "min_occurrences": self.options.header_min_occurrences,
                "pages_sampled": pages_to_use.copy() if isinstance(pages_to_use, list) else list(pages_to_use),
            }

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

    def get_debug_info(self) -> dict[str, Any] | None:
        """Return debug information about header detection.

        Returns
        -------
        dict or None
            Debug information dictionary if header_debug_output was enabled,
            None otherwise. The dictionary contains:
            - font_size_distribution: Frequency of each font size
            - bold_font_sizes: Sizes where bold text was found
            - allcaps_font_sizes: Sizes where all-caps text was found
            - body_text_size: Detected body text font size
            - header_sizes: Font sizes classified as headers
            - header_id_mapping: Mapping from size to header level
            - bold_header_sizes: Sizes treated as headers due to bold
            - allcaps_header_sizes: Sizes treated as headers due to all-caps
            - percentile_threshold: Threshold used for detection
            - font_size_ratio: Minimum ratio for header classification
            - min_occurrences: Minimum occurrences threshold
            - pages_sampled: Pages analyzed for header detection

        Examples
        --------
        >>> options = PdfOptions(header_debug_output=True)
        >>> hdr = IdentifyHeaders(doc, options=options)
        >>> debug_info = hdr.get_debug_info()
        >>> if debug_info:
        ...     print(f"Body text size: {debug_info['body_text_size']}")
        ...     print(f"Header sizes: {debug_info['header_sizes']}")

        """
        return self.debug_info



class PdfToAstConverter(BaseParser):
    """Convert PDF to AST representation.

    This converter parses PDF documents using PyMuPDF and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PdfOptions or None, default = None
        Conversion options

    """

    def __init__(
        self,
        options: PdfOptions | None = None,
        progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the PDF parser with options and progress callback."""
        options = options or PdfOptions()
        super().__init__(options, progress_callback)
        self.options: PdfOptions = options
        self._hdr_identifier: Optional[IdentifyHeaders] = None
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    @requires_dependencies("pdf", [("pymupdf", "fitz", f">={PDF_MIN_PYMUPDF_VERSION}")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse PDF document into AST.

        This method handles loading the PDF file and converting it to AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            PDF file to parse

        Returns
        -------
        Document
            AST document node

        """
        import fitz
        _check_pymupdf_version()

        # Validate and convert input
        doc_input, input_type = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like (BytesIO)", "fitz.Document objects"]
        )

        # Open document based on input type
        try:
            if input_type == "path":
                doc = fitz.open(filename=str(doc_input))
            elif input_type in ("file", "bytes"):
                doc = fitz.open(stream=doc_input, filetype="pdf")
                # Handle different file-like object types
            elif input_type == "object":
                if isinstance(doc_input, fitz.Document) or (
                        hasattr(doc_input, "page_count") and hasattr(doc_input, "__getitem__")
                ):
                    doc = doc_input
                else:
                    raise ValidationError(
                        f"Expected fitz.Document object, got {type(doc_input).__name__}",
                        parameter_name="input_data",
                        parameter_value=doc_input,
                    )
            else:
                raise ValidationError(
                    f"Unsupported input type: {input_type}", parameter_name="input_data", parameter_value=doc_input
                )
        except Exception as e:
            raise MalformedFileError(
                f"Failed to open PDF document: {e!r}",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e
            ) from e

        # Handle password-protected PDFs using PyMuPDF's authentication API
        if doc.is_encrypted:
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            if self.options.password:
                # Attempt authentication with provided password
                auth_result = doc.authenticate(self.options.password)
                if auth_result == 0:
                    # Authentication failed (return code 0)
                    raise PasswordProtectedError(
                        message=(
                            "Failed to authenticate PDF with provided password. "
                            "Please check the password is correct."
                        ),
                        filename=filename
                    )
                # auth_result > 0 indicates successful authentication
                # (1=no passwords, 2=user password, 4=owner password, 6=both equal)
            else:
                # Document is encrypted but no password provided
                raise PasswordProtectedError(
                    message=(
                        "PDF document is password-protected. "
                        "Please provide a password using the 'password' option."
                    ),
                    filename=filename
                )

        # Validate page range
        try:
            validated_pages = validate_page_range(self.options.pages, doc.page_count)
            pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
        except Exception as e:
            raise ValidationError(
                f"Invalid page range: {str(e)}", parameter_name="pdf.pages", parameter_value=self.options.pages
            ) from e

        # Extract base filename for standardized attachment naming
        if input_type == "path" and isinstance(doc_input, (str, Path)):
            base_filename = Path(doc_input).stem
        else:
            # For non-file inputs, use a default name
            base_filename = "document"

        self._hdr_identifier = IdentifyHeaders(doc,
                                               pages=pages_to_use if isinstance(pages_to_use, list) else None,
                                               options=self.options)

        return self.convert_to_ast(doc, pages_to_use, base_filename)

    def extract_metadata(self, document: "fitz.Document") -> DocumentMetadata:
        """Extract metadata from PDF document.

        Extracts standard metadata fields from a PDF document including title,
        author, subject, keywords, creation date, modification date, and creator
        application information. Also preserves any custom metadata fields that
        are not part of the standard set.

        Parameters
        ----------
        document : fitz.Document
            PyMuPDF document object to extract metadata from

        Returns
        -------
        DocumentMetadata
            Extracted metadata including standard fields (title, author, dates, etc.)
            and any custom fields found in the PDF. Returns empty DocumentMetadata
            if no metadata is available.

        Notes
        -----
        - PDF date strings in format 'D:YYYYMMDDHHmmSS' are parsed into datetime objects
        - Empty or whitespace-only metadata values are ignored
        - Internal PDF fields (format, trapped, encryption) are excluded
        - Unknown metadata fields are stored in the custom dictionary

        """
        # PyMuPDF provides metadata as a dictionary
        pdf_meta = document.metadata if hasattr(document, 'metadata') else {}

        if not pdf_meta:
            return DocumentMetadata()

        # Create custom handlers for PDF-specific field processing
        def handle_pdf_dates(meta_dict: dict[str, Any], field_names: list[str]) -> Any:
            """Handle PDF date fields with special parsing."""
            for field_name in field_names:
                if field_name in meta_dict:
                    date_val = meta_dict[field_name]
                    if date_val and str(date_val).strip():
                        return self._parse_pdf_date(str(date_val).strip())
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
                processed_keys.add(field_names)  # type: ignore[unreachable]

        # Skip internal PDF fields
        internal_fields = {'format', 'trapped', 'encryption'}

        for key, value in pdf_meta.items():
            if key not in processed_keys and key not in internal_fields:
                if value and str(value).strip():
                    metadata.custom[key] = value

        return metadata

    def _parse_pdf_date(self, date_str: str) -> str:
        """Parse PDF date format into a readable string.

        Converts PDF date strings from the internal format 'D:YYYYMMDDHHmmSS'
        into datetime objects for standardized date handling.

        Parameters
        ----------
        date_str : str
            PDF date string in format 'D:YYYYMMDDHHmmSS' with optional timezone

        Returns
        -------
        str
            Parsed datetime object or original string if parsing fails

        Notes
        -----
        Handles both UTC (Z suffix) and timezone offset formats.
        Returns original string if format is unrecognized.

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
                return datetime(year, month, day).isoformat()
        except (ValueError, IndexError):
            pass
        return date_str

    def convert_to_ast(self, doc: "fitz.Document", pages_to_use: range | list[int], base_filename: str) -> Document:
        """Convert PDF document to AST Document.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to convert
        pages_to_use : range or list of int
            Pages to process
        base_filename : str
            Base filename for attachments

        Returns
        -------
        Document
            AST document node

        """
        # Reset footnote collection for this conversion
        self._attachment_footnotes = {}

        total_pages = len(list(pages_to_use))
        children: list[Node] = []

        # Emit started event
        self._emit_progress(
            "started",
            f"Converting PDF with {total_pages} page{'s' if total_pages != 1 else ''}",
            current=0,
            total=total_pages
        )

        attachment_sequencer = create_attachment_sequencer()

        pages_list = list(pages_to_use)
        for idx, pno in enumerate(pages_list):
            try:
                page = doc[pno]
                page_nodes = self._process_page_to_ast(page, pno, base_filename, attachment_sequencer, total_pages)
                if page_nodes:
                    children.extend(page_nodes)

                # Add page separator between pages (but not after the last page)
                if idx < len(pages_list) - 1:
                    # Add special marker for page separator
                    # Format: <!-- PAGE_SEP:{page_num}/{total_pages} -->
                    sep_marker = f"<!-- PAGE_SEP:{pno + 1}/{total_pages} -->"
                    children.append(HTMLBlock(content=sep_marker))

                # Emit page done event
                self._emit_progress(
                    "page_done",
                    f"Page {pno + 1} of {total_pages} processed",
                    current=idx + 1,
                    total=total_pages,
                    page=pno + 1
                )
            except Exception as e:
                # Emit error event but continue processing
                self._emit_progress(
                    "error",
                    f"Error processing page {pno + 1}: {str(e)}",
                    current=idx + 1,
                    total=total_pages,
                    error=str(e),
                    page=pno + 1
                )
                # Re-raise to maintain existing error handling
                raise

        # Extract and attach metadata
        metadata = self.extract_metadata(doc)

        # Append footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children,
                self._attachment_footnotes,
                self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress(
            "finished",
            f"PDF conversion completed ({total_pages} page{'s' if total_pages != 1 else ''})",
            current=total_pages,
            total=total_pages
        )

        return Document(children=children, metadata=metadata.to_dict())

    def _process_page_to_ast(self,
                             page: "fitz.Page",
                             page_num: int,
                             base_filename: str,
                             attachment_sequencer: Callable[[str, str], tuple[str, int]],
                             total_pages: int = 0) -> list[Node]:
        """Process a PDF page to AST nodes.

        Parameters
        ----------
        page : fitz.Page
            PDF page to process
        page_num : int
            Page number (0-based)
        base_filename : str
            Base filename for attachments
        attachment_sequencer : Callable
            Sequencer for generating unique attachment names
        total_pages : int, default=0
            Total number of pages being processed

        Returns
        -------
        list of Node
            List of AST nodes representing the page

        """
        import fitz

        nodes: list[Node] = []

        # Extract images for all attachment modes except "skip"
        page_images = []
        if self.options.attachment_mode != "skip":
            page_images, page_footnotes = extract_page_images(
                page, page_num, self.options, base_filename, attachment_sequencer
            )
            # Merge footnotes from this page into the document-wide collection
            self._attachment_footnotes.update(page_footnotes)

        # 1. Locate all tables on page based on table_detection_mode
        tabs = None
        mode = self.options.table_detection_mode.lower()

        # Define EmptyTables class for cases where no tables are found
        class EmptyTables:
            tables: list[Any] = []

            def __getitem__(self, index: int) -> Any:
                return self.tables[index]

        fallback_table_rects = []
        fallback_table_lines = []

        if mode == "none":
            # No table detection
            tabs = EmptyTables()
        elif mode == "pymupdf":
            # Only use PyMuPDF table detection
            tabs = page.find_tables()
        elif mode == "ruling":
            # Only use ruling line detection (fallback method)
            fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                page, self.options.table_ruling_line_threshold
            )
            # Use EmptyTables for PyMuPDF tables, we'll process fallback tables separately
            tabs = EmptyTables()
        else:  # "both" or default
            # Use PyMuPDF first, fallback to ruling if needed
            tabs = page.find_tables()
            if self.options.enable_table_fallback_detection and not tabs.tables:
                fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                    page, self.options.table_ruling_line_threshold
                )

        # Emit table detected event if tables found
        total_table_count = len(tabs.tables) + len(fallback_table_rects)
        if total_table_count > 0:
            self._emit_progress(
                "table_detected",
                f"Found {total_table_count} table{'s' if total_table_count != 1 else ''} on page {page_num + 1}",
                current=page_num + 1,
                total=total_pages,
                table_count=total_table_count,
                page=page_num + 1
            )

        # 2. Make a list of table boundary boxes, sort by top-left corner
        # Combine PyMuPDF tables and fallback tables
        tab_rects = sorted(
            [(fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox), i, "pymupdf") for i, t in enumerate(tabs.tables)]
            + [(rect, i, "fallback") for i, rect in enumerate(fallback_table_rects)],
            key=lambda r: (r[0].y0, r[0].x0),
        )

        # 3. Final list of all text and table rectangles
        text_rects = []
        # Compute rectangles outside tables and fill final rect list
        for i, (r, idx, table_type) in enumerate(tab_rects):
            if i == 0:  # Compute rect above all tables
                tr = page.rect
                tr.y1 = r.y0
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0, ""))
                text_rects.append(("table", r, idx, table_type))
                continue
            # Read previous rectangle in final list: always a table
            _, r0, idx0, _ = text_rects[-1]

            # Check if a non-empty text rect is fitting in between tables
            tr = page.rect
            tr.y0 = r0.y1
            tr.y1 = r.y0
            if not tr.is_empty:  # Empty if two tables overlap vertically
                text_rects.append(("text", tr, 0, ""))

            text_rects.append(("table", r, idx, table_type))

            # There may also be text below all tables
            if i == len(tab_rects) - 1:
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0, ""))

        if not text_rects:  # This will happen for table-free pages
            text_rects.append(("text", page.rect, 0, ""))
        else:
            rtype, r, idx, _ = text_rects[-1]
            if rtype == "table":
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0, ""))

        # Add image placement markers if enabled
        if page_images and self.options.image_placement_markers:
            # Sort images by vertical position
            page_images.sort(key=lambda img: img["bbox"].y0)

            # Insert images at appropriate positions
            combined_rects: list[tuple[str, fitz.Rect, int | dict, str]] = []
            img_idx = 0

            for rtype, r, idx, table_type in text_rects:
                # Check if any images should be placed before this rect
                while img_idx < len(page_images) and page_images[img_idx]["bbox"].y1 <= r.y0:
                    img = page_images[img_idx]
                    combined_rects.append(("image", img["bbox"], img, ""))
                    img_idx += 1

                combined_rects.append((rtype, r, idx, table_type))

            # Add remaining images
            while img_idx < len(page_images):
                img = page_images[img_idx]
                combined_rects.append(("image", img["bbox"], img, ""))
                img_idx += 1

            text_rects = combined_rects  # type: ignore[assignment]

        # Process all rectangles and convert to AST nodes
        for rtype, r, idx, table_type in text_rects:
            if rtype == "text":  # A text rectangle
                text_nodes = self._process_text_region_to_ast(page, r, page_num)
                if text_nodes:
                    nodes.extend(text_nodes)
            elif rtype == "table":  # A table rect
                if table_type == "pymupdf":
                    # Process PyMuPDF table
                    table_node = self._process_table_to_ast(tabs[idx], page_num)
                    if table_node:
                        nodes.append(table_node)
                elif table_type == "fallback":
                    # Process fallback table using ruling lines
                    h_lines, v_lines = fallback_table_lines[idx]
                    table_node = self._extract_table_from_ruling_rect(
                        page, fallback_table_rects[idx], h_lines, v_lines, page_num
                    )
                    if table_node:
                        nodes.append(table_node)
            elif rtype == "image":  # An image
                # idx contains image info dict in this case
                if isinstance(idx, dict):  # type: ignore[unreachable]  # Type guard
                    img_node = self._create_image_node(idx, page_num)  # type: ignore[unreachable]
                    if img_node:
                        nodes.append(img_node)

        return nodes

    def _process_text_region_to_ast(
        self, page: "fitz.Page", clip: "fitz.Rect", page_num: int
    ) -> list[Node]:
        """Process a text region to AST nodes.

        Parameters
        ----------
        page : fitz.Page
            PDF page
        clip : fitz.Rect
            Clipping rectangle for text extraction
        page_num : int
            Page number for source tracking

        Returns
        -------
        list of Node
            List of AST nodes (paragraphs, headings, code blocks)

        """
        import fitz

        nodes: list[Node] = []

        # Extract URL type links on page
        try:
            links = [line for line in page.get_links() if line["kind"] == 2]
        except (AttributeError, Exception):
            links = []

        # Extract text blocks
        try:
            # Build flags: always include TEXTFLAGS_TEXT, conditionally add TEXT_DEHYPHENATE
            text_flags = fitz.TEXTFLAGS_TEXT
            if self.options.merge_hyphenated_words:
                text_flags |= fitz.TEXT_DEHYPHENATE

            blocks = page.get_text(
                "dict",
                clip=clip,
                flags=text_flags,
                sort=False,
            )["blocks"]
        except (AttributeError, KeyError, Exception):
            # If extraction fails (e.g., in tests), return empty
            return []

        # Filter out headers/footers if trim_headers_footers is enabled
        if self.options.trim_headers_footers:
            blocks = self._filter_headers_footers(blocks, page)

        # Apply column detection if enabled
        if self.options.detect_columns:
            # Check column_detection_mode option
            if self.options.column_detection_mode == "disabled":
                # Force single column (no detection)
                blocks_to_process = blocks
            elif self.options.column_detection_mode == "force_single":
                # Force single column layout
                blocks_to_process = blocks
            elif self.options.column_detection_mode == "force_multi":
                # Force multi-column detection
                columns: list[list[dict]] = detect_columns(
                    blocks,
                    self.options.column_gap_threshold,
                    use_clustering=self.options.use_column_clustering
                )
                # Process blocks column by column for proper reading order
                blocks_to_process = []
                for column in columns:
                    # Sort blocks within column by y-coordinate (top to bottom)
                    column_sorted = sorted(column, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
                    blocks_to_process.extend(column_sorted)
            else:  # "auto" mode (default)
                columns = detect_columns(
                    blocks,
                    self.options.column_gap_threshold,
                    use_clustering=self.options.use_column_clustering
                )
                # Process blocks column by column for proper reading order
                blocks_to_process = []
                for column in columns:
                    # Sort blocks within column by y-coordinate (top to bottom)
                    column_sorted = sorted(column, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
                    blocks_to_process.extend(column_sorted)
        else:
            blocks_to_process = blocks

        # Track if we're in a code block
        in_code_block = False
        code_block_lines: list[str] = []

        for block in blocks_to_process:  # Iterate textblocks
            previous_y = 0

            for line in block["lines"]:  # Iterate lines in block
                # Handle rotated text if enabled, otherwise skip non-horizontal lines
                if line["dir"][1] != 0:  # Non-horizontal lines
                    if self.options.handle_rotated_text:
                        rotated_text = handle_rotated_text(line, None)
                        if rotated_text.strip():
                            # Add as paragraph
                            nodes.append(AstParagraph(content=[Text(content=rotated_text)]))
                    continue

                spans = list(line["spans"])
                if not spans:
                    continue

                this_y = line["bbox"][3]  # Current bottom coord

                # Check for still being on same line
                same_line = abs(this_y - previous_y) <= DEFAULT_OVERLAP_THRESHOLD_PX and previous_y > 0

                # Are all spans in line in a mono-spaced font?
                all_mono = all(s["flags"] & 8 for s in spans)

                # Compute text of the line
                text = "".join([s["text"] for s in spans])

                if not same_line:
                    previous_y = this_y

                # Handle monospace text (code blocks)
                if all_mono:
                    if not in_code_block:
                        in_code_block = True
                    # Add line to code block
                    # Compute approximate indentation
                    delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (spans[0]["size"] * 0.5))
                    code_block_lines.append(" " * delta + text)
                    continue

                # If we were in a code block and now we're not, finalize it
                if in_code_block:
                    code_content = "\n".join(code_block_lines)
                    nodes.append(
                        CodeBlock(
                            content=code_content,
                            source_location=SourceLocation(format="pdf", page=page_num + 1)
                        )
                    )
                    in_code_block = False
                    code_block_lines = []

                # Process non-monospace text
                # Check if first span is a header
                first_span = spans[0]
                header_level = 0
                if self._hdr_identifier:
                    header_level = self._hdr_identifier.get_header_level(first_span)

                if header_level > 0:
                    # This is a heading
                    inline_content = self._process_text_spans_to_inline(spans, links, page_num)
                    if inline_content:
                        nodes.append(
                            Heading(
                                level=header_level,
                                content=inline_content,
                                source_location=SourceLocation(format="pdf", page=page_num + 1)
                            )
                        )
                else:
                    # Regular paragraph
                    inline_content = self._process_text_spans_to_inline(spans, links, page_num)
                    if inline_content:
                        nodes.append(
                            AstParagraph(
                                content=inline_content,
                                source_location=SourceLocation(format="pdf", page=page_num + 1)
                            )
                        )

        # Finalize any remaining code block
        if in_code_block and code_block_lines:
            code_content = "\n".join(code_block_lines)
            nodes.append(
                CodeBlock(
                    content=code_content,
                    source_location=SourceLocation(format="pdf", page=page_num + 1)
                )
            )

        return nodes

    def _process_text_spans_to_inline(
        self, spans: list[dict], links: list[dict], page_num: int
    ) -> list[Node]:
        """Process text spans to inline AST nodes.

        Parameters
        ----------
        spans : list of dict
            Text spans from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking

        Returns
        -------
        list of Node
            List of inline AST nodes

        """
        result: list[Node] = []

        for span in spans:
            span_text = span["text"].strip()
            if not span_text:
                continue

            # Check for list bullets before treating as monospace
            is_list_bullet = span_text in ['-', 'o', '•', '◦', '▪'] and len(span_text) == 1

            # Decode font properties
            mono = span["flags"] & 8
            bold = span["flags"] & 16
            italic = span["flags"] & 2

            # Check for links
            link_url = self._resolve_link_for_span(links, span)

            # Build the inline node
            if mono and not is_list_bullet:
                # Inline code
                inline_node: Node = Code(content=span_text)
            else:
                # Regular text with optional formatting
                # Replace special characters
                span_text = (
                    span_text.replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace(chr(0xF0B7), "-")
                    .replace(chr(0xB7), "-")
                    .replace(chr(8226), "-")
                    .replace(chr(9679), "-")
                )

                inline_node = Text(content=span_text)

                # Apply formatting layers
                if bold:
                    inline_node = Strong(content=[inline_node])
                if italic:
                    inline_node = Emphasis(content=[inline_node])

            # Wrap in link if URL present
            if link_url:
                inline_node = Link(url=link_url, content=[inline_node])

            result.append(inline_node)

        return result

    def _resolve_link_for_span(self, links: list[dict], span: dict) -> str | None:
        """Resolve link URL for a text span.

        Parameters
        ----------
        links : list of dict
            Links on the page
        span : dict
            Text span

        Returns
        -------
        str or None
            Link URL if span is part of a link

        Notes
        -----
        Uses the link_overlap_threshold option from self.options to determine
        the minimum overlap required for link detection.

        """
        if not links or not span.get("text"):
            return None

        import fitz
        bbox = fitz.Rect(span["bbox"])

        # Use threshold from options
        threshold_percent = self.options.link_overlap_threshold

        # Find all links that overlap with this span
        for link in links:
            hot = link["from"]  # The hot area of the link
            overlap = hot & bbox
            bbox_area = (threshold_percent / 100.0) * abs(bbox)
            if abs(overlap) >= bbox_area:
                return link.get("uri")

        return None

    def _process_table_to_ast(self, table: Any, page_num: int) -> AstTable | None:
        """Process a PyMuPDF table to AST Table node.

        Directly accesses table cell data from PyMuPDF table object instead of
        converting to markdown and re-parsing, which is more efficient and robust.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if table has content

        """
        try:
            # Try to extract cells directly from PyMuPDF table object
            # PyMuPDF tables have a `extract()` method that returns cell data
            table_data = table.extract()

            if not table_data or len(table_data) == 0:
                logger.debug("Table has no data")
                return None

            # Separate header row (first row) from data rows
            header_row_data = table_data[0] if table_data else []
            data_rows_data = table_data[1:] if len(table_data) > 1 else []

            # Build AST header row
            header_cells = []
            for cell_text in header_row_data:
                # Cell text could be None, convert to empty string
                cell_content = str(cell_text).strip() if cell_text is not None else ""
                header_cells.append(TableCell(content=[Text(content=cell_content)]))

            header_row = TableRow(cells=header_cells, is_header=True)

            # Build AST data rows
            data_rows = []
            for row_data in data_rows_data:
                row_cells = []
                for cell_text in row_data:
                    # Cell text could be None, convert to empty string
                    cell_content = str(cell_text).strip() if cell_text is not None else ""
                    row_cells.append(TableCell(content=[Text(content=cell_content)]))

                data_rows.append(TableRow(cells=row_cells))

            return AstTable(
                header=header_row,
                rows=data_rows,
                source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except (AttributeError, Exception) as e:
            # Fallback to markdown conversion if direct extraction fails
            logger.debug(f"Direct table extraction failed ({e}), falling back to markdown parsing")
            return self._process_table_to_ast_fallback(table, page_num)

    def _process_table_to_ast_fallback(self, table: Any, page_num: int) -> AstTable | None:
        """Fallback method using markdown conversion when direct extraction fails.

        Parameters
        ----------
        table : PyMuPDF Table
            Table object from find_tables()
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if table has content

        """
        try:
            # Get table as markdown
            table_md = table.to_markdown(clean=False)
            if not table_md:
                return None

            # Parse the markdown table to extract structure
            lines = table_md.strip().split('\n')
            if len(lines) < 2:  # Need at least header and separator
                return None

            # Parse header row (first line)
            header_line = lines[0]
            header_cells_text = self._parse_markdown_table_row(header_line)

            # Skip separator line (second line)
            # Parse data rows (remaining lines)
            data_rows_text = []
            for line in lines[2:]:
                if line.strip():
                    row_cells = self._parse_markdown_table_row(line)
                    if row_cells:
                        data_rows_text.append(row_cells)

            # Build AST table
            header_cells = [TableCell(content=[Text(content=cell)]) for cell in header_cells_text]
            header_row = TableRow(cells=header_cells, is_header=True)

            data_rows = []
            for row_cells in data_rows_text:
                cells = [TableCell(content=[Text(content=cell)]) for cell in row_cells]
                data_rows.append(TableRow(cells=cells))

            return AstTable(
                header=header_row,
                rows=data_rows,
                source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except Exception as e:
            logger.debug(f"Fallback table processing failed: {e}")
            return None

    def _extract_table_from_ruling_rect(
        self, page: "fitz.Page", table_rect: "fitz.Rect", h_lines: list[tuple], v_lines: list[tuple], page_num: int
    ) -> AstTable | None:
        """Extract table content from a bounding box using ruling lines.

        Implements basic grid-based cell segmentation using detected horizontal
        and vertical lines to extract text from each cell.

        Parameters
        ----------
        page : fitz.Page
            PDF page containing the table
        table_rect : fitz.Rect
            Bounding box of the table
        h_lines : list of tuple
            Horizontal ruling lines as (x0, y0, x1, y1) tuples
        v_lines : list of tuple
            Vertical ruling lines as (x0, y0, x1, y1) tuples
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstTable or None
            Table node if extraction successful

        Notes
        -----
        This method uses grid-based cell segmentation. It may not work well
        for tables without clear ruling lines or with merged cells.

        """
        if self.options.table_fallback_extraction_mode == "none":
            return None

        # Sort lines for grid creation
        h_lines_sorted = sorted(h_lines, key=lambda line: line[1])  # Sort by y-coordinate
        v_lines_sorted = sorted(v_lines, key=lambda line: line[0])  # Sort by x-coordinate

        if len(h_lines_sorted) < 2 or len(v_lines_sorted) < 2:
            # Need at least 2 horizontal and 2 vertical lines to form cells
            return None

        # Create grid cells from line intersections
        rows: list[TableRow] = []

        # Extract y-coordinates for rows (between consecutive h_lines)
        row_y_coords = [(h_lines_sorted[i][1], h_lines_sorted[i + 1][1])
                       for i in range(len(h_lines_sorted) - 1)]

        # Extract x-coordinates for columns (between consecutive v_lines)
        col_x_coords = [(v_lines_sorted[i][0], v_lines_sorted[i + 1][0])
                       for i in range(len(v_lines_sorted) - 1)]

        import fitz

        for row_idx, (y0, y1) in enumerate(row_y_coords):
            cells: list[TableCell] = []

            for col_idx, (x0, x1) in enumerate(col_x_coords):
                # Create cell rectangle
                cell_rect = fitz.Rect(x0, y0, x1, y1)

                # Extract text from cell
                cell_text = page.get_textbox(cell_rect)
                if cell_text:
                    cell_text = cell_text.strip()
                else:
                    cell_text = ""

                cells.append(TableCell(content=[Text(content=cell_text)]))

            # First row is typically the header
            is_header = (row_idx == 0)
            rows.append(TableRow(cells=cells, is_header=is_header))

        if not rows:
            return None

        # Separate header and data rows
        header_row = rows[0] if rows else TableRow(cells=[])
        data_rows = rows[1:] if len(rows) > 1 else []

        return AstTable(
            header=header_row,
            rows=data_rows,
            source_location=SourceLocation(format="pdf", page=page_num + 1)
        )

    def _parse_markdown_table_row(self, row_line: str) -> list[str]:
        """Parse a markdown table row into cell contents.

        Parameters
        ----------
        row_line : str
            Markdown table row (e.g., "| cell1 | cell2 |")

        Returns
        -------
        list of str
            Cell contents

        """
        # Remove leading/trailing pipes and split
        row_line = row_line.strip()
        if row_line.startswith('|'):
            row_line = row_line[1:]
        if row_line.endswith('|'):
            row_line = row_line[:-1]

        cells = [cell.strip() for cell in row_line.split('|')]
        return cells

    def _create_image_node(self, img_info: dict, page_num: int) -> AstParagraph | None:
        """Create an image node from image info.

        Parameters
        ----------
        img_info : dict
            Image information dict with 'path' and 'caption' keys
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstParagraph or None
            Paragraph containing the image node

        """
        try:
            # Create Image node
            img_node = Image(
                url=img_info["path"],
                alt_text=img_info.get("caption") or "Image",
                source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

            # Wrap in paragraph
            return AstParagraph(
                content=[img_node],
                source_location=SourceLocation(format="pdf", page=page_num + 1)
            )

        except Exception as e:
            logger.debug(f"Failed to create image node: {e}")
            return None

    def _filter_headers_footers(self, blocks: list[dict], page: "fitz.Page") -> list[dict]:
        """Filter out text blocks in header/footer zones.

        Parameters
        ----------
        blocks : list of dict
            Text blocks from PyMuPDF
        page : fitz.Page
            PDF page

        Returns
        -------
        list of dict
            Filtered blocks excluding headers and footers

        """
        if not self.options.trim_headers_footers:
            return blocks

        page_height = page.rect.height
        header_zone = self.options.header_height
        footer_zone = self.options.footer_height

        filtered_blocks = []
        for block in blocks:
            bbox = block.get("bbox")
            if not bbox:
                filtered_blocks.append(block)
                continue

            # Check if block is in header zone (top of page)
            if header_zone > 0 and bbox[1] < header_zone:
                continue  # Skip this block

            # Check if block is in footer zone (bottom of page)
            if footer_zone > 0 and bbox[3] > (page_height - footer_zone):
                continue  # Skip this block

            filtered_blocks.append(block)

        return filtered_blocks


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf"],
    magic_bytes=[
        (b"%PDF", 0),
    ],
    parser_class=PdfToAstConverter,
    renderer_class="all2md.renderers.pdf.PdfRenderer",
    renders_as_string=False,
    parser_required_packages=[("pymupdf", "fitz", ">=1.26.4")],
    renderer_required_packages=[("reportlab", "reportlab", ">=4.0.0")],
    optional_packages=[],
    import_error_message=(
        "PDF conversion requires 'PyMuPDF'. "
        "Install with: pip install pymupdf"
    ),
    parser_options_class=PdfOptions,
    renderer_options_class="PdfRendererOptions",
    description="Convert PDF documents to/from AST with table detection",
    priority=10
)

