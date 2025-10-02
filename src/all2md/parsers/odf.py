#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/odf.py
"""ODF to AST converter.

This module provides conversion from ODF documents (ODT, ODP) to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import logging
from typing import Any

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
from all2md.options import OdfOptions
from all2md.utils.attachments import process_attachment

logger = logging.getLogger(__name__)


class OdfToAstConverter:
    """Convert ODF documents to AST representation.

    This converter processes ODF documents (ODT, ODP) and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    doc : odf.opendocument.OpenDocumentText or OpenDocumentPresentation
        ODF document object
    options : OdfOptions or None
        Conversion options

    """

    def __init__(self, doc: Any, options: OdfOptions | None = None):
        from odf.namespaces import DRAWNS, STYLENS, TEXTNS

        self.doc = doc
        self.options = options or OdfOptions()
        self.list_level = 0

        # Namespace constants
        self.TEXTNS = TEXTNS
        self.DRAWNS = DRAWNS
        self.STYLENS = STYLENS

    def convert_to_ast(self) -> Document:
        """Convert ODF document to AST Document.

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        # For ODT, content is in doc.text. For ODP, it's in doc.presentation
        content_root = getattr(self.doc, 'text', None) or getattr(self.doc, 'presentation', None)
        if not content_root:
            return Document(children=[])

        for element in content_root.childNodes:
            node = self._process_element(element)
            if node:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        return Document(children=children)

    def _process_element(self, element: Any) -> Node | list[Node] | None:
        """Process an ODF element to AST node(s).

        Parameters
        ----------
        element : Any
            ODF element to process

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
            return self._process_paragraph(element)
        elif qname == (self.TEXTNS, "h"):
            return self._process_heading(element)
        elif qname == (self.TEXTNS, "list"):
            return self._process_list(element)
        elif qname[0] == "urn:oasis:names:tc:opendocument:xmlns:table:1.0" and qname[1] == "table":
            return self._process_table(element)
        elif qname == (self.DRAWNS, "frame"):
            return self._process_image(element)

        return None

    def _process_text_runs(self, element: Any) -> list[Node]:
        """Process text runs within an element, handling formatting.

        Parameters
        ----------
        element : Any
            ODF element containing text runs

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
                    inner_nodes = self._process_text_runs(node)
                    # Check style for formatting
                    style_name = node.getAttribute("stylename")
                    if style_name and self.doc:
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

    def _process_paragraph(self, p: Any) -> Paragraph | None:
        """Convert paragraph element to AST Paragraph.

        Parameters
        ----------
        p : odf.text.P
            Paragraph element

        Returns
        -------
        Paragraph or None
            AST paragraph node

        """
        content = self._process_text_runs(p)
        if not content:
            return None

        return Paragraph(content=content)

    def _process_heading(self, h: Any) -> Heading:
        """Convert heading element to AST Heading.

        Parameters
        ----------
        h : odf.text.H
            Heading element

        Returns
        -------
        Heading
            AST heading node

        """
        level = int(h.getAttribute("outlinelevel") or 1)
        content = self._process_text_runs(h)
        return Heading(level=level, content=content)

    def _process_list(self, lst: Any) -> List:
        """Convert list element to AST List.

        Parameters
        ----------
        lst : odf.text.List
            List element

        Returns
        -------
        List
            AST list node

        """
        self.list_level += 1
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
                        para = self._process_paragraph(element)
                        if para:
                            item_children.append(para)
                    elif element.qname == (self.TEXTNS, "list"):
                        nested_list = self._process_list(element)
                        item_children.append(nested_list)

            if item_children:
                items.append(ListItem(children=item_children))

        self.list_level -= 1
        return List(ordered=is_ordered, items=items)

    def _is_ordered_list(self, lst: Any) -> bool:
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

    def _process_table(self, tbl: Any) -> Table | None:
        """Convert table element to AST Table.

        Parameters
        ----------
        tbl : odf.table.Table
            Table element

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
                TableCell(content=self._process_text_runs(cell), alignment="center")
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
                        TableCell(content=self._process_text_runs(cell), alignment="left")
                        for cell in data_cells
                    ],
                    is_header=False,
                )
            )

        return Table(header=header_row, rows=data_rows, alignments=["left"] * len(header_cells))

    def _process_image(self, frame: Any) -> Image | None:
        """Extract and process an image.

        Parameters
        ----------
        frame : odf.draw.Frame
            Frame element containing image

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
            image_data = self.doc.getPart(href)
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

        match = re.match(r"!\[([^\]]*)\](?:\(([^)]+)\))?", markdown_result)
        if match:
            alt_text = match.group(1) or "image"
            url = match.group(2) or ""
            return Image(url=url, alt_text=alt_text, title=None)

        return None
