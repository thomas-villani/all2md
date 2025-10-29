#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/plaintext.py
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
from all2md.options.plaintext import PlainTextParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
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

    def __init__(
        self, options: PlainTextParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the plain text parser with options and progress callback."""
        # Validate options type before processing
        BaseParser._validate_options_type(options, PlainTextParserOptions, "plaintext")
        options = options or PlainTextParserOptions()
        super().__init__(options, progress_callback)
        self.options: PlainTextParserOptions = options

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
        content = self._load_text_content(input_data)
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
        # Normalize line endings to Unix-style (\n) to handle Windows (\r\n) and Mac (\r) files
        # This prevents \r characters from appearing as unwanted spaces in the output
        content = content.replace("\r\n", "\n").replace("\r", "\n")

        # Split content into paragraphs (double newline separated)
        # This preserves some structure while keeping it simple
        paragraphs = content.split("\n\n")

        children: list[Node] = []
        for para_text in paragraphs:
            # Skip empty paragraphs
            stripped = para_text.strip()
            if not stripped:
                continue

            # Handle newlines based on preserve_single_newlines option
            if self.options.preserve_single_newlines:
                # Keep newlines as-is for formats that need exact whitespace preservation
                normalized_text = stripped
            else:
                # Normalize single newlines to spaces (standard text rendering behavior)
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
    parser_options_class="all2md.options.plaintext.PlainTextParserOptions",
    renderer_options_class="all2md.options.plaintext.PlainTextOptions",
    description="Parse and render plain text files.",
    priority=1,
)
