#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/docx.py
"""DOCX rendering from AST.

This module provides the DocxRenderer class which converts AST nodes
to Microsoft Word (.docx) format. The renderer uses the python-docx library
to generate properly formatted Word documents.

The rendering process uses the visitor pattern to traverse the AST and
generate DOCX content with appropriate styles and formatting.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from docx.table import _Cell
    from docx.text.paragraph import Paragraph

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
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
    Document as ASTDocument,
)
from all2md.ast.nodes import (
    Paragraph as ASTParagraph,
)
from all2md.ast.visitors import NodeVisitor
from all2md.exceptions import RenderingError
from all2md.options import DocxRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.images import decode_base64_image_to_file

logger = logging.getLogger(__name__)


class DocxRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to DOCX format.

    This class implements the visitor pattern to traverse an AST and
    generate a Microsoft Word document. It uses python-docx for document
    generation and supports most common formatting features.

    Parameters
    ----------
    options : DocxRendererOptions or None, default = None
        DOCX formatting options

    Examples
    --------
    Basic usage:

        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.options import DocxRendererOptions
        >>> from all2md.renderers.docx import DocxRenderer
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = DocxRendererOptions()
        >>> renderer = DocxRenderer(options)
        >>> renderer.render(doc, "output.docx")

    """

    def __init__(self, options: DocxRendererOptions | None = None):
        """Initialize the DOCX renderer with options."""
        options = options or DocxRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: DocxRendererOptions = options
        self.document: Any = None  # Word document (python-docx Document object)
        self._current_paragraph: Paragraph | None = None
        self._list_level: int = 0
        self._in_table: bool = False
        self._temp_files: list[str] = []
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level
        self._blockquote_depth: int = 0  # Track blockquote nesting depth

    @requires_dependencies("docx_render", [("python-docx", "docx", ">=1.2.0")])
    def render(self, doc: ASTDocument, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to a DOCX file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        RenderingError
            If DOCX generation fails

        """
        from docx import Document
        from docx.enum.style import WD_STYLE_TYPE
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Inches, Pt, RGBColor

        # Store imports as instance variables for use in other methods
        self._Document = Document
        self._WD_STYLE_TYPE = WD_STYLE_TYPE
        self._WD_ALIGN_PARAGRAPH = WD_ALIGN_PARAGRAPH
        self._OxmlElement = OxmlElement
        self._qn = qn
        self._Inches = Inches
        self._Pt = Pt
        self._RGBColor = RGBColor

        try:
            # Create new Word document (with template if specified)
            if self.options.template_path:
                self.document = self._Document(self.options.template_path)
            else:
                self.document = self._Document()

            # Set default font
            self._set_document_defaults()

            # Render document
            doc.accept(self)

            # Save document
            if isinstance(output, (str, Path)):
                self.document.save(str(output))
            else:
                self.document.save(output)
        except Exception as e:
            raise RenderingError(
                f"Failed to render DOCX: {e!r}",
                rendering_stage="rendering",
                original_error=e
            ) from e
        finally:
            # Clean up temp files
            self._cleanup_temp_files()

    @requires_dependencies("docx_render", [("python-docx", "docx", ">=1.2.0")])
    def render_to_bytes(self, doc: ASTDocument) -> bytes:
        """Render the AST to DOCX bytes.

        Parameters
        ----------
        doc : Document
            AST Document node to render

        Returns
        -------
        bytes
            DOCX file content as bytes

        Raises
        ------
        RenderingError
            If DOCX generation fails

        """
        from io import BytesIO

        # Create a BytesIO buffer and render to it
        buffer = BytesIO()
        self.render(doc, buffer)

        # Return the bytes content
        return buffer.getvalue()

    def _set_document_defaults(self) -> None:
        """Set default document styles and formatting."""
        if not self.document:
            return

        # Set default font for Normal style
        style = self.document.styles['Normal']
        font = style.font
        font.name = self.options.default_font
        font.size = self._Pt(self.options.default_font_size)

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
        # Render metadata as document properties if present
        if node.metadata:
            self._set_document_properties(node.metadata)

        # Render children
        for child in node.children:
            child.accept(self)

    def _set_document_properties(self, metadata: dict) -> None:
        """Set document properties from metadata.

        Parameters
        ----------
        metadata : dict
            Document metadata

        """
        if not self.document:
            return

        core_props = self.document.core_properties
        if 'title' in metadata:
            core_props.title = str(metadata['title'])
        if 'author' in metadata:
            core_props.author = str(metadata['author'])
        if 'subject' in metadata:
            core_props.subject = str(metadata['subject'])
        if 'keywords' in metadata:
            keywords = metadata['keywords']
            if isinstance(keywords, list):
                core_props.keywords = ', '.join(str(k) for k in keywords)
            else:
                core_props.keywords = str(keywords)

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node.

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        if not self.document:
            return

        # Add heading with appropriate level
        level = min(9, max(1, node.level))  # Word supports levels 1-9

        if self.options.use_styles:
            # Use built-in heading styles
            heading = self.document.add_heading(level=level)
            # Clear the heading text (add_heading adds empty text)
            heading.text = ''
        else:
            # Use direct formatting
            heading = self.document.add_paragraph()
            if self.options.heading_font_sizes and level in self.options.heading_font_sizes:
                for run in heading.runs:
                    run.font.size = self._Pt(self.options.heading_font_sizes[level])
                    run.font.bold = True

        # Apply blockquote indentation if inside a blockquote
        if self._blockquote_depth > 0:
            heading.paragraph_format.left_indent = self._Inches(0.5 * self._blockquote_depth)

        self._current_paragraph = heading

        # Render content
        for child in node.content:
            child.accept(self)

        self._current_paragraph = None

    def visit_paragraph(self, node: ASTParagraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        if not self.document:
            return

        # Don't create new paragraph if we're already in one (e.g., heading)
        if self._current_paragraph is None:
            self._current_paragraph = self.document.add_paragraph()

            # Apply blockquote indentation if inside a blockquote
            if self._blockquote_depth > 0:
                self._current_paragraph.paragraph_format.left_indent = self._Inches(0.5 * self._blockquote_depth)

        # Render content
        for child in node.content:
            child.accept(self)

        # Only clear if we created the paragraph
        if not self._in_table:
            self._current_paragraph = None

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if not self.document:
            return

        # Add paragraph with code formatting
        para = self.document.add_paragraph()
        run = para.add_run(node.content)
        run.font.name = self.options.code_font
        run.font.size = self._Pt(self.options.code_font_size)

        # Apply blockquote indentation if inside a blockquote
        if self._blockquote_depth > 0:
            para.paragraph_format.left_indent = self._Inches(0.5 * self._blockquote_depth)

        # Set paragraph background (light gray)
        self._set_paragraph_shading(para, "F0F0F0")

    def _set_paragraph_shading(self, paragraph: Paragraph, color: str) -> None:
        """Set paragraph background color.

        Parameters
        ----------
        paragraph : Paragraph
            Paragraph to shade
        color : str
            Hex color code (e.g., "F0F0F0")

        """
        shading_elm = self._OxmlElement('w:shd')
        shading_elm.set(self._qn('w:fill'), color)
        paragraph._element.get_or_add_pPr().append(shading_elm)

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render a BlockQuote node.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        # Increase blockquote depth for indentation tracking
        self._blockquote_depth += 1

        # Render children (they will check _blockquote_depth and indent themselves)
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
        self._list_level += 1
        self._list_ordered_stack.append(node.ordered)

        for _i, item in enumerate(node.items):
            item.accept(self)

        self._list_level -= 1
        self._list_ordered_stack.pop()

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        """
        if not self.document:
            return

        # Create paragraph for list item
        para = self.document.add_paragraph()

        # Determine list style based on ordered/unordered
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False
        if is_ordered:
            para.style = 'List Number'
        else:
            para.style = 'List Bullet'

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

        self._current_paragraph = None

    def visit_table(self, node: Table) -> None:
        """Render a Table node.

        Parameters
        ----------
        node : Table
            Table to render

        """
        if not self.document:
            return

        # Calculate table dimensions
        num_rows = len(node.rows) + (1 if node.header else 0)
        num_cols = len(node.header.cells) if node.header else (len(node.rows[0].cells) if node.rows else 0)

        if num_cols == 0:
            return

        # Create table
        table = self.document.add_table(rows=num_rows, cols=num_cols)

        # Apply table style if requested
        if self.options.table_style:
            table.style = self.options.table_style

        self._in_table = True

        # Render header
        row_idx = 0
        if node.header:
            table_row = table.rows[row_idx]
            for col_idx, cell in enumerate(node.header.cells):
                if col_idx < len(table_row.cells):
                    self._render_table_cell(table_row.cells[col_idx], cell, is_header=True)
            row_idx += 1

        # Render body rows
        for ast_row in node.rows:
            if row_idx < len(table.rows):
                table_row = table.rows[row_idx]
                for col_idx, cell in enumerate(ast_row.cells):
                    if col_idx < len(table_row.cells):
                        self._render_table_cell(table_row.cells[col_idx], cell)
            row_idx += 1

        self._in_table = False

    def _render_table_cell(self, docx_cell: _Cell, ast_cell: TableCell, is_header: bool = False) -> None:
        """Render a single table cell.

        Parameters
        ----------
        docx_cell : _Cell
            python-docx table cell
        ast_cell : TableCell
            AST table cell node
        is_header : bool, default = False
            Whether this is a header cell

        """
        # Clear default paragraph
        if len(docx_cell.paragraphs) > 0:
            docx_cell.paragraphs[0].text = ''
            self._current_paragraph = docx_cell.paragraphs[0]
        else:
            self._current_paragraph = docx_cell.add_paragraph()

        # Render cell content
        for child in ast_cell.content:
            child.accept(self)

        # Make header cells bold
        if is_header:
            for para in docx_cell.paragraphs:
                for run in para.runs:
                    run.font.bold = True

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
        if not self.document:
            return

        # Add horizontal line using a simple text separator
        para = self.document.add_paragraph()
        run = para.add_run('─' * 80)  # Em dash character
        run.font.color.rgb = self._RGBColor(192, 192, 192)  # Light gray

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Render an HTMLBlock node.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to render

        """
        # Skip HTML content in DOCX
        pass

    def _render_inlines(
            self,
            paragraph: Paragraph,
            nodes: list[Node],
            bold: bool = False,
            italic: bool = False,
            underline: bool = False,
            strike: bool = False,
            superscript: bool = False,
            subscript: bool = False,
            code_font: bool = False,
    ) -> None:
        """Render inline nodes directly into a paragraph with formatting.

        This method efficiently renders inline content by applying formatting
        flags recursively, avoiding the overhead of creating temporary documents
        and paragraphs.

        Parameters
        ----------
        paragraph : Paragraph
            Target paragraph to render into
        nodes : list of Node
            Inline nodes to render
        bold : bool, default = False
            Apply bold formatting
        italic : bool, default = False
            Apply italic formatting
        underline : bool, default = False
            Apply underline formatting
        strike : bool, default = False
            Apply strikethrough formatting
        superscript : bool, default = False
            Apply superscript formatting
        subscript : bool, default = False
            Apply subscript formatting
        code_font : bool, default = False
            Apply code font formatting

        """
        for node in nodes:
            if isinstance(node, Text):
                # Create run with text and apply all formatting
                run = paragraph.add_run(node.content)
                if bold:
                    run.bold = True
                if italic:
                    run.italic = True
                if underline:
                    run.underline = True
                if strike:
                    run.font.strike = True
                if superscript:
                    run.font.superscript = True
                if subscript:
                    run.font.subscript = True
                if code_font:
                    run.font.name = self.options.code_font
                    run.font.size = self._Pt(self.options.code_font_size)

            elif isinstance(node, Strong):
                # Recursively render with bold flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=True, italic=italic, underline=underline, strike=strike,
                    superscript=superscript, subscript=subscript, code_font=code_font
                )

            elif isinstance(node, Emphasis):
                # Recursively render with italic flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=bold, italic=True, underline=underline, strike=strike,
                    superscript=superscript, subscript=subscript, code_font=code_font
                )

            elif isinstance(node, Underline):
                # Recursively render with underline flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=bold, italic=italic, underline=True, strike=strike,
                    superscript=superscript, subscript=subscript, code_font=code_font
                )

            elif isinstance(node, Strikethrough):
                # Recursively render with strike flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=bold, italic=italic, underline=underline, strike=True,
                    superscript=superscript, subscript=subscript, code_font=code_font
                )

            elif isinstance(node, Superscript):
                # Recursively render with superscript flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=bold, italic=italic, underline=underline, strike=strike,
                    superscript=True, subscript=subscript, code_font=code_font
                )

            elif isinstance(node, Subscript):
                # Recursively render with subscript flag
                self._render_inlines(
                    paragraph, node.content,
                    bold=bold, italic=italic, underline=underline, strike=strike,
                    superscript=superscript, subscript=True, code_font=code_font
                )

            elif isinstance(node, Code):
                # Render as code with code font
                self._render_inlines(
                    paragraph, [Text(content=node.content)],
                    bold=bold, italic=italic, underline=underline, strike=strike,
                    superscript=superscript, subscript=subscript, code_font=True
                )

            elif isinstance(node, Link):
                # Extract link text by rendering to a temporary paragraph
                temp_para = self.document.add_paragraph()
                self._render_inlines(
                    temp_para, node.content,
                    bold=bold, italic=italic, underline=underline, strike=strike,
                    superscript=superscript, subscript=subscript, code_font=code_font
                )
                link_text = temp_para.text
                # Remove the temporary paragraph
                self.document._element.body.remove(temp_para._element)
                # Add hyperlink to target paragraph
                self._add_hyperlink(paragraph, node.url, link_text)

            elif isinstance(node, LineBreak):
                paragraph.add_run().add_break()

            else:
                # For other inline nodes, try to process if they have content
                if hasattr(node, 'content') and isinstance(node.content, list):
                    self._render_inlines(
                        paragraph, node.content,
                        bold=bold, italic=italic, underline=underline, strike=strike,
                        superscript=superscript, subscript=subscript, code_font=code_font
                    )

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        if self._current_paragraph:
            self._current_paragraph.add_run(node.content)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, italic=True)

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, bold=True)

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering with code font
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, [Text(content=node.content)], code_font=True)

    def visit_link(self, node: Link) -> None:
        """Render a Link node.

        Parameters
        ----------
        node : Link
            Link to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering (handles links internally)
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, [node])

    def _add_hyperlink(self, paragraph: Paragraph, url: str, text: str) -> None:
        """Add a hyperlink to a paragraph.

        Parameters
        ----------
        paragraph : Paragraph
            Paragraph to add link to
        url : str
            URL to link to
        text : str
            Link text

        """
        # This is a complex operation in python-docx requiring XML manipulation
        part = paragraph.part
        r_id = part.relate_to(
            url, 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink', is_external=True
        )

        # Create hyperlink element
        hyperlink = self._OxmlElement('w:hyperlink')
        hyperlink.set(self._qn('r:id'), r_id)

        # Create run element
        new_run = self._OxmlElement('w:r')
        rPr = self._OxmlElement('w:rPr')

        # Add hyperlink style
        r_style = self._OxmlElement('w:rStyle')
        r_style.set(self._qn('w:val'), 'Hyperlink')
        rPr.append(r_style)
        new_run.append(rPr)

        # Create text element (required by OOXML spec)
        t = self._OxmlElement('w:t')
        t.text = text
        new_run.append(t)

        hyperlink.append(new_run)
        paragraph._element.append(hyperlink)

    def visit_image(self, node: Image) -> None:
        """Render an Image node.

        Parameters
        ----------
        node : Image
            Image to render

        """
        if not self.document or not node.url:
            return

        try:
            # Handle different image sources
            if node.url.startswith('data:'):
                # Base64 encoded image
                image_file = self._decode_base64_image(node.url)
            elif urlparse(node.url).scheme in ('http', 'https'):
                # Remote URL - for now, skip (could download in future)
                return
            else:
                # Local file
                image_file = node.url

            # Add image to document
            if image_file:
                para = self.document.add_paragraph()
                run = para.add_run()
                run.add_picture(image_file, width=self._Inches(4))

                # Add caption if alt text exists
                if node.alt_text:
                    caption_para = self.document.add_paragraph(node.alt_text)
                    caption_para.alignment = self._WD_ALIGN_PARAGRAPH.CENTER
                    caption_para.runs[0].italic = True
        except Exception as e:
            # If image loading fails, log and optionally raise
            logger.warning(f"Failed to add image to DOCX: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to add image to DOCX: {e!r}",
                    rendering_stage="image_processing",
                    original_error=e
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

    def visit_line_break(self, node: LineBreak) -> None:
        """Render a LineBreak node.

        Parameters
        ----------
        node : LineBreak
            Line break to render

        """
        if self._current_paragraph:
            self._current_paragraph.add_run().add_break()

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render a Strikethrough node.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, strike=True)

    def visit_underline(self, node: Underline) -> None:
        """Render an Underline node.

        Parameters
        ----------
        node : Underline
            Underline to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, underline=True)

    def visit_superscript(self, node: Superscript) -> None:
        """Render a Superscript node.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, superscript=True)

    def visit_subscript(self, node: Subscript) -> None:
        """Render a Subscript node.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        # Use efficient inline rendering
        if self._current_paragraph:
            self._render_inlines(self._current_paragraph, node.content, subscript=True)

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Render an HTMLInline node.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to render

        """
        # Skip inline HTML in DOCX
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render a FootnoteReference node.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        # Footnote references could be rendered as endnotes in Word
        # For now, render as superscript text
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        if self._current_paragraph:
            run = self._current_paragraph.add_run(f'[{node.identifier}]')
            run.font.superscript = True

    def visit_math_inline(self, node: MathInline) -> None:
        """Render a MathInline node.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        # Render math with best available representation (fallback to plain text)
        if self._current_paragraph is None:
            if self.document:
                self._current_paragraph = self.document.add_paragraph()

        if self._current_paragraph:
            content, notation = node.get_preferred_representation("latex")
            if notation == "latex":
                text = f'${content}$'
            else:
                text = content

            self._current_paragraph.add_run(text)

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Render a FootnoteDefinition node.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to render

        """
        # Render as a separate paragraph
        if not self.document:
            return

        para = self.document.add_paragraph()
        run = para.add_run(f'[{node.identifier}]: ')
        run.font.superscript = True

        self._current_paragraph = para
        for child in node.content:
            child.accept(self)
        self._current_paragraph = None

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render a DefinitionList node.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for term, descriptions in node.items:
            # Render term as bold paragraph
            if self.document:
                term_para = self.document.add_paragraph()
                self._current_paragraph = term_para

                for child in term.content:
                    child.accept(self)

                # Make term bold
                for run in term_para.runs:
                    run.bold = True

                # Render descriptions as indented paragraphs
                for desc in descriptions:
                    desc_para = self.document.add_paragraph()
                    desc_para.paragraph_format.left_indent = self._Inches(0.5)
                    self._current_paragraph = desc_para

                    for child in desc.content:
                        child.accept(self)

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
        # Render math as code block (proper equation rendering is complex)
        if not self.document:
            return

        para = self.document.add_paragraph()
        content, notation = node.get_preferred_representation("latex")
        if notation == "latex":
            text = f'$$\n{content}\n$$'
        else:
            text = content

        run = para.add_run(text)
        run.font.name = self.options.code_font
        run.font.size = self._Pt(self.options.code_font_size)
