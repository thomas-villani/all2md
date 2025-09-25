#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# src/all2md/rtf2markdown.py
"""Rich Text Format (RTF) to Markdown conversion module.

This module provides functionality to convert Rich Text Format (RTF) documents
to Markdown, preserving essential formatting, structure, and embedded content.
It handles common RTF elements like paragraphs, text formatting, tables, and images.

The converter processes RTF documents by parsing their structure into a document
object model and then translating these objects into their Markdown equivalents.

Key Features
------------
- Text formatting preservation (bold, italic, underline)
- Table structure conversion to Markdown tables
- Heuristic-based list detection (bulleted and numbered)
- Image extraction and handling via unified attachment processing
- Paragraph and line break management

Dependencies
------------
- pyth: For parsing the RTF document structure

Note
----
Requires the `pyth` package. Some advanced RTF features, such as complex list
numbering schemes or hyperlinks, may not be fully supported due to limitations
in the parsing library.
"""

import io
import logging
import re
from pathlib import Path
from typing import IO, Any, Union

# Conditional import for pyth
# try:
from pyth.document import Document, Image, List, ListEntry, Paragraph, Text
from pyth.plugins.rtf15.reader import Rtf15Reader

from ._attachment_utils import process_attachment
from ._input_utils import validate_and_convert_input
from .exceptions import MdparseConversionError
from .options import MarkdownOptions, RtfOptions

# except ImportError:
#     Document = None
#     Rtf15Reader = None

logger = logging.getLogger(__name__)


class RtfConverter:
    """A class to convert a pyth Document object to Markdown."""

    def __init__(self, options: RtfOptions):
        self.options = options
        self.md_options = options.markdown_options or MarkdownOptions()
        self.list_stack: list[tuple[str, int, int]] = []  # (type, level, number)

    def convert(self, doc: Document) -> str:
        """Convert the pyth Document to a Markdown string."""
        if not doc:
            return ""

        markdown_parts = [self._process_element(elem) for elem in doc.content]

        # Clean up excessive newlines
        full_text = "".join(markdown_parts)
        return re.sub(r"\n{3,}", "\n\n", full_text).strip()

    def _process_element(self, element: Any) -> str:
        """Dispatch element processing to the appropriate method."""
        if isinstance(element, Paragraph):
            return self._process_paragraph(element)
        elif isinstance(element, List):
            return self._process_list(element)
        elif isinstance(element, ListEntry):
            return self._process_list_entry(element)

        # Other top-level elements can be added here
        return ""

    def _process_paragraph(self, para: Paragraph) -> str:
        """Convert a Paragraph object to Markdown."""
        if not para.content:
            return "\n"

        # Process inner content (mostly Text and Image objects)
        text_parts = []
        for item in para.content:
            if isinstance(item, Text):
                text_parts.append(self._process_text(item))
            elif isinstance(item, Image):
                text_parts.append(self._process_image(item))

        full_text = "".join(text_parts).strip()
        if not full_text:
            return "\n"

        # Heuristic for list detection
        indent = para.properties.get("start_indent", 0)
        # Assuming a standard indent of ~360 TWIPs per level
        level = int(indent / 360) + 1 if indent else 1

        list_type = None
        # Check for bullet/numbering prefixes
        if re.match(r"^[*\-•]\s+", full_text):
            list_type = "bullet"
            full_text = re.sub(r"^[*\-•]\s+", "", full_text)
        elif re.match(r"^\d+[.)]\s+", full_text):
            list_type = "number"
            full_text = re.sub(r"^\d+[.)]\s+", "", full_text)

        if list_type:
            # End deeper lists
            while self.list_stack and self.list_stack[-1][1] > level:
                self.list_stack.pop()

            if self.list_stack and self.list_stack[-1][1] == level:
                # Continue list at the same level
                current_number = self.list_stack[-1][2] + 1 if list_type == "number" else 1
                self.list_stack[-1] = (list_type, level, current_number)
            else:
                # Start a new list
                self.list_stack.append((list_type, level, 1))

            indent_str = " " * (self.md_options.list_indent_width * (level - 1))

            if list_type == "bullet":
                bullet = self.md_options.bullet_symbols[(level - 1) % len(self.md_options.bullet_symbols)]
                marker = f"{bullet} "
            else:  # number
                marker = f"{self.list_stack[-1][2]}. "

            return f"{indent_str}{marker}{full_text}\n"
        else:
            # Not a list, reset stack
            self.list_stack = []
            return f"{full_text}\n\n"

    def _process_list(self, list_elem: List) -> str:
        """Convert a List object to Markdown."""
        if not list_elem.content:
            return ""

        # Process each list entry
        list_parts = []
        for entry in list_elem.content:
            if isinstance(entry, ListEntry):
                list_parts.append(self._process_list_entry(entry))
            else:
                # Handle other potential content in lists
                list_parts.append(self._process_element(entry))

        return "".join(list_parts)

    def _process_list_entry(self, entry: ListEntry) -> str:
        """Convert a ListEntry object to Markdown."""
        if not entry.content:
            return "\n"

        # Process the content of the list entry
        entry_parts = []
        for item in entry.content:
            entry_parts.append(self._process_element(item))

        entry_text = "".join(entry_parts).strip()
        if not entry_text:
            return "\n"

        # Use bullet point format for list entries
        return f"- {entry_text}\n"

    def _process_text(self, text: Text) -> str:
        """Convert a Text object to Markdown, applying formatting."""
        # Text.content is a list of strings, so join them
        content = "".join(text.content) if isinstance(text.content, list) else str(text.content)
        if not content.strip():
            return content  # Preserve whitespace

        props = text.properties
        if props.get("bold"):
            content = f"**{content}**"
        if props.get("italic"):
            content = f"*{content}*"
        if props.get("underline"):
            # Using non-standard but common double underscore for underline
            content = f"__{content}__"

        return content

    def _process_image(self, image: Image) -> str:
        """Process an Image object using the unified attachment handler."""
        image_data = image.data
        filename = image.filename or "image.png"
        alt_text = Path(filename).stem

        return process_attachment(
            attachment_data=image_data,
            attachment_name=filename,
            alt_text=alt_text,
            attachment_mode=self.options.attachment_mode,
            attachment_output_dir=self.options.attachment_output_dir,
            attachment_base_url=self.options.attachment_base_url,
            is_image=True,
        )


