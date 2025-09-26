#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# src/all2md/converters/pdf2markdown.py
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

    >>> from all2md.converters.pdf2markdown import pdf_to_markdown
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
from typing import IO, TYPE_CHECKING, Union, Optional

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
from all2md.utils.attachments import generate_attachment_filename, process_attachment
from all2md.utils.inputs import escape_markdown_special, validate_and_convert_input, validate_page_range
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled

# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf", "application/x-pdf"],
    magic_bytes=[
        (b"%PDF", 0),  # PDF signature
    ],
    converter_module="all2md.converters.pdf2markdown",
    converter_function="pdf_to_markdown",
    required_packages=[("pymupdf", ">=1.24.0")],
    optional_packages=[],
    import_error_message=(
        "PDF conversion requires 'pymupdf' version 1.24.0 or later. "
        "Install with: pip install 'pymupdf>=1.24.0'"
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

        # Get header sizes based on percentile threshold
        if self.options.header_percentile_threshold and fontsizes:
            sorted_sizes = sorted(fontsizes.keys(), reverse=True)
            percentile_idx = int(len(sorted_sizes) * (1 - self.options.header_percentile_threshold / 100))
            percentile_threshold = sorted_sizes[max(0, percentile_idx - 1)] if percentile_idx > 0 else sorted_sizes[0]
            sizes = [s for s in sorted_sizes if s >= percentile_threshold and s > body_limit]
        else:
            sizes = sorted([f for f in fontsizes if f > body_limit], reverse=True)

        # Add sizes from allowlist
        if self.options.header_size_allowlist:
            for size in self.options.header_size_allowlist:
                rounded_size = round(size)
                if rounded_size not in sizes and rounded_size > body_limit:
                    sizes.append(rounded_size)
            sizes = sorted(sizes, reverse=True)

        # Add bold and all-caps sizes as potential headers
        if self.options.header_use_font_weight:
            for size in fontweight_sizes:
                if size not in sizes and size >= body_limit:
                    sizes.append(size)
                    self.bold_header_sizes.add(size)

        if self.options.header_use_all_caps:
            for size in allcaps_sizes:
                if size not in sizes and size >= body_limit:
                    sizes.append(size)
                    self.allcaps_header_sizes.add(size)

        sizes = sorted(set(sizes), reverse=True)

        # make the header tag dictionary
        for i, size in enumerate(sizes):
            self.header_id[size] = "#" * min(i + 1, 6) + " "  # Limit to h6

    def get_header_id(self, span: dict) -> str:
        """Return appropriate markdown header prefix for a text span.

        Analyzes the font size of a text span and returns the corresponding
        Markdown header prefix (e.g., "# ", "## ", "### ") or empty string
        if the span should be treated as body text.

        Parameters
        ----------
        span : dict
            Text span dictionary from PyMuPDF extraction containing 'size' key

        Returns
        -------
        str
            Markdown header prefix string ("# ", "## ", etc.) or empty string
        """
        fontsize = round(span["size"])  # compute fontsize
        hdr_id = self.header_id.get(fontsize, "")

        # Check for additional header indicators if no size-based header found
        if not hdr_id and self.options:
            text = span.get("text", "").strip()

            # Check for bold header
            if self.options.header_use_font_weight and (span.get("flags", 0) & 16):
                if fontsize in self.bold_header_sizes:
                    hdr_id = self.header_id.get(fontsize, "")

            # Check for all-caps header
            if self.options.header_use_all_caps and text.isupper() and text.isalpha():
                if fontsize in self.allcaps_header_sizes:
                    hdr_id = self.header_id.get(fontsize, "")

        return hdr_id


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


def page_to_markdown(
        page: "fitz.Page",
        clip: Optional["fitz.Rect"],
        hdr_prefix: IdentifyHeaders,
        md_options: MarkdownOptions | None = None,
        pdf_options: PdfOptions | None = None,
) -> str:
    """Convert text from a page region to Markdown format.

    Extracts and processes text within the specified clipping rectangle,
    applying Markdown formatting for headers, emphasis, code blocks, and links.
    Handles various text styling including bold, italic, headers, and monospace fonts.

    Parameters
    ----------
    page : fitz.Page
        PDF page object to extract text from
    clip : fitz.Rect or None
        Clipping rectangle to limit text extraction. If None, uses entire page.
    hdr_prefix : IdentifyHeaders
        Header identification object for determining header levels
    md_options : MarkdownOptions or None, optional
        Markdown formatting options including character escaping preferences

    Returns
    -------
    str
        Markdown-formatted text content from the specified page region

    Notes
    -----
    - Recognizes headers, body text, code blocks, inline code styling
    - Handles bold, italic, and bold-italic text formatting
    - Provides basic support for ordered and unordered lists
    - Processes hyperlinks and converts them to Markdown link format
    - Detects code blocks using monospace font analysis
    """
    import fitz

    output_parts = []  # Performance optimization: use list instead of string concatenation
    code = False  # mode indicator: outputting code

    # extract URL type links on page
    links = [line for line in page.get_links() if line["kind"] == 2]

    blocks = page.get_text(
        "dict",
        clip=clip,
        flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_DEHYPHENATE,  # Use PyMuPDF's built-in dehyphenation
        sort=False,
    )["blocks"]

    # Apply column detection if enabled
    if pdf_options and pdf_options.detect_columns:
        columns: list[list[dict]] = detect_columns(blocks, pdf_options.column_gap_threshold)
        # Process blocks column by column for proper reading order
        blocks_to_process = []
        for column in columns:
            # Sort blocks within column by y-coordinate (top to bottom)
            column_sorted = sorted(column, key=lambda b: b.get("bbox", [0, 0, 0, 0])[1])
            blocks_to_process.extend(column_sorted)
    else:
        blocks_to_process = blocks

    for block in blocks_to_process:  # iterate textblocks
        previous_y = 0
        for line in block["lines"]:  # iterate lines in block
            # Handle rotated text if enabled, otherwise skip non-horizontal lines
            if line["dir"][1] != 0:  # non-horizontal lines
                if pdf_options and pdf_options.handle_rotated_text:
                    rotated_text = handle_rotated_text(line, md_options)
                    if rotated_text.strip():
                        output_parts.append(rotated_text + "\n\n")
                continue
            spans = list(line["spans"])

            this_y = line["bbox"][3]  # current bottom coord

            # check for still being on same line
            same_line = abs(this_y - previous_y) <= DEFAULT_OVERLAP_THRESHOLD_PX and previous_y > 0

            if same_line and output_parts and output_parts[-1].endswith("\n"):
                output_parts[-1] = output_parts[-1][:-1]

            # are all spans in line in a mono-spaced font?
            all_mono = all(s["flags"] & 8 for s in spans)

            # compute text of the line
            text = "".join([s["text"] for s in spans])
            if not same_line:
                previous_y = this_y
                if not (output_parts and output_parts[-1].endswith("\n")):
                    output_parts.append("\n")

            if all_mono:
                # compute approx. distance from left - assuming a width
                # of 0.5*fontsize.
                delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (spans[0]["size"] * 0.5))
                if not code:  # if not already in code output  mode:
                    output_parts.append("```")  # switch on "code" mode
                    code = True
                if not same_line:  # new code line with left indentation
                    output_parts.append("\n" + " " * delta + text + " ")
                    previous_y = this_y
                else:  # same line, simply append
                    output_parts.append(text + " ")
                continue  # done with this line

            for i, s in enumerate(spans):  # iterate spans of the line
                # Get text since last line for header detection
                full_output = "".join(output_parts)
                since_last_line = full_output[full_output.rindex("\n") + 1:] if "\n" in full_output else full_output
                # if since_last_line:
                #     print(since_last_line)
                # this line is not all-mono, so switch off "code" mode
                if code:  # still in code output mode?
                    output_parts.append("```\n")  # switch of code mode
                    code = False
                # decode font properties
                mono = s["flags"] & 8
                bold = s["flags"] & 16
                italic = s["flags"] & 2

                if mono:
                    # this is text in some monospaced font
                    output_parts.append(f"`{s['text'].strip()}` ")
                else:  # not a mono text
                    # for first span, get header prefix string if present
                    hdr_string = hdr_prefix.get_header_id(s) if i == 0 else ""

                    if hdr_string and "#" in since_last_line:
                        hdr_string = ""

                    prefix = ""
                    suffix = ""
                    if hdr_string == "" and "#" not in since_last_line:
                        if bold:
                            prefix = "**"
                            suffix += "**"
                        if italic:
                            prefix += "_"
                            suffix = "_" + suffix

                    ltext = resolve_links(links, s, md_options)
                    if ltext:
                        text = f"{hdr_string}{prefix}{ltext}{suffix} "
                    else:
                        span_text = s["text"].strip()
                        if md_options and md_options.escape_special:
                            span_text = escape_markdown_special(span_text)
                        text = f"{hdr_string}{prefix}{span_text}{suffix} "
                    text = (
                        text.replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace(chr(0xF0B7), "-")
                        .replace(chr(0xB7), "-")
                        .replace(chr(8226), "-")
                        .replace(chr(9679), "-")
                    )

                    output_parts.append(text)
            previous_y = this_y
            if not code:
                output_parts.append("\n")
        output_parts.append("\n")
    if code:
        if not (output_parts and output_parts[-1].endswith("```")):
            output_parts.append("```\n")  # switch of code mode
        code = False

    return "".join(output_parts).replace(" \n", "\n")


