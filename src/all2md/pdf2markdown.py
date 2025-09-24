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

    >>> from all2md.pdf2markdown import pdf_to_markdown
    >>> markdown_content = pdf_to_markdown("document.pdf")

Convert specific pages with options:

    >>> from all2md.options import PdfOptions
    >>> options = PdfOptions(pages=[0, 1, 2], convert_images_to_base64=True)
    >>> content = pdf_to_markdown("document.pdf", options=options)

Convert from file-like object:

    >>> from io import BytesIO
    >>> with open("document.pdf", "rb") as f:
    ...     content = pdf_to_markdown(BytesIO(f.read()))

Original from pdf4llm package, modified by Tom Villani to improve table processing.

---

This script accepts a PDF document filename and converts it to a text file
in Markdown format, compatible with the GitHub standard.

It must be invoked with the filename like this:

python pymupdf_rag.py input.pdf [-pages PAGES]

The "PAGES" parameter is a string (containing no spaces) of comma-separated
page numbers to consider. Each item is either a single page number or a
number range "m-n". Use "N" to address the document's last page number.
Example: "-pages 2-15,40,43-N"

It will produce a markdown text file called "input.md".

Text will be sorted in Western reading order. Any table will be included in
the text in markdwn format as well.

Use in some other script
-------------------------
import fitz
from to_markdown import to_markdown

doc = fitz.open("input.pdf")
page_list = [ list of 0-based page numbers ]
md_text = to_markdown(doc, pages=page_list)

Dependencies
-------------
PyMuPDF v1.24.0 or later

Copyright and License
----------------------
Copyright 2024 Artifex Software, Inc.
License GNU Affero GPL 3.0
"""

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

import re
import string
from io import BytesIO
from pathlib import Path
from typing import Union

import fitz

from ._input_utils import escape_markdown_special, validate_and_convert_input, validate_page_range
from .constants import (
    DEFAULT_OVERLAP_THRESHOLD_PERCENT,
    DEFAULT_OVERLAP_THRESHOLD_PX,
    PDF_MIN_PYMUPDF_VERSION,
)
from .exceptions import MdparseConversionError, MdparseInputError, MdparsePasswordError
from .options import MarkdownOptions, PdfOptions


def _check_pymupdf_version() -> None:
    """Check that PyMuPDF version meets minimum requirements.

    Raises
    ------
    MdparseConversionError
        If PyMuPDF version is too old
    """
    min_version = tuple(map(int, PDF_MIN_PYMUPDF_VERSION.split('.')))
    if fitz.pymupdf_version_tuple < min_version:
        raise MdparseConversionError(
            f"PyMuPDF version {PDF_MIN_PYMUPDF_VERSION} or later is required, "
            f"but {'.'.join(map(str, fitz.pymupdf_version_tuple))} is installed."
        )

_check_pymupdf_version()

SPACES = set(string.whitespace)  # used to check relevance of text pieces
paragraph_fixer = re.compile(r"(?<!\n)\n(?!\n)")


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

    Attributes
    ----------
    header_id : dict[int, str]
        Mapping from font size to markdown header prefix string
    """

    def __init__(self, doc: fitz.Document, pages: list[int] | range | None = None, body_limit: float | None = None) -> None:
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
        """
        pages_to_use: range | list[int] = pages if pages is not None else range(doc.page_count)
        fontsizes: dict[int, int] = {}
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
                count = fontsizes.get(fontsz, 0) + len(span["text"].strip())
                fontsizes[fontsz] = count

        # maps a fontsize to a string of multiple # header tag characters
        self.header_id = {}

        # If not provided, choose the most frequent font size as body text.
        # If no text at all on all pages, just use 12
        if body_limit is None:
            temp = sorted(
                fontsizes.items(),
                key=lambda i: i[1],
                reverse=True,
            )
            body_limit = temp[0][0] if temp else 12

        sizes = sorted([f for f in fontsizes if f > body_limit], reverse=True)

        # make the header tag dictionary
        for i, size in enumerate(sizes):
            self.header_id[size] = "#" * (i + 1) + " "

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
        return hdr_id


def resolve_links(links: list, span: dict, md_options: MarkdownOptions | None = None) -> str | None:
    """Accept a span bbox and return a markdown link string.

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
    bbox = fitz.Rect(span["bbox"])  # span bbox
    # a link should overlap at least {DEFAULT_OVERLAP_THRESHOLD_PERCENT}% of the span
    bbox_area = (DEFAULT_OVERLAP_THRESHOLD_PERCENT / 100.0) * abs(bbox)
    for link in links:
        hot = link["from"]  # the hot area of the link
        if not abs(hot & bbox) >= bbox_area:
            continue  # does not touch the bbox
        link_text = span['text'].strip()
        if md_options and md_options.escape_special:
            link_text = escape_markdown_special(link_text, md_options.bullet_symbols)
        text = f"[{link_text}]({link['uri']})"
        return text
    return None


