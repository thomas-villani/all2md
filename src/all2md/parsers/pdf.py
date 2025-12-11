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
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Callable, Optional, Union

from all2md.options.common import OCROptions
from all2md.options.markdown import MarkdownRendererOptions
from all2md.options.pdf import PdfOptions
from all2md.utils.attachments import create_attachment_sequencer, generate_attachment_filename, process_attachment
from all2md.utils.parser_helpers import attachment_result_to_image_node

if TYPE_CHECKING:
    import fitz

from all2md.ast import (
    Code,
    CodeBlock,
    Comment,
    Document,
    Emphasis,
    Heading,
    Link,
    List,
    ListItem,
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
from all2md.ast.transforms import InlineFormattingConsolidator
from all2md.constants import (
    DEFAULT_OVERLAP_THRESHOLD_PERCENT,
    DEFAULT_OVERLAP_THRESHOLD_PX,
    DEPS_PDF,
    DEPS_PDF_LANGDETECT,
    DEPS_PDF_OCR,
    PDF_COLUMN_FREQ_THRESHOLD_RATIO,
    PDF_COLUMN_GAP_QUANTIZATION,
    PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK,
    PDF_COLUMN_MIN_FREQ_COUNT,
    PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO,
    PDF_COLUMN_X_TOLERANCE,
    PDF_MIN_PYMUPDF_VERSION,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import DependencyError, MalformedFileError, PasswordProtectedError, ValidationError
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import normalize_stream_to_bytes
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
    """Cluster 1D values using k-means algorithm.

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
    step = max(1, len(sorted_values) // k)  # Ensure step is at least 1

    # Generate initial indices with bounds checking
    initial_indices = []
    for i in range(k):
        idx = min(i * step, len(sorted_values) - 1)  # Clamp to valid range
        initial_indices.append(idx)

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


def _detect_columns_by_clustering(
    blocks: list, block_centers: list[float], x_coords: list[float], column_gap_threshold: float
) -> list[list[dict]] | None:
    """Detect columns using k-means clustering.

    Parameters
    ----------
    blocks : list
        Text blocks
    block_centers : list of float
        Center x-coordinates of blocks
    x_coords : list of float
        Starting x-coordinates
    column_gap_threshold : float
        Minimum gap threshold

    Returns
    -------
    list of list of dict or None
        Detected columns or None if single column

    """
    # Estimate number of columns from gap analysis
    sorted_x = sorted(set(x_coords))
    num_columns = 1
    for i in range(1, len(sorted_x)):
        gap = sorted_x[i] - sorted_x[i - 1]
        if gap >= column_gap_threshold:
            num_columns += 1

    num_columns = max(1, min(num_columns, 4))

    if num_columns <= 1:
        return None

    # Apply k-means clustering
    cluster_assignments = _simple_kmeans_1d(block_centers, num_columns)

    # Group blocks by cluster
    columns_dict: dict[int, list[dict]] = {i: [] for i in range(num_columns)}
    for block, cluster_id in zip(blocks, cluster_assignments, strict=False):
        if "bbox" in block:
            columns_dict[cluster_id].append(block)
        else:
            columns_dict[0].append(block)

    # Sort clusters by mean x-coordinate
    cluster_centers = {}
    for cluster_id, cluster_blocks in columns_dict.items():
        if cluster_blocks:
            centers = [(b["bbox"][0] + b["bbox"][2]) / 2 for b in cluster_blocks if "bbox" in b]
            cluster_centers[cluster_id] = sum(centers) / len(centers) if centers else 0
        else:
            cluster_centers[cluster_id] = 0

    sorted_clusters = sorted(cluster_centers.items(), key=lambda x: x[1])
    columns = [columns_dict[cluster_id] for cluster_id, _ in sorted_clusters if columns_dict[cluster_id]]

    # Sort blocks within each column by y-coordinate
    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    return columns


def _detect_columns_by_whitespace(
    blocks: list,
    block_ranges: list[tuple[float, float]],
    column_gap_threshold: float,
    page_width: float,
    spanning_threshold: float,
    force_multi_column: bool,
) -> list[list[dict]] | None:
    """Detect columns using whitespace gap analysis.

    Parameters
    ----------
    blocks : list
        Text blocks
    block_ranges : list of tuple
        (x0, x1) ranges for each block
    column_gap_threshold : float
        Minimum gap threshold
    page_width : float
        Page width
    spanning_threshold : float
        Threshold for spanning blocks
    force_multi_column : bool
        Force multi-column detection

    Returns
    -------
    list of list of dict or None
        Detected columns or None if single column

    """
    x_tolerance = PDF_COLUMN_X_TOLERANCE
    x0_groups = defaultdict(list)

    # Group blocks by x0 position
    for i, (x0, x1) in enumerate(block_ranges):
        width = x1 - x0
        if not force_multi_column and width > spanning_threshold * page_width:
            continue
        x0_key = round(x0 / x_tolerance) * x_tolerance
        x0_groups[x0_key].append((x0, x1, i))

    if not x0_groups:
        return None

    # Find group ranges
    group_ranges = []
    for x0_key in sorted(x0_groups.keys()):
        group = x0_groups[x0_key]
        min_x0 = min(x0 for x0, x1, i in group)
        max_x1 = max(x1 for x0, x1, i in group)
        group_ranges.append((min_x0, max_x1))

    # Find whitespace gaps
    whitespace_gaps = []
    for i in range(len(group_ranges) - 1):
        gap_width = group_ranges[i + 1][0] - group_ranges[i][1]
        if gap_width >= column_gap_threshold:
            whitespace_gaps.append({"start": group_ranges[i][1], "end": group_ranges[i + 1][0], "width": gap_width})

    if not whitespace_gaps:
        return None

    # Find consistent gaps
    gap_frequency: dict[float, int] = {}
    for gap in whitespace_gaps:
        gap_pos = round((gap["start"] + gap["end"]) / 2 / PDF_COLUMN_GAP_QUANTIZATION) * PDF_COLUMN_GAP_QUANTIZATION
        gap_frequency[gap_pos] = gap_frequency.get(gap_pos, 0) + 1

    if not gap_frequency:
        return None

    max_freq = max(gap_frequency.values())
    threshold_freq = max(PDF_COLUMN_MIN_FREQ_COUNT, max_freq * PDF_COLUMN_FREQ_THRESHOLD_RATIO)
    column_boundaries = sorted([pos for pos, freq in gap_frequency.items() if freq >= threshold_freq])

    if not column_boundaries:
        return None

    # Split blocks into columns
    whitespace_columns: list[list[dict]] = [[] for _ in range(len(column_boundaries) + 1)]

    for block in blocks:
        if "bbox" not in block:
            whitespace_columns[0].append(block)
            continue

        block_center = (block["bbox"][0] + block["bbox"][2]) / 2
        assigned = False
        for i, boundary in enumerate(column_boundaries):
            if block_center < boundary:
                whitespace_columns[i].append(block)
                assigned = True
                break

        if not assigned:
            whitespace_columns[-1].append(block)

    # Sort and clean up
    for column in whitespace_columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    whitespace_columns = [col for col in whitespace_columns if col]

    return whitespace_columns if len(whitespace_columns) > 1 else None


def _detect_columns_by_gaps(
    blocks: list,
    block_ranges: list[tuple[float, float]],
    x_coords: list[float],
    column_gap_threshold: float,
    force_multi_column: bool,
) -> list[list[dict]]:
    """Detect columns using simple gap detection (fallback method).

    Parameters
    ----------
    blocks : list
        Text blocks
    block_ranges : list of tuple
        (x0, x1) ranges for each block
    x_coords : list of float
        Starting x-coordinates
    column_gap_threshold : float
        Minimum gap threshold
    force_multi_column : bool
        Force multi-column detection

    Returns
    -------
    list of list of dict
        Detected columns (always returns at least single column)

    """
    # Sort block ranges by starting position to find actual whitespace gaps
    sorted_ranges = sorted(block_ranges, key=lambda r: r[0])

    # Find column boundaries based on actual whitespace gaps (end of one block to start of next)
    column_boundaries = [sorted_ranges[0][0]]

    for i in range(1, len(sorted_ranges)):
        prev_x1 = sorted_ranges[i - 1][1]
        curr_x0 = sorted_ranges[i][0]
        gap = curr_x0 - prev_x1

        if gap >= column_gap_threshold:
            column_boundaries.append(curr_x0)

    if len(column_boundaries) <= 1:
        return [blocks]

    # Check for single column heuristic
    if not force_multi_column and len(block_ranges) >= PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK:
        widths = [x1 - x0 for x0, x1 in block_ranges]
        median_width = sorted(widths)[len(widths) // 2]
        min_x = min(x0 for x0, x1 in block_ranges)
        max_x = max(x1 for x0, x1 in block_ranges)
        page_width = max_x - min_x

        if median_width > PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO * page_width:
            return [blocks]

    # Group blocks into columns
    columns: list[list[dict]] = [[] for _ in range(len(column_boundaries))]

    for block in blocks:
        if "bbox" not in block:
            columns[0].append(block)
            continue

        x0 = block["bbox"][0]
        assigned = False
        for i in range(len(column_boundaries) - 1):
            if column_boundaries[i] <= x0 < column_boundaries[i + 1]:
                columns[i].append(block)
                assigned = True
                break

        if not assigned:
            columns[-1].append(block)

    # Sort and clean up
    for column in columns:
        column.sort(key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])

    return [col for col in columns if col]


def detect_columns(
    blocks: list, column_gap_threshold: float = 20, use_clustering: bool = False, force_multi_column: bool = False
) -> list[list[dict]]:
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
    force_multi_column : bool, default False
        Force multi-column detection by bypassing spanning block heuristics.
        When True, skips the check that treats wide blocks as single-column indicators.
        Useful when you know the document has multi-column layout despite wide headers/footers.

    Returns
    -------
    list[list[dict]]
        List of columns, where each column is a list of blocks

    Notes
    -----
    When use_clustering=True, the function uses k-means clustering to identify
    column groupings based on block center positions. This can be more robust
    for complex layouts but requires estimating the number of columns first.

    When force_multi_column=True, the function bypasses heuristics that would
    normally detect single-column layouts (e.g., blocks spanning most of the page width).
    This is useful when you have headers/footers spanning the full width but want to
    detect multi-column content in the body.

    """
    if not blocks:
        return [blocks]

    # Extract block coordinates
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

    # Calculate page dimensions
    min_x = min(x0 for x0, x1 in block_ranges)
    max_x = max(x1 for x0, x1 in block_ranges)
    page_width = max_x - min_x
    spanning_threshold = 0.65

    # Try clustering-based detection if requested
    if use_clustering and block_centers:
        columns = _detect_columns_by_clustering(blocks, block_centers, x_coords, column_gap_threshold)
        if columns:
            return columns

    # Try whitespace-based detection
    columns = _detect_columns_by_whitespace(
        blocks, block_ranges, column_gap_threshold, page_width, spanning_threshold, force_multi_column
    )
    if columns:
        return columns

    # Fallback to simple gap detection
    return _detect_columns_by_gaps(blocks, block_ranges, x_coords, column_gap_threshold, force_multi_column)


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


def detect_tables_by_ruling_lines(
    page: "fitz.Page", threshold: float = 0.5
) -> tuple[list["fitz.Rect"], list[tuple[list[tuple], list[tuple]]]]:
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
        table_h_lines = [line for line in h_lines if line[1] >= table_rect.y0 and line[1] <= table_rect.y1]
        table_v_lines = [line for line in v_lines if line[0] >= table_rect.x0 and line[0] <= table_rect.x1]
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
                if not SPACES.issuperset(s["text"]) and line.get("dir") == (1, 0)
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
            if len(text) > 50 and text.endswith((".", "!", "?")):
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


def _calculate_image_coverage(page: "fitz.Page") -> float:
    """Calculate the ratio of image area to total page area.

    This function analyzes a PDF page to determine what fraction of the page
    is covered by images, which helps identify image-based or scanned pages.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze

    Returns
    -------
    float
        Ratio of image area to page area (0.0 to 1.0)

    Notes
    -----
    This function accounts for overlapping images by combining their bounding
    boxes and calculating the total covered area.

    """
    page_area = page.rect.width * page.rect.height
    if page_area == 0:
        return 0.0

    # Get all images on the page
    image_list = page.get_images()
    if not image_list:
        return 0.0

    # Calculate total image area (accounting for potential overlaps)
    # We'll use a simple approach: sum individual image areas
    # For more accuracy, we could use union of bounding boxes
    total_image_area = 0.0

    for img in image_list:
        xref = img[0]
        img_rects = page.get_image_rects(xref)
        if img_rects:
            # Use first occurrence of image on page
            bbox = img_rects[0]
            img_area = (bbox.width) * (bbox.height)
            total_image_area += img_area

    # Calculate ratio
    coverage_ratio = min(1.0, total_image_area / page_area)
    return coverage_ratio


def _should_use_ocr(page: "fitz.Page", extracted_text: str, options: PdfOptions) -> bool:
    """Determine whether OCR should be applied to a PDF page.

    Analyzes the page content based on the OCR mode and detection thresholds
    to decide if OCR processing is needed.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze
    extracted_text : str
        Text extracted by PyMuPDF from the page
    options : PdfOptions
        PDF conversion options containing OCR settings

    Returns
    -------
    bool
        True if OCR should be applied, False otherwise

    Notes
    -----
    Detection logic depends on ocr.mode:
    - "off": Always returns False
    - "force": Always returns True
    - "auto": Uses text_threshold and image_area_threshold to detect scanned pages

    """
    ocr_opts: OCROptions = options.ocr

    # Check if OCR is enabled
    if not ocr_opts.enabled or ocr_opts.mode == "off":
        return False

    # Force mode always uses OCR
    if ocr_opts.mode == "force":
        return True

    # Auto mode: detect based on thresholds
    if ocr_opts.mode == "auto":
        # Check text threshold
        text_length = len(extracted_text.strip())
        if text_length < ocr_opts.text_threshold:
            logger.debug(f"Page has {text_length} chars (threshold: {ocr_opts.text_threshold}), triggering OCR")
            return True

        # Check image coverage threshold
        image_coverage = _calculate_image_coverage(page)
        if image_coverage >= ocr_opts.image_area_threshold:
            logger.debug(
                f"Page has {image_coverage:.1%} image coverage "
                f"(threshold: {ocr_opts.image_area_threshold:.1%}), triggering OCR"
            )
            return True

    return False


def _get_tesseract_lang(detected_lang_code: str) -> str:
    """Map ISO 639-1 language codes (and some variants) to Tesseract language codes.

    Parameters
    ----------
    detected_lang_code : str
        ISO 639-1 language code (e.g., "en", "fr", "zh-cn")

    Returns
    -------
    str
        Tesseract language code (e.g., "eng", "fra", "chi_sim")

    """
    lang_map = {
        # English and variants
        "en": "eng",
        # European languages
        "fr": "fra",  # French
        "es": "spa",  # Spanish
        "de": "deu",  # German
        "it": "ita",  # Italian
        "pt": "por",  # Portuguese
        "ru": "rus",  # Russian
        "nl": "nld",  # Dutch
        "sv": "swe",  # Swedish
        "no": "nor",  # Norwegian
        "da": "dan",  # Danish
        "fi": "fin",  # Finnish
        "pl": "pol",  # Polish
        "cs": "ces",  # Czech
        "sk": "slk",  # Slovak
        "hu": "hun",  # Hungarian
        "ro": "ron",  # Romanian
        "bg": "bul",  # Bulgarian
        "el": "ell",  # Greek
        "tr": "tur",  # Turkish
        "uk": "ukr",  # Ukrainian
        "hr": "hrv",  # Croatian
        "sr": "srp",  # Serbian
        "sl": "slv",  # Slovenian
        "lv": "lav",  # Latvian
        "lt": "lit",  # Lithuanian
        "et": "est",  # Estonian
        # Asian languages
        "zh-cn": "chi_sim",  # Chinese Simplified
        "zh-tw": "chi_tra",  # Chinese Traditional
        "zh": "chi_sim",  # Default to Simplified
        "ja": "jpn",  # Japanese
        "ko": "kor",  # Korean
        "hi": "hin",  # Hindi
        "th": "tha",  # Thai
        "vi": "vie",  # Vietnamese
        "my": "mya",  # Burmese
        "km": "khm",  # Khmer
        "bn": "ben",  # Bengali
        # Middle Eastern languages
        "ar": "ara",  # Arabic
        "fa": "fas",  # Persian (Farsi)
        "he": "heb",  # Hebrew
        "ur": "urd",  # Urdu
        # Others
        "id": "ind",  # Indonesian
        "ms": "msa",  # Malay
        "ta": "tam",  # Tamil
        "te": "tel",  # Telugu
        "kn": "kan",  # Kannada
        "ml": "mal",  # Malayalam
        "gu": "guj",  # Gujarati
        "mr": "mar",  # Marathi
        "pa": "pan",  # Punjabi
        "si": "sin",  # Sinhala
    }

    # Normalize input to lowercase
    code = detected_lang_code.lower()

    # Handle cases like 'zh-cn', 'zh-tw'
    if code in lang_map:
        return lang_map[code]

    # Sometimes language codes come with region subtags, e.g. 'en-US', 'pt-BR'
    if "-" in code:
        base_code = code.split("-")[0]
        if base_code in lang_map:
            return lang_map[base_code]

    # Fallback to English if unknown
    return "eng"


@requires_dependencies("pdf", DEPS_PDF_LANGDETECT)
def _detect_page_language(page: "fitz.Page", options: PdfOptions) -> str:
    """Attempt to auto-detect the language of a PDF page for OCR.

    This is an experimental feature that tries to determine the language
    of the page content to optimize OCR accuracy.

    Parameters
    ----------
    page : fitz.Page
        PDF page to analyze
    options : PdfOptions
        PDF conversion options containing OCR settings

    Returns
    -------
    str
        Tesseract language code (e.g., "eng", "fra", "deu")
        Falls back to options.ocr.languages if detection fails

    """
    from langdetect import detect
    from langdetect.detector import Detector

    page_text_sample = page.get_text()[:10000]  # Limit to 10KB
    detected_lang_code = detect(page_text_sample)

    if detected_lang_code == Detector.UNKNOWN_LANG:
        # Return the configured languages (handle both string and list formats)
        if isinstance(options.ocr.languages, list):
            return "+".join(options.ocr.languages)
        return options.ocr.languages

    return _get_tesseract_lang(detected_lang_code)


class PdfToAstConverter(BaseParser):
    """Convert PDF to AST representation.

    This converter parses PDF documents using PyMuPDF and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PdfOptions or None, default = None
        Conversion options

    """

    def __init__(self, options: PdfOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the PDF parser with options and progress callback."""
        BaseParser._validate_options_type(options, PdfOptions, "pdf")
        options = options or PdfOptions()
        super().__init__(options, progress_callback)
        self.options: PdfOptions = options
        self._hdr_identifier: Optional[IdentifyHeaders] = None
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    @requires_dependencies("pdf", DEPS_PDF)
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
                # PyMuPDF expects bytes, not file-like objects
                stream_bytes = normalize_stream_to_bytes(doc_input)
                doc = fitz.open(stream=stream_bytes, filetype="pdf")
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
                original_error=e,
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
                            "Failed to authenticate PDF with provided password. Please check the password is correct."
                        ),
                        filename=filename,
                    )
                # auth_result > 0 indicates successful authentication
                # (1=no passwords, 2=user password, 4=owner password, 6=both equal)
            else:
                # Document is encrypted but no password provided
                raise PasswordProtectedError(
                    message=(
                        "PDF document is password-protected. Please provide a password using the 'password' option."
                    ),
                    filename=filename,
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

        self._hdr_identifier = IdentifyHeaders(
            doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=self.options
        )

        # Auto-detect header/footer zones if requested
        if self.options.auto_trim_headers_footers:
            self._auto_detect_header_footer_zones(doc, pages_to_use)

        return self.convert_to_ast(doc, pages_to_use, base_filename)

    def _auto_detect_header_footer_zones(self, doc: "fitz.Document", pages_to_use: range | list[int]) -> None:
        """Automatically detect and set header/footer zones by analyzing repeating text patterns.

        This method analyzes text blocks across multiple pages to identify repeating
        headers and footers. It looks for text that appears in similar vertical positions
        across multiple pages and calculates appropriate header_height and footer_height
        values to exclude them from conversion.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to analyze
        pages_to_use : range or list[int]
            Pages to process (used to determine sample range)

        """
        import fitz

        # Sample pages for analysis (min 3, max 10, or all if fewer pages)
        total_pages = len(list(pages_to_use))
        if total_pages < 3:
            # Need at least 3 pages to detect patterns
            return

        # Sample evenly distributed pages
        sample_size = min(10, total_pages)
        if isinstance(pages_to_use, range):
            step = max(1, total_pages // sample_size)
            sample_pages = [pages_to_use.start + i * step for i in range(sample_size)]
        else:
            step = max(1, len(pages_to_use) // sample_size)
            sample_pages = [pages_to_use[i * step] for i in range(sample_size)]

        # Collect text blocks from each sampled page
        # Structure: {page_num: [(text, y_top, y_bottom), ...]}
        page_blocks: dict[int, list[tuple[str, float, float]]] = {}

        for page_num in sample_pages:
            page = doc[page_num]
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

            page_blocks[page_num] = []
            for block in blocks:
                if block.get("type") != 0:  # Only process text blocks
                    continue

                bbox = block.get("bbox")
                if not bbox:
                    continue

                # Extract text from block
                text_lines = []
                for line in block.get("lines", []):
                    line_text = " ".join(span["text"] for span in line.get("spans", []))
                    text_lines.append(line_text.strip())

                block_text = " ".join(text_lines).strip()
                if not block_text:
                    continue

                # Store text with vertical position
                y_top = bbox[1]
                y_bottom = bbox[3]
                page_blocks[page_num].append((block_text, y_top, y_bottom))

        # Find repeating patterns in header zone (top 20% of page)
        # and footer zone (bottom 20% of page)
        if not page_blocks:
            return

        # Get representative page height from first sampled page
        first_page = doc[sample_pages[0]]
        page_height = first_page.rect.height

        # Track potential headers (text appearing in top portion of multiple pages)
        # Structure: {text: [y_bottom_values]}
        header_candidates: dict[str, list[float]] = {}
        footer_candidates: dict[str, list[float]] = {}

        header_zone_threshold = page_height * 0.2  # Top 20%
        footer_zone_threshold = page_height * 0.8  # Bottom 20%

        for blocks in page_blocks.values():
            for text, y_top, y_bottom in blocks:
                # Check if in potential header zone
                if y_bottom < header_zone_threshold:
                    if text not in header_candidates:
                        header_candidates[text] = []
                    header_candidates[text].append(y_bottom)

                # Check if in potential footer zone
                if y_top > footer_zone_threshold:
                    if text not in footer_candidates:
                        footer_candidates[text] = []
                    footer_candidates[text].append(y_top)

        # Find repeating headers (text appearing on at least 50% of sampled pages)
        min_occurrences = max(2, sample_size // 2)
        max_header_y = 0.0
        max_footer_y = page_height

        for _text, y_values in header_candidates.items():
            if len(y_values) >= min_occurrences:
                # This text appears frequently in header zone
                max_y = max(y_values)
                max_header_y = max(max_header_y, max_y)

        for _text, y_values in footer_candidates.items():
            if len(y_values) >= min_occurrences:
                # This text appears frequently in footer zone
                min_y = min(y_values)
                max_footer_y = min(max_footer_y, min_y)

        # Set header_height and footer_height if we found repeating patterns
        # Add small margin (5 points) to ensure we capture the full header/footer
        if max_header_y > 0:
            # Update the options object (create new frozen instance)
            self.options = self.options.create_updated(header_height=int(max_header_y + 5), trim_headers_footers=True)

        if max_footer_y < page_height:
            footer_height_value = int(page_height - max_footer_y + 5)
            self.options = self.options.create_updated(footer_height=footer_height_value, trim_headers_footers=True)

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
        pdf_meta = document.metadata if hasattr(document, "metadata") else {}

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
        pdf_mapping.update(
            {
                "creation_date": ["creationDate", "CreationDate"],
                "modification_date": ["modDate", "ModDate"],
            }
        )

        # Custom handlers for special fields
        custom_handlers = {
            "creation_date": handle_pdf_dates,
            "modification_date": handle_pdf_dates,
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
        internal_fields = {"format", "trapped", "encryption"}

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
        if not date_str or not date_str.startswith("D:"):
            return date_str

        try:
            # Remove D: prefix and parse
            clean_date = date_str[2:]
            if "Z" in clean_date:
                clean_date = clean_date.replace("Z", "+0000")
            # Basic parsing - format is YYYYMMDDHHmmSS
            if len(clean_date) >= 8:
                year = int(clean_date[0:4])
                month = int(clean_date[4:6])
                day = int(clean_date[6:8])

                # Validate date ranges before passing to datetime
                if not (1000 <= year <= 9999):
                    logger.debug(f"Invalid year in PDF date: {year}")
                    return date_str
                if not (1 <= month <= 12):
                    logger.debug(f"Invalid month in PDF date: {month}")
                    return date_str
                if not (1 <= day <= 31):
                    logger.debug(f"Invalid day in PDF date: {day}")
                    return date_str

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
            total=total_pages,
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
                if idx < len(pages_list) - 1 and self.options.include_page_numbers:
                    # Add page separator as Comment node - renderers decide whether to display it
                    # Format using page_separator_template with placeholders
                    separator_text = self.options.page_separator_template.format(
                        page_num=pno + 1, total_pages=total_pages
                    )
                    children.append(Comment(content=separator_text, metadata={"comment_type": "page_separator"}))

                # Emit page done event
                self._emit_progress(
                    "item_done",
                    f"Page {pno + 1} of {total_pages} processed",
                    current=idx + 1,
                    total=total_pages,
                    item_type="page",
                    page=pno + 1,
                )
            except Exception as e:
                # Emit error event but continue processing
                self._emit_progress(
                    "error",
                    f"Error processing page {pno + 1}: {str(e)}",
                    current=idx + 1,
                    total=total_pages,
                    error=str(e),
                    stage="page_processing",
                    page=pno + 1,
                )
                # Re-raise to maintain existing error handling
                raise

        # Extract and attach metadata
        metadata = self.extract_metadata(doc)

        # Attach header detection debug info if enabled
        if self.options.header_debug_output and self._hdr_identifier:
            debug_info = self._hdr_identifier.get_debug_info()
            if debug_info:
                metadata.custom["pdf_header_debug"] = debug_info
                logger.debug("Attached PDF header detection debug info to document metadata")

        # Append footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        # Emit finished event
        self._emit_progress(
            "finished",
            f"PDF conversion completed ({total_pages} page{'s' if total_pages != 1 else ''})",
            current=total_pages,
            total=total_pages,
        )

        # Build the document
        ast_doc = Document(children=children, metadata=metadata.to_dict())

        # Apply inline formatting consolidation if enabled
        if self.options.consolidate_inline_formatting:
            consolidator = InlineFormattingConsolidator()
            consolidated = consolidator.transform(ast_doc)
            if isinstance(consolidated, Document):
                ast_doc = consolidated

        return ast_doc

    @staticmethod
    @requires_dependencies("pdf", DEPS_PDF_OCR)
    def _ocr_page_to_text(page: "fitz.Page", options: PdfOptions) -> str:
        """Extract text from a PDF page using OCR (Optical Character Recognition).

        This method renders the PDF page as an image and uses Tesseract OCR
        to extract text from it. Useful for scanned documents or image-based PDFs.

        Parameters
        ----------
        page : fitz.Page
            PDF page to extract text from
        options : PdfOptions
            PDF conversion options containing OCR settings

        Returns
        -------
        str
            Text extracted via OCR

        Raises
        ------
        DependencyError
            If pytesseract or Pillow are not installed
        RuntimeError
            If Tesseract is not properly installed on the system

        Notes
        -----
        This method requires:
        1. Python packages: pytesseract and Pillow (pip install all2md[ocr])
        2. Tesseract OCR engine installed on the system (platform-specific)

        """
        import pytesseract
        from PIL import Image

        # Get OCR configuration
        ocr_opts = options.ocr
        dpi = ocr_opts.dpi

        # Determine language to use
        if ocr_opts.auto_detect_language:
            lang = _detect_page_language(page, options)
        else:
            # Convert list to string if needed
            if isinstance(ocr_opts.languages, list):
                lang = "+".join(ocr_opts.languages)
            else:
                lang = ocr_opts.languages

        # Render page to image (pixmap) at specified DPI
        # DPI is specified via the matrix parameter (DPI/72 = zoom factor)
        zoom = dpi / 72.0
        import fitz

        # Initialize pixmap reference for proper cleanup in finally block
        pix = None
        try:
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Convert PyMuPDF pixmap to PIL Image
            # PyMuPDF uses RGB format
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # Build custom config if provided
            config = ocr_opts.tesseract_config if ocr_opts.tesseract_config else ""

            # Extract text using pytesseract
            ocr_text = pytesseract.image_to_string(img, lang=lang, config=config)

            logger.debug(f"OCR extracted {len(ocr_text)} characters using language '{lang}' at {dpi} DPI")

            return ocr_text

        except pytesseract.TesseractNotFoundError as e:
            raise RuntimeError(
                "Tesseract OCR is not installed or not in PATH. "
                "Please install Tesseract: "
                "https://github.com/tesseract-ocr/tesseract/wiki"
            ) from e
        except Exception as e:
            logger.warning(f"OCR failed for page: {e}")
            return ""
        finally:
            # Clean up pixmap resources to prevent memory leaks
            # This is critical for long-running OCR operations
            if pix is not None:
                pix = None

    def _detect_page_tables(
        self, page: "fitz.Page", page_num: int, total_pages: int
    ) -> tuple[list[dict], list[Any], list[Any]]:
        """Detect tables on a PDF page.

        Parameters
        ----------
        page : fitz.Page
            PDF page to analyze
        page_num : int
            Page number (0-based)
        total_pages : int
            Total number of pages

        Returns
        -------
        tuple
            (table_info, fallback_table_rects, fallback_table_lines)

        """
        import fitz

        mode = self.options.table_detection_mode.lower()

        class EmptyTables:
            tables: list[Any] = []

            def __getitem__(self, index: int) -> Any:
                return self.tables[index]

        fallback_table_rects: list[Any] = []
        fallback_table_lines: list[Any] = []
        tabs = None

        if mode == "none":
            tabs = EmptyTables()
        elif mode == "pymupdf":
            tabs = page.find_tables()
        elif mode == "ruling":
            fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                page, self.options.table_ruling_line_threshold
            )
            tabs = EmptyTables()
        else:
            tabs = page.find_tables()
            if self.options.enable_table_fallback_detection and not tabs.tables:
                fallback_table_rects, fallback_table_lines = detect_tables_by_ruling_lines(
                    page, self.options.table_ruling_line_threshold
                )

        # Build table info list
        table_info = []
        for i, t in enumerate(tabs.tables):
            bbox = fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox)
            table_info.append({"bbox": bbox, "idx": i, "type": "pymupdf", "table_obj": t})
        for i, rect in enumerate(fallback_table_rects):
            table_info.append({"bbox": rect, "idx": i, "type": "fallback", "lines": fallback_table_lines[i]})

        # Emit progress event if tables found
        total_table_count = len(table_info)
        if total_table_count > 0:
            self._emit_progress(
                "detected",
                f"Found {total_table_count} table{'s' if total_table_count != 1 else ''} on page {page_num + 1}",
                current=page_num + 1,
                total=total_pages,
                detected_type="table",
                table_count=total_table_count,
                page=page_num + 1,
            )

        return table_info, fallback_table_rects, fallback_table_lines

    def _apply_ocr_if_needed(self, page: "fitz.Page", all_blocks: list[dict], extracted_text: str) -> list[dict]:
        """Apply OCR to page if needed based on options and content.

        Parameters
        ----------
        page : fitz.Page
            PDF page
        all_blocks : list of dict
            Extracted text blocks
        extracted_text : str
            Extracted plain text from blocks

        Returns
        -------
        list of dict
            Updated blocks (may include OCR-generated blocks)

        """
        use_ocr = _should_use_ocr(page, extracted_text, self.options)

        if not use_ocr:
            return all_blocks

        try:
            ocr_text = self._ocr_page_to_text(page, self.options)

            if not ocr_text.strip():
                logger.warning("OCR returned empty text, keeping original extraction")
                return all_blocks

            # Handle preserve_existing_text option
            if self.options.ocr.preserve_existing_text and extracted_text.strip():
                logger.debug(
                    f"Supplementing existing text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)"
                )
                # Add OCR as additional block
                ocr_block = {
                    "type": 0,
                    "bbox": page.rect,
                    "lines": [
                        {
                            "spans": [{"text": ocr_text, "font": "OCR", "size": 11, "flags": 0, "color": 0}],
                            "bbox": page.rect,
                            "dir": (1, 0),  # Horizontal text direction
                        }
                    ],
                }
                all_blocks.append(ocr_block)
                return all_blocks
            else:
                logger.debug(f"Replacing PyMuPDF text ({len(extracted_text)} chars) with OCR ({len(ocr_text)} chars)")
                # Replace with OCR block
                return [
                    {
                        "type": 0,
                        "bbox": page.rect,
                        "lines": [
                            {
                                "spans": [{"text": ocr_text, "font": "OCR", "size": 11, "flags": 0, "color": 0}],
                                "bbox": page.rect,
                                "dir": (1, 0),  # Horizontal text direction
                            }
                        ],
                    }
                ]

        except Exception as e:
            logger.warning(f"OCR processing failed: {e}. Falling back to standard text extraction.")
            return all_blocks

    def _assign_tables_to_columns(self, table_info: list[dict], columns: list[list[dict]]) -> None:
        """Assign each table to a column based on x-coordinate.

        Parameters
        ----------
        table_info : list of dict
            Table information with bbox
        columns : list of list of dict
            Column blocks

        """
        for table in table_info:
            table_center_x = (table["bbox"].x0 + table["bbox"].x1) / 2
            table["column"] = 0  # Default to first column

            for col_idx, column in enumerate(columns):
                if column:
                    col_x_values = [b["bbox"][0] for b in column if "bbox" in b]
                    if col_x_values:
                        col_min_x = min(col_x_values)
                        col_max_x = max(b["bbox"][2] for b in column if "bbox" in b)
                        if col_min_x <= table_center_x <= col_max_x:
                            table["column"] = col_idx
                            break

    def _process_columns_and_tables(
        self,
        columns: list[list[dict]],
        table_info: list[dict],
        page: "fitz.Page",
        page_num: int,
        page_images: list[Any],
    ) -> list[Node]:
        """Process columns with tables inserted at correct positions.

        Parameters
        ----------
        columns : list of list of dict
            Text block columns
        table_info : list of dict
            Table information
        page : fitz.Page
            PDF page
        page_num : int
            Page number
        page_images : list
            Extracted images for the page

        Returns
        -------
        list of Node
            Processed AST nodes

        """
        nodes: list[Node] = []

        # Calculate average line height for link overlap threshold
        line_heights = []
        for column in columns:
            for block in column:
                for line in block.get("lines", []):
                    if "bbox" in line:
                        line_height = line["bbox"][3] - line["bbox"][1]
                        if line_height > 0:
                            line_heights.append(line_height)
        average_line_height: float | None = sum(line_heights) / len(line_heights) if line_heights else None

        # Process each column
        for col_idx, column in enumerate(columns):
            col_tables = [t for t in table_info if t["column"] == col_idx]

            # Build combined list of blocks and tables, sorted by y-coordinate
            items = []
            for block in column:
                if "bbox" in block:
                    items.append(("block", block["bbox"][1], block))
            for table in col_tables:
                items.append(("table", table["bbox"].y0, table))

            items.sort(key=lambda x: x[1])

            # Process items in order
            try:
                links = [line for line in page.get_links() if line["kind"] == 2]
            except (AttributeError, Exception):
                links = []

            for item_type, _y, item_data in items:
                if item_type == "block":
                    block_nodes = self._process_single_block_to_ast(item_data, links, page_num, average_line_height)
                    nodes.extend(block_nodes)
                elif item_type == "table":
                    if item_data["type"] == "pymupdf":
                        table_node = self._process_table_to_ast(item_data["table_obj"], page_num)
                        if table_node:
                            nodes.append(table_node)
                    elif item_data["type"] == "fallback":
                        h_lines, v_lines = item_data["lines"]
                        table_node = self._extract_table_from_ruling_rect(
                            page, item_data["bbox"], h_lines, v_lines, page_num
                        )
                        if table_node:
                            nodes.append(table_node)

        # Post-processing
        nodes = self._merge_adjacent_paragraphs(nodes)
        nodes = self._convert_paragraphs_to_lists(nodes)

        # Add images if placement markers enabled
        if page_images and self.options.image_placement_markers:
            for img in page_images:
                img_node = self._create_image_node(img, page_num)
                if img_node:
                    nodes.append(img_node)

        return nodes

    def _process_page_to_ast(
        self,
        page: "fitz.Page",
        page_num: int,
        base_filename: str,
        attachment_sequencer: Callable[[str, str], tuple[str, int]],
        total_pages: int = 0,
    ) -> list[Node]:
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

        # Extract images if needed
        page_images: list[Any] = []
        if self.options.attachment_mode != "skip":
            page_images, page_footnotes = extract_page_images(
                page, page_num, self.options, base_filename, attachment_sequencer
            )
            self._attachment_footnotes.update(page_footnotes)

        # Detect tables on the page
        table_info, _, _ = self._detect_page_tables(page, page_num, total_pages)

        # Extract all text blocks from the page
        try:
            text_flags = fitz.TEXTFLAGS_TEXT
            if self.options.merge_hyphenated_words:
                text_flags |= fitz.TEXT_DEHYPHENATE

            all_blocks = page.get_text("dict", flags=text_flags, sort=False)["blocks"]
        except (AttributeError, KeyError, Exception):
            return []

        # Extract plain text for OCR detection
        extracted_text = "".join(
            span.get("text", "")
            for block in all_blocks
            if block.get("type") == 0
            for line in block.get("lines", [])
            for span in line.get("spans", [])
        )

        # Apply OCR if needed
        all_blocks = self._apply_ocr_if_needed(page, all_blocks, extracted_text)

        # Filter headers/footers if enabled
        if self.options.trim_headers_footers:
            all_blocks = self._filter_headers_footers(all_blocks, page)

        # Filter out blocks inside table regions
        text_blocks = []
        for block in all_blocks:
            if "bbox" not in block:
                text_blocks.append(block)
                continue

            block_rect = fitz.Rect(block["bbox"])
            is_in_table = any(abs(block_rect & table["bbox"]) > 0.5 * abs(block_rect) for table in table_info)
            if not is_in_table:
                text_blocks.append(block)

        # Apply column detection if enabled
        if self.options.detect_columns and self.options.column_detection_mode not in ("disabled", "force_single"):
            force_multi = self.options.column_detection_mode == "force_multi"
            columns = detect_columns(
                text_blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=force_multi,
            )
        else:
            columns = [text_blocks]

        # Assign tables to columns
        self._assign_tables_to_columns(table_info, columns)

        # Process columns and tables
        nodes = self._process_columns_and_tables(columns, table_info, page, page_num, page_images)

        return nodes

    def _apply_column_detection(self, blocks: list[dict]) -> list[dict]:
        """Apply column detection to text blocks based on options.

        Parameters
        ----------
        blocks : list[dict]
            List of text blocks from PyMuPDF

        Returns
        -------
        list[dict]
            Processed blocks in reading order

        """
        if not self.options.detect_columns:
            return blocks

        # Check column_detection_mode option
        if self.options.column_detection_mode in ("disabled", "force_single"):
            # Force single column (no detection)
            return blocks

        # Apply column detection for force_multi or auto modes
        if self.options.column_detection_mode == "force_multi":
            columns: list[list[dict]] = detect_columns(
                blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=True,
            )
        else:  # "auto" mode (default)
            columns = detect_columns(
                blocks,
                self.options.column_gap_threshold,
                use_clustering=self.options.use_column_clustering,
                force_multi_column=False,
            )

        # Process blocks in proper reading order: top-to-bottom, left-to-right
        return self._merge_columns_for_reading_order(columns)

    def _process_text_blocks_to_nodes(
        self, blocks_to_process: list[dict], links: list[dict], page_num: int
    ) -> list[Node]:
        """Process text blocks into AST nodes.

        Parameters
        ----------
        blocks_to_process : list[dict]
            Text blocks to process
        links : list[dict]
            Links on the page
        page_num : int
            Page number for source tracking

        Returns
        -------
        list[Node]
            List of AST nodes

        """
        nodes: list[Node] = []

        # Calculate average line height for auto-calibration of link overlap threshold
        line_heights = []
        for block in blocks_to_process:
            for line in block.get("lines", []):
                if "bbox" in line:
                    line_height = line["bbox"][3] - line["bbox"][1]  # y1 - y0
                    if line_height > 0:
                        line_heights.append(line_height)

        average_line_height: float | None = None
        if line_heights:
            average_line_height = sum(line_heights) / len(line_heights)
            logger.debug(f"Calculated average line height for page: {average_line_height:.2f} points")

        # Track if we're in a code block
        in_code_block = False
        code_block_lines: list[str] = []

        for block in blocks_to_process:  # Iterate textblocks
            previous_y = 0

            for line in block["lines"]:  # Iterate lines in block
                # Handle rotated text if enabled, otherwise skip non-horizontal lines
                if line.get("dir", (0, 0))[1] != 0:  # Non-horizontal lines
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
                    span_size = spans[0]["size"]
                    if span_size > 0:
                        delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (span_size * 0.5))
                    else:
                        delta = 0
                    code_block_lines.append(" " * delta + text)
                    continue

                # If we were in a code block and now we're not, finalize it
                if in_code_block:
                    code_content = "\n".join(code_block_lines)
                    nodes.append(
                        CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
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
                    inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
                    if inline_content:
                        nodes.append(
                            Heading(
                                level=header_level,
                                content=inline_content,
                                source_location=SourceLocation(format="pdf", page=page_num + 1),
                            )
                        )
                else:
                    # Regular paragraph
                    inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
                    if inline_content:
                        nodes.append(
                            AstParagraph(
                                content=inline_content, source_location=SourceLocation(format="pdf", page=page_num + 1)
                            )
                        )

        # Finalize any remaining code block
        if in_code_block and code_block_lines:
            code_content = "\n".join(code_block_lines)
            nodes.append(
                CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
            )

        return nodes

    def _process_text_region_to_ast(self, page: "fitz.Page", clip: "fitz.Rect", page_num: int) -> list[Node]:
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

        # Apply column detection
        blocks_to_process = self._apply_column_detection(blocks)

        # Process blocks to create AST nodes
        return self._process_text_blocks_to_nodes(blocks_to_process, links, page_num)

    def _process_text_spans_to_inline(
        self, spans: list[dict], links: list[dict], page_num: int, average_line_height: float | None = None
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
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of inline AST nodes

        """
        result: list[Node] = []

        for span in spans:
            span_text = span["text"]
            # Skip completely empty spans, but preserve single spaces
            if not span_text:
                continue

            # Check for list bullets before treating as monospace
            is_list_bullet = span_text in ["-", "o", "•", "◦", "▪"] and len(span_text) == 1

            # Decode font properties
            mono = span["flags"] & 8
            bold = span["flags"] & 16
            italic = span["flags"] & 2

            # Check for links with auto-calibrated threshold
            link_url = self._resolve_link_for_span(links, span, average_line_height)

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

    def _calculate_paragraph_break_threshold(self, block: dict) -> float:
        """Calculate adaptive paragraph break threshold based on line heights.

        Parameters
        ----------
        block : dict
            Text block from PyMuPDF

        Returns
        -------
        float
            Paragraph break threshold in points

        """
        line_heights_in_block = []
        for line in block["lines"]:
            if "bbox" in line and "dir" in line and line["dir"][1] == 0:  # Only horizontal lines
                line_height = line["bbox"][3] - line["bbox"][1]
                if line_height > 0:
                    line_heights_in_block.append(line_height)

        # Use median line height for robustness (less affected by outliers)
        if line_heights_in_block:
            sorted_heights = sorted(line_heights_in_block)
            median_height = sorted_heights[len(sorted_heights) // 2]
            # Paragraph break threshold: 50% of typical line height
            return median_height * 0.5
        else:
            # Fallback to fixed threshold if we can't calculate
            return 5.0

    def _build_paragraph_metadata(
        self,
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
    ) -> dict:
        """Build metadata dict including bbox and list marker info.

        Parameters
        ----------
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker

        Returns
        -------
        dict
            Metadata dictionary

        """
        metadata: dict[str, Any] = {"bbox": paragraph_bbox} if paragraph_bbox else {}
        if paragraph_is_list:
            metadata["is_list_item"] = True
            metadata["list_type"] = paragraph_list_type
            if paragraph_bbox:
                metadata["marker_x"] = paragraph_bbox[0]
        return metadata

    def _flush_paragraph(
        self,
        paragraph_content: list[Node],
        paragraph_bbox: tuple[float, float, float, float] | None,
        paragraph_is_list: bool,
        paragraph_list_type: str | None,
        page_num: int,
        nodes: list[Node],
    ) -> None:
        """Flush accumulated paragraph content to nodes list.

        Parameters
        ----------
        paragraph_content : list of Node
            Accumulated inline nodes for paragraph
        paragraph_bbox : tuple or None
            Bounding box of paragraph
        paragraph_is_list : bool
            Whether paragraph is a list item
        paragraph_list_type : str or None
            Type of list marker
        page_num : int
            Page number for source tracking
        nodes : list of Node
            Output nodes list to append to

        """
        if paragraph_content:
            metadata = self._build_paragraph_metadata(paragraph_bbox, paragraph_is_list, paragraph_list_type)
            source_loc = SourceLocation(format="pdf", page=page_num + 1, metadata=metadata)
            nodes.append(AstParagraph(content=paragraph_content, source_location=source_loc))

    def _process_single_block_to_ast(
        self, block: dict, links: list[dict], page_num: int, average_line_height: float | None = None
    ) -> list[Node]:
        """Process a single text block to AST nodes.

        Parameters
        ----------
        block : dict
            Single text block from PyMuPDF
        links : list of dict
            Links on the page
        page_num : int
            Page number for source tracking
        average_line_height : float or None, optional
            Average line height for the page, used for link threshold auto-calibration

        Returns
        -------
        list of Node
            List of AST nodes (paragraphs, headings, code blocks)

        """
        nodes: list[Node] = []

        if "lines" not in block:
            return nodes

        previous_y = 0
        in_code_block = False
        code_block_lines: list[str] = []

        # Track accumulated paragraph content
        paragraph_content: list[Node] = []
        paragraph_bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)
        paragraph_is_list: bool = False  # Track if paragraph starts with list marker
        paragraph_list_type: str | None = None

        # Calculate adaptive paragraph break threshold based on line heights in this block
        paragraph_break_threshold = self._calculate_paragraph_break_threshold(block)

        for line in block["lines"]:
            # Handle rotated text if enabled, otherwise skip non-horizontal lines
            if line["dir"][1] != 0:  # Non-horizontal lines
                if self.options.handle_rotated_text:
                    rotated_text = handle_rotated_text(line, None)
                    if rotated_text.strip():
                        # Flush any accumulated paragraph first
                        self._flush_paragraph(
                            paragraph_content, paragraph_bbox, paragraph_is_list, paragraph_list_type, page_num, nodes
                        )
                        paragraph_content = []
                        paragraph_bbox = None
                        paragraph_is_list = False
                        paragraph_list_type = None
                        nodes.append(AstParagraph(content=[Text(content=rotated_text)]))
                continue

            spans = list(line.get("spans", []))
            if not spans:
                continue

            this_y = line["bbox"][3]  # Current bottom coord

            # Calculate vertical gap from previous line
            vertical_gap = abs(this_y - previous_y) if previous_y > 0 else 0

            # Are all spans in line in a mono-spaced font?
            all_mono = all(s["flags"] & 8 for s in spans)

            # Compute text of the line
            text = "".join([s["text"] for s in spans])

            previous_y = this_y

            # Handle monospace text (code blocks)
            if all_mono:
                # Flush accumulated paragraph before starting code block
                self._flush_paragraph(
                    paragraph_content, paragraph_bbox, paragraph_is_list, paragraph_list_type, page_num, nodes
                )
                paragraph_content = []
                paragraph_bbox = None
                paragraph_is_list = False
                paragraph_list_type = None

                if not in_code_block:
                    in_code_block = True
                # Add line to code block
                # Compute approximate indentation
                span_size = spans[0]["size"]
                if span_size > 0:
                    delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (span_size * 0.5))
                else:
                    delta = 0
                code_block_lines.append(" " * delta + text)
                continue

            # If we were in a code block and now we're not, finalize it
            if in_code_block:
                code_content = "\n".join(code_block_lines)
                nodes.append(
                    CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
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
                # Flush accumulated paragraph before adding heading
                self._flush_paragraph(
                    paragraph_content, paragraph_bbox, paragraph_is_list, paragraph_list_type, page_num, nodes
                )
                paragraph_content = []
                paragraph_bbox = None
                paragraph_is_list = False
                paragraph_list_type = None

                # This is a heading
                inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
                if inline_content:
                    nodes.append(
                        Heading(
                            level=header_level,
                            content=inline_content,
                            source_location=SourceLocation(format="pdf", page=page_num + 1),
                        )
                    )
            else:
                # Regular text - check if we should start a new paragraph
                # Large vertical gap (adaptive threshold based on line height) indicates paragraph break
                # BUT: Don't break list items - they may span multiple lines
                if vertical_gap > paragraph_break_threshold and paragraph_content and not paragraph_is_list:
                    # Flush previous paragraph (unless it's a list item)
                    self._flush_paragraph(
                        paragraph_content, paragraph_bbox, paragraph_is_list, paragraph_list_type, page_num, nodes
                    )
                    paragraph_content = []
                    paragraph_bbox = None
                    paragraph_is_list = False
                    paragraph_list_type = None

                # Accumulate inline content
                inline_content = self._process_text_spans_to_inline(spans, links, page_num, average_line_height)
                if inline_content:
                    # Add space between lines if we're continuing a paragraph
                    if paragraph_content:
                        paragraph_content.append(Text(content=" "))
                    else:
                        # Starting new paragraph - initialize bbox and check for list marker
                        paragraph_bbox = line["bbox"]
                        # Detect list markers at the start of paragraph
                        first_text = ""
                        for node in inline_content:
                            if isinstance(node, Text):
                                first_text = node.content
                                break
                        paragraph_is_list, paragraph_list_type = self._is_valid_list_marker(first_text)

                    paragraph_content.extend(inline_content)
                    # Expand bbox to include this line
                    if paragraph_bbox:
                        line_bbox = line["bbox"]
                        paragraph_bbox = (
                            min(paragraph_bbox[0], line_bbox[0]),  # x0
                            min(paragraph_bbox[1], line_bbox[1]),  # y0
                            max(paragraph_bbox[2], line_bbox[2]),  # x1
                            max(paragraph_bbox[3], line_bbox[3]),  # y1
                        )

        # Flush any remaining paragraph content
        self._flush_paragraph(
            paragraph_content, paragraph_bbox, paragraph_is_list, paragraph_list_type, page_num, nodes
        )

        # Finalize any remaining code block
        if in_code_block and code_block_lines:
            code_content = "\n".join(code_block_lines)
            nodes.append(
                CodeBlock(content=code_content, source_location=SourceLocation(format="pdf", page=page_num + 1))
            )

        return nodes

    def _resolve_link_for_span(
        self, links: list[dict], span: dict, average_line_height: float | None = None
    ) -> str | None:
        """Resolve link URL for a text span with auto-calibrated overlap threshold.

        Parameters
        ----------
        links : list of dict
            Links on the page
        span : dict
            Text span
        average_line_height : float or None, optional
            Average line height for the page, used for auto-calibration of threshold
            for spans with unusual heights (e.g., large fonts)

        Returns
        -------
        str or None
            Link URL if span is part of a link

        Notes
        -----
        Uses the link_overlap_threshold option from self.options to determine
        the minimum overlap required for link detection. When average_line_height
        is provided, automatically adjusts the threshold for spans that are
        significantly taller than average (common in documents with font scaling).

        """
        if not links or not span.get("text"):
            return None

        import fitz

        bbox = fitz.Rect(span["bbox"])

        # Calculate span height
        span_height = bbox.height

        # Use threshold from options
        threshold_percent = self.options.link_overlap_threshold

        # Auto-calibrate threshold for tall spans if average line height is available
        if average_line_height and average_line_height > 0 and span_height > average_line_height * 1.5:
            # Span is significantly taller than average (>1.5x), likely due to font scaling
            # Relax the threshold to compensate for the increased bbox area
            # Scale down threshold proportionally to the height ratio
            height_ratio = span_height / average_line_height
            adjusted_threshold = threshold_percent / (height_ratio**0.5)  # Square root dampening
            adjusted_threshold = max(adjusted_threshold, 30.0)  # Don't go below 30%
            threshold_percent = adjusted_threshold
            logger.debug(
                f"Auto-calibrated link threshold for tall span: "
                f"{self.options.link_overlap_threshold:.1f}% -> {threshold_percent:.1f}% "
                f"(span height: {span_height:.1f}, avg: {average_line_height:.1f})"
            )

        # Find all links that overlap with this span
        for link in links:
            hot = link["from"]  # The hot area of the link
            overlap = hot & bbox
            bbox_area = (threshold_percent / 100.0) * abs(bbox)
            if abs(overlap) >= bbox_area:
                return link.get("uri")

        return None

    @staticmethod
    def _extract_cell_text(cell_text: Any) -> str:
        """Extract and normalize text from a table cell.

        Parameters
        ----------
        cell_text : Any
            Cell text value which may be None, string, or other type

        Returns
        -------
        str
            Normalized cell text as string, empty string if None

        """
        return str(cell_text).strip() if cell_text is not None else ""

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
                cell_content = self._extract_cell_text(cell_text)
                header_cells.append(TableCell(content=[Text(content=cell_content)]))

            header_row = TableRow(cells=header_cells, is_header=True)

            # Build AST data rows
            data_rows = []
            for row_data in data_rows_data:
                row_cells = []
                for cell_text in row_data:
                    cell_content = self._extract_cell_text(cell_text)
                    row_cells.append(TableCell(content=[Text(content=cell_content)]))

                data_rows.append(TableRow(cells=row_cells))

            return AstTable(
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
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
            lines = table_md.strip().split("\n")
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
                header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
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
        row_y_coords = [(h_lines_sorted[i][1], h_lines_sorted[i + 1][1]) for i in range(len(h_lines_sorted) - 1)]

        # Extract x-coordinates for columns (between consecutive v_lines)
        col_x_coords = [(v_lines_sorted[i][0], v_lines_sorted[i + 1][0]) for i in range(len(v_lines_sorted) - 1)]

        import fitz

        for row_idx, (y0, y1) in enumerate(row_y_coords):
            cells: list[TableCell] = []

            for _col_idx, (x0, x1) in enumerate(col_x_coords):
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
            is_header = row_idx == 0
            rows.append(TableRow(cells=cells, is_header=is_header))

        if not rows:
            return None

        # Separate header and data rows
        header_row = rows[0] if rows else TableRow(cells=[])
        data_rows = rows[1:] if len(rows) > 1 else []

        return AstTable(
            header=header_row, rows=data_rows, source_location=SourceLocation(format="pdf", page=page_num + 1)
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
        if row_line.startswith("|"):
            row_line = row_line[1:]
        if row_line.endswith("|"):
            row_line = row_line[:-1]

        cells = [cell.strip() for cell in row_line.split("|")]
        return cells

    def _create_image_node(self, img_info: dict, page_num: int) -> AstParagraph | None:
        """Create an image node from image info.

        Parameters
        ----------
        img_info : dict
            Image information dict with 'result' (process_attachment result) and 'caption' keys
        page_num : int
            Page number for source tracking

        Returns
        -------
        AstParagraph or None
            Paragraph containing the image node

        """
        try:
            # Get the process_attachment result
            result = img_info.get("result", {})
            caption = img_info.get("caption") or "Image"

            # Convert result to Image node using helper
            img_node = attachment_result_to_image_node(result, fallback_alt_text=caption)

            if img_node:
                # Add source location
                img_node.source_location = SourceLocation(format="pdf", page=page_num + 1)

                # Wrap in paragraph
                return AstParagraph(content=[img_node], source_location=SourceLocation(format="pdf", page=page_num + 1))

            return None

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

    def _merge_columns_for_reading_order(self, columns: list[list[dict]]) -> list[dict]:
        """Merge multiple columns into proper reading order.

        For multi-column layouts, the standard reading order is column-by-column:
        read the entire left column top-to-bottom, then move to the right column
        and read it top-to-bottom. This matches how PyMuPDF naturally orders blocks
        and is the expected behavior for most multi-column documents.

        Parameters
        ----------
        columns : list[list[dict]]
            List of columns, where each column is a list of blocks

        Returns
        -------
        list[dict]
            Merged list of blocks in proper reading order

        """
        if len(columns) <= 1:
            # Single column or empty, just return flattened
            return [block for col in columns for block in col]

        # Sort each column by y-coordinate (top to bottom)
        # Then concatenate: all of column 0, then all of column 1, etc.
        result = []
        for column in columns:
            sorted_column = sorted(column, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
            result.extend(sorted_column)

        return result

    def _is_list_item_paragraph(self, paragraph: AstParagraph) -> bool:
        """Check if paragraph starts with a list marker.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to check

        Returns
        -------
        bool
            True if paragraph starts with list marker

        """
        if not paragraph.content:
            return False

        def extract_text(nodes: list[Node]) -> str:
            """Recursively extract text from nodes."""
            text_parts = []
            for node in nodes:
                if isinstance(node, Text):
                    text_parts.append(node.content)
                elif hasattr(node, "content") and isinstance(node.content, list):
                    text_parts.append(extract_text(node.content))
            return "".join(text_parts)

        full_text = extract_text(paragraph.content)
        is_list, _ = self._is_valid_list_marker(full_text)
        return is_list

    def _determine_list_level_from_x(self, x_coord: float, x_levels: dict[int, float]) -> int:
        """Determine the nesting level of a list item based on its x-coordinate.

        Parameters
        ----------
        x_coord : float
            The x-coordinate of the list item
        x_levels : dict
            Dictionary mapping level numbers to representative x-coordinates

        Returns
        -------
        int
            The nesting level (0-based)

        Notes
        -----
        X-coordinates within 5 points of each other are considered the same level.

        """
        LEVEL_THRESHOLD = 5.0

        # Check if x_coord matches an existing level
        for level, level_x in x_levels.items():
            if abs(x_coord - level_x) < LEVEL_THRESHOLD:
                return level

        # New level - assign it the next available level number
        new_level = len(x_levels)
        x_levels[new_level] = x_coord
        return new_level

    def _apply_list_indentation(
        self, paragraph: AstParagraph, current_bbox: tuple[float, float, float, float], first_list_item_x: float
    ) -> None:
        """Store bbox information for later use in nested list detection.

        Parameters
        ----------
        paragraph : AstParagraph
            Paragraph to process
        current_bbox : tuple
            Current bounding box
        first_list_item_x : float
            X-coordinate of first list item (unused, kept for API compatibility)

        Notes
        -----
        This method no longer adds manual spacing. List nesting is now handled
        structurally in _convert_paragraphs_to_lists using x-coordinate data.

        """
        # No-op: nesting is now handled structurally, not via spacing
        pass

    def _should_merge_with_accumulated(
        self,
        current_bbox: tuple[float, float, float, float] | None,
        last_bbox_bottom: float | None,
        accumulated_content: list[Node],
        is_list_item: bool,
        last_was_list_item: bool,
        merge_threshold: float,
        current_metadata: dict | None = None,
        last_metadata: dict | None = None,
    ) -> bool:
        """Determine if current paragraph should merge with accumulated content.

        Parameters
        ----------
        current_bbox : tuple or None
            Current paragraph bounding box
        last_bbox_bottom : float or None
            Bottom y-coordinate of last paragraph
        accumulated_content : list of Node
            Accumulated content so far
        is_list_item : bool
            Whether current paragraph is a list item
        last_was_list_item : bool
            Whether last paragraph was a list item
        merge_threshold : float
            Threshold for vertical gap merging
        current_metadata : dict or None, optional
            Metadata from current paragraph's source location
        last_metadata : dict or None, optional
            Metadata from last paragraph's source location

        Returns
        -------
        bool
            True if should merge

        """
        # Check metadata for list markers first (more reliable than text-based detection)
        current_is_list = (current_metadata and current_metadata.get("is_list_item", False)) or is_list_item
        last_is_list = (last_metadata and last_metadata.get("is_list_item", False)) or last_was_list_item

        # Don't merge list items with anything
        if current_is_list or last_is_list:
            return False

        # If bbox information is missing, don't merge to be safe
        if not current_bbox or last_bbox_bottom is None:
            return not accumulated_content

        # Must have accumulated content and valid bbox info
        if not accumulated_content:
            return True

        # Calculate vertical gap
        current_bbox_top = current_bbox[1]
        vertical_gap = current_bbox_top - last_bbox_bottom

        # Only merge if gap is small
        return vertical_gap < merge_threshold

    def _merge_adjacent_paragraphs(self, nodes: list[Node]) -> list[Node]:
        """Merge consecutive paragraph nodes that should be combined.

        In multi-column layouts, PyMuPDF often creates separate blocks for each
        line of text. This results in many small paragraph nodes that should be
        merged into cohesive paragraphs. This method combines consecutive
        Paragraph nodes that have small vertical gaps (< 10 points), indicating
        they're part of the same logical paragraph.

        Parameters
        ----------
        nodes : list of Node
            List of AST nodes (paragraphs, headings, tables, etc.)

        Returns
        -------
        list of Node
            List of nodes with consecutive paragraphs merged

        Notes
        -----
        Only Paragraph nodes with small vertical gaps are merged. Paragraphs
        with larger gaps (>= 10 points) are kept separate. Headings, code blocks,
        tables, and other block-level elements act as natural paragraph boundaries.

        This method requires bbox information to be stored in SourceLocation.metadata['bbox'].
        If bbox information is not available, paragraphs without bbox are not merged.

        """
        if not nodes:
            return nodes

        MERGE_THRESHOLD = 5.0

        merged: list[Node] = []
        accumulated_content: list[Node] = []
        last_source_location: SourceLocation | None = None
        last_bbox_bottom: float | None = None
        last_was_list_item: bool = False
        last_metadata: dict | None = None
        first_list_item_x: float | None = None

        for node in nodes:
            if isinstance(node, AstParagraph):
                current_bbox = None
                current_metadata = None
                if node.source_location and node.source_location.metadata:
                    current_bbox = node.source_location.metadata.get("bbox")
                    current_metadata = node.source_location.metadata

                is_list_item = self._is_list_item_paragraph(node)

                # Handle list item indentation
                if is_list_item and current_bbox:
                    if first_list_item_x is None:
                        first_list_item_x = current_bbox[0]
                    self._apply_list_indentation(node, current_bbox, first_list_item_x)

                # Determine if we should merge
                should_merge = self._should_merge_with_accumulated(
                    current_bbox,
                    last_bbox_bottom,
                    accumulated_content,
                    is_list_item,
                    last_was_list_item,
                    MERGE_THRESHOLD,
                    current_metadata,
                    last_metadata,
                )

                if should_merge:
                    # Merge: accumulate content
                    if accumulated_content and node.content:
                        accumulated_content.append(Text(content=" "))
                    accumulated_content.extend(node.content)
                    if last_source_location is None:
                        last_source_location = node.source_location
                    if current_bbox:
                        last_bbox_bottom = current_bbox[3]
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                else:
                    # Don't merge: flush accumulated content
                    if accumulated_content:
                        merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = list(node.content)
                    last_source_location = node.source_location
                    last_bbox_bottom = current_bbox[3] if current_bbox else None
                    last_was_list_item = is_list_item
                    last_metadata = current_metadata
                    if not is_list_item:
                        first_list_item_x = None
            else:
                # Non-paragraph node: flush and reset
                if accumulated_content:
                    merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))
                    accumulated_content = []
                    last_source_location = None
                    last_bbox_bottom = None
                    last_was_list_item = False
                    last_metadata = None
                    first_list_item_x = None
                merged.append(node)

        # Flush remaining content
        if accumulated_content:
            merged.append(AstParagraph(content=accumulated_content, source_location=last_source_location))

        return merged

    @staticmethod
    def _is_valid_list_marker(text: str) -> tuple[bool, str | None]:
        """Check if text starts with a valid list marker.

        Parameters
        ----------
        text : str
            Text to check for list markers

        Returns
        -------
        tuple[bool, str | None]
            (is_list_item, list_type) where list_type is "ordered", "unordered", or None

        Notes
        -----
        This function is more conservative about detecting list markers to avoid false positives:
        - Letter "o" must be followed by a space to be treated as a marker (avoids "office", "online", etc.)
        - Numbered markers must be followed by space (avoids dates like "2024")

        """
        if not text:
            return False, None

        stripped = text.lstrip()
        if not stripped:
            return False, None

        first_char = stripped[0]

        # Check for bullet markers - but be careful with "o"
        # Include EN DASH (–, U+2013) and EM DASH (—, U+2014) which are commonly used in PDFs
        if first_char in ("-", "\u2013", "\u2014", "*", "+", "•", "◦", "▪", "▫"):
            return True, "unordered"

        # Special handling for lowercase "o" - only treat as marker if followed by space
        if first_char == "o":
            # Must have at least 2 characters and second must be space
            if len(stripped) >= 2 and stripped[1] == " ":
                return True, "unordered"
            else:
                return False, None

        # Check for numbered list markers (1. or 1) followed by space)
        # More robust: require space after marker to avoid matching dates/numbers
        match = re.match(r"^\s*(\d+)[\.\)]\s", text)
        if match:
            return True, "ordered"

        return False, None

    def _detect_list_marker(self, para: AstParagraph) -> tuple[bool, str | None]:
        """Detect if a paragraph is a list item and return its type.

        Parameters
        ----------
        para : AstParagraph
            The paragraph to check

        Returns
        -------
        tuple[bool, str | None]
            A tuple of (is_list_item, list_type) where list_type is
            "ordered", "unordered", or None

        """
        full_text = ""
        for node in para.content:
            if isinstance(node, Text):
                full_text = node.content
                break

        return self._is_valid_list_marker(full_text)

    def _extract_list_item_x_coord(self, node: AstParagraph) -> float | None:
        """Extract x-coordinate from a paragraph's bbox metadata.

        Parameters
        ----------
        node : AstParagraph
            The paragraph node

        Returns
        -------
        float | None
            The x-coordinate if available, None otherwise

        """
        if node.source_location and node.source_location.metadata:
            bbox = node.source_location.metadata.get("bbox")
            if bbox and len(bbox) >= 1:
                return bbox[0]
        return None

    def _strip_list_marker(self, para: AstParagraph) -> list[Node]:
        """Remove list marker from paragraph content and return cleaned content.

        Parameters
        ----------
        para : AstParagraph
            The paragraph containing a list marker

        Returns
        -------
        list[Node]
            Content nodes with the list marker removed

        """
        full_text = ""
        for node in para.content:
            if isinstance(node, Text):
                full_text = node.content
                break

        # Use the robust marker detection to validate this is actually a list item
        is_list, list_type = self._is_valid_list_marker(full_text)
        if not is_list:
            # Not a valid list marker, return content as-is
            return list(para.content)

        # Determine marker and strip it
        stripped = full_text.lstrip()
        marker_end = 0

        if list_type == "unordered":
            # Bullet marker - find where it ends (marker + space)
            marker_char = stripped[0]
            marker_end = full_text.index(marker_char) + 1
            # Skip following space if present
            if marker_end < len(full_text) and full_text[marker_end] == " ":
                marker_end += 1
        elif list_type == "ordered":
            # Numbered marker - use regex to find end
            match = re.match(r"^(\s*)(\d+[\.\)])\s", full_text)
            if match:
                marker_end = match.end()

        # Create new content without the marker
        new_content: list[Node] = []
        if marker_end > 0:
            # Remove marker from first text node
            for i, node in enumerate(para.content):
                if i == 0 and isinstance(node, Text):
                    remaining_text = node.content[marker_end:]
                    if remaining_text:
                        new_content.append(Text(content=remaining_text))
                else:
                    new_content.append(node)
        else:
            new_content = list(para.content)

        return new_content

    def _finalize_pending_lists(self, list_stack: list[tuple[str, int, list[ListItem]]], result: list[Node]) -> None:
        """Finalize all lists in the stack, nesting them properly.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of (list_type, level, items) tuples
        result : list[Node]
            Result list to append finalized top-level list to

        """
        while len(list_stack) > 1:
            # Pop deeper list
            deeper_type, deeper_level, deeper_items = list_stack.pop()
            nested_list = List(ordered=(deeper_type == "ordered"), items=deeper_items, tight=True)

            # Add to parent's last item
            parent_items = list_stack[-1][2]
            if parent_items:
                parent_items[-1].children.append(nested_list)

        # Add the top-level list to results
        if list_stack:
            list_type, level, items = list_stack.pop()
            result.append(List(ordered=(list_type == "ordered"), items=items, tight=True))

    def _handle_empty_stack(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item when stack is empty.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples (will be empty when called)
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_deeper_nesting(
        self, list_stack: list[tuple[str, int, list[ListItem]]], list_type: str, level: int, item_node: ListItem
    ) -> None:
        """Handle adding a list item at a deeper nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (greater than current stack top level)
        item_node : ListItem
            The list item to add

        """
        list_stack.append((list_type, level, [item_node]))

    def _handle_shallower_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        level: int,
        item_node: ListItem,
        result: list[Node],
    ) -> None:
        """Handle adding a list item at a shallower nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        level : int
            Nesting level (less than current stack top level)
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists

        """
        # Going back to shallower level - finalize deeper lists
        while list_stack and list_stack[-1][1] > level:
            popped_type, popped_level, popped_items = list_stack.pop()
            nested_list = List(ordered=(popped_type == "ordered"), items=popped_items, tight=True)

            # Add nested list to parent's last item
            if list_stack:
                parent_items = list_stack[-1][2]
                if parent_items:
                    parent_items[-1].children.append(nested_list)

        # Check if we're at the same level and type
        if list_stack and list_stack[-1][1] == level:
            if list_stack[-1][0] == list_type:
                # Same level and type - add item
                list_stack[-1][2].append(item_node)
            else:
                # Different type at same level - finalize old, start new
                old_type, old_level, old_items = list_stack.pop()
                result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
                list_stack.append((list_type, level, [item_node]))
        else:
            # Start new list at this level
            list_stack.append((list_type, level, [item_node]))

    def _handle_same_level(
        self,
        list_stack: list[tuple[str, int, list[ListItem]]],
        list_type: str,
        item_node: ListItem,
        result: list[Node],
        current_type: str,
        current_level: int,
    ) -> None:
        """Handle adding a list item at the same nesting level.

        Parameters
        ----------
        list_stack : list[tuple[str, int, list[ListItem]]]
            Stack of list tuples
        list_type : str
            Type of list ("ordered" or "unordered")
        item_node : ListItem
            The list item to add
        result : list[Node]
            Result list for finalized lists
        current_type : str
            Current list type from stack top
        current_level : int
            Current nesting level from stack top

        """
        if current_type == list_type:
            # Same type - add to current list
            list_stack[-1][2].append(item_node)
        else:
            # Different type at same level - finalize old, start new
            old_type, old_level, old_items = list_stack.pop()
            result.append(List(ordered=(old_type == "ordered"), items=old_items, tight=True))
            list_stack.append((list_type, current_level, [item_node]))

    def _convert_paragraphs_to_lists(self, nodes: list[Node]) -> list[Node]:
        """Convert paragraphs with list markers into List/ListItem structures with proper nesting.

        Parameters
        ----------
        nodes : list of Node
            AST nodes that may contain list marker paragraphs

        Returns
        -------
        list of Node
            Nodes with list paragraphs converted to nested List structures

        Notes
        -----
        Uses x-coordinate information from bbox metadata to determine nesting levels.
        Implements a stack-based algorithm to build properly nested list structures.

        """
        result: list[Node] = []
        list_stack: list[tuple[str, int, list[ListItem]]] = []
        x_levels: dict[int, float] = {}

        for node in nodes:
            if isinstance(node, AstParagraph):
                # Check if this is a list item
                is_list_item, list_type = self._detect_list_marker(node)

                if is_list_item and list_type:
                    # Extract x-coordinate and determine nesting level
                    x_coord = self._extract_list_item_x_coord(node)
                    level = 0
                    if x_coord is not None:
                        level = self._determine_list_level_from_x(x_coord, x_levels)

                    # Create list item with cleaned content
                    cleaned_content = self._strip_list_marker(node)
                    item_node = ListItem(children=[AstParagraph(content=cleaned_content)])

                    # Handle list stack based on level
                    if not list_stack:
                        self._handle_empty_stack(list_stack, list_type, level, item_node)
                    else:
                        current_type, current_level, current_items = list_stack[-1]

                        if level > current_level:
                            self._handle_deeper_nesting(list_stack, list_type, level, item_node)
                        elif level < current_level:
                            self._handle_shallower_level(list_stack, list_type, level, item_node, result)
                        else:
                            self._handle_same_level(
                                list_stack, list_type, item_node, result, current_type, current_level
                            )
                else:
                    # Not a list item - finalize any pending lists
                    self._finalize_pending_lists(list_stack, result)
                    x_levels.clear()
                    result.append(node)
            else:
                # Non-paragraph - finalize any pending lists
                self._finalize_pending_lists(list_stack, result)
                x_levels.clear()
                result.append(node)

        # Finalize any remaining lists
        self._finalize_pending_lists(list_stack, result)

        return result


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
    optional_packages=[
        ("pytesseract", "pytesseract"),
        ("Pillow", "PIL"),
    ],
    import_error_message=("PDF conversion requires 'PyMuPDF'. Install with: pip install pymupdf"),
    parser_options_class=PdfOptions,
    renderer_options_class="all2md.options.pdf.PdfRendererOptions",
    description="Convert PDF documents to/from AST with table detection and optional OCR support",
    priority=10,
)