def extract_page_images(
        page: "fitz.Page", page_num: int, options: PdfOptions | None = None, base_filename: str = "document"
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

            # Process image using unified attachment handling
            img_bytes = pix_rgb.tobytes("png")
            img_filename = generate_attachment_filename(
                base_stem=base_filename,
                format_type="pdf",
                page_num=page_num + 1,  # Convert to 1-based
                sequence_num=img_idx + 1,
                extension="png"
            )

            image_path = process_attachment(
                attachment_data=img_bytes,
                attachment_name=img_filename,
                alt_text=f"Image from page {page_num + 1}",
                attachment_mode=options.attachment_mode,
                attachment_output_dir=options.attachment_output_dir,
                attachment_base_url=options.attachment_base_url,
                is_image=True,
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
    metadata = DocumentMetadata()

    # PyMuPDF provides metadata as a dictionary
    pdf_meta = doc.metadata if hasattr(doc, 'metadata') else {}

    # Map PDF metadata fields to our standard fields
    if pdf_meta:
        # Helper to get non-empty string values
        def get_non_empty(key1, key2=None):
            val = pdf_meta.get(key1, '')
            if val and val.strip():
                return val.strip()
            if key2:
                val = pdf_meta.get(key2, '')
                if val and val.strip():
                    return val.strip()
            return None

        metadata.title = get_non_empty('title', 'Title')
        metadata.author = get_non_empty('author', 'Author')
        metadata.subject = get_non_empty('subject', 'Subject')
        metadata.creator = get_non_empty('creator', 'Creator')
        metadata.producer = get_non_empty('producer', 'Producer')

        # Handle keywords - may be a string that needs splitting
        keywords = get_non_empty('keywords', 'Keywords')
        if keywords:
            if isinstance(keywords, str):
                # Split by common delimiters
                import re
                metadata.keywords = [k.strip() for k in re.split('[,;]', keywords) if k.strip()]
            elif isinstance(keywords, list):
                metadata.keywords = keywords

        # Handle dates
        creation_date = get_non_empty('creationDate', 'CreationDate')
        if creation_date:
            # PyMuPDF returns dates as strings like "D:20210315120000Z"
            if isinstance(creation_date, str) and creation_date.startswith('D:'):
                # Parse PDF date format
                try:
                    from datetime import datetime
                    # Remove D: prefix and parse
                    date_str = creation_date[2:]
                    if 'Z' in date_str:
                        date_str = date_str.replace('Z', '+0000')
                    # Basic parsing - format is YYYYMMDDHHmmSS
                    if len(date_str) >= 8:
                        year = int(date_str[0:4])
                        month = int(date_str[4:6])
                        day = int(date_str[6:8])
                        metadata.creation_date = datetime(year, month, day)
                except (ValueError, IndexError):
                    metadata.creation_date = creation_date
            else:
                metadata.creation_date = creation_date

        mod_date = get_non_empty('modDate', 'ModDate')
        if mod_date:
            # Same parsing as creation date
            if isinstance(mod_date, str) and mod_date.startswith('D:'):
                try:
                    from datetime import datetime
                    date_str = mod_date[2:]
                    if 'Z' in date_str:
                        date_str = date_str.replace('Z', '+0000')
                    if len(date_str) >= 8:
                        year = int(date_str[0:4])
                        month = int(date_str[4:6])
                        day = int(date_str[6:8])
                        metadata.modification_date = datetime(year, month, day)
                except (ValueError, IndexError):
                    metadata.modification_date = mod_date
            else:
                metadata.modification_date = mod_date

        # Store any additional PDF-specific metadata
        for key, value in pdf_meta.items():
            if key not in ['title', 'Title', 'author', 'Author', 'subject', 'Subject',
                           'creator', 'Creator', 'producer', 'Producer', 'keywords', 'Keywords',
                           'creationDate', 'CreationDate', 'modDate', 'ModDate', 'format',
                           'trapped', 'encryption']:  # Skip internal PDF fields
                if value and str(value).strip():  # Only include non-empty values
                    metadata.custom[key] = value

    return metadata


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

    hdr_prefix = IdentifyHeaders(doc, pages=pages_to_use if isinstance(pages_to_use, list) else None, options=options)
    md_string = ""

    for pno in pages_to_use:
        page = doc[pno]

        # Extract images for all attachment modes except "skip"
        page_images = []
        if options.attachment_mode != "skip":
            page_images = extract_page_images(page, pno, options, base_filename)

        # 1. first locate all tables on page
        tabs = page.find_tables()

        # Use fallback table detection if enabled and no tables found
        if options.table_fallback_detection and not tabs.tables:
            _fallback_rects = detect_tables_by_ruling_lines(page, options.table_ruling_line_threshold)
            # Note: We can't create actual table objects from fallback detection,
            # but we can mark these regions for special processing

        # 2. make a list of table boundary boxes, sort by top-left corner.
        # Must include the header bbox, which may be external.
        tab_rects = sorted(
            [(fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox), i) for i, t in enumerate(tabs.tables)],
            key=lambda r: (r[0].y0, r[0].x0),
        )

        # 3. final list of all text and table rectangles
        text_rects = []
        # compute rectangles outside tables and fill final rect list
        for i, (r, idx) in enumerate(tab_rects):
            if i == 0:  # compute rect above all tables
                tr = page.rect
                tr.y1 = r.y0
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))
                text_rects.append(("table", r, idx))
                continue
            # read previous rectangle in final list: always a table!
            _, r0, idx0 = text_rects[-1]

            # check if a non-empty text rect is fitting in between tables
            tr = page.rect
            tr.y0 = r0.y1
            tr.y1 = r.y0
            if not tr.is_empty:  # empty if two tables overlap vertically!
                text_rects.append(("text", tr, 0))

            text_rects.append(("table", r, idx))

            # there may also be text below all tables
            if i == len(tab_rects) - 1:
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))

        if not text_rects:  # this will happen for table-free pages
            text_rects.append(("text", page.rect, 0))
        else:
            rtype, r, idx = text_rects[-1]
            if rtype == "table":
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))

        # Add image placement markers if enabled
        if page_images and options.image_placement_markers:
            # Sort images by vertical position
            page_images.sort(key=lambda img: img["bbox"].y0)

            # Insert images at appropriate positions
            combined_rects: list[tuple[str, fitz.Rect, Union[int, dict]]] = []
            img_idx = 0

            for rtype, r, idx in text_rects:
                # Check if any images should be placed before this rect
                while img_idx < len(page_images) and page_images[img_idx]["bbox"].y1 <= r.y0:
                    img = page_images[img_idx]
                    combined_rects.append(("image", img["bbox"], img))
                    img_idx += 1

                combined_rects.append((rtype, r, idx))

            # Add remaining images
            while img_idx < len(page_images):
                img = page_images[img_idx]
                combined_rects.append(("image", img["bbox"], img))
                img_idx += 1

            text_rects = combined_rects  # type: ignore[assignment]

        # we have all rectangles and can start outputting their contents
        for rtype, r, idx in text_rects:
            if rtype == "text":  # a text rectangle
                md_string += page_to_markdown(page, r, hdr_prefix, md_options, options)  # write MD content
                md_string += "\n"
            elif rtype == "table":  # a table rect
                md_string += tabs[idx].to_markdown(clean=False)
            elif rtype == "image":  # an image
                img_info = idx  # type: ignore[assignment]  # In this case, idx contains the image info dict
                if isinstance(img_info, dict):  # Type guard
                    if img_info["path"].startswith("data:"):
                        # Embedded base64 image
                        md_string += f"![{img_info.get('caption', 'Image')}]({img_info['path']})\n"
                    else:
                        # File path
                        md_string += f"![{img_info.get('caption', 'Image')}]({img_info['path']})\n"
                    if img_info.get("caption"):
                        md_string += f"*{img_info['caption']}*\n"
                md_string += "\n"

        # Add customizable page separator
        if md_options.include_page_numbers:
            separator = md_options.page_separator_format.replace("{page_num}", str(pno + 1))
            md_string += f"\n{separator}\n\n"
        else:
            md_string += f"\n{md_options.page_separator}\n\n"

    # Prepend metadata if enabled
    md_string = prepend_metadata_if_enabled(md_string, metadata, options.extract_metadata)

    return md_string