def page_to_markdown(page: fitz.Page, clip: fitz.Rect | None, hdr_prefix: IdentifyHeaders, md_options: MarkdownOptions | None = None) -> str:
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
    out_string = ""
    code = False  # mode indicator: outputting code

    # extract URL type links on page
    links = [line for line in page.get_links() if line["kind"] == 2]

    blocks = page.get_text(
        "dict",
        clip=clip,
        flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_DEHYPHENATE,
        sort=False,
    )["blocks"]

    for block in blocks:  # iterate textblocks
        previous_y = 0
        for line in block["lines"]:  # iterate lines in block
            if line["dir"][1] != 0:  # only consider horizontal lines
                continue
            spans = list(line["spans"])

            this_y = line["bbox"][3]  # current bottom coord

            # check for still being on same line
            same_line = abs(this_y - previous_y) <= DEFAULT_OVERLAP_THRESHOLD_PX and previous_y > 0

            if same_line and out_string.endswith("\n"):
                out_string = out_string[:-1]

            # are all spans in line in a mono-spaced font?
            all_mono = all(s["flags"] & 8 for s in spans)

            # compute text of the line
            text = "".join([s["text"] for s in spans])
            if not same_line:
                previous_y = this_y
                if not out_string.endswith("\n"):
                    out_string += "\n"

            if all_mono:
                # compute approx. distance from left - assuming a width
                # of 0.5*fontsize.
                delta = int((spans[0]["bbox"][0] - block["bbox"][0]) / (spans[0]["size"] * 0.5))
                if not code:  # if not already in code output  mode:
                    out_string += "```"  # switch on "code" mode
                    code = True
                if not same_line:  # new code line with left indentation
                    out_string += "\n" + " " * delta + text + " "
                    previous_y = this_y
                else:  # same line, simply append
                    out_string += text + " "
                continue  # done with this line

            for i, s in enumerate(spans):  # iterate spans of the line
                since_last_line = out_string[out_string.rindex("\n") + 1 :] if "\n" in out_string else ""
                # if since_last_line:
                #     print(since_last_line)
                # this line is not all-mono, so switch off "code" mode
                if code:  # still in code output mode?
                    out_string += "```\n"  # switch of code mode
                    code = False
                # decode font properties
                mono = s["flags"] & 8
                bold = s["flags"] & 16
                italic = s["flags"] & 2

                if mono:
                    # this is text in some monospaced font
                    out_string += f"`{s['text'].strip()}` "
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
                        span_text = s['text'].strip()
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

                    out_string += text
            previous_y = this_y
            if not code:
                out_string += "\n"
        out_string += "\n"
    if code:
        if not out_string.endswith("```"):
            out_string += "```\n"  # switch of code mode
        code = False

    return out_string.replace(" \n", "\n")


def parse_page(page: fitz.Page) -> list[tuple[str, fitz.Rect, int]]:
    """Parse a PDF page to identify text and table regions with their locations.

    Analyzes a PDF page to locate all tables and compute text regions that
    exist outside of table boundaries. Returns a list of rectangular regions
    with type identifiers and indices for processing in reading order.

    The function processes the page by:
    1. Finding all tables using PyMuPDF's table detection
    2. Computing table boundary boxes including headers
    3. Identifying text regions between and around tables
    4. Returning regions sorted in reading order (top to bottom)

    Parameters
    ----------
    page : fitz.Page
        PyMuPDF page object to parse for text and table regions.

    Returns
    -------
    list[tuple[str, fitz.Rect, int]]
        List of tuples containing:
        - str: region type ("text" or "table")
        - fitz.Rect: bounding rectangle for the region
        - int: table index (0 for text regions, table index for tables)

    Notes
    -----
    - Tables are detected using PyMuPDF's find_tables() method
    - Text regions are computed as areas not covered by tables
    - Regions are ordered by vertical position (y-coordinate)
    - Empty regions are automatically filtered out
    - Handles pages with no tables by returning single text region
    - Table headers are included in table boundary calculations
    """
    # 1. first locate all tables on page
    tabs = page.find_tables()
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

    return text_rects


