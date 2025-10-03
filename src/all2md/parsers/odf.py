#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/odf.py
"""ODF to AST converter.

This module provides conversion from ODF documents (ODT, ODP) to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations
from typing import TYPE_CHECKING
import logging
from pathlib import Path
from typing import IO, Any, Union

from all2md import InputError
from all2md.ast import (
    Code,
    Document,
    Emphasis,
    Heading,
    Image,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
    Underline,
)
from all2md.converter_metadata import ConverterMetadata
from all2md.options import OdfOptions
from all2md.exceptions import DependencyError, MarkdownConversionError
from all2md.parsers.base import BaseParser
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.security import validate_zip_archive

if TYPE_CHECKING:
    import odf
    import odf.opendocument

logger = logging.getLogger(__name__)


class OdfToAstConverter(BaseParser):
    """Convert ODF documents to AST representation.

    This converter processes ODF documents (ODT, ODP) and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : OdfOptions or None
        Conversion options

    """

    def __init__(self, options: OdfOptions | None = None):
        options = options or OdfOptions()
        super().__init__(options)
        self.options: OdfOptions = options
        
        try:
            from odf.namespaces import DRAWNS, STYLENS, TEXTNS
        except ImportError as e:
            raise DependencyError(
                converter_name="odf",
                missing_packages=[("odfpy", "")],
            ) from e

        self._list_level = 0

        # Namespace constants
        self.TEXTNS = TEXTNS
        self.DRAWNS = DRAWNS
        self.STYLENS = STYLENS

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ODF document into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ODF document to parse

        Returns
        -------
        Document
            AST Document node representing the parsed document structure

        Raises
        ------
        MarkdownConversionError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed

        """
        try:
            from odf import opendocument
        except ImportError as e:
            raise DependencyError(
                converter_name="odf",
                missing_packages=[("odfpy", "")],
            ) from e
        

        # Validate ZIP archive security for file-based inputs
        if isinstance(input_data, (str, Path)) and Path(input_data).exists():
            validate_zip_archive(input_data)
            

        try:
            doc = opendocument.load(input_data)
        except Exception as e:
            raise InputError(
                f"Failed to open ODF document: {e!r}",
                parameter_name="input_data",
                parameter_value=input_data,
                original_error=e
            ) from e

        return self.convert_to_ast(doc)

    def convert_to_ast(self, doc: "odf.opendocument.OpenDocument") -> Document:
        """Convert ODF document to AST Document.

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        # For ODT, content is in doc.text. For ODP, it's in doc.presentation
        content_root = getattr(doc, 'text', None) or getattr(doc, 'presentation', None)

        # Extract metadata
        metadata = self.extract_metadata(doc)

        if not content_root:
            return Document(children=[], metadata=metadata.to_dict())

        for element in content_root.childNodes:
            node = self._process_element(element, doc)
            if node:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        return Document(children=children, metadata=metadata.to_dict())

    def _process_element(self, element: Any, doc: "odf.opendocument.OpenDocument") -> Node | list[Node] | None:
        """Process an ODF element to AST node(s).

        Parameters
        ----------
        element : Any
            ODF element to process
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        from odf import draw, table, text

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
            return self._process_image(element, doc)

        return None

    def _process_text_runs(self, element: Any, doc: "odf.opendocument.OpenDocument") -> list[Node]:
        """Process text runs within an element, handling formatting.

        Parameters
        ----------
        element : Any
            ODF element containing text runs
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        list[Node]
            List of inline AST nodes

        """
        from odf import text

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
                        # For now, wrap in formatting nodes if we detect common patterns
                        text_content = "".join(
                            n.content for n in inner_nodes if isinstance(n, Text)
                        )
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
                    link_text = self._get_text_content(node)
                    nodes.append(Link(url=href, content=[Text(content=link_text)], title=None))
                elif qname == (self.TEXTNS, "s"):
                    # Space
                    nodes.append(Text(content=" "))
                elif qname == (self.TEXTNS, "tab"):
                    nodes.append(Text(content="\t"))
                elif qname == (self.TEXTNS, "line-break"):
                    nodes.append(Text(content="\n"))

        return nodes

    def _get_text_content(self, element: Any) -> str:
        """Extract plain text content from an element.

        Parameters
        ----------
        element : Any
            ODF element

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

    def _process_paragraph(self, p: Any, doc: "odf.opendocument.OpenDocument") -> Paragraph | None:
        """Convert paragraph element to AST Paragraph.

        Parameters
        ----------
        p : odf.text.P
            Paragraph element
        doc : odf.opendocument.OpenDocument
            The document to process

        Returns
        -------
        Paragraph or None
            AST paragraph node

        """
        content = self._process_text_runs(p, doc)
        if not content:
            return None

        return Paragraph(content=content)

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
            cells=[
                TableCell(content=self._process_text_runs(cell, doc), alignment="center")
                for cell in header_cells
            ],
            is_header=True,
        )

        # Process data rows
        data_rows = []
        for row in rows_elements[1:]:
            data_cells = row.getElementsByType(table.TableCell)
            data_rows.append(
                TableRow(
                    cells=[
                        TableCell(content=self._process_text_runs(cell, doc), alignment="left")
                        for cell in data_cells
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
            logger.warning(f"Image not found in ODF package: {href}")
            return None

        alt_text = "image"

        # Process attachment
        markdown_result = process_attachment(
            attachment_data=image_data,
            attachment_name=href.split("/")[-1],
            alt_text=alt_text,
            attachment_mode=self.options.attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
            alt_text_mode=self.options.alt_text_mode,
        )

        # Parse markdown result to extract URL
        import re

        match = re.match(r"!\[([^]]*)](?:\(([^)]+)\))?", markdown_result)
        if match:
            alt_text = match.group(1) or "image"
            url = match.group(2) or ""
            return Image(url=url, alt_text=alt_text, title=None)

        return None

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from ODF document.

        Parameters
        ----------
        document : opendocument.OpenDocument
            ODF document object from odfpy

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Access document metadata
        if hasattr(document, 'meta'):
            meta = document.meta

            # Extract Dublin Core metadata
            if hasattr(meta, 'getElementsByType'):
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
                            import re
                            parts = [k.strip() for k in re.split('[,;]', kw_text) if k.strip()]
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
        if hasattr(document, 'mimetype'):
            doc_type = 'presentation' if 'presentation' in document.mimetype else 'text'
            metadata.custom['document_type'] = doc_type

        # Count pages/slides if it's a presentation
        if hasattr(document, 'body'):
            try:
                from odf.draw import Page
                pages = document.body.getElementsByType(Page)
                if pages:
                    metadata.custom['page_count'] = len(pages)
            except Exception:
                pass

            # Count paragraphs for text documents
            try:
                from odf.text import P
                paragraphs = document.body.getElementsByType(P)
                if paragraphs:
                    metadata.custom['paragraph_count'] = len(paragraphs)
            except Exception:
                pass

            # Count tables
            try:
                from odf.table import Table
                tables = document.body.getElementsByType(Table)
                if tables:
                    metadata.custom['table_count'] = len(tables)
            except Exception:
                pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="odf",
    extensions=[".odt", ".odp"],
    mime_types=["application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),
    ],
    parser_class=OdfToAstConverter,
    renderer_class=None,
    required_packages=[("odfpy", "odf", "")],
    import_error_message="ODF conversion requires 'odfpy'. Install with: pip install odfpy",
    options_class=OdfOptions,
    description="Convert OpenDocument files to Markdown",
    priority=4
)
