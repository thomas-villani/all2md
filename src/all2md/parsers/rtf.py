#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/rtf.py
"""RTF to AST converter.

This module provides conversion from RTF documents (via pyth) to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import logging
from typing import Any

from all2md.ast import (
    Document,
    Emphasis,
    Image,
    List,
    ListItem,
    Node,
    Paragraph,
    Strong,
    Text,
    Underline,
)
from all2md.options import RtfOptions
from all2md.utils.attachments import process_attachment

logger = logging.getLogger(__name__)


class RtfToAstConverter:
    """Convert RTF documents (pyth Document) to AST representation.

    This converter processes pyth Document objects and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : RtfOptions or None
        Conversion options
    base_filename : str
        Base filename for attachments
    attachment_sequencer : callable or None
        Function to generate sequential attachment names

    """

    def __init__(
        self,
        options: RtfOptions | None = None,
        base_filename: str = "document",
        attachment_sequencer: Any = None,
    ):
        # Import pyth types for use in converter methods
        try:
            from pyth.document import Document as PythDocument
            from pyth.document import Image as PythImage
            from pyth.document import List as PythList
            from pyth.document import ListEntry as PythListEntry
            from pyth.document import Paragraph as PythParagraph
            from pyth.document import Text as PythText

            self.PythParagraph = PythParagraph
            self.PythList = PythList
            self.PythListEntry = PythListEntry
            self.PythText = PythText
            self.PythImage = PythImage
            self.PythDocument = PythDocument
        except ImportError:
            # Will fail when actually trying to convert
            pass

        self.options = options or RtfOptions()
        self.base_filename = base_filename
        self.attachment_sequencer = attachment_sequencer
        self.list_stack: list[tuple[str, int, int]] = []  # (type, level, number)

    def convert_to_ast(self, pyth_doc: Any) -> Document:
        """Convert pyth Document to AST Document.

        Parameters
        ----------
        pyth_doc : pyth.document.Document
            Pyth document object

        Returns
        -------
        Document
            AST document node

        """
        if not pyth_doc or not hasattr(pyth_doc, "content"):
            return Document(children=[])

        children: list[Node] = []
        for elem in pyth_doc.content:
            node = self._process_element(elem)
            if node:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        return Document(children=children)

    def _process_element(self, element: Any) -> Node | list[Node] | None:
        """Dispatch element processing to the appropriate method.

        Parameters
        ----------
        element : Any
            Pyth element to process

        Returns
        -------
        Node, list[Node], or None
            Resulting AST node(s)

        """
        if isinstance(element, self.PythParagraph):
            return self._process_paragraph(element)
        elif isinstance(element, self.PythList):
            return self._process_list(element)
        elif isinstance(element, self.PythListEntry):
            return self._process_list_entry(element)

        return None

    def _process_paragraph(self, para: Any) -> Paragraph | None:
        """Convert pyth Paragraph to AST Paragraph.

        Parameters
        ----------
        para : pyth.document.Paragraph
            Pyth paragraph object

        Returns
        -------
        Paragraph or None
            AST paragraph node

        """
        if not para.content:
            return None

        # Process inner content (Text and Image objects)
        inline_content: list[Node] = []
        for item in para.content:
            if isinstance(item, self.PythText):
                nodes = self._process_text(item)
                if nodes:
                    if isinstance(nodes, list):
                        inline_content.extend(nodes)
                    else:
                        inline_content.append(nodes)
            elif isinstance(item, self.PythImage):
                img_node = self._process_image(item)
                if img_node:
                    inline_content.append(img_node)

        if not inline_content:
            return None

        return Paragraph(content=inline_content)

    def _process_list(self, pyth_list: Any) -> List:
        """Convert pyth List to AST List.

        Parameters
        ----------
        pyth_list : pyth.document.List
            Pyth list object

        Returns
        -------
        List
            AST list node

        """
        items: list[ListItem] = []

        for entry in pyth_list.content:
            if isinstance(entry, self.PythListEntry):
                item = self._process_list_entry(entry)
                if item:
                    items.append(item)

        # Detect if ordered or unordered (pyth doesn't always provide this info)
        # Default to unordered for now
        return List(ordered=False, items=items)

    def _process_list_entry(self, entry: Any) -> ListItem:
        """Convert pyth ListEntry to AST ListItem.

        Parameters
        ----------
        entry : pyth.document.ListEntry
            Pyth list entry object

        Returns
        -------
        ListItem
            AST list item node

        """
        children: list[Node] = []

        for elem in entry.content:
            node = self._process_element(elem)
            if node:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        return ListItem(children=children)

    def _process_text(self, text: Any) -> Node | list[Node] | None:
        """Convert pyth Text to AST inline nodes.

        Parameters
        ----------
        text : pyth.document.Text
            Pyth text object

        Returns
        -------
        Node, list[Node], or None
            AST inline node(s) with formatting

        """
        # Text.content is a list of strings, so join them
        content = "".join(text.content) if isinstance(text.content, list) else str(text.content)
        if not content:
            return None

        # Create text node
        text_node: Node = Text(content=content)

        # Apply formatting based on properties
        props = text.properties if hasattr(text, "properties") else {}

        # Wrap in formatting nodes (innermost first)
        if props.get("underline"):
            text_node = Underline(content=[text_node])
        if props.get("italic"):
            text_node = Emphasis(content=[text_node])
        if props.get("bold"):
            text_node = Strong(content=[text_node])

        return text_node

    def _process_image(self, image: Any) -> Image | None:
        """Process pyth Image object to AST Image node.

        Parameters
        ----------
        image : pyth.document.Image
            Pyth image object

        Returns
        -------
        Image or None
            AST image node

        """
        if not hasattr(image, "data") or not image.data:
            return None

        image_data = image.data

        # Generate standardized image filename
        if self.attachment_sequencer:
            filename, _ = self.attachment_sequencer(
                base_stem=self.base_filename, format_type="general", extension="png"
            )
        else:
            filename = f"{self.base_filename}_image.png"

        # Process attachment using unified handler
        try:
            markdown_result = process_attachment(
                attachment_data=image_data,
                attachment_name=filename,
                alt_text="Image",
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                is_image=True,
                alt_text_mode=self.options.alt_text_mode,
            )

            # Parse markdown result to extract URL and alt text
            # Format: ![alt](url) or ![alt]
            import re

            match = re.match(r"!\[([^\]]*)\](?:\(([^)]+)\))?", markdown_result)
            if match:
                alt_text = match.group(1) or "Image"
                url = match.group(2) or ""
                return Image(url=url, alt_text=alt_text, title=None)

        except Exception as e:
            logger.warning(f"Failed to process image: {e}")

        return None
