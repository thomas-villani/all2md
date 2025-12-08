#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/rtf.py
"""RTF to AST converter.

This module provides conversion from RTF documents (via pyth) to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, Union

from all2md.ast import (
    Document,
    Emphasis,
    Image,
    Link,
    List,
    ListItem,
    Node,
    Paragraph,
    Strikethrough,
    Strong,
    Subscript,
    Superscript,
    Text,
    Underline,
)
from all2md.constants import DEPS_RTF
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError, ValidationError
from all2md.options.rtf import RtfOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import create_attachment_sequencer, process_attachment
from all2md.utils.decorators import requires_dependencies
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import attachment_result_to_image_node

if TYPE_CHECKING:
    import pyth
    import pyth.document

logger = logging.getLogger(__name__)


class RtfToAstConverter(BaseParser):
    """Convert RTF documents (pyth Document) to AST representation.

    This converter processes pyth Document objects and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : RtfOptions or None
        Conversion options

    """

    @requires_dependencies("rtf", DEPS_RTF)
    def __init__(self, options: RtfOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the RTF parser with options and progress callback."""
        BaseParser._validate_options_type(options, RtfOptions, "rtf")
        options = options or RtfOptions()
        super().__init__(options, progress_callback)
        self.options: RtfOptions = options
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

        # Import pyth types for use in converter methods
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

        self._base_filename = "document"
        self._attachment_sequencer = create_attachment_sequencer()
        self._list_stack: list[tuple[str, int, int]] = []  # (type, level, number)

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse RTF input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            RTF document to parse

        Returns
        -------
        Document
            AST Document node

        Raises
        ------
        ParsingError
            If parsing fails or required dependencies are missing

        """
        from pyth.plugins.rtf15.reader import Rtf15Reader

        doc = None
        try:
            doc_input, input_type = validate_and_convert_input(input_data, supported_types=["path-like", "file-like"])
            if input_type == "path":
                with open(doc_input, "rb") as f:
                    doc = Rtf15Reader.read(f)
                base_filename = Path(doc_input).stem
            elif input_type in ("file", "bytes"):
                doc = Rtf15Reader.read(doc_input)
                # Try to get filename from file object's name attribute
                if hasattr(doc_input, "name") and doc_input.name not in (None, "unknown"):
                    base_filename = Path(doc_input.name).stem
                else:
                    base_filename = "document"
            else:
                raise ValidationError(
                    f"Unsupported input type for RTF conversion: {type(input_data)}",
                    parameter_name="input_data",
                    parameter_value=input_data,
                )

        except ValidationError as e:
            raise e
        except Exception as e:
            raise ParsingError(
                f"Failed to read or parse RTF document: {e!r}",
                original_error=e,
            ) from e

        self._base_filename = base_filename
        # Convert pyth document to AST
        return self.convert_to_ast(doc)

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
        # Extract metadata
        metadata = self.extract_metadata(pyth_doc)

        if not pyth_doc or not hasattr(pyth_doc, "content"):
            return Document(children=[], metadata=metadata.to_dict())

        # Reset parser state to prevent leakage across parse calls
        self._attachment_footnotes = {}
        self._attachment_sequencer = create_attachment_sequencer()
        self._list_stack = []

        children: list[Node] = []
        for elem in pyth_doc.content:
            node = self._process_element(elem)
            if node:
                if isinstance(node, list):
                    children.extend(node)
                else:
                    children.append(node)

        # Append attachment footnote definitions if any were collected
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        return Document(children=children, metadata=metadata.to_dict())

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

        Notes
        -----
        The pyth library has limited support for RTF formatting. This method attempts
        to extract all available formatting properties including:
        - bold, italic, underline (well supported)
        - strikethrough, superscript, subscript (may or may not be exposed by pyth)
        - hyperlinks (not well supported by pyth - would require URL property)

        """
        # Text.content is a list of strings, so join them
        content = "".join(text.content) if isinstance(text.content, list) else str(text.content)
        if not content:
            return None

        # Create text node
        text_node: Node = Text(content=content)

        # Apply formatting based on properties
        props = text.properties if hasattr(text, "properties") else {}

        # Wrap in formatting nodes (innermost to outermost)
        # Note: pyth may not expose all these properties, so we use .get() with defaults

        # Check for strikethrough (might be "strike" or "strikethrough")
        if props.get("strikethrough") or props.get("strike"):
            text_node = Strikethrough(content=[text_node])

        # Check for subscript/superscript
        if props.get("sub") or props.get("subscript"):
            text_node = Subscript(content=[text_node])
        elif props.get("super") or props.get("superscript"):
            text_node = Superscript(content=[text_node])

        # Standard formatting
        if props.get("underline"):
            text_node = Underline(content=[text_node])
        if props.get("italic"):
            text_node = Emphasis(content=[text_node])
        if props.get("bold"):
            text_node = Strong(content=[text_node])

        # Check for hyperlinks (pyth support is limited)
        # If pyth exposes a URL property, we could wrap in Link node
        url = props.get("url") or props.get("hyperlink")
        if url:
            text_node = Link(url=url, content=[text_node])

        return text_node

    def _process_image(self, image: "pyth.document.Image") -> Image | None:
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
        if not hasattr(image, "content") or not image.content:
            return None

        image_data = image.content

        # Generate standardized image filename
        filename, _ = self._attachment_sequencer(base_stem=self._base_filename, format_type="general", extension="png")

        # Process attachment using unified handler
        try:
            result = process_attachment(
                attachment_data=image_data,
                attachment_name=filename,
                alt_text="Image",
                attachment_mode=self.options.attachment_mode,
                attachment_output_dir=self.options.attachment_output_dir,
                attachment_base_url=self.options.attachment_base_url,
                is_image=True,
                alt_text_mode=self.options.alt_text_mode,
            )

            # Collect footnote info if present
            if result.get("footnote_label") and result.get("footnote_content"):
                self._attachment_footnotes[result["footnote_label"]] = result["footnote_content"]

            # Convert result to Image node using helper
            image_node = attachment_result_to_image_node(result, fallback_alt_text="Image")
            if image_node and isinstance(image_node, Image):
                return image_node

        except Exception as e:
            logger.warning(f"Failed to process image: {e}")

        return None

    def extract_metadata(self, document: "pyth.document.Document") -> DocumentMetadata:
        """Extract metadata from RTF document.

        Parameters
        ----------
        document : pyth.document.Document
            Parsed RTF document from pyth

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        # Import pyth types for isinstance checks
        from pyth.document import Image, List, ListEntry, Paragraph, Text

        metadata = DocumentMetadata()

        # RTF documents parsed by pyth have limited metadata access
        # Most RTF metadata is not easily accessible through the pyth library
        # We can extract some basic document statistics and content analysis

        if not document or not hasattr(document, "content") or not document.content:
            return metadata

        # Count different element types
        paragraph_count = 0
        list_count = 0
        image_count = 0
        text_content = []

        def analyze_element(element: Any) -> None:
            nonlocal paragraph_count, list_count, image_count

            if isinstance(element, Paragraph):
                paragraph_count += 1
                # Extract text content for analysis
                for item in element.content or []:
                    if isinstance(item, Text):
                        if isinstance(item.content, list):
                            text_content.extend(item.content)
                        else:
                            text_content.append(str(item.content))
                    elif isinstance(item, Image):
                        image_count += 1
            elif isinstance(element, List):
                list_count += 1
                # Recursively analyze list content
                for entry in element.content or []:
                    analyze_element(entry)
            elif isinstance(element, ListEntry):
                # Analyze list entry content
                for item in element.content or []:
                    analyze_element(item)

        # Analyze all document content
        for element in document.content:
            analyze_element(element)

        # Set document statistics
        if paragraph_count > 0:
            metadata.custom["paragraph_count"] = paragraph_count

        if list_count > 0:
            metadata.custom["list_count"] = list_count

        if image_count > 0:
            metadata.custom["image_count"] = image_count

        # Analyze text content
        if text_content:
            full_text = " ".join(str(t) for t in text_content if t)

            # Word count
            words = full_text.split()
            if words:
                metadata.custom["word_count"] = len(words)

            # Character count
            if full_text.strip():
                metadata.custom["character_count"] = len(full_text.strip())

            # Try to extract title from first significant text
            # Look for title-like content (short first line or heading)
            text_lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            if text_lines:
                first_line = text_lines[0]
                # If the first line is reasonably short and looks like a title
                if len(first_line) < 100 and not first_line.endswith("."):
                    # Check if it's likely a title (short, no sentence ending)
                    words_in_first = first_line.split()
                    if 1 <= len(words_in_first) <= 15:  # Reasonable title length
                        metadata.title = first_line

        # RTF document type
        metadata.custom["document_type"] = "rtf"
        metadata.custom["format"] = "Rich Text Format"

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="rtf",
    extensions=[".rtf"],
    mime_types=["application/rtf", "text/rtf"],
    magic_bytes=[
        (b"{\\rtf", 0),
    ],
    parser_class=RtfToAstConverter,
    renderer_class="all2md.renderers.rtf.RtfRenderer",
    renders_as_string=True,
    parser_required_packages=[("pyth3", "pyth", ""), ("six", "six", ">=1.16.0")],
    renderer_required_packages=[("pyth3", "pyth", ""), ("six", "six", ">=1.16.0")],
    import_error_message="RTF conversion requires 'pyth3' and 'six'. Install with: pip install pyth3 six",
    parser_options_class=RtfOptions,
    renderer_options_class="all2md.options.rtf.RtfRendererOptions",
    description="Convert Rich Text Format documents to Markdown",
    priority=4,
)
