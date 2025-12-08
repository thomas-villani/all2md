#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/odp.py
"""ODP (OpenDocument Presentation) to AST converter.

This module provides conversion from ODP presentation files to AST representation.
It replaces the combined ODF parser with a focused presentation parser.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, Union, cast

from all2md.ast import (
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    MathBlock,
    MathInline,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    Underline,
)
from all2md.constants import DEPS_ODF
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError
from all2md.options.odp import OdpOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.html_sanitizer import sanitize_url
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import append_attachment_footnotes, attachment_result_to_image_node

if TYPE_CHECKING:
    import odf
    import odf.opendocument

logger = logging.getLogger(__name__)


class OdpToAstConverter(BaseParser):
    """Convert ODP presentation files to AST representation.

    This converter processes ODP (OpenDocument Presentation) files and builds
    an AST that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : OdpOptions or None
        Conversion options

    """

    @requires_dependencies("odp", DEPS_ODF)
    def __init__(self, options: Optional[OdpOptions] = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the ODP parser with options and progress callback."""
        BaseParser._validate_options_type(options, OdpOptions, "odp")
        options = options or OdpOptions()
        super().__init__(options, progress_callback)
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

        # Type hint for IDE
        self.options: OdpOptions = options

        from odf import namespaces

        self._list_level = 0
        self._current_slide = 0

        # Namespace constants
        self.TEXTNS = namespaces.TEXTNS
        self.DRAWNS = namespaces.DRAWNS
        self.STYLENS = namespaces.STYLENS
        self.MATHNS = getattr(namespaces, "MATHNS", "http://www.w3.org/1998/Math/MathML")
        self.PRESENTATIONNS = getattr(
            namespaces, "PRESENTATIONNS", "urn:oasis:names:tc:opendocument:xmlns:presentation:1.0"
        )

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ODP document into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ODP document to parse

        Returns
        -------
        Document
            AST Document node representing the parsed presentation structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed

        """
        from odf import opendocument

        # Validate ZIP archive security and get validated input
        # For bytes/IO inputs, this creates a temp file that odfpy can read
        with self._validated_zip_input(input_data, suffix=".odp") as validated_input:
            try:
                doc = opendocument.load(validated_input)
            except Exception as e:
                raise MalformedFileError(f"Failed to open ODP document: {e!r}", original_error=e) from e

            return self.convert_to_ast(doc)

    def convert_to_ast(self, doc: "odf.opendocument.OpenDocument") -> Document:
        """Convert ODP document to AST Document.

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        # For ODP, content is in doc.presentation
        content_root = getattr(doc, "presentation", None)

        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}
        self._list_level = 0
        self._current_slide = 0

        # Extract metadata
        metadata = self.extract_metadata(doc)

        if not content_root:
            return Document(children=[], metadata=metadata.to_dict())

        # Parse slide selection if specified
        slide_indices = self._parse_slide_selection(self.options.slides, metadata)

        slide_num = 0
        total_slides = len([e for e in content_root.childNodes if self._is_slide_element(e)])

        for element in content_root.childNodes:
            if not self._is_slide_element(element):
                continue

            slide_num += 1

            # Skip if not in selection
            if slide_indices is not None and (slide_num - 1) not in slide_indices:
                continue

            self._current_slide = slide_num

            # Add slide separator if requested
            if slide_num > 1 and self.options.page_separator_template:
                separator_text = self.options.page_separator_template.format(
                    page_num=slide_num, total_pages=total_slides
                )
                children.append(Paragraph(content=[Text(content=separator_text)]))

            # Add slide number if requested
            if self.options.include_slide_numbers:
                slide_label = f"Slide {slide_num}"
                if total_slides > 0:
                    slide_label += f" of {total_slides}"
                children.append(Paragraph(content=[Text(content=slide_label)]))

            # Process slide content
            slide_nodes = self._process_slide(element, doc)
            if slide_nodes:
                children.extend(slide_nodes)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children, metadata=metadata.to_dict())

    def _is_slide_element(self, element: Any) -> bool:
        """Check if element is a slide/page element.

        Parameters
        ----------
        element : Any
            Element to check

        Returns
        -------
        bool
            True if element is a slide

        """
        if not hasattr(element, "qname"):
            return False
        return element.qname == (self.DRAWNS, "page")

    def _parse_slide_selection(self, slides_spec: str | None, metadata: DocumentMetadata) -> set[int] | None:
        """Parse slide selection specification.

        Parameters
        ----------
        slides_spec : str or None
            Slide selection string (e.g., "1,3-5,8")
        metadata : DocumentMetadata
            Document metadata for total slide count

        Returns
        -------
        set[int] or None
            Set of 0-based slide indices, or None for all slides

        """
        if not slides_spec:
            return None

        indices: set[int | tuple[int, int | float]] = set()
        for part in slides_spec.split(","):
            part = part.strip()
            if "-" in part:
                # Range
                start_str, end_str = part.split("-", 1)
                start = int(start_str) - 1 if start_str else 0
                end = int(end_str) - 1 if end_str else float("inf")
                # We'll expand this during iteration
                indices.add((start, end))
            else:
                # Single slide (1-based to 0-based)
                indices.add(int(part) - 1)

        # Expand ranges
        expanded: set[int] = set()
        max_slide = metadata.custom.get("page_count", 100)  # Fallback to 100 if unknown
        for item in indices:
            if isinstance(item, tuple):
                start, end = item
                for i in range(start, min(int(end) + 1, max_slide)):
                    expanded.add(i)
            elif isinstance(item, int):
                expanded.add(item)

        return expanded if expanded else None

    def _process_slide(self, slide_element: Any, doc: "odf.opendocument.OpenDocument") -> list[Node] | None:
        """Process a slide element.

        Parameters
        ----------
        slide_element : Any
            Slide element to process
        doc : odf.opendocument.OpenDocument
            The document

        Returns
        -------
        list[Node] or None
            List of AST nodes from the slide

        """
        nodes: list[Node] = []

        for element in slide_element.childNodes:
            node = self._process_element(element, doc)
            if node:
                if isinstance(node, list):
                    nodes.extend(node)
                else:
                    nodes.append(node)

        # Process slide notes if requested
        if self.options.include_notes:
            notes_nodes = self._extract_slide_notes(slide_element, doc)
            if notes_nodes:
                nodes.extend(notes_nodes)

        return nodes if nodes else None

    def _extract_slide_notes(self, slide_element: Any, doc: "odf.opendocument.OpenDocument") -> list[Node]:
        """Extract speaker notes from a slide.

        Parameters
        ----------
        slide_element : Any
            Slide element
        doc : odf.opendocument.OpenDocument
            The document

        Returns
        -------
        list[Node]
            Notes nodes

        """
        notes_nodes: list[Node] = []

        try:
            # Look for presentation:notes elements within the slide
            for child in slide_element.childNodes:
                if not hasattr(child, "qname"):
                    continue

                # Check if this is a notes element
                if child.qname == (self.PRESENTATIONNS, "notes"):
                    # Process notes content
                    notes_content: list[Node] = []

                    # Process all elements within the notes
                    for notes_child in child.childNodes:
                        node = self._process_element(notes_child, doc)
                        if node:
                            if isinstance(node, list):
                                notes_content.extend(node)
                            else:
                                notes_content.append(node)

                    # Only add notes section if we found content
                    if notes_content:
                        # Add heading to identify speaker notes section (consistent with PPTX)
                        notes_nodes.append(Heading(level=3, content=[Text(content="Speaker Notes")]))
                        notes_nodes.extend(notes_content)

                    break  # Only process first notes element

        except Exception as e:
            logger.debug(f"Failed to extract speaker notes from slide: {e}")

        return notes_nodes

    def _process_element(self, element: Any, doc: "odf.opendocument.OpenDocument") -> Node | list[Node] | None:
        """Process an ODP element to AST node(s).

        Parameters
        ----------
        element : Any
            ODP element to process
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        if not hasattr(element, "qname"):
            return None

        qname = element.qname

        if qname == (self.TEXTNS, "p"):
            return self._process_paragraph(element, doc)
        elif qname == (self.TEXTNS, "h"):
            return self._process_heading(element, doc)
        elif qname == (self.TEXTNS, "list"):
            return self._process_list(element, doc)
        elif qname[0] == "urn:oasis:names:tc:opendocument:xmlns:table:1.0" and qname[1] == "table":
            return self._process_table(element, doc)
        elif qname == (self.DRAWNS, "frame"):
            return self._process_frame(element, doc)

        return None

    def _process_frame(self, frame: Any, doc: "odf.opendocument.OpenDocument") -> Node | list[Node] | None:
        """Process a drawing frame (could be image, text box, etc.).

        Parameters
        ----------
        frame : Any
            Frame element
        doc : odf.opendocument.OpenDocument
            The document

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        # Try image first
        image_node = self._process_image(frame, doc)
        if image_node:
            return image_node

        # Check for text box
        for child in frame.childNodes:
            if hasattr(child, "qname") and child.qname == (self.DRAWNS, "text-box"):
                # Process text box content
                nodes: list[Node] = []
                for element in child.childNodes:
                    node = self._process_element(element, doc)
                    if node:
                        if isinstance(node, list):
                            nodes.extend(node)
                        else:
                            nodes.append(node)
                return nodes if nodes else None

        return None

    def _process_text_runs(self, element: Any, doc: "odf.opendocument.OpenDocument") -> list[Node]:
        """Process text runs within an element, handling formatting.

        Parameters
        ----------
        element : Any
            ODP element containing text runs
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        list[Node]
            List of inline AST nodes

        """
        nodes: list[Node] = []

        for node in element.childNodes:
            if hasattr(node, "data"):
                # Plain text node
                nodes.append(Text(content=node.data))
            elif hasattr(node, "qname"):
                qname = node.qname
                if qname == (self.TEXTNS, "span"):
                    # Text with formatting
                    inner_nodes = self._process_text_runs(node, doc)
                    # Check style for formatting
                    style_name = node.getAttribute("stylename")
                    if style_name and doc:
                        # Apply formatting based on style
                        # Simple heuristic: check style name for hints
                        if "bold" in style_name.lower() or "strong" in style_name.lower():
                            nodes.append(Strong(content=inner_nodes))
                        elif "italic" in style_name.lower() or "emphasis" in style_name.lower():
                            nodes.append(Emphasis(content=inner_nodes))
                        elif "underline" in style_name.lower():
                            nodes.append(Underline(content=inner_nodes))
                        else:
                            nodes.extend(inner_nodes)
                    else:
                        nodes.extend(inner_nodes)
                elif qname == (self.TEXTNS, "a"):
                    # Hyperlink
                    href = node.getAttribute("href") or ""
                    # Sanitize URL to prevent XSS attacks
                    href = sanitize_url(href)
                    link_text = self._get_text_content(node)
                    nodes.append(Link(url=href, content=[Text(content=link_text)], title=None))
                elif qname == (self.TEXTNS, "s"):
                    # Space
                    nodes.append(Text(content=" "))
                elif qname == (self.TEXTNS, "tab"):
                    nodes.append(Text(content="\t"))
                elif qname == (self.TEXTNS, "line-break"):
                    nodes.append(Text(content="\n"))
                elif qname == (self.MATHNS, "math"):
                    display = node.getAttribute("display")
                    mathml = node.toXml()
                    if display == "block":
                        continue
                    nodes.append(MathInline(content=mathml, notation="mathml"))

        return nodes

    def _get_text_content(self, element: Any) -> str:
        """Extract plain text content from an element.

        Parameters
        ----------
        element : Any
            ODP element

        Returns
        -------
        str
            Plain text content

        """
        parts = []
        for node in element.childNodes:
            if hasattr(node, "data"):
                parts.append(node.data)
            elif hasattr(node, "childNodes"):
                parts.append(self._get_text_content(node))
        return "".join(parts)

    def _process_paragraph(self, p: Any, doc: "odf.opendocument.OpenDocument") -> Node | list[Node] | None:
        """Convert paragraph element to AST Paragraph.

        Parameters
        ----------
        p : odf.text.P
            Paragraph element
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        Node, list[Node], or None
            AST paragraph node or math blocks

        """
        math_blocks = self._extract_math_blocks(p)
        content = self._process_text_runs(p, doc)

        if content:
            return Paragraph(content=content)

        if math_blocks:
            if len(math_blocks) == 1:
                return math_blocks[0]

            return cast(list[Node], math_blocks)

        return None

    def _extract_math_blocks(self, element: Any) -> list[MathBlock]:
        """Extract block-level math from an element.

        Parameters
        ----------
        element : Any
            Element to process

        Returns
        -------
        list[MathBlock]
            Math block nodes

        """
        blocks: list[MathBlock] = []
        for node in getattr(element, "childNodes", []):
            if not hasattr(node, "qname"):
                continue
            if node.qname != (self.MATHNS, "math"):
                continue
            display = node.getAttribute("display")
            if display != "block":
                continue
            mathml = node.toXml()
            blocks.append(MathBlock(content=mathml, notation="mathml"))
        return blocks

    def _process_heading(self, h: Any, doc: "odf.opendocument.OpenDocument") -> Heading:
        """Convert heading element to AST Heading.

        Parameters
        ----------
        h : odf.text.H
            Heading element
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        Heading
            AST heading node

        """
        level = int(h.getAttribute("outlinelevel") or 1)
        content = self._process_text_runs(h, doc)
        return Heading(level=level, content=content)

    def _process_list(self, lst: Any, doc: "odf.opendocument.OpenDocument") -> List:
        """Convert list element to AST List.

        Parameters
        ----------
        lst : odf.text.List
            List element
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        List
            AST list node

        """
        self._list_level += 1
        items: list[ListItem] = []

        # Detect if it's ordered
        is_ordered = self._is_ordered_list(lst)

        for item in lst.childNodes:
            if not hasattr(item, "qname") or item.qname != (self.TEXTNS, "list-item"):
                continue

            item_children: list[Node] = []
            for element in item.childNodes:
                if hasattr(element, "qname"):
                    if element.qname == (self.TEXTNS, "p"):
                        para = self._process_paragraph(element, doc)
                        if para:
                            if isinstance(para, list):
                                item_children.extend(para)
                            else:
                                item_children.append(para)
                    elif element.qname == (self.TEXTNS, "list"):
                        nested_list = self._process_list(element, doc)
                        item_children.append(nested_list)

            if item_children:
                items.append(ListItem(children=item_children))

        self._list_level -= 1
        return List(ordered=is_ordered, items=items)

    @staticmethod
    def _is_ordered_list(lst: Any) -> bool:
        """Detect if a list is ordered (numbered).

        Parameters
        ----------
        lst : odf.text.List
            List element

        Returns
        -------
        bool
            True if ordered, False if unordered

        """
        # Check list style to determine if ordered
        style_name = lst.getAttribute("stylename")
        if style_name:
            # Simple heuristic: check if style name contains "number" or "numeric"
            style_lower = style_name.lower()
            if "number" in style_lower or "numeric" in style_lower:
                return True
        return False

    def _process_table(self, tbl: Any, doc: "odf.opendocument.OpenDocument") -> Table | None:
        """Convert table element to AST Table.

        Parameters
        ----------
        tbl : odf.table.Table
            Table element
        doc : odf.opendocument.OpenDocument
            The document to process


        Returns
        -------
        Table or None
            AST table node

        """
        from odf import table

        if not self.options.preserve_tables:
            return None

        rows_elements = tbl.getElementsByType(table.TableRow)
        if not rows_elements:
            return None

        # Process header (first row)
        header_cells = rows_elements[0].getElementsByType(table.TableCell)
        header_row = TableRow(
            cells=[TableCell(content=self._process_text_runs(cell, doc), alignment="center") for cell in header_cells],
            is_header=True,
        )

        # Process data rows
        data_rows = []
        for row in rows_elements[1:]:
            data_cells = row.getElementsByType(table.TableCell)
            data_rows.append(
                TableRow(
                    cells=[
                        TableCell(content=self._process_text_runs(cell, doc), alignment="left") for cell in data_cells
                    ],
                    is_header=False,
                )
            )

        return Table(header=header_row, rows=data_rows, alignments=["left"] * len(header_cells))

    def _process_image(self, frame: Any, doc: "odf.opendocument.OpenDocument") -> Image | None:
        """Extract and process an image.

        Parameters
        ----------
        frame : odf.draw.Frame
            Frame element containing image
        doc : odf.opendocument.OpenDocument
            The document to process


        Returns
        -------
        Image or None
            AST image node

        """
        from odf import draw

        image_element = frame.getElementsByType(draw.Image)
        if not image_element:
            return None

        href = image_element[0].getAttribute("href")
        if not href:
            return None

        try:
            # odfpy stores parts in a dict-like object
            image_data = doc.getPart(href)
        except KeyError:
            logger.warning(f"Image not found in ODP package: {href}")
            return None

        alt_text = "image"

        # Process attachment
        result = process_attachment(
            attachment_data=image_data,
            attachment_name=href.split("/")[-1],
            alt_text=alt_text,
            attachment_mode=self.options.attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
            alt_text_mode=self.options.alt_text_mode,
        )

        # Collect footnote info if present
        if result.get("footnote_label") and result.get("footnote_content"):
            self._attachment_footnotes[result["footnote_label"]] = result["footnote_content"]

        # Convert attachment result to Image node using helper
        image_node = attachment_result_to_image_node(result, fallback_alt_text="image")
        if image_node and isinstance(image_node, Image):
            return image_node
        return None

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from ODP document.

        Parameters
        ----------
        document : opendocument.OpenDocument
            ODP document object from odfpy

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Access document metadata
        if hasattr(document, "meta"):
            meta = document.meta

            # Extract Dublin Core metadata
            if hasattr(meta, "getElementsByType"):
                from odf.dc import Creator, Description, Language, Subject, Title
                from odf.meta import CreationDate, Generator, InitialCreator, Keyword

                # Title
                titles = meta.getElementsByType(Title)
                if titles and len(titles) > 0:
                    metadata.title = str(titles[0]).strip()

                # Creator/Author
                creators = meta.getElementsByType(Creator)
                if creators and len(creators) > 0:
                    metadata.author = str(creators[0]).strip()
                else:
                    # Try initial creator
                    initial_creators = meta.getElementsByType(InitialCreator)
                    if initial_creators and len(initial_creators) > 0:
                        metadata.author = str(initial_creators[0]).strip()

                # Description/Subject
                descriptions = meta.getElementsByType(Description)
                if descriptions and len(descriptions) > 0:
                    metadata.subject = str(descriptions[0]).strip()
                else:
                    subjects = meta.getElementsByType(Subject)
                    if subjects and len(subjects) > 0:
                        metadata.subject = str(subjects[0]).strip()

                # Keywords
                keywords = meta.getElementsByType(Keyword)
                if keywords and len(keywords) > 0:
                    # ODF can have multiple keyword elements
                    keyword_list = []
                    for kw in keywords:
                        kw_text = str(kw).strip()
                        if kw_text:
                            # Split by common delimiters

                            parts = [k.strip() for k in re.split("[,;]", kw_text) if k.strip()]
                            keyword_list.extend(parts)
                    if keyword_list:
                        metadata.keywords = keyword_list

                # Creation date
                creation_dates = meta.getElementsByType(CreationDate)
                if creation_dates and len(creation_dates) > 0:
                    metadata.creation_date = str(creation_dates[0]).strip()

                # Generator (application)
                generators = meta.getElementsByType(Generator)
                if generators and len(generators) > 0:
                    metadata.creator = str(generators[0]).strip()

                # Language
                languages = meta.getElementsByType(Language)
                if languages and len(languages) > 0:
                    metadata.language = str(languages[0]).strip()

        # Document type and statistics
        metadata.custom["document_type"] = "presentation"

        # Count slides
        if hasattr(document, "presentation"):
            try:
                from odf.draw import Page

                pages = document.presentation.getElementsByType(Page)
                if pages:
                    metadata.custom["page_count"] = len(pages)
                    metadata.custom["slide_count"] = len(pages)
            except Exception:
                pass

            # Count tables
            try:
                from odf.table import Table

                tables = document.presentation.getElementsByType(Table)
                if tables:
                    metadata.custom["table_count"] = len(tables)
            except Exception:
                pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="odp",
    extensions=[".odp"],
    mime_types=["application/vnd.oasis.opendocument.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),
    ],
    parser_class=OdpToAstConverter,
    renderer_class="OdpRenderer",
    parser_required_packages=[("odfpy", "odf", "")],
    renderer_required_packages=[("odfpy", "odf", "")],
    import_error_message="ODP conversion requires 'odfpy'. Install with: pip install odfpy",
    parser_options_class=OdpOptions,
    renderer_options_class="OdpRendererOptions",
    description="Convert OpenDocument Presentation files to/from Markdown",
    priority=5,
)
