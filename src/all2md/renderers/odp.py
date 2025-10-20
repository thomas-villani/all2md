#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/odp.py
"""ODP rendering from AST.

This module provides the OdpRenderer class which converts AST nodes
to OpenDocument Presentation (.odp) format. The renderer uses odfpy to generate
.odp files with proper slide layouts and formatting.

The rendering process splits the AST into slides using configurable
strategies (separator-based or heading-based), converts each slide's
content to ODP shapes, and assembles a complete presentation.

"""

from __future__ import annotations

import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass

from all2md.ast.nodes import (
    BlockQuote,
    Code,
    CodeBlock,
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
    Image,
    LineBreak,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
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
from all2md.ast.visitors import NodeVisitor
from all2md.exceptions import RenderingError
from all2md.options.odp import OdpRendererOptions
from all2md.renderers._split_utils import (
    auto_split_ast,
    extract_heading_text,
    split_ast_by_heading,
    split_ast_by_separator,
)
from all2md.renderers.base import BaseRenderer
from all2md.utils.decorators import requires_dependencies
from all2md.utils.images import decode_base64_image_to_file
from all2md.utils.network_security import fetch_image_securely, is_network_disabled

logger = logging.getLogger(__name__)


class OdpRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to ODP format.

    This class converts an AST document into an OpenDocument Presentation
    using odfpy. It splits the document into slides based on
    configured strategy and generates proper slide layouts and content.

    Parameters
    ----------
    options : OdpRendererOptions or None, default = None
        ODP rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.options.odp import OdpRendererOptions
        >>> from all2md.ast import Document, Heading, Paragraph, Text
        >>> from all2md.renderers.odp import OdpRenderer
        >>> doc = Document(children=[
        ...     Heading(level=2, content=[Text(content="Slide 1")]),
        ...     Paragraph(content=[Text(content="Content here")])
        ... ])
        >>> options = OdpRendererOptions()
        >>> renderer = OdpRenderer(options)
        >>> renderer.render(doc, "output.odp")

    """

    def __init__(self, options: OdpRendererOptions | None = None):
        """Initialize the ODP renderer with options."""
        options = options or OdpRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: OdpRendererOptions = options

        # Rendering state
        self._current_frame: Any | None = None  # Current text frame being rendered
        self._current_paragraph: Any = None
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level
        self._temp_files: list[str] = []  # Track temp files for cleanup

    @requires_dependencies("odp_render", [("odfpy", "odf", "")])
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to an ODP file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        DependencyError
            If odfpy is not installed
        RenderingError
            If ODP generation fails

        """
        from odf.opendocument import OpenDocumentPresentation
        from odf.style import MasterPage, PageLayout, PageLayoutProperties

        try:
            # Create presentation
            if self.options.template_path:
                prs = OpenDocumentPresentation.load(self.options.template_path)
                # Find existing master page
                master_page = None
                for mp in prs.masterstyles.childNodes:
                    if mp.qname == (prs.STYLENS, 'master-page'):
                        master_page = mp
                        break
            else:
                prs = OpenDocumentPresentation()

                # Define basic page layout
                page_layout = PageLayout(name="StandardLayout")
                page_layout.addElement(PageLayoutProperties(
                    margintop="1in", marginbottom="1in",
                    marginleft="1in", marginright="1in"
                ))
                prs.automaticstyles.addElement(page_layout)

                # Create master page
                master_page = MasterPage(name="Standard", pagelayoutname=page_layout)
                prs.masterstyles.addElement(master_page)

            # Store master page for slide creation
            self._master_page = master_page

            # Split document into slides
            slides_data = self._split_into_slides(doc)

            # Create slides
            for idx, (heading, content_nodes) in enumerate(slides_data, start=1):
                self._create_slide(prs, heading, content_nodes, is_first=(idx == 1))

            # Save presentation
            if isinstance(output, (str, Path)):
                prs.save(str(output))
            else:
                # For file-like objects, save to BytesIO first
                buffer = BytesIO()
                prs.save(buffer)
                buffer.seek(0)
                output.write(buffer.read())
        except Exception as e:
            raise RenderingError(
                f"Failed to write ODP file: {e!r}", rendering_stage="rendering", original_error=e
            ) from e
        finally:
            # Clean up temporary files
            import os

            for temp_file in self._temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception:
                    pass  # Ignore cleanup errors

    @requires_dependencies("odp_render", [("odfpy", "odf", "")])
    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to ODP bytes.

        Returns
        -------
        bytes
            ODP file content as bytes

        """
        buffer = BytesIO()
        self.render(doc, buffer)
        return buffer.getvalue()

    def _split_into_slides(self, doc: Document) -> list[tuple[Heading | None, list[Node]]]:
        """Split AST document into slides based on configured strategy.

        Parameters
        ----------
        doc : Document
            AST document to split

        Returns
        -------
        list of tuple[Heading or None, list of Node]
            List of (heading, content_nodes) tuples

        """
        split_mode = self.options.slide_split_mode

        if split_mode == "separator":
            # Split on ThematicBreak nodes
            separator_chunks = split_ast_by_separator(doc)
            return [(None, chunk) for chunk in separator_chunks]

        elif split_mode == "heading":
            # Split on heading level
            return split_ast_by_heading(doc, heading_level=self.options.slide_split_heading_level)

        else:  # "auto"
            # Auto-detect best strategy
            return auto_split_ast(doc, heading_level=self.options.slide_split_heading_level)

    def _create_slide(
        self, prs: Any, heading: Heading | None, content_nodes: list[Node], is_first: bool = False
    ) -> Any:
        """Create a slide with content.

        Parameters
        ----------
        prs : OpenDocumentPresentation
            ODP presentation object
        heading : Heading or None
            Slide heading (becomes title if use_heading_as_slide_title=True)
        content_nodes : list of Node
            AST nodes to render on slide
        is_first : bool, default False
            Whether this is the first slide

        Returns
        -------
        Any
            Created slide/page object

        """
        from odf.draw import Frame, Page, TextBox
        from odf.text import P

        # Create page (slide) with master page
        page = Page(
            name=f"page{id(heading) if heading else id(content_nodes)}",
            masterpagename=self._master_page
        )

        # Determine title
        title = ""
        nodes_to_render = content_nodes

        if self.options.use_heading_as_slide_title:
            if heading:
                # Heading provided by splitting strategy (heading mode)
                title = extract_heading_text(heading)
            elif content_nodes and isinstance(content_nodes[0], Heading):
                # Extract first heading from content (separator mode)
                title = extract_heading_text(content_nodes[0])
                # Don't render the heading again in content
                nodes_to_render = content_nodes[1:]

        # Create title frame if we have a title
        if title:
            title_frame = Frame(
                width="9in",
                height="1in",
                x="0.5in",
                y="0.5in"
            )
            title_textbox = TextBox()
            title_para = P()
            title_para.addText(title)
            title_textbox.addElement(title_para)
            title_frame.addElement(title_textbox)
            page.addElement(title_frame)

        # Create content frame
        content_frame = Frame(
            width="9in",
            height="6in",
            x="0.5in",
            y="1.75in"
        )
        content_textbox = TextBox()

        # Set current frame for rendering
        self._current_frame = content_textbox

        # Render content nodes
        for node in nodes_to_render:
            if isinstance(node, Table):
                # Tables need special handling - render directly to page
                self._render_table(page, node)
            elif isinstance(node, Image):
                # Images need special handling - render directly to page
                self._render_image(page, node)
            else:
                # Render to text box
                node.accept(self)

        content_frame.addElement(content_textbox)
        page.addElement(content_frame)

        # Add page to presentation
        prs.presentation.addElement(page)

        return page

    def _render_table(self, page: Any, table: Table) -> None:
        """Render a table on the slide.

        Parameters
        ----------
        page : Page
            ODP page to add table to
        table : Table
            AST table node

        """
        from odf.table import Table as OdfTable
        from odf.table import TableCell, TableColumn, TableRow

        # Calculate table dimensions
        num_cols = len(table.header.cells) if table.header else (len(table.rows[0].cells) if table.rows else 0)

        if num_cols == 0:
            return

        # Create table
        odf_table = OdfTable()

        # Add columns
        for _ in range(num_cols):
            odf_table.addElement(TableColumn())

        # Render header
        if table.header:
            table_row = TableRow()
            for cell in table.header.cells:
                table_cell = TableCell()
                cell_text = self._extract_text_from_nodes(cell.content)
                from odf.text import P
                para = P()
                para.addText(cell_text)
                table_cell.addElement(para)
                table_row.addElement(table_cell)
            odf_table.addElement(table_row)

        # Render body rows
        for ast_row in table.rows:
            table_row = TableRow()
            for cell in ast_row.cells:
                table_cell = TableCell()
                cell_text = self._extract_text_from_nodes(cell.content)
                from odf.text import P
                para = P()
                para.addText(cell_text)
                table_cell.addElement(para)
                table_row.addElement(table_cell)
            odf_table.addElement(table_row)

        # Add table to page
        # Note: Tables in ODP typically go in a frame
        from odf.draw import Frame
        frame = Frame(width="8in", height="4in", x="1in", y="2in")
        frame.addElement(odf_table)
        page.addElement(frame)

    def _render_image(self, page: Any, image: Image) -> None:
        """Render an image on the slide.

        Parameters
        ----------
        page : Page
            ODP page to add image to
        image : Image
            AST image node

        """
        # Skip if no URL
        if not image.url:
            return

        try:
            # Handle different image sources
            image_file = None

            if image.url.startswith("data:"):
                # Base64 encoded image
                image_file = self._decode_base64_image(image.url)
            elif urlparse(image.url).scheme in ("http", "https"):
                # Remote URL - use secure fetching if enabled
                image_file = self._fetch_remote_image(image.url)
            else:
                # Local file path
                image_file = image.url

            # Add image to page if we have a valid file
            if image_file:
                # Generate unique name for image
                import os

                from odf.draw import Frame
                from odf.draw import Image as OdfImage
                ext = os.path.splitext(image_file)[1] or '.png'
                image_name = f"Pictures/image_{id(image)}{ext}"

                # Note: In a complete implementation, we would need to:
                # 1. Read the image data
                # 2. Add it to the presentation's manifest
                # 3. Properly embed it in the ODP package
                # For now, we just create the frame reference

                # Create frame and image
                frame = Frame(width="4in", height="4in", x="2.5in", y="2.5in")
                img = OdfImage(href=image_name)
                frame.addElement(img)
                page.addElement(frame)

        except Exception as e:
            # Log warning but don't fail rendering
            logger.warning(f"Failed to render image {image.url}: {e}")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    f"Failed to render image {image.url}: {e!r}", rendering_stage="image_processing", original_error=e
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
        else:
            logger.warning(f"Failed to decode base64 image: {data_uri[:50]}...")
            if self.options.fail_on_resource_errors:
                raise RenderingError(
                    "Failed to decode base64 image", rendering_stage="image_processing", original_error=None
                )
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

    def _extract_text_from_nodes(self, nodes: list[Node]) -> str:
        """Extract plain text from inline nodes.

        Parameters
        ----------
        nodes : list of Node
            Inline nodes to extract text from

        Returns
        -------
        str
            Plain text content

        """
        text_parts: list[str] = []

        def collect_text(node_list: list[Node]) -> None:
            """Recursively collect text."""
            for node in node_list:
                if isinstance(node, Text):
                    text_parts.append(node.content)
                elif hasattr(node, "content"):
                    if isinstance(node.content, list):
                        collect_text(node.content)
                    elif isinstance(node.content, str):
                        text_parts.append(node.content)

        collect_text(nodes)
        return "".join(text_parts)

    # Visitor methods for rendering to text frame

    def visit_paragraph(self, node: Paragraph) -> None:
        """Render a Paragraph node.

        Parameters
        ----------
        node : Paragraph
            Paragraph to render

        """
        from odf.text import P

        if not self._current_frame:
            return

        # Add paragraph to text frame
        p = P()
        self._current_paragraph = p

        # Render content
        for child in node.content:
            child.accept(self)

        self._current_frame.addElement(p)
        self._current_paragraph = None

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node (non-title headings).

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        from odf.text import P

        if not self._current_frame:
            return

        # Create paragraph for heading
        p = P()
        self._current_paragraph = p

        # Render content
        for child in node.content:
            child.accept(self)

        self._current_frame.addElement(p)
        self._current_paragraph = None

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        if self._current_paragraph:
            self._current_paragraph.addText(node.content)

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

        # Render content with bold
        for child in node.content:
            if isinstance(child, Text):
                span = Span()
                span.addText(child.content)
                # TODO: Apply bold style
                self._current_paragraph.addElement(span)
            else:
                child.accept(self)

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

        # Render content with italic
        for child in node.content:
            if isinstance(child, Text):
                span = Span()
                span.addText(child.content)
                # TODO: Apply italic style
                self._current_paragraph.addElement(span)
            else:
                child.accept(self)

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

        span = Span()
        span.addText(node.content)
        # TODO: Apply code font style
        self._current_paragraph.addElement(span)

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        from odf.text import P

        if not self._current_frame:
            return

        p = P()
        p.addText(node.content)
        # TODO: Apply code style
        self._current_frame.addElement(p)

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        from odf.text import List as OdfList

        # Track ordered/unordered
        self._list_ordered_stack.append(node.ordered)

        # Create ODF list
        odf_list = OdfList()

        # Render list items
        for item in node.items:
            saved_list = getattr(self, '_current_list', None)
            self._current_list = odf_list
            item.accept(self)
            self._current_list = saved_list

        # Add list to current frame or paragraph
        if self._current_paragraph:
            self._current_paragraph.addElement(odf_list)
        elif self._current_frame:
            self._current_frame.addElement(odf_list)

        # Clean up state
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
            if isinstance(child, Paragraph):
                # Render paragraph content directly
                for inline in child.content:
                    inline.accept(self)
            elif isinstance(child, List):
                # Nested list - will be handled by visit_list
                child.accept(self)
            else:
                child.accept(self)

        list_item.addElement(para)

        # Add to current list
        if hasattr(self, '_current_list'):
            self._current_list.addElement(list_item)

        self._current_paragraph = None

    # Stub methods for other node types

    def visit_document(self, node: Document) -> None:
        """Document handled by render() method."""
        pass

    def visit_link(self, node: Link) -> None:
        """Render link."""
        from odf.text import A

        if not self._current_paragraph:
            return

        link = A(href=node.url)
        saved_para = self._current_paragraph
        self._current_paragraph = link

        for child in node.content:
            child.accept(self)

        self._current_paragraph = saved_para
        saved_para.addElement(link)

    def visit_image(self, node: Image) -> None:
        """Images handled separately by _render_image()."""
        pass

    def visit_table(self, node: Table) -> None:
        """Tables handled separately by _render_table()."""
        pass

    def visit_table_row(self, node: TableRow) -> None:
        """Handle table row (delegated to visit_table)."""
        pass

    def visit_table_cell(self, node: TableCell) -> None:
        """Handle table cell (delegated to visit_table)."""
        pass

    def visit_line_break(self, node: LineBreak) -> None:
        """Render line break."""
        from odf.text import LineBreak as OdfLineBreak

        if self._current_paragraph:
            self._current_paragraph.addElement(OdfLineBreak())

    def visit_underline(self, node: Underline) -> None:
        """Render underline."""
        for child in node.content:
            child.accept(self)

    def visit_block_quote(self, node: BlockQuote) -> None:
        """Render block quote."""
        if not self._current_frame:
            return

        # Render children
        for child in node.children:
            child.accept(self)

    def visit_thematic_break(self, node: ThematicBreak) -> None:
        """Render thematic break."""
        from odf.text import P

        if not self._current_frame:
            return

        # Add a separator paragraph
        p = P()
        p.addText("---")
        self._current_frame.addElement(p)

    def visit_strikethrough(self, node: Strikethrough) -> None:
        """Render strikethrough text."""
        for child in node.content:
            child.accept(self)

    def visit_subscript(self, node: Subscript) -> None:
        """Render subscript text."""
        for child in node.content:
            child.accept(self)

    def visit_superscript(self, node: Superscript) -> None:
        """Render superscript text."""
        for child in node.content:
            child.accept(self)

    def visit_html_block(self, node: HTMLBlock) -> None:
        """Skip HTML blocks in ODP rendering."""
        pass

    def visit_html_inline(self, node: HTMLInline) -> None:
        """Skip inline HTML in ODP rendering."""
        pass

    def visit_footnote_reference(self, node: FootnoteReference) -> None:
        """Render footnote reference."""
        if not self._current_paragraph:
            return

        self._current_paragraph.addText(f"[{node.identifier}]")

    def visit_footnote_definition(self, node: FootnoteDefinition) -> None:
        """Skip footnote definitions in ODP rendering."""
        pass

    def visit_math_inline(self, node: MathInline) -> None:
        """Render inline math as plain text."""
        if not self._current_paragraph:
            return

        # Get preferred representation (prefer latex, fallback to others)
        content, notation = node.get_preferred_representation("latex")

        # Wrap latex in $ delimiters for clarity
        if notation == "latex":
            text = f"${content}$"
        else:
            text = content

        self._current_paragraph.addText(text)

    def visit_math_block(self, node: MathBlock) -> None:
        """Render math block as plain text."""
        from odf.text import P

        if not self._current_frame:
            return

        # Get preferred representation (prefer latex, fallback to others)
        content, notation = node.get_preferred_representation("latex")

        p = P()
        # Wrap latex in $$ delimiters for clarity
        if notation == "latex":
            text = f"$${content}$$"
        else:
            text = content

        p.addText(text)
        self._current_frame.addElement(p)

    def visit_definition_list(self, node: DefinitionList) -> None:
        """Render definition list."""
        for term, descriptions in node.items:
            term.accept(self)
            for desc in descriptions:
                desc.accept(self)

    def visit_definition_term(self, node: DefinitionTerm) -> None:
        """Render definition term as bold text."""
        from odf.text import P

        if not self._current_frame:
            return

        p = P()
        self._current_paragraph = p

        for child in node.content:
            child.accept(self)

        self._current_frame.addElement(p)
        self._current_paragraph = None

    def visit_definition_description(self, node: DefinitionDescription) -> None:
        """Render definition description as indented text."""
        from odf.text import P

        if not self._current_frame:
            return

        p = P()
        self._current_paragraph = p

        for child in node.content:
            child.accept(self)

        self._current_frame.addElement(p)
        self._current_paragraph = None
