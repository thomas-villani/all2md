"""
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

import fitz

if fitz.pymupdf_version_tuple < (1, 24, 0):
    raise NotImplementedError("PyMuPDF version 1.24.0 or later is needed.")

SPACES = set(string.whitespace)  # used to check relevance of text pieces
paragraph_fixer = re.compile(r"(?<!\n)\n(?!\n)")


class IdentifyHeaders:
    """Compute data for identifying header text."""

    def __init__(self, doc: fitz.Document, pages: list[int] | range | None = None, body_limit: float | None = None) -> None:
        """Read all text and make a dictionary of fontsizes.

        Args:
            pages: optional list of pages to consider
            body_limit: consider text with larger font size as some header
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
        """Return appropriate markdown header prefix.

        Given a text span from a "dict"/"radict" extraction, determine the
        markdown header prefix string of 0 to many concatenated '#' characters.
        """
        fontsize = round(span["size"])  # compute fontsize
        hdr_id = self.header_id.get(fontsize, "")
        return hdr_id


def resolve_links(links: list, span: dict) -> str | None:
    """Accept a span bbox and return a markdown link string."""
    bbox = fitz.Rect(span["bbox"])  # span bbox
    # a link should overlap at least 70% of the span
    bbox_area = 0.7 * abs(bbox)
    for link in links:
        hot = link["from"]  # the hot area of the link
        if not abs(hot & bbox) >= bbox_area:
            continue  # does not touch the bbox
        text = f"[{span['text'].strip()}]({link['uri']})"
        return text
    return None


def page_to_markdown(page: fitz.Page, clip: fitz.Rect | None, hdr_prefix: IdentifyHeaders) -> str:
    """Output the text found inside the given clip.

    This is an alternative for plain text in that it outputs
    text enriched with markdown styling.
    The logic is capable of recognizing headers, body text, code blocks,
    inline code, bold, italic and bold-italic styling.
    There is also some effort for list supported (ordered / unordered) in
    that typical characters are replaced by respective markdown characters.
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
            same_line = abs(this_y - previous_y) <= 5 and previous_y > 0

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

                    ltext = resolve_links(links, s)
                    if ltext:
                        text = f"{hdr_string}{prefix}{ltext}{suffix} "
                    else:
                        text = f"{hdr_string}{prefix}{s['text'].strip()}{suffix} "
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


def pdf_to_markdown(doc: fitz.Document | BytesIO | str, pages: list[int] | None = None) -> str:
    """Process the document and return the text of its pages.

    Will attempt to find tables and parse them in-line.

    .. Note:: Occasionally tables end up out of order compared to their original position in the text,
              and complex tables can cause issues with breaking into multiple tables.


    Parameters
    ----------
    doc : fitz.Document | BytesIO | str
        Source document to process
    pages : list[int]
        List of page numbers to process (0-indexed)

    Returns
    -------
    str
        Markdown version of PDF.

    """

    if isinstance(doc, str):
        doc = fitz.open(filename=doc)
    elif isinstance(doc, BytesIO):
        doc = fitz.open(stream=doc)

    pages_to_use: range | list[int] = pages if pages else range(doc.page_count)

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
                md_string += page_to_markdown(page, r, hdr_prefix)  # write MD content
                md_string += "\n"
            else:  # a table rect
                md_string += tabs[idx].to_markdown(clean=False)

        md_string += "\n-----\n\n"

    return md_string
