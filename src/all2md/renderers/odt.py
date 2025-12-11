#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/odt.py
"""ODT rendering from AST.

This module provides the OdtRenderer class which converts AST nodes
to OpenDocument Text (.odt) format. The renderer uses the odfpy library
to generate properly formatted ODT documents.

The rendering process uses the visitor pattern to traverse the AST and
generate ODT content with appropriate styles and formatting.

"""

from __future__ import annotations

import logging
import os
import tempfile
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Union
from urllib.parse import urlparse

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Emphasis,
    FootnoteDefinition,
    FootnoteReference,
    Heading,
    HTMLBlock,
    HTMLInline,
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
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
    Document as ASTDocument,
)
from all2md.ast.nodes import (
    Paragraph as ASTParagraph,
)
from all2md.ast.visitors import NodeVisitor
from all2md.constants import DEPS_ODF_RENDER
from all2md.exceptions import RenderingError
from all2md.options.odt import OdtRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.images import decode_base64_image_to_file, detect_image_format_from_bytes
from all2md.utils.network_security import fetch_image_securely, is_network_disabled

logger = logging.getLogger(__name__)


class OdtRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to ODT format.

    This class implements the visitor pattern to traverse an AST and
    generate an OpenDocument Text document. It uses odfpy for document
    generation and supports most common formatting features.

    Parameters
    ----------
    options : OdtRendererOptions or None, default = None
        ODT formatting options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.options.odt import OdtRendererOptions
        >>> from all2md.renderers.odt import OdtRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = OdtRendererOptions()
        >>> renderer = OdtRenderer(options)
        >>> renderer.render(doc, "output.odt")

    """

    def __init__(self, options: OdtRendererOptions | None = None):
        """Initialize the ODT renderer with options."""
        BaseRenderer._validate_options_type(options, OdtRendererOptions, "odt")
        options = options or OdtRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: OdtRendererOptions = options
        self.document: Any = None  # ODT document (odfpy OpenDocument object)
        self._current_paragraph: Any = None  # Current odf.text.P element
        self._list_level: int = 0
        self._in_table: bool = False
        self._temp_files: list[str] = []
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level
        self._blockquote_depth: int = 0  # Track blockquote nesting depth
        self._in_table_header: bool = False  # Track if rendering table header cell

    @requires_dependencies("odt_render", DEPS_ODF_RENDER)
    def render(self, doc: ASTDocument, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to an ODT file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        RenderingError
            If ODT generation fails

        """
        from odf import opendocument

        try:
            # Create new ODT document (with template if specified)
            if self.options.template_path:
                self.document = opendocument.load(self.options.template_path)
            else:
                self.document = opendocument.OpenDocumentText()

            # Set creator metadata if configured
            if self.options.creator:
                self._set_creator_metadata()

            # Set up styles
            self._setup_styles()

            # Render document
            doc.accept(self)

            # Save document
            if isinstance(output, (str, Path)):
                self.document.save(str(output))
            else:
                self.document.save(output)
        except Exception as e:
            raise RenderingError(f"Failed to render ODT: {e!r}", rendering_stage="rendering", original_error=e) from e
        finally:
            # Clean up temp files
            self._cleanup_temp_files()

    @requires_dependencies("odt_render", DEPS_ODF_RENDER)
    def render_to_bytes(self, doc: ASTDocument) -> bytes:
        """Render the AST to ODT bytes.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        bytes
            ODT file content as bytes

        Raises
        ------
        RenderingError
            If ODT generation fails

        """
        # Create a BytesIO buffer and render to it
        buffer = BytesIO()
        self.render(doc, buffer)

        # Return the bytes content
        return buffer.getvalue()

    def _set_creator_metadata(self) -> None:
        """Set creator application metadata in ODT document."""
        if not self.document or not self.options.creator:
            return

        from odf.meta import Generator

        # Set generator (creating application) metadata
        generator = Generator()
        generator.addText(self.options.creator)
        self.document.meta.addElement(generator)

    def _setup_styles(self) -> None:
        """Set up default document styles and formatting."""
        from odf.style import FontFace, ParagraphProperties, Style, TextProperties

        if not self.document:
            return

        # Add font faces
        font_face = FontFace(name=self.options.default_font, fontfamily=self.options.default_font)
        self.document.fontfacedecls.addElement(font_face)

        code_font = FontFace(name=self.options.code_font, fontfamily=self.options.code_font)
        self.document.fontfacedecls.addElement(code_font)

        # Create default text style
        default_style = Style(name="Standard", family="paragraph")
        default_props = TextProperties(
            fontname=self.options.default_font, fontsize=f"{self.options.default_font_size}pt"
        )
        default_style.addElement(default_props)
        self.document.styles.addElement(default_style)

        # Create code style
        code_style = Style(name="Code", family="text")
        code_props = TextProperties(fontname=self.options.code_font, fontsize=f"{self.options.code_font_size}pt")
        code_style.addElement(code_props)
        self.document.styles.addElement(code_style)

        # Create blockquote style with indentation
        blockquote_style = Style(name="Blockquote", family="paragraph")
        blockquote_para_props = ParagraphProperties(marginleft="0.5in")
        blockquote_style.addElement(blockquote_para_props)
        self.document.styles.addElement(blockquote_style)

        # Create text formatting styles
        bold_style = Style(name="Bold", family="text")
        bold_props = TextProperties(fontweight="bold")
        bold_style.addElement(bold_props)
        self.document.styles.addElement(bold_style)

        italic_style = Style(name="Italic", family="text")
        italic_props = TextProperties(fontstyle="italic")
        italic_style.addElement(italic_props)
        self.document.styles.addElement(italic_style)

        underline_style = Style(name="Underline", family="text")
        underline_props = TextProperties(
            textunderlinestyle="solid", textunderlinewidth="auto", textunderlinecolor="font-color"
        )
        underline_style.addElement(underline_props)
        self.document.styles.addElement(underline_style)

        strikethrough_style = Style(name="Strikethrough", family="text")
        strikethrough_props = TextProperties(textlinethroughstyle="solid")
        strikethrough_style.addElement(strikethrough_props)
        self.document.styles.addElement(strikethrough_style)

        superscript_style = Style(name="Superscript", family="text")
        superscript_props = TextProperties(textposition="super 58%")
        superscript_style.addElement(superscript_props)
        self.document.styles.addElement(superscript_style)

        subscript_style = Style(name="Subscript", family="text")
        subscript_props = TextProperties(textposition="sub 58%")
        subscript_style.addElement(subscript_props)
        self.document.styles.addElement(subscript_style)

        # Create definition list styles
        defterm_style = Style(name="DefinitionTerm", family="paragraph")
        defterm_props = TextProperties(fontweight="bold")
        defterm_style.addElement(defterm_props)
        self.document.styles.addElement(defterm_style)

        defdesc_style = Style(name="DefinitionDescription", family="paragraph")
        defdesc_para_props = ParagraphProperties(marginleft="0.5in")
        defdesc_style.addElement(defdesc_para_props)
        self.document.styles.addElement(defdesc_style)

    def _cleanup_temp_files(self) -> None:
        """Remove temporary files created during rendering."""
        for temp_file in self._temp_files:
            try:
                Path(temp_file).unlink(missing_ok=True)
            except Exception as e:
                logger.debug(f"Failed to cleanup temp file {temp_file}: {e}")
        self._temp_files.clear()

    def visit_document(self, node: ASTDocument) -> None:
        """Render a Document node.

        Parameters
        ----------
        node : Document
            Document to render

        """
        # Set metadata if present
        if node.metadata:
            self._set_document_properties(node.metadata)

        # Render children
        for child in node.children:
            child.accept(self)

    def _set_document_properties(self, metadata: dict) -> None:
        """Set document metadata.

        Parameters
        ----------
        metadata : dict
            Document metadata

        """
        if not self.document:
            return

        from odf.dc import Creator, Subject, Title
        from odf.meta import InitialCreator, Keyword

        meta = self.document.meta

        if "title" in metadata:
            title = Title()
            title.addText(str(metadata["title"]))
            meta.addElement(title)

        if "author" in metadata:
            creator = Creator()
            creator.addText(str(metadata["author"]))
            meta.addElement(creator)

            initial_creator = InitialCreator()
            initial_creator.addText(str(metadata["author"]))
            meta.addElement(initial_creator)

        if "subject" in metadata:
            subject = Subject()
            subject.addText(str(metadata["subject"]))
            meta.addElement(subject)

        if "keywords" in metadata:
            keywords = metadata["keywords"]
            if isinstance(keywords, list):
                for kw in keywords:
                    keyword_elem = Keyword()
                    keyword_elem.addText(str(kw))
                    meta.addElement(keyword_elem)
            else:
                keyword_elem = Keyword()
                keyword_elem.addText(str(keywords))
                meta.addElement(keyword_elem)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        from odf.text import H

        if not self.document:
            return

        # Create heading
        level = min(10, max(1, node.level))  # ODT supports levels 1-10
        heading = H(outlinelevel=level)

        self._current_paragraph = heading

        # Render content
        for child in node.content:
            child.accept(self)

        self.document.text.addElement(heading)
        self._current_paragraph = None

    def visit_paragraph(self, node: ASTParagraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        from odf.text import P

        if not self.document:
            return

        # Don't create new paragraph if we're already in one (e.g., heading)
        if self._current_paragraph is None:
            # Apply blockquote style if needed
            if self._blockquote_depth > 0:
                para = P(stylename="Blockquote")
            else:
                para = P()
            self._current_paragraph = para

        # Render content
        for child in node.content:
            child.accept(self)

        # Only add if we created the paragraph
        if not self._in_table:
            self.document.text.addElement(self._current_paragraph)
            self._current_paragraph = None

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        from odf.text import P, Span

        if not self.document:
            return

        # Create paragraph for code block
        para = P()
        span = Span(stylename="Code")
        span.addText(node.content)
        para.addElement(span)

        self.document.text.addElement(para)

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        # Increase blockquote depth for indentation tracking
        self._blockquote_depth += 1

        # Render children (they will check _blockquote_depth and style themselves)
        for child in node.children:
            child.accept(self)

        # Decrease blockquote depth
        self._blockquote_depth -= 1

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        from odf.text import List as OdfList

        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)

        # Create ODF list
        odf_list = OdfList()

        for item in node.items:
            # Store current list for item to add to
            saved_list = getattr(self, "_current_list", None)
            self._current_list = odf_list
            item.accept(self)
            self._current_list = saved_list

        # Add list to document
        if self._current_paragraph:
            self._current_paragraph.addElement(odf_list)
        else:
            self.document.text.addElement(odf_list)

        self._list_level -= 1
        self._list_ordered_stack.pop()

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        from odf.text import ListItem as OdfListItem
        from odf.text import P

        # Create list item
        list_item = OdfListItem()

        # Create paragraph for item content
        para = P()
        self._current_paragraph = para

        # Render children
        for child in node.children:
            if isinstance(child, (ASTParagraph, List)):
                # For nested elements, handle specially
                saved_para = self._current_paragraph
                self._current_paragraph = None
                child.accept(self)
                self._current_paragraph = saved_para
            else:
                child.accept(self)

        list_item.addElement(para)

        # Add to current list
        if hasattr(self, "_current_list"):
            self._current_list.addElement(list_item)

        self._current_paragraph = None

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        from odf.table import CoveredTableCell, TableCell, TableColumn, TableRow
        from odf.table import Table as OdfTable

        if not self.document:
            return

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

        # Create table
        table = OdfTable()

        # Add columns
        for _ in range(num_cols):
            table.addElement(TableColumn())

        self._in_table = True

        # Track which grid cells are occupied
        occupied = [[False] * num_cols for _ in range(num_rows)]

        # Render all rows
        for row_idx, ast_row in enumerate(all_rows):
            table_row = TableRow()
            col_idx = 0

            for ast_cell in ast_row.cells:
                # Skip occupied cells, add CoveredTableCell
                while col_idx < num_cols and occupied[row_idx][col_idx]:
                    table_row.addElement(CoveredTableCell())
                    col_idx += 1

                if col_idx >= num_cols:
                    break

                # Create cell
                table_cell = TableCell()

                # Set colspan/rowspan attributes
                if ast_cell.colspan > 1:
                    table_cell.setAttribute("numbercolumnsspanned", str(ast_cell.colspan))
                if ast_cell.rowspan > 1:
                    table_cell.setAttribute("numberrowsspanned", str(ast_cell.rowspan))

                # Render cell content
                is_header = row_idx == 0 and node.header is not None
                self._render_table_cell(table_cell, ast_cell, is_header=is_header)
                table_row.addElement(table_cell)

                # Mark occupied cells
                for r in range(row_idx, min(row_idx + ast_cell.rowspan, num_rows)):
                    for c in range(col_idx, min(col_idx + ast_cell.colspan, num_cols)):
                        occupied[r][c] = True

                col_idx += ast_cell.colspan

            # Add remaining covered cells at end of row if needed
            while col_idx < num_cols and occupied[row_idx][col_idx]:
                table_row.addElement(CoveredTableCell())
                col_idx += 1

            table.addElement(table_row)

        self.document.text.addElement(table)
        self._in_table = False

    def _render_table_cell(self, odt_cell: Any, ast_cell: TableCell, is_header: bool = False) -> None:
        """Render a single table cell.

        Parameters
        ----------
        odt_cell : TableCell
            ODT table cell
        ast_cell : TableCell
            AST table cell node
        is_header : bool, default = False
            Whether this is a header cell

        """
        from odf.text import P

        # Create paragraph for cell content
        para = P()
        self._current_paragraph = para

        # Set flag for header cells to apply bold formatting
        if is_header:
            self._in_table_header = True

        # Render cell content
        for child in ast_cell.content:
            child.accept(self)

        # Reset header flag
        if is_header:
            self._in_table_header = False

        odt_cell.addElement(para)
        self._current_paragraph = None

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
        from odf.text import P

        if not self.document:
            return

        # Add horizontal line using text separator
        para = P()
        para.addText("─" * 80)
        self.document.text.addElement(para)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # Skip HTML content in ODT
        pass

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        if self._current_paragraph:
            # Wrap in bold span if in table header
            if self._in_table_header and self.options.preserve_formatting:
                from odf.text import Span

                span = Span(stylename="Bold")
                span.addText(node.content)
                self._current_paragraph.addElement(span)
            else:
                self._current_paragraph.addText(node.content)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with italic style
        if self.options.preserve_formatting:
            span = Span(stylename="Italic")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with bold style
        if self.options.preserve_formatting:
            span = Span(stylename="Bold")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with code style
        span = Span(stylename="Code")
        span.addText(node.content)
        self._current_paragraph.addElement(span)

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        from odf.text import A

        if not self._current_paragraph:
            return

        # Create hyperlink
        link = A(href=node.url)
        saved_para = self._current_paragraph
        self._current_paragraph = link

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(link)

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        from odf.draw import Frame
        from odf.draw import Image as OdfImage
        from odf.text import P

        if not self.document or not node.url:
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

            # Add image to document
            if image_file:
                # Read image data
                with open(image_file, "rb") as f:
                    image_data = f.read()

                # Add picture to document's manifest

                # Generate unique name for image
                ext = os.path.splitext(image_file)[1] or ".png"
                image_name = f"Pictures/image_{id(node)}{ext}"

                # Detect actual image format for correct MIME type
                image_format = detect_image_format_from_bytes(image_data)
                if image_format:
                    # Map format to MIME type
                    mime_type = f"image/{image_format}"
                else:
                    # Fallback to extension-based detection
                    mime_type = f"image/{ext.lstrip('.') or 'png'}"

                # Add to document
                self.document.addPicture(image_name, mediatype=mime_type, content=image_data)

                # Create frame and image
                frame = Frame(width="3in", height="3in")
                img = OdfImage(href=image_name)
                frame.addElement(img)

                # Add to paragraph
                para = P()
                para.addElement(frame)
                self.document.text.addElement(para)

                # Add caption if alt text exists
                if node.alt_text:
                    caption_para = P()
                    caption_para.addText(node.alt_text)
                    self.document.text.addElement(caption_para)
        except Exception as e:
            # If image loading fails, log and optionally raise
            logger.warning(f"Failed to add image to ODT: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to add image to ODT: {e!r}", rendering_stage="image_processing", original_error=e
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
            Path to temporary file containing the image, or None if fetching failed

        """
        if is_network_disabled():
            logger.debug(f"Network disabled, skipping remote image: {url}")
            return None

        if not self.options.network.allow_remote_fetch:
            logger.debug(f"Remote fetching disabled, skipping image: {url}")
            return None

        try:
            image_data = fetch_image_securely(
                url=url,
                allowed_hosts=self.options.network.allowed_hosts,
                require_https=self.options.network.require_https,
                max_size_bytes=self.options.max_asset_size_bytes,
                timeout=self.options.network.network_timeout,
                require_head_success=self.options.network.require_head_success,
            )

            # Determine extension from URL
            parsed = urlparse(url)
            path_lower = parsed.path.lower()
            if path_lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg")):
                ext = path_lower.split(".")[-1]
            else:
                ext = "png"

            # Write to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as f:
                f.write(image_data)
                temp_path = f.name

            self._temp_files.append(temp_path)
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
        from odf.text import LineBreak as OdfLineBreak

        if self._current_paragraph:
            self._current_paragraph.addElement(OdfLineBreak())

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with strikethrough style
        if self.options.preserve_formatting:
            span = Span(stylename="Strikethrough")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with underline style
        if self.options.preserve_formatting:
            span = Span(stylename="Underline")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with superscript style
        if self.options.preserve_formatting:
            span = Span(stylename="Superscript")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Create span with subscript style
        if self.options.preserve_formatting:
            span = Span(stylename="Subscript")
        else:
            span = Span()

        saved_para = self._current_paragraph
        self._current_paragraph = span

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        self._current_paragraph.addElement(span)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        # Skip inline HTML in ODT
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        from odf.text import Span

        if not self._current_paragraph:
            return

        # Render as superscript text
        if self.options.preserve_formatting:
            span = Span(stylename="Superscript")
        else:
            span = Span()
        span.addText(f"[{node.identifier}]")
        self._current_paragraph.addElement(span)

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        if not self._current_paragraph:
            return

        # Render math with best available representation
        content, notation = node.get_preferred_representation("latex")
        if notation == "latex":
            text = f"${content}$"
        else:
            text = content

        self._current_paragraph.addText(text)

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        from odf.text import P, Span

        if not self.document:
            return

        # Render as a separate paragraph
        para = P()
        if self.options.preserve_formatting:
            span = Span(stylename="Superscript")
        else:
            span = Span()
        span.addText(f"[{node.identifier}]: ")
        para.addElement(span)

        self._current_paragraph = para
        for child in node.content:
            child.accept(self)

        self.document.text.addElement(para)
        self._current_paragraph = None

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        from odf.text import P

        for term, descriptions in node.items:
            # Render term as bold paragraph
            if self.document:
                # Apply DefinitionTerm style for bold formatting
                if self.options.preserve_formatting:
                    term_para = P(stylename="DefinitionTerm")
                else:
                    term_para = P()

                self._current_paragraph = term_para

                for child in term.content:
                    child.accept(self)

                self.document.text.addElement(term_para)

                # Render descriptions as indented paragraphs
                for desc in descriptions:
                    # Apply DefinitionDescription style for indentation
                    desc_para = P(stylename="DefinitionDescription")
                    self._current_paragraph = desc_para

                    for child in desc.content:
                        child.accept(self)

                    self.document.text.addElement(desc_para)

                self._current_paragraph = None

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
        from odf.text import P, Span

        if not self.document:
            return

        # Render math as code block
        para = P()
        span = Span(stylename="Code")
        content, notation = node.get_preferred_representation("latex")
        if notation == "latex":
            text = f"$$\n{content}\n$$"
        else:
            text = content
        span.addText(text)
        para.addElement(span)
        self.document.text.addElement(para)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (block-level).

        Parameters
        ----------
        node : Comment
            Comment block to render

        """
        from odf.dc import Creator, Date
        from odf.office import Annotation
        from odf.text import P, Span

        if not self.document:
            return

        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        if comment_mode == "visible":
            # Render as visible text paragraph with attribution
            para = P()

            # Build attribution prefix
            prefix_parts = []
            if comment_type:
                prefix_parts.append(comment_type.upper())
            if label:
                prefix_parts.append(f"#{label}")
            prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

            # Add attribution as bold span
            if author:
                if date:
                    attribution_text = f"{prefix} by {author} ({date}): "
                else:
                    attribution_text = f"{prefix} by {author}: "

                attribution_span = Span(stylename="Bold")
                attribution_span.addText(attribution_text)
                para.addElement(attribution_span)

            # Add comment content as italic span
            content_span = Span(stylename="Italic")
            content_span.addText(node.content)
            para.addElement(content_span)

            self.document.text.addElement(para)
            return

        # Mode is "native" - create annotation using odfpy's native annotation support
        annotation = Annotation()

        # Add author if available
        if author:
            creator = Creator()
            creator.addText(author)
            annotation.addElement(creator)

        # Add date if available
        if date:
            date_elem = Date()
            date_elem.addText(date)
            annotation.addElement(date_elem)

        # Add comment content as paragraph(s)
        comment_para = P()
        comment_para.addText(node.content)
        annotation.addElement(comment_para)

        # In ODT, annotations must be anchored within paragraphs
        # For block-level comments, we create a paragraph to contain the annotation
        anchor_para = P()
        anchor_para.addElement(annotation)
        self.document.text.addElement(anchor_para)

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (inline).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        """
        from odf.dc import Creator, Date
        from odf.office import Annotation
        from odf.text import P, Span

        if not self._current_paragraph:
            return

        # Check comment_mode option
        comment_mode = self.options.comment_mode

        if comment_mode == "ignore":
            # Skip rendering comment entirely
            return

        # Extract metadata
        author = node.metadata.get("author", "")
        date = node.metadata.get("date", "")
        label = node.metadata.get("label", "")
        comment_type = node.metadata.get("comment_type", "")

        if comment_mode == "visible":
            # Render as visible inline text with attribution
            # Build attribution prefix
            prefix_parts = []
            if comment_type:
                prefix_parts.append(comment_type.upper())
            if label:
                prefix_parts.append(f"#{label}")
            prefix = " ".join(prefix_parts) if prefix_parts else "Comment"

            # Build full text
            if author:
                if date:
                    full_text = f"[{prefix} by {author} ({date}): {node.content}]"
                else:
                    full_text = f"[{prefix} by {author}: {node.content}]"
            else:
                full_text = f"[{node.content}]"

            # Add as italic span
            span = Span(stylename="Italic")
            span.addText(full_text)
            self._current_paragraph.addElement(span)
            return

        # Mode is "native" - create inline annotation using odfpy's native annotation support
        annotation = Annotation()

        # Add author if available
        if author:
            creator = Creator()
            creator.addText(author)
            annotation.addElement(creator)

        # Add date if available
        if date:
            date_elem = Date()
            date_elem.addText(date)
            annotation.addElement(date_elem)

        # Add comment content as paragraph
        comment_para = P()
        comment_para.addText(node.content)
        annotation.addElement(comment_para)

        # Add annotation to current paragraph
        # In ODT, inline annotations are embedded within paragraphs
        self._current_paragraph.addElement(annotation)
