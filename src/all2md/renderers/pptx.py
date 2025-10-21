#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/pptx.py
"""PPTX rendering from AST.

This module provides the PptxRenderer class which converts AST nodes
to PowerPoint presentations. The renderer uses python-pptx to generate
.pptx files with proper slide layouts and formatting.

The rendering process splits the AST into slides using configurable
strategies (separator-based or heading-based), converts each slide's
content to PowerPoint shapes, and assembles a complete presentation.

"""

from __future__ import annotations

import logging
import tempfile
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Union
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pptx.presentation import Presentation
    from pptx.slide import Slide
    from pptx.text.text import TextFrame

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
from all2md.options.pptx import PptxRendererOptions
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


class PptxRenderer(NodeVisitor, BaseRenderer):
    """Render AST nodes to PPTX format.

    This class converts an AST document into a PowerPoint presentation
    using python-pptx. It splits the document into slides based on
    configured strategy and generates proper slide layouts and content.

    Parameters
    ----------
    options : PptxRendererOptions or None, default = None
        PPTX rendering options

    Examples
    --------
    Basic usage:

        >>> from all2md.options.pptx import PptxRendererOptions
        >>> from all2md.ast import Document, Heading, Paragraph, Text
        >>> from all2md.renderers.pptx import PptxRenderer
        >>> doc = Document(children=[
        ...     Heading(level=2, content=[Text(content="Slide 1")]),
        ...     Paragraph(content=[Text(content="Content here")])
        ... ])
        >>> options = PptxRendererOptions()
        >>> renderer = PptxRenderer(options)
        >>> renderer.render(doc, "output.pptx")


    """

    def __init__(self, options: PptxRendererOptions | None = None):
        """Initialize the PPTX renderer with options."""
        options = options or PptxRendererOptions()
        BaseRenderer.__init__(self, options)
        self.options: PptxRendererOptions = options

        # Rendering state
        self._current_textbox: TextFrame | None = None
        self._current_paragraph: Any = None
        self._list_ordered_stack: list[bool] = []  # Track ordered/unordered at each level
        self._list_item_counters: list[int] = []  # Track item number at each level for ordered lists
        self._temp_files: list[str] = []  # Track temp files for cleanup

    @requires_dependencies("pptx_render", [("python-pptx", "pptx", ">=0.6.21")])
    def render(self, doc: Document, output: Union[str, Path, IO[bytes]]) -> None:
        """Render the AST to a PPTX file.

        Parameters
        ----------
        doc : Document
            AST Document node to render
        output : str, Path, or IO[bytes]
            Output destination (file path or file-like object)

        Raises
        ------
        DependencyError
            If python-pptx is not installed
        RenderingError
            If PPTX generation fails

        """
        from pptx import Presentation
        from pptx.util import Inches, Pt

        # Store imports
        self._Inches = Inches
        self._Pt = Pt

        # Create presentation
        if self.options.template_path:
            prs = Presentation(self.options.template_path)
        else:
            prs = Presentation()

        # Split document into slides
        slides_data = self._split_into_slides(doc)

        # Create slides
        for idx, (heading, content_nodes) in enumerate(slides_data, start=1):
            self._create_slide(prs, heading, content_nodes, is_first=(idx == 1))

        # Save presentation
        try:
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
                f"Failed to write PPTX file: {e!r}", rendering_stage="rendering", original_error=e
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

    @requires_dependencies("pptx_render", [("python-pptx", "pptx", ">=0.6.21")])
    def render_to_bytes(self, doc: Document) -> bytes:
        """Render the AST to PPTX bytes.

        Returns
        -------
        bytes
            PPTX file content as bytes

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
            self, prs: "Presentation", heading: Heading | None, content_nodes: list[Node], is_first: bool = False
    ) -> "Slide":
        """Create a slide with content.

        Parameters
        ----------
        prs : Presentation
            PowerPoint presentation object
        heading : Heading or None
            Slide heading (becomes title if use_heading_as_slide_title=True)
        content_nodes : list of Node
            AST nodes to render on slide
        is_first : bool, default False
            Whether this is the first slide (uses title slide layout)

        Returns
        -------
        Slide
            Created slide object

        """
        # Determine layout
        if is_first:
            layout_name = self.options.title_slide_layout
        else:
            layout_name = self.options.default_layout

        # Find layout (fallback to index 0 if not found)
        layout = None
        for slide_layout in prs.slide_layouts:
            if slide_layout.name == layout_name:
                layout = slide_layout
                break

        if layout is None:
            layout = prs.slide_layouts[0]  # Use first layout as fallback

        # Create slide
        slide = prs.slides.add_slide(layout)

        # Set title
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

        # Add title to slide if it has a title placeholder
        if slide.shapes.title and title:
            slide.shapes.title.text = title

        # Render content nodes
        self._render_slide_content(slide, nodes_to_render)

        return slide

    def _render_slide_content(self, slide: "Slide", nodes: list[Node]) -> None:
        """Render AST nodes as slide content.

        Parameters
        ----------
        slide : Slide
            Slide to add content to
        nodes : list of Node
            AST nodes to render

        """
        # Try to find content placeholder with robust detection
        content_placeholder = None

        # Strategy 1: Look for text frame placeholders that aren't the title
        for shape in slide.placeholders:
            if not hasattr(shape, "text_frame"):
                continue

            # Skip title placeholder (usually idx 0)
            try:
                if shape.placeholder_format.idx == 0:
                    continue
            except Exception:
                pass

            # Try to find body/content placeholder by type
            try:
                # PP_PLACEHOLDER type 2 is body/content
                if hasattr(shape.placeholder_format, "type") and shape.placeholder_format.type == 2:
                    content_placeholder = shape
                    break
            except Exception:
                pass

            # Fallback: Use first non-title placeholder with text frame
            if content_placeholder is None and shape.has_text_frame:
                content_placeholder = shape

        if content_placeholder:
            # Use placeholder text frame
            text_frame = content_placeholder.text_frame
            text_frame.clear()  # Clear any default text
            self._current_textbox = text_frame
        else:
            # Create a text box for content
            from pptx.util import Inches

            left = Inches(0.5)
            top = Inches(1.5)
            width = Inches(9.0)
            height = Inches(5.0)

            textbox = slide.shapes.add_textbox(left, top, width, height)
            self._current_textbox = textbox.text_frame

        # Render nodes
        for node in nodes:
            if isinstance(node, Table):
                self._render_table(slide, node)
            elif isinstance(node, Image):
                self._render_image(slide, node)
            else:
                # Render to text frame
                node.accept(self)

    def _render_table(self, slide: "Slide", table: Table) -> None:
        """Render a table as a PowerPoint table.

        Parameters
        ----------
        slide : Slide
            Slide to add table to
        table : Table
            AST table node

        """
        from pptx.util import Inches

        # Calculate table dimensions
        num_rows = len(table.rows) + (1 if table.header else 0)
        num_cols = len(table.header.cells) if table.header else (len(table.rows[0].cells) if table.rows else 0)

        if num_cols == 0 or num_rows == 0:
            return

        # Use configurable positioning and sizing
        left = Inches(self.options.table_left)
        top = Inches(self.options.table_top)
        width = Inches(self.options.table_width)
        height = Inches(self.options.table_height_per_row * num_rows)

        table_shape = slide.shapes.add_table(num_rows, num_cols, left, top, width, height)
        pptx_table = table_shape.table

        # Render header
        row_idx = 0
        if table.header:
            for col_idx, cell in enumerate(table.header.cells):
                if col_idx < len(pptx_table.rows[row_idx].cells):
                    cell_text = self._extract_text_from_nodes(cell.content)
                    pptx_table.rows[row_idx].cells[col_idx].text = cell_text
            row_idx += 1

        # Render body rows
        for ast_row in table.rows:
            if row_idx < len(pptx_table.rows):
                for col_idx, cell in enumerate(ast_row.cells):
                    if col_idx < len(pptx_table.rows[row_idx].cells):
                        cell_text = self._extract_text_from_nodes(cell.content)
                        pptx_table.rows[row_idx].cells[col_idx].text = cell_text
            row_idx += 1

    def _render_image(self, slide: "Slide", image: Image) -> None:
        """Render an image on the slide.

        Parameters
        ----------
        slide : Slide
            Slide to add image to
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

            # Add image to slide if we have a valid file
            if image_file:
                from pptx.util import Inches

                # Use configurable positioning and sizing
                left = Inches(self.options.image_left)
                top = Inches(self.options.image_top)

                # Add image with configurable width, maintaining aspect ratio
                try:
                    slide.shapes.add_picture(image_file, left, top, width=Inches(self.options.image_width))
                except Exception as e:
                    logger.warning(f"Failed to add image to slide: {e}")
                    if self.options.fail_on_resource_errors:
                        raise RenderingError(
                            f"Failed to add image to slide: {e!r}", rendering_stage="image_processing", original_error=e
                        ) from e

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
        if not self._current_textbox:
            return

        # Add paragraph to text frame
        p = self._current_textbox.add_paragraph()
        self._current_paragraph = p

        # Set font size
        p.font.size = self._Pt(self.options.default_font_size)

        # Render content
        for child in node.content:
            child.accept(self)

        self._current_paragraph = None

    def visit_heading(self, node: Heading) -> None:
        """Render a Heading node (non-title headings).

        Parameters
        ----------
        node : Heading
            Heading to render

        """
        if not self._current_textbox:
            return

        # Create paragraph for heading
        p = self._current_textbox.add_paragraph()
        self._current_paragraph = p

        # Make it bold and larger
        p.font.bold = True
        p.font.size = self._Pt(self.options.default_font_size + 4)

        # Render content
        for child in node.content:
            child.accept(self)

        self._current_paragraph = None

    def visit_text(self, node: Text) -> None:
        """Render a Text node.

        Parameters
        ----------
        node : Text
            Text to render

        """
        if not self._current_paragraph:
            return

        run = self._current_paragraph.add_run()
        run.text = node.content

    def visit_strong(self, node: Strong) -> None:
        """Render a Strong node.

        Parameters
        ----------
        node : Strong
            Strong to render

        """
        if not self._current_paragraph:
            return

        # Render content with bold
        for child in node.content:
            if isinstance(child, Text):
                run = self._current_paragraph.add_run()
                run.text = child.content
                run.font.bold = True
            else:
                child.accept(self)

    def visit_emphasis(self, node: Emphasis) -> None:
        """Render an Emphasis node.

        Parameters
        ----------
        node : Emphasis
            Emphasis to render

        """
        if not self._current_paragraph:
            return

        # Render content with italic
        for child in node.content:
            if isinstance(child, Text):
                run = self._current_paragraph.add_run()
                run.text = child.content
                run.font.italic = True
            else:
                child.accept(self)

    def visit_code(self, node: Code) -> None:
        """Render a Code node.

        Parameters
        ----------
        node : Code
            Code to render

        """
        if not self._current_paragraph:
            return

        run = self._current_paragraph.add_run()
        run.text = node.content
        run.font.name = "Courier New"

    def visit_code_block(self, node: CodeBlock) -> None:
        """Render a CodeBlock node.

        Parameters
        ----------
        node : CodeBlock
            Code block to render

        """
        if not self._current_textbox:
            return

        p = self._current_textbox.add_paragraph()
        run = p.add_run()
        run.text = node.content
        run.font.name = "Courier New"
        run.font.size = self._Pt(self.options.default_font_size - 2)

    def visit_list(self, node: List) -> None:
        """Render a List node.

        Parameters
        ----------
        node : List
            List to render

        """
        # Track ordered/unordered and initialize counter for ordered lists
        self._list_ordered_stack.append(node.ordered)
        if node.ordered:
            self._list_item_counters.append(node.start if hasattr(node, "start") else 1)
        else:
            self._list_item_counters.append(0)  # Not used for unordered

        # Render list items
        for item in node.items:
            item.accept(self)
            # Increment counter for ordered lists
            if node.ordered and self._list_item_counters:
                self._list_item_counters[-1] += 1

        # Clean up state
        self._list_ordered_stack.pop()
        self._list_item_counters.pop()

    def visit_list_item(self, node: ListItem) -> None:
        """Render a ListItem node.

        Parameters
        ----------
        node : ListItem
            List item to render

        Notes
        -----
        **Bullet Handling in Text Boxes vs Placeholders:**

        PowerPoint behaves differently for text boxes vs content placeholders:
        - **Content placeholders**: Bullets are enabled by default, setting `p.level`
          is sufficient to display bullets at the appropriate nesting level.
        - **Text boxes**: Bullets are disabled by default. Setting `p.level` alone
          will NOT show bullets. We must explicitly enable bullets via OOXML.

        This implementation uses python-pptx's OOXML API to programmatically enable
        bullets for unordered lists in all contexts (both placeholders and text boxes).

        """
        if not self._current_textbox:
            return

        # Create paragraph for list item
        p = self._current_textbox.add_paragraph()

        # Determine if this is ordered or unordered
        is_ordered = self._list_ordered_stack[-1] if self._list_ordered_stack else False

        # Calculate nesting level (depth in the stack)
        nesting_level = len(self._list_ordered_stack) - 1
        # Limit to reasonable depth for PowerPoint (0-8)
        nesting_level = min(nesting_level, 8)

        if is_ordered:
            # For ordered lists, manually add number prefix since python-pptx
            # has limited support for numbered lists
            item_number = self._list_item_counters[-1] if self._list_item_counters else 1

            # Set indentation level but no bullet (we're adding our own number)
            p.level = nesting_level

            # Add numbered prefix as the first run with configurable spacing
            run = p.add_run()
            spaces = " " * self.options.list_number_spacing
            run.text = f"{item_number}.{spaces}"
            run.font.bold = True  # Make number bold for visibility

            # Apply configurable indentation for nested lists
            # Note: Actual spacing may vary across templates
            if nesting_level > 0:
                try:
                    # python-pptx's level property handles indentation automatically,
                    # but templates may override this. The list_indent_per_level option
                    # documents the intent, though actual rendering depends on template.
                    p.level = nesting_level  # Already set above, but explicit for clarity
                except Exception as e:
                    logger.debug(f"Failed to apply list indentation: {e}")
        else:
            # For unordered lists, use PowerPoint's built-in bullet system
            p.level = nesting_level

            # Explicitly enable bullets via OOXML for text boxes
            # This ensures bullets appear in both text boxes and content placeholders
            try:
                # Access paragraph properties element
                pPr = p._element.get_or_add_pPr()
                # Enable bullet numbering by adding/updating buFont, buChar, or buAutoNum
                # For simple bullets, we add a buChar element (bullet character)
                from pptx.oxml import parse_xml

                # Check if bullet is already configured
                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                if pPr.find(".//a:buChar", namespaces=ns) is None:
                    # Add bullet character (standard bullet: U+2022)
                    xml_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
                    bu_char_xml = f'<a:buChar xmlns:a="{xml_ns}" char="\u2022"/>'
                    bu_char = parse_xml(bu_char_xml)
                    pPr.append(bu_char)
            except Exception as e:
                # If OOXML manipulation fails, log warning but continue
                # Bullets may not appear in text boxes, but rendering won't fail
                logger.debug(f"Failed to enable bullets via OOXML: {e}")

            # Apply configurable indentation for nested lists
            # Note: list_indent_per_level option documents intent, but actual
            # rendering depends on template as python-pptx's level property
            # handles indentation automatically based on template settings
            if nesting_level > 0:
                # Indentation is controlled by p.level which was set above
                # The list_indent_per_level option documents expected behavior
                pass

        self._current_paragraph = p

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

        self._current_paragraph = None

    # Stub methods for other node types

    def visit_document(self, node: Document) -> None:
        """Document handled by render() method."""
        pass

    def visit_link(self, node: Link) -> None:
        """Render link as plain text (hyperlinks not implemented yet)."""
        for child in node.content:
            child.accept(self)

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
        if self._current_paragraph:
            self._current_paragraph.add_run().text = "\n"

    def visit_underline(self, node: Underline) -> None:
        """Render underline."""
        for child in node.content:
            child.accept(self)

    def visit_block_quote(self, node: "BlockQuote") -> None:
        """Render block quote as indented text.

        Parameters
        ----------
        node : BlockQuote
            Block quote to render

        """
        if not self._current_textbox:
            return

        # Render children with indentation
        for child in node.children:
            child.accept(self)

    def visit_thematic_break(self, node: "ThematicBreak") -> None:
        """Render thematic break as separator line.

        Parameters
        ----------
        node : ThematicBreak
            Thematic break to render

        """
        if not self._current_textbox:
            return

        # Add a separator paragraph
        p = self._current_textbox.add_paragraph()
        run = p.add_run()
        run.text = "---"

    def visit_strikethrough(self, node: "Strikethrough") -> None:
        """Render strikethrough text.

        Parameters
        ----------
        node : Strikethrough
            Strikethrough to render

        """
        if not self._current_paragraph:
            return

        # Render content with strikethrough (python-pptx doesn't support strikethrough directly)
        for child in node.content:
            child.accept(self)

    def visit_subscript(self, node: "Subscript") -> None:
        """Render subscript text.

        Parameters
        ----------
        node : Subscript
            Subscript to render

        """
        if not self._current_paragraph:
            return

        # Render content (python-pptx has limited subscript support)
        for child in node.content:
            child.accept(self)

    def visit_superscript(self, node: "Superscript") -> None:
        """Render superscript text.

        Parameters
        ----------
        node : Superscript
            Superscript to render

        """
        if not self._current_paragraph:
            return

        # Render content (python-pptx has limited superscript support)
        for child in node.content:
            child.accept(self)

    def visit_html_block(self, node: "HTMLBlock") -> None:
        """Skip HTML blocks in PPTX rendering.

        Parameters
        ----------
        node : HTMLBlock
            HTML block to skip

        """
        pass

    def visit_html_inline(self, node: "HTMLInline") -> None:
        """Skip inline HTML in PPTX rendering.

        Parameters
        ----------
        node : HTMLInline
            Inline HTML to skip

        """
        pass

    def visit_footnote_reference(self, node: "FootnoteReference") -> None:
        """Render footnote reference as superscript number.

        Parameters
        ----------
        node : FootnoteReference
            Footnote reference to render

        """
        if not self._current_paragraph:
            return

        run = self._current_paragraph.add_run()
        run.text = f"[{node.identifier}]"

    def visit_footnote_definition(self, node: "FootnoteDefinition") -> None:
        """Skip footnote definitions in PPTX rendering.

        Parameters
        ----------
        node : FootnoteDefinition
            Footnote definition to skip

        """
        pass

    def visit_math_inline(self, node: "MathInline") -> None:
        """Render inline math as plain text.

        Parameters
        ----------
        node : MathInline
            Inline math to render

        """
        if not self._current_paragraph:
            return

        # Get preferred representation (prefer latex, fallback to others)
        content, notation = node.get_preferred_representation("latex")

        run = self._current_paragraph.add_run()
        # Wrap latex in $ delimiters for clarity
        if notation == "latex":
            run.text = f"${content}$"
        else:
            run.text = content

    def visit_math_block(self, node: "MathBlock") -> None:
        """Render math block as plain text.

        Parameters
        ----------
        node : MathBlock
            Math block to render

        """
        if not self._current_textbox:
            return

        # Get preferred representation (prefer latex, fallback to others)
        content, notation = node.get_preferred_representation("latex")

        p = self._current_textbox.add_paragraph()
        run = p.add_run()
        # Wrap latex in $$ delimiters for clarity
        if notation == "latex":
            run.text = f"$${content}$$"
        else:
            run.text = content

    def visit_definition_list(self, node: "DefinitionList") -> None:
        """Render definition list.

        Parameters
        ----------
        node : DefinitionList
            Definition list to render

        """
        for term, descriptions in node.items:
            term.accept(self)
            for desc in descriptions:
                desc.accept(self)

    def visit_definition_term(self, node: "DefinitionTerm") -> None:
        """Render definition term as bold text.

        Parameters
        ----------
        node : DefinitionTerm
            Definition term to render

        """
        if not self._current_textbox:
            return

        p = self._current_textbox.add_paragraph()
        self._current_paragraph = p
        p.font.bold = True

        for child in node.content:
            child.accept(self)

        self._current_paragraph = None

    def visit_definition_description(self, node: "DefinitionDescription") -> None:
        """Render definition description as indented text.

        Parameters
        ----------
        node : DefinitionDescription
            Definition description to render

        """
        if not self._current_textbox:
            return

        p = self._current_textbox.add_paragraph()
        p.level = 1
        self._current_paragraph = p

        for child in node.content:
            child.accept(self)

        self._current_paragraph = None