def rtf_to_markdown(
        input_data: Union[str, Path, IO[bytes]], options: RtfOptions | None = None
) -> str:
    """Convert an RTF document to Markdown format.

    Processes RTF documents from various input sources and converts them to
    well-formatted Markdown, preserving structure and formatting like tables,
    lists, and text styles.

    Parameters
    ----------
    input_data : str, pathlib.Path, or file-like object
        RTF content to convert. Can be:
        - String path to an RTF file
        - pathlib.Path object pointing to an RTF file
        - File-like object (e.g., BytesIO) containing RTF data
    options : RtfOptions or None, default None
        Configuration options for RTF conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the RTF document.

    Raises
    ------
    MdparseInputError
        If input type is not supported or file cannot be read.
    MdparseConversionError
        If the `pyth` library is not installed or if RTF parsing fails.
    """
    if Rtf15Reader is None:
        raise MdparseConversionError(
            "`pyth` library is required for RTF conversion. Install with: pip install pyth",
            conversion_stage="dependency_check",
        )

    if options is None:
        options = RtfOptions()

    try:
        doc_input, _ = validate_and_convert_input(
            input_data, supported_types=["path-like", "file-like"]
        )

        if isinstance(doc_input, (str, Path)):
            with open(doc_input, "rb") as f:
                doc = Rtf15Reader.read(f)
        elif hasattr(doc_input, "read"):
            # Ensure we have a binary stream
            if isinstance(doc_input, io.TextIOBase):
                raise MdparseConversionError("RTF input stream must be binary, not text.")
            doc = Rtf15Reader.read(doc_input)
        else:
            raise MdparseConversionError(f"Unsupported input type for RTF conversion: {type(doc_input)}")

    except Exception as e:
        if isinstance(e, MdparseConversionError):
            raise
        raise MdparseConversionError(
            f"Failed to read or parse RTF document: {e}",
            conversion_stage="document_parsing",
            original_error=e,
        ) from e

    converter = RtfConverter(options)
    return converter.convert(doc)
