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
import string
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import fitz

from all2md.ast import (
    Code,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
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
)
from all2md.options import PdfOptions
from all2md.utils.inputs import escape_markdown_special

logger = logging.getLogger(__name__)

# Used to check relevance of text pieces
SPACES = set(string.whitespace)


class PdfToAstConverter:
    """Convert PDF to AST representation.

    This converter parses PDF documents using PyMuPDF and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : PdfOptions or None, default = None
        Conversion options
    doc : fitz.Document
        PDF document to convert
    base_filename : str
        Base filename for image attachments
    attachment_sequencer : callable or None
        Sequencer for generating attachment filenames
    hdr_identifier : IdentifyHeaders or None
        Header identification object for determining header levels

    """

    def __init__(
        self,
        options: PdfOptions | None = None,
        doc: "fitz.Document | None" = None,
        base_filename: str = "document",
        attachment_sequencer: Any = None,
        hdr_identifier: Any = None,
    ):
        self.options = options or PdfOptions()
        self.doc = doc
        self.base_filename = base_filename
        self.attachment_sequencer = attachment_sequencer
        self.hdr_identifier = hdr_identifier
        self._current_page_num = 0

    def convert_to_ast(self, doc: "fitz.Document", pages_to_use: range | list[int]) -> Document:
        """Convert PDF document to AST Document.

        Parameters
        ----------
        doc : fitz.Document
            PDF document to convert
        pages_to_use : range or list of int
            Pages to process

        Returns
        -------
        Document
            AST document node

        """
        import fitz
        from all2md.ast import HTMLBlock

        self.doc = doc
        self._total_pages = len(list(pages_to_use))
        children: list[Node] = []

        pages_list = list(pages_to_use)
        for idx, pno in enumerate(pages_list):
            self._current_page_num = pno
            page = doc[pno]
            page_nodes = self._process_page_to_ast(page, pno)
            if page_nodes:
                children.extend(page_nodes)

            # Add page separator between pages (but not after the last page)
            if idx < len(pages_list) - 1:
                # Add special marker for page separator
                # Format: <!-- PAGE_SEP:{page_num}/{total_pages} -->
                sep_marker = f"<!-- PAGE_SEP:{pno + 1}/{self._total_pages} -->"
                children.append(HTMLBlock(content=sep_marker))

        return Document(children=children)

    def _process_page_to_ast(self, page: "fitz.Page", page_num: int) -> list[Node]:
        """Process a PDF page to AST nodes.

        Parameters
        ----------
        page : fitz.Page
            PDF page to process
        page_num : int
            Page number (0-based)

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
            from all2md.parsers.pdf2markdown import extract_page_images
            page_images = extract_page_images(
                page, page_num, self.options, self.base_filename, self.attachment_sequencer
            )

        # 1. Locate all tables on page based on table_detection_mode
        tabs = None
        mode = self.options.table_detection_mode.lower()

        if mode == "none":
            # No table detection
            class EmptyTables:
                tables = []
            tabs = EmptyTables()
        elif mode == "pymupdf":
            # Only use PyMuPDF table detection
            tabs = page.find_tables()
        elif mode == "ruling":
            # Only use ruling line detection (fallback method)
            from all2md.parsers.pdf2markdown import detect_tables_by_ruling_lines
            _fallback_rects = detect_tables_by_ruling_lines(page, self.options.table_ruling_line_threshold)
            # Fallback detection returns rects but not actual table objects we can use
            # For now, just use empty tables (future: could convert rects to table objects)
            class EmptyTables:
                tables = []
            tabs = EmptyTables()
        else:  # "both" or default
            # Use PyMuPDF first, fallback to ruling if needed
            tabs = page.find_tables()
            if self.options.enable_table_fallback_detection and not tabs.tables:
                from all2md.parsers.pdf2markdown import detect_tables_by_ruling_lines
                _fallback_rects = detect_tables_by_ruling_lines(page, self.options.table_ruling_line_threshold)

        # 2. Make a list of table boundary boxes, sort by top-left corner
        tab_rects = sorted(
            [(fitz.Rect(t.bbox) | fitz.Rect(t.header.bbox), i) for i, t in enumerate(tabs.tables)],
            key=lambda r: (r[0].y0, r[0].x0),
        )

        # 3. Final list of all text and table rectangles
        text_rects = []
        # Compute rectangles outside tables and fill final rect list
        for i, (r, idx) in enumerate(tab_rects):
            if i == 0:  # Compute rect above all tables
                tr = page.rect
                tr.y1 = r.y0
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))
                text_rects.append(("table", r, idx))
                continue
            # Read previous rectangle in final list: always a table
            _, r0, idx0 = text_rects[-1]

            # Check if a non-empty text rect is fitting in between tables
            tr = page.rect
            tr.y0 = r0.y1
            tr.y1 = r.y0
            if not tr.is_empty:  # Empty if two tables overlap vertically
                text_rects.append(("text", tr, 0))

            text_rects.append(("table", r, idx))

            # There may also be text below all tables
            if i == len(tab_rects) - 1:
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))

        if not text_rects:  # This will happen for table-free pages
            text_rects.append(("text", page.rect, 0))
        else:
            rtype, r, idx = text_rects[-1]
            if rtype == "table":
                tr = page.rect
                tr.y0 = r.y1
                if not tr.is_empty:
                    text_rects.append(("text", tr, 0))

        # Add image placement markers if enabled
        if page_images and self.options.image_placement_markers:
            # Sort images by vertical position
            page_images.sort(key=lambda img: img["bbox"].y0)

            # Insert images at appropriate positions
            combined_rects: list[tuple[str, fitz.Rect, int | dict]] = []
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

        # Process all rectangles and convert to AST nodes
        for rtype, r, idx in text_rects:
            if rtype == "text":  # A text rectangle
                text_nodes = self._process_text_region_to_ast(page, r, page_num)
                if text_nodes:
                    nodes.extend(text_nodes)
            elif rtype == "table":  # A table rect
                table_node = self._process_table_to_ast(tabs[idx], page_num)
                if table_node:
                    nodes.append(table_node)
            elif rtype == "image":  # An image
                # idx contains image info dict in this case
                if isinstance(idx, dict):  # Type guard
                    img_node = self._create_image_node(idx, page_num)
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
            from all2md.parsers.pdf2markdown import detect_columns
            columns: list[list[dict]] = detect_columns(blocks, self.options.column_gap_threshold)
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
                        from all2md.parsers.pdf2markdown import handle_rotated_text
                        rotated_text = handle_rotated_text(line, self.options.markdown_options)
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
                if self.hdr_identifier:
                    header_level = self.hdr_identifier.get_header_level(first_span)

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
                # Escape markdown special characters if enabled
                if self.options.markdown_options and self.options.markdown_options.escape_special:
                    span_text = escape_markdown_special(span_text)

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

        """
        if not links or not span.get("text"):
            return None

        import fitz
        bbox = fitz.Rect(span["bbox"])

        # Find all links that overlap with this span
        for link in links:
            hot = link["from"]  # The hot area of the link
            overlap = hot & bbox
            bbox_area = (DEFAULT_OVERLAP_THRESHOLD_PERCENT / 100.0) * abs(bbox)
            if abs(overlap) >= bbox_area:
                return link.get("uri")

        return None

    def _process_table_to_ast(self, table: Any, page_num: int) -> AstTable | None:
        """Process a PyMuPDF table to AST Table node.

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
        # PyMuPDF's table has to_markdown() method
        # We'll parse the markdown output to extract table structure
        # Alternative: Extract cells directly from table object

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
            logger.debug(f"Failed to process table: {e}")
            return None

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
