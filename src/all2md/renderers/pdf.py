#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/pdf.py
"""PDF rendering from AST.

This module provides the PdfRenderer class which converts AST nodes
to PDF format using the ReportLab library. The renderer uses the Platypus
framework for high-level layout and automatic page breaking.

The rendering process uses the visitor pattern to traverse the AST and
generate PDF flowables (paragraphs, tables, images, etc.) that are then
assembled into a complete PDF document.

"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from reportlab.lib.styles import StyleSheet1
    from reportlab.platypus import Flowable

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Document,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    LineBreak,
    Link,
    List,
    MathBlock,
    MathInline,
    Node,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Table,
    TableCell,
    TableRow,
    Text,
    ThematicBreak,
    Underline,
)
from all2md.ast.nodes import (
    Image as ASTImage,
)
from all2md.ast.nodes import (
    ListItem as ASTListItem,
)
from all2md.ast.nodes import (
    Paragraph as ASTParagraph,
)
from all2md.ast.visitors import NodeVisitor
from all2md.constants import DEPS_PDF_RENDER
from all2md.exceptions import RenderingError
from all2md.options.pdf import PdfRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.images import decode_base64_image_to_file
from all2md.utils.network_security import fetch_image_securely, is_network_disabled

logger = logging.getLogger(__name__)


class PdfRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to PDF format.

    This class implements the visitor pattern to traverse an AST and
    generate a PDF document using ReportLab's Platypus framework. It
    supports most common formatting features and automatic page layout.

    Parameters
    ----------
    options : PdfRendererOptions or None, default = None
        PDF rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.options.pdf import PdfRendererOptions        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.pdf import PdfRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = PdfRendererOptions()
        >>> renderer = PdfRenderer(options)
        >>> renderer.render(doc, "output.pdf")

    """

    def __init__(self, options: PdfRendererOptions | None = None):
        """Initialize the PDF renderer with options."""
        BaseRenderer._validate_options_type(options, PdfRendererOptions, "pdf")
        options = options or PdfRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: PdfRendererOptions = options
        self._flowables: list[Flowable] = []
        # _styles is initialized in render() before any visitor methods are called
        self._styles: Any = None
        self._temp_files: list[str] = []
        self._footnote_counter: int = 0
        self._footnote_id_to_number: dict[str, int] = {}
        self._footnote_definitions: dict[str, str] = {}
        self._paragraph_buffer: list[str] | None = None

    @requires_dependencies("pdf_render", DEPS_PDF_RENDER)
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to a PDF file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        RenderingError
            If PDF generation fails

        """
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4, LEGAL, LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            HRFlowable,
            Image,
            ListFlowable,
            ListItem,
            PageBreak,
            Paragraph,
            Preformatted,
            SimpleDocTemplate,
            Spacer,
            TableStyle,
        )
        from reportlab.platypus import (
            Table as ReportLabTable,
        )

        # Store imports as instance variables
        self._colors = colors
        self._TA_CENTER = TA_CENTER
        self._TA_LEFT = TA_LEFT
        self._TA_RIGHT = TA_RIGHT
        self._TA_JUSTIFY = TA_JUSTIFY
        self._A4 = A4
        self._LETTER = LETTER
        self._LEGAL = LEGAL
        self._ParagraphStyle = ParagraphStyle
        self._getSampleStyleSheet = getSampleStyleSheet
        self._inch = inch
        self._HRFlowable = HRFlowable
        self._Image = Image
        self._ListFlowable = ListFlowable
        self._ListItem = ListItem
        self._PageBreak = PageBreak
        self._Paragraph = Paragraph
        self._Preformatted = Preformatted
        self._SimpleDocTemplate = SimpleDocTemplate
        self._Spacer = Spacer
        self._ReportLabTable = ReportLabTable
        self._TableStyle = TableStyle

        try:
            # Reset state
            self._flowables = []
            self._footnote_counter = 0
            self._footnote_id_to_number = {}
            self._footnote_definitions = {}

            # Create styles
            self._styles = self._create_styles()

            # Render document
            doc.accept(self)

            # Add footnotes if any
            if self._footnote_definitions:
                self._flowables.append(self._Spacer(1, 0.3 * self._inch))
                self._flowables.append(self._HRFlowable(width="80%", color=self._colors.grey))
                self._flowables.append(self._Spacer(1, 0.2 * self._inch))

                # Sort footnotes by their assigned numbers
                sorted_footnotes = sorted(self._footnote_id_to_number.items(), key=lambda x: x[1])
                for identifier, num in sorted_footnotes:
                    text = self._footnote_definitions.get(identifier, "")
                    if text:
                        footnote_para = self._Paragraph(
                            f'<font size="8"><sup>{num}</sup> {text}</font>', self._styles["Normal"]
                        )
                        self._flowables.append(footnote_para)
                        self._flowables.append(self._Spacer(1, 0.1 * self._inch))

            # Get page size
            page_size = self._get_page_size()

            # Build common kwargs for SimpleDocTemplate
            doc_kwargs: dict[str, Any] = {
                "pagesize": page_size,
                "rightMargin": self.options.margin_right,
                "leftMargin": self.options.margin_left,
                "topMargin": self.options.margin_top,
                "bottomMargin": self.options.margin_bottom,
            }

            # Set creator metadata if configured
            if self.options.creator:
                doc_kwargs["creator"] = self.options.creator

            # Create PDF document
            if isinstance(output, (str, Path)):
                pdf_doc = self._SimpleDocTemplate(str(output), **doc_kwargs)
            else:
                # For file-like objects, use BytesIO buffer
                buffer = io.BytesIO()
                pdf_doc = self._SimpleDocTemplate(buffer, **doc_kwargs)

            # Build PDF
            pdf_doc.build(self._flowables)

            # Write to file-like object if needed
            if not isinstance(output, (str, Path)):
                buffer.seek(0)
                output.write(buffer.read())
        except Exception as e:
            raise RenderingError(f"Failed to render PDF: {e!r}", rendering_stage="rendering", original_error=e) from e
        finally:
            # Clean up temp files
            self._cleanup_temp_files()

    @requires_dependencies("pdf_render", DEPS_PDF_RENDER)
    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to PDF bytes.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        bytes
            PDF file content as bytes

        Raises
        ------
        RenderingError
            If PDF generation fails

        """
        # Create a BytesIO buffer and render to it
        buffer = io.BytesIO()
        self.render(doc, buffer)

        # Return the bytes content
        return buffer.getvalue()

    def _cleanup_temp_files(self) -> None:
        """Remove temporary files created during rendering."""
        for temp_file in self._temp_files:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {temp_file}: {e}")
        self._temp_files.clear()

    def _get_page_size(self) -> tuple[float, float]:
        """Get page size based on options.

        Returns
        -------
        tuple of float
            (width, height) in points

        """
        size_map = {
            "letter": self._LETTER,
            "a4": self._A4,
            "legal": self._LEGAL,
        }
        return size_map.get(self.options.page_size, self._LETTER)

    def _get_bold_font(self, base_font: str) -> str:
        """Get the bold variant of a font.

        Parameters
        ----------
        base_font : str
            Base font name

        Returns
        -------
        str
            Bold font name

        """
        font_bold_map = {
            "Times-Roman": "Times-Bold",
            "Helvetica": "Helvetica-Bold",
            "Courier": "Courier-Bold",
        }
        return font_bold_map.get(base_font, base_font + "-Bold")

    def _create_styles(self) -> StyleSheet1:
        """Create paragraph styles for the document.

        Returns
        -------
        StyleSheet1
            StyleSheet1 object containing paragraph styles

        """
        styles = self._getSampleStyleSheet()

        # Modify default styles
        styles["Normal"].fontName = self.options.font_name
        styles["Normal"].fontSize = self.options.font_size
        styles["Normal"].leading = self.options.font_size * self.options.line_spacing

        # Create/modify heading styles
        heading_fonts = self.options.heading_fonts or {}

        for level in range(1, 7):
            style_name = f"Heading{level}"
            if level in heading_fonts:
                font_name, font_size = heading_fonts[level]
            else:
                # Default: scale font size based on level
                font_name = self._get_bold_font(self.options.font_name)
                font_size = self.options.font_size + (7 - level) * 2

            # Check if style exists, if not create it
            if style_name in styles:
                # Modify existing style
                style = styles[style_name]
                style.fontName = font_name
                style.fontSize = font_size
                style.leading = font_size * 1.2
                style.spaceAfter = 12
                style.spaceBefore = 12
            else:
                # Create new style
                styles.add(
                    self._ParagraphStyle(
                        name=style_name,
                        parent=styles["Normal"],
                        fontName=font_name,
                        fontSize=font_size,
                        leading=font_size * 1.2,
                        spaceAfter=12,
                        spaceBefore=12,
                    )
                )

        # Create/modify code style
        if "Code" not in styles:
            styles.add(
                self._ParagraphStyle(
                    name="Code",
                    parent=styles["Normal"],
                    fontName=self.options.code_font,
                    fontSize=self.options.font_size - 1,
                    backColor=self._colors.HexColor("#F5F5F5"),
                    leftIndent=10,
                    rightIndent=10,
                    spaceBefore=6,
                    spaceAfter=6,
                )
            )

        # Create/modify blockquote style
        if "BlockQuote" not in styles:
            styles.add(
                self._ParagraphStyle(
                    name="BlockQuote",
                    parent=styles["Normal"],
                    leftIndent=20,
                    rightIndent=20,
                    textColor=self._colors.HexColor("#666666"),
                    borderColor=self._colors.HexColor("#CCCCCC"),
                    borderWidth=1,
                    borderPadding=10,
                )
            )

        return styles

    def _process_inline_content(self, nodes: list[Node]) -> str:
        """Convert inline nodes to ReportLab Paragraph XML.

        Parameters
        ----------
        nodes : list of Node
            Inline nodes to process

        Returns
        -------
        str
            ReportLab Paragraph XML markup

        """
        parts = []
        for node in nodes:
            if isinstance(node, Text):
                # Escape special characters
                text = node.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(text)
            elif isinstance(node, Strong):
                inner = self._process_inline_content(node.content)
                parts.append(f"<b>{inner}</b>")
            elif isinstance(node, Emphasis):
                inner = self._process_inline_content(node.content)
                parts.append(f"<i>{inner}</i>")
            elif isinstance(node, Code):
                escaped = node.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                parts.append(f'<font name="{self.options.code_font}" backColor="#F0F0F0">{escaped}</font>')
            elif isinstance(node, Strikethrough):
                inner = self._process_inline_content(node.content)
                parts.append(f"<strike>{inner}</strike>")
            elif isinstance(node, Underline):
                inner = self._process_inline_content(node.content)
                parts.append(f"<u>{inner}</u>")
            elif isinstance(node, Superscript):
                inner = self._process_inline_content(node.content)
                parts.append(f"<super>{inner}</super>")
            elif isinstance(node, Subscript):
                inner = self._process_inline_content(node.content)
                parts.append(f"<sub>{inner}</sub>")
            elif isinstance(node, Link):
                inner = self._process_inline_content(node.content)
                parts.append(f'<link href="{node.url}">{inner}</link>')
            elif isinstance(node, LineBreak):
                parts.append("<br/>")
            elif isinstance(node, FootnoteReference):
                # Get or assign a stable number for this footnote identifier
                if node.identifier not in self._footnote_id_to_number:
                    self._footnote_counter += 1
                    self._footnote_id_to_number[node.identifier] = self._footnote_counter
                footnote_number = self._footnote_id_to_number[node.identifier]
                parts.append(f"<super>{footnote_number}</super>")
            elif isinstance(node, MathInline):
                # Render math as plain text (proper rendering would require additional libraries)
                content, notation = node.get_preferred_representation("latex")
                if notation == "latex":
                    parts.append(f"${content}$")
                else:
                    parts.append(content)
            else:
                # For other inline nodes, try to extract text
                pass

        return "".join(parts)

    def visit_document(self, node: Document) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        # Add title from metadata if present
        if node.metadata and "title" in node.metadata:
            title_text = str(node.metadata["title"])
            title_para = self._Paragraph(title_text, self._styles["Heading1"])
            self._flowables.append(title_para)
            self._flowables.append(self._Spacer(1, 0.3 * self._inch))

        # Render children
        for child in node.children:
            child.accept(self)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        level = min(6, max(1, node.level))
        style_name = f"Heading{level}"

        text = self._process_inline_content(node.content)
        para = self._Paragraph(text, self._styles[style_name])
        self._flowables.append(para)

    def visit_paragraph(self, node: ASTParagraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        text = self._process_inline_content(node.content)
        para = self._Paragraph(text, self._styles["Normal"])
        self._flowables.append(para)
        self._flowables.append(self._Spacer(1, 0.1 * self._inch))

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        # Use Preformatted for code blocks
        pre = self._Preformatted(
            node.content,
            self._styles["Code"],
            maxLineLength=80,
        )
        self._flowables.append(pre)
        self._flowables.append(self._Spacer(1, 0.1 * self._inch))

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        # Save current flowables
        saved_flowables = self._flowables
        self._flowables = []

        # Render children
        for child in node.children:
            child.accept(self)

        # Wrap in indented container (simplified approach)
        for flowable in self._flowables:
            if isinstance(flowable, self._Paragraph):
                # Re-create with BlockQuote style
                quoted_para = self._Paragraph(flowable.text, self._styles["BlockQuote"])
                saved_flowables.append(quoted_para)
            else:
                saved_flowables.append(flowable)

        self._flowables = saved_flowables

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        # Collect list items
        items = []
        for item_node in node.items:
            # Save current flowables
            saved_flowables = self._flowables
            self._flowables = []

            # Render item content
            for child in item_node.children:
                child.accept(self)

            # Create list item from flowables
            if self._flowables:
                # Pass all flowables to preserve multi-paragraph and nested content
                items.append(self._ListItem(self._flowables, bulletType="bullet" if not node.ordered else "1"))

            self._flowables = saved_flowables

        # Create list flowable
        if items:
            list_flowable = self._ListFlowable(
                items,  # type: ignore[arg-type]
                bulletType="bullet" if not node.ordered else "1",
                start=node.start if node.ordered else None,
            )
            self._flowables.append(list_flowable)
            self._flowables.append(self._Spacer(1, 0.1 * self._inch))

    def visit_list_item(self, node: ASTListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        # Handled by visit_list
        pass

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        # Collect all rows
        all_rows = []
        if node.header:
            all_rows.append(node.header)
        all_rows.extend(node.rows)

        if not all_rows:
            return

        # Compute grid dimensions accounting for colspan/rowspan
        num_rows = len(all_rows)
        num_cols = self._compute_table_columns(all_rows)

        if num_cols == 0:
            return

        # Build expanded grid data - initialize with empty Paragraph objects
        data: list[list[Any]] = [
            [self._Paragraph("", self._styles["Normal"]) for _ in range(num_cols)] for _ in range(num_rows)
        ]
        span_commands: list[tuple[str, tuple[int, int], tuple[int, int]]] = []

        # Track which grid cells are occupied
        occupied = [[False] * num_cols for _ in range(num_rows)]

        # Fill the grid
        for row_idx, ast_row in enumerate(all_rows):
            col_idx = 0
            for ast_cell in ast_row.cells:
                # Skip occupied cells
                while col_idx < num_cols and occupied[row_idx][col_idx]:
                    col_idx += 1

                if col_idx >= num_cols:
                    break

                # Render cell content
                text = self._process_inline_content(ast_cell.content)
                data[row_idx][col_idx] = self._Paragraph(text, self._styles["Normal"])

                # Handle cell spanning
                colspan = ast_cell.colspan
                rowspan = ast_cell.rowspan

                # Mark occupied cells
                for r in range(row_idx, min(row_idx + rowspan, num_rows)):
                    for c in range(col_idx, min(col_idx + colspan, num_cols)):
                        occupied[r][c] = True

                # Add SPAN command if needed
                if colspan > 1 or rowspan > 1:
                    end_row = min(row_idx + rowspan - 1, num_rows - 1)
                    end_col = min(col_idx + colspan - 1, num_cols - 1)
                    span_commands.append(("SPAN", (col_idx, row_idx), (end_col, end_row)))

                col_idx += colspan

        # Create table
        table = self._ReportLabTable(data)

        # Apply table style
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), self._colors.grey) if node.header else None,
            ("TEXTCOLOR", (0, 0), (-1, 0), self._colors.whitesmoke) if node.header else None,
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), self._get_bold_font(self.options.font_name)) if node.header else None,
            ("FONTSIZE", (0, 0), (-1, 0), self.options.font_size) if node.header else None,
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12) if node.header else None,
            ("BACKGROUND", (0, 1), (-1, -1), self._colors.beige),
            ("GRID", (0, 0), (-1, -1), 1, self._colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]

        # Filter out None commands and add span commands
        style_commands = [cmd for cmd in style_commands if cmd is not None]
        style_commands.extend(span_commands)  # type: ignore[arg-type]

        table.setStyle(self._TableStyle(style_commands))  # type: ignore[arg-type]

        self._flowables.append(table)
        self._flowables.append(self._Spacer(1, 0.2 * self._inch))

    def visit_table_row(self, node: TableRow) -> None:
        """Render a TableRow node.

        Parameters
        ----------
        node : TableRow
            Table row to render

        """
        # Handled by visit_table
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Render a TableCell node.

        Parameters
        ----------
        node : TableCell
            Table cell to render

        """
        # Handled by visit_table
        pass

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render a ThematicBreak node.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        hr = self._HRFlowable(
            width="100%",
            thickness=1,
            color=self._colors.grey,
            spaceAfter=0.2 * self._inch,
            spaceBefore=0.2 * self._inch,
        )
        self._flowables.append(hr)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # Skip HTML content in PDF
        pass

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        # Text nodes are handled by _process_inline_content
        pass

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        # Handled by _process_inline_content
        pass

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        # Handled by _process_inline_content
        pass

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        # Handled by _process_inline_content
        pass

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        # Handled by _process_inline_content
        pass

    def visit_image(self, node: ASTImage) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        if not node.url:
            return

        try:
            # Handle different image sources
            if node.url.startswith("data:"):
                # Base64 encoded image
                image_file = self._decode_base64_image(node.url)
            elif urlparse(node.url).scheme in ("http", "https"):
                # Remote URL - use secure fetching if enabled
                image_file = self._fetch_remote_image(node.url)
            else:
                # Local file
                image_file = node.url

            if image_file:
                # Add image
                img = self._Image(image_file, width=4 * self._inch, height=None, kind="proportional")
                self._flowables.append(img)

                # Add caption if alt text exists
                if node.alt_text:
                    caption_style = self._ParagraphStyle(
                        "ImageCaption",
                        parent=self._styles["Normal"],
                        alignment=self._TA_CENTER,  # type: ignore[arg-type]
                        fontSize=self.options.font_size - 1,
                        textColor=self._colors.grey,
                    )
                    caption = self._Paragraph(f"<i>{node.alt_text}</i>", caption_style)
                    self._flowables.append(caption)

                self._flowables.append(self._Spacer(1, 0.2 * self._inch))
        except Exception as e:
            # If image loading fails, log and optionally raise
            logger.warning(f"Failed to add image to PDF: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to add image to PDF: {e!r}", rendering_stage="image_processing", original_error=e
                ) from e

    def _decode_base64_image(self, data_uri: str) -> str | None:
        """Decode base64 image to temporary file.

        Parameters
        ----------
        data_uri : str
            Data URI with base64 encoded image

        Returns
        -------
        str or None
            Path to temporary file, or None if decoding failed

        """
        # Use centralized image utility
        temp_path = decode_base64_image_to_file(data_uri, delete_on_exit=False)
        if temp_path:
            self._temp_files.append(temp_path)
        return temp_path

    def _fetch_remote_image(self, url: str) -> str | None:
        """Fetch remote image securely.

        Parameters
        ----------
        url : str
            Remote image URL

        Returns
        -------
        str or None
            Path to temporary file with image data, or None if fetch failed

        """
        # Check global network disable flag
        if is_network_disabled():
            logger.debug(f"Network disabled, skipping remote image: {url}")
            return None

        # Check if remote fetching is allowed
        if not self.options.network.allow_remote_fetch:
            logger.debug(f"Remote fetching disabled, skipping image: {url}")
            return None

        try:
            # Fetch image data securely
            image_data = fetch_image_securely(
                url=url,
                allowed_hosts=self.options.network.allowed_hosts,
                require_https=self.options.network.require_https,
                max_size_bytes=self.options.max_asset_size_bytes,
                timeout=self.options.network.network_timeout,
                require_head_success=self.options.network.require_head_success,
            )

            # Determine file extension from URL or content type
            parsed = urlparse(url)
            path_lower = parsed.path.lower()

            if path_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg")):
                ext = path_lower.split(".")[-1]
            else:
                # Default to png
                ext = "png"

            # Write to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as f:
                f.write(image_data)
                temp_path = f.name

            self._temp_files.append(temp_path)
            logger.debug(f"Successfully fetched remote image: {url}")
            return temp_path

        except Exception as e:
            logger.warning(f"Failed to fetch remote image {url}: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to fetch remote image {url}: {e!r}", rendering_stage="image_processing", original_error=e
                ) from e
            return None

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        # Handled by _process_inline_content
        pass

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        # Handled by _process_inline_content
        pass

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        # Handled by _process_inline_content
        pass

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        # Handled by _process_inline_content
        pass

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        # Handled by _process_inline_content
        pass

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        # Skip inline HTML in PDF
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # Handled by _process_inline_content
        pass

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        # Handled by _process_inline_content
        pass

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # FootnoteDefinition.content is a list of block-level nodes
        # We need to extract text from them for the footnote section
        text_parts = []

        for child in node.content:
            if isinstance(child, ASTParagraph):
                # Extract inline content from paragraph
                text_parts.append(self._process_inline_content(child.content))
            elif isinstance(child, List):
                # For lists, extract text from items (simplified)
                list_text = []
                for item in child.items:
                    for item_child in item.children:
                        if isinstance(item_child, ASTParagraph):
                            list_text.append(self._process_inline_content(item_child.content))
                if list_text:
                    text_parts.append(" ".join(list_text))
            elif isinstance(child, Text):
                # Handle bare Text nodes (for backward compatibility with tests)
                text_parts.append(child.content)
            elif isinstance(child, CodeBlock):
                # Include code block content
                text_parts.append(child.content)
            # Add more block types as needed

        # Join all parts with spaces
        text = " ".join(text_parts)
        self._footnote_definitions[node.identifier] = text

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for term, descriptions in node.items:
            # Render term in bold
            term_text = self._process_inline_content(term.content)
            term_para = self._Paragraph(f"<b>{term_text}</b>", self._styles["Normal"])
            self._flowables.append(term_para)

            # Render descriptions with indentation
            for desc in descriptions:
                # Save current flowables
                saved_flowables = self._flowables
                self._flowables = []

                for child in desc.content:
                    child.accept(self)

                # Add indented flowables
                for flowable in self._flowables:
                    if isinstance(flowable, self._Paragraph):
                        # Create indented style
                        indent_style = self._ParagraphStyle(
                            "DefinitionDesc",
                            parent=self._styles["Normal"],
                            leftIndent=20,
                        )
                        indented_para = self._Paragraph(flowable.text, indent_style)
                        saved_flowables.append(indented_para)
                    else:
                        saved_flowables.append(flowable)

                self._flowables = saved_flowables

            self._flowables.append(self._Spacer(1, 0.1 * self._inch))

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render a DefinitionTerm node.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        # Handled by visit_definition_list
        pass

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render a DefinitionDescription node.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        # Handled by visit_definition_list
        pass

    def visit_math_block(self, node: MathBlock) -> None:
        """Render a MathBlock node.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        content, notation = node.get_preferred_representation("latex")
        if notation == "latex":
            text = f"$$\n{content}\n$$"
        else:
            text = content

        pre = self._Preformatted(
            text,
            self._styles["Code"],
            maxLineLength=80,
        )
        self._flowables.append(pre)
        self._flowables.append(self._Spacer(1, 0.1 * self._inch))

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node according to comment_mode option.

        Parameters
        ----------
        node : Comment
            Comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "visible": Render as visible text
        - "ignore": Skip comment entirely (default)

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author"):
            author = node.metadata.get("author")
            date = node.metadata.get("date", "")
            label = node.metadata.get("label", "")
            prefix = f"Comment {label}" if label else "Comment"
            if date:
                comment_text = f"{prefix} by {author} ({date}): {comment_text}"
            else:
                comment_text = f"{prefix} by {author}: {comment_text}"

        if comment_mode == "visible":
            # Render as visible paragraph
            p = self._Paragraph(f"[{comment_text}]", self._styles["BodyText"])
            self._flowables.append(p)
            self._flowables.append(self._Spacer(1, 6))

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node according to comment_mode option.

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Supports multiple rendering modes via comment_mode option:
        - "visible": Render as visible bracketed text
        - "ignore": Skip comment entirely (default)

        """
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            return

        # Format comment with metadata
        comment_text = node.content
        if node.metadata.get("author") or node.metadata.get("label"):
            prefix_parts = []
            if node.metadata.get("label"):
                prefix_parts.append(f"Comment {node.metadata['label']}")
            else:
                prefix_parts.append("Comment")

            if node.metadata.get("author"):
                prefix_parts.append(f"by {node.metadata['author']}")

            if node.metadata.get("date"):
                prefix_parts.append(f"({node.metadata['date']})")

            prefix = " ".join(prefix_parts)
            comment_text = f"[{prefix}: {comment_text}]"
        else:
            comment_text = f"[{comment_text}]"

        if comment_mode == "visible":
            # Add to current paragraph buffer
            if self._paragraph_buffer is None:
                self._paragraph_buffer = []
            self._paragraph_buffer.append(comment_text)
