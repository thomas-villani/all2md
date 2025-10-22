#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/txt.py
"""Plain text to AST converter.

This module provides a simple converter for plain text files (.txt) that
preserves the text content as-is without syntax highlighting or code block
formatting.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, Optional, Union

from all2md.ast import Document, Node, Paragraph, Text
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.base import BaseParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.encoding import read_text_with_encoding_detection
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class PlainTextToAstConverter(BaseParser):
    """Convert plain text files to AST representation.

    This converter creates a simple AST with the text content preserved
    as-is without any special formatting or syntax highlighting.

    Parameters
    ----------
    options : BaseParserOptions or None
        Conversion options

    """

    def __init__(self, options: BaseParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the plain text parser with options and progress callback."""
        super().__init__(options or BaseParserOptions(), progress_callback)

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse plain text input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input plain text to parse

        Returns
        -------
        Document
            AST Document node with text content

        Raises
        ------
        ParsingError
            If parsing fails

        """
        # Read content based on input type with encoding detection
        try:
            if isinstance(input_data, (str, Path)):
                # Read from file path
                with open(input_data, "rb") as f:
                    raw_content = f.read()
                content = read_text_with_encoding_detection(raw_content)
            elif isinstance(input_data, bytes):
                # Decode bytes with encoding detection
                content = read_text_with_encoding_detection(input_data)
            elif hasattr(input_data, "read"):
                # Handle file-like object (IO[bytes])
                raw_content = input_data.read()
                if isinstance(raw_content, bytes):
                    content = read_text_with_encoding_detection(raw_content)
                else:
                    content = str(raw_content)
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")
        except Exception as e:
            raise ParsingError(f"Failed to read plain text: {e}") from e

        return self.convert_to_ast(content)

    def convert_to_ast(self, content: str) -> Document:
        """Convert plain text content to AST Document.

        Parameters
        ----------
        content : str
            Plain text content

        Returns
        -------
        Document
            AST document with text content

        """
        # Split content into paragraphs (double newline separated)
        # This preserves some structure while keeping it simple
        paragraphs = content.split("\n\n")

        children: list[Node] = []
        for para_text in paragraphs:
            # Skip empty paragraphs
            stripped = para_text.strip()
            if not stripped:
                continue

            # Preserve single newlines within paragraphs as spaces
            # (standard text rendering behavior)
            normalized_text = " ".join(stripped.split("\n"))

            children.append(Paragraph(content=[Text(content=normalized_text)]))

        # If no paragraphs found, create one empty paragraph
        if not children:
            children.append(Paragraph(content=[Text(content="")]))

        return Document(children=children)

    def extract_metadata(self, input_data: Union[str, Path, IO[bytes], bytes]) -> DocumentMetadata:
        """Extract metadata from plain text file.

        Parameters
        ----------
        input_data : various types
            Input data

        Returns
        -------
        DocumentMetadata
            Basic metadata

        """
        return DocumentMetadata()


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="plaintext",
    extensions=[".txt", ".text"],
    mime_types=["text/plain"],
    magic_bytes=[],  # Plain text has no magic bytes
    parser_class=PlainTextToAstConverter,
    renderer_class="all2md.renderers.plaintext.PlainTextRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # No dependencies
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=BaseParserOptions,
    renderer_options_class="all2md.options.PlainTextOptions",
    description="Parse and render plain text files.",
    priority=1,
)