def pdf_to_markdown(
    input_data: Union[str, BytesIO, fitz.Document],
    options: PdfOptions | None = None,
    pages: list[int] | None = None,  # Deprecated, use options.pages
    convert_images_to_base64: bool | None = None,  # Deprecated, use options.convert_images_to_base64
    password: str | None = None  # Deprecated, use options.password
) -> str:
    """Convert PDF document to Markdown format.

    This function processes PDF documents and converts them to well-formatted
    Markdown with support for headers, tables, links, and code blocks. It uses
    PyMuPDF's advanced table detection and preserves document structure.

    Parameters
    ----------
    input_data : str, BytesIO, or fitz.Document
        PDF document to convert. Can be:
        - String path to PDF file
        - BytesIO object containing PDF data
        - Already opened PyMuPDF Document object
    options : PdfOptions or None, default None
        Configuration options for PDF conversion. If None, uses default settings.
    pages : list[int] or None, optional
        **Deprecated**: Use options.pages instead.
        List of 0-based page numbers to convert. If None, converts all pages.
    convert_images_to_base64 : bool or None, optional
        **Deprecated**: Use options.convert_images_to_base64 instead.
        Whether to embed images as base64-encoded data URLs.
    password : str or None, optional
        **Deprecated**: Use options.password instead.
        Password for encrypted PDF documents.

    Returns
    -------
    str
        Markdown-formatted text content of the PDF document.

    Raises
    ------
    MdparseInputError
        If input type is not supported or page numbers are invalid
    MdparsePasswordError
        If PDF is password-protected and no/incorrect password provided
    MdparseConversionError
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
        >>> options = PdfOptions(pages=[0, 1, 2], convert_images_to_base64=True)
        >>> content = pdf_to_markdown("document.pdf", options=options)

    Convert from BytesIO with password:

        >>> from io import BytesIO
        >>> with open("encrypted.pdf", "rb") as f:
        ...     data = BytesIO(f.read())
        >>> options = PdfOptions(password="secret123")
        >>> content = pdf_to_markdown(data, options=options)
    """

    # Handle backward compatibility and merge options
    if options is None:
        options = PdfOptions()

    # Handle deprecated parameters (with deprecation warnings would be ideal)
    if pages is not None and options.pages is None:
        options.pages = pages
    if convert_images_to_base64 is not None and options.convert_images_to_base64 is None:
        options.convert_images_to_base64 = convert_images_to_base64
    if password is not None and options.password is None:
        options.password = password

    # Validate and convert input
    doc_input, input_type = validate_and_convert_input(
        input_data,
        supported_types=["path-like", "file-like (BytesIO)", "fitz.Document objects"]
    )

    # Open document based on input type
    try:
        if input_type == "path":
            doc = fitz.open(filename=str(doc_input))
        elif input_type in ("file", "bytes"):
            doc = fitz.open(stream=doc_input)
        elif input_type == "object":
            if isinstance(doc_input, fitz.Document):
                doc = doc_input
            else:
                raise MdparseInputError(
                    f"Expected fitz.Document object, got {type(doc_input).__name__}",
                    parameter_name="input_data",
                    parameter_value=doc_input
                )
        else:
            raise MdparseInputError(
                f"Unsupported input type: {input_type}",
                parameter_name="input_data",
                parameter_value=doc_input
            )
    except Exception as e:
        if "password" in str(e).lower() or "encrypt" in str(e).lower():
            filename = str(input_data) if isinstance(input_data, (str, Path)) else None
            raise MdparsePasswordError(filename=filename) from e
        else:
            raise MdparseConversionError(
                f"Failed to open PDF document: {str(e)}",
                conversion_stage="document_opening",
                original_error=e
            ) from e

    # Validate page range
    try:
        validated_pages = validate_page_range(options.pages, doc.page_count)
        pages_to_use: range | list[int] = validated_pages if validated_pages else range(doc.page_count)
    except Exception as e:
        raise MdparseInputError(
            f"Invalid page range: {str(e)}",
            parameter_name="pages",
            parameter_value=options.pages
        ) from e

    # Get Markdown options (create default if not provided)
    md_options = options.markdown_options or MarkdownOptions()

    hdr_prefix = IdentifyHeaders(doc, pages=pages_to_use if isinstance(pages_to_use, list) else pages)
    md_string = ""

    for pno in pages_to_use:
        page = doc[pno]
        # 1. first locate all tables on page
        tabs = page.find_tables()

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

        # we have all rectangles and can start outputting their contents
        for rtype, r, idx in text_rects:
            if rtype == "text":  # a text rectangle
                md_string += page_to_markdown(page, r, hdr_prefix, md_options)  # write MD content
                md_string += "\n"
            else:  # a table rect
                md_string += tabs[idx].to_markdown(clean=False)

        md_string += f"\n{md_options.page_separator}\n\n"

    return md_string
