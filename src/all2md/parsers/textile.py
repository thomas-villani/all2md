#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/textile.py
"""Textile to AST converter.

This module provides conversion from Textile markup to AST representation
using the textile library. It enables bidirectional transformation by parsing
Textile documents into the same AST structure used for other formats.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md import HtmlOptions, NetworkFetchOptions
from all2md.ast import Document
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.textile import TextileParserOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.html import HtmlToAstConverter
from all2md.progress import ProgressCallback
from all2md.utils.decorators import requires_dependencies
from all2md.utils.encoding import normalize_stream_to_text, read_text_with_encoding_detection
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


class TextileParser(BaseParser):
    r"""Convert Textile markup to AST representation.

    This converter uses the textile library to convert Textile markup to HTML,
    then leverages the existing HtmlToAstConverter to build an AST that matches
    the structure used throughout all2md, enabling bidirectional conversion and
    transformation pipelines.

    Parameters
    ----------
    options : TextileParserOptions or None, default = None
        Parser configuration options
    progress_callback : ProgressCallback or None, default = None
        Optional callback for progress updates

    Examples
    --------
    Basic parsing:

        >>> parser = TextileParser()
        >>> doc = parser.parse("h1. Title\n\nThis is *bold*.")

    With options:

        >>> options = TextileParserOptions(strict_mode=True)
        >>> parser = TextileParser(options)
        >>> doc = parser.parse(textile_text)

    """

    def __init__(
        self, options: TextileParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the Textile parser with options and progress callback."""
        options = options or TextileParserOptions()
        super().__init__(options, progress_callback)
        self.options: TextileParserOptions = options

    @requires_dependencies("textile", [("textile", "textile", "")])
    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse Textile input into AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Textile input to parse. Can be:
            - File path (str or Path)
            - File-like object in binary mode
            - Raw Textile bytes
            - Textile string

        Returns
        -------
        Document
            AST document node

        Raises
        ------
        DependencyError
            If textile is not installed
        ParsingError
            If parsing fails

        """
        # Emit progress event
        self._emit_progress("started", "Parsing Textile", current=0, total=100)

        # Load Textile content from various input types
        textile_content = self._load_textile_content(input_data)

        self._emit_progress("item_done", "Loaded Textile content", current=20, total=100, item_type="loading")

        # Import textile library (lazy loaded via decorator)
        import textile

        # Convert Textile to HTML
        try:
            html_content = textile.textile(textile_content)
        except Exception as e:
            if self.options.strict_mode:
                raise ParsingError(f"Failed to parse Textile markup: {e}") from e
            else:
                logger.warning(f"Textile parsing encountered error, attempting recovery: {e}", stacklevel=2)
                # Attempt to parse anyway, textile.textile() is fairly robust
                html_content = str(textile_content)

        self._emit_progress("item_done", "Converted Textile to HTML", current=50, total=100, item_type="conversion")

        # Use HtmlToAstConverter to convert HTML to AST
        # Configure network options to allow HTTP links (not just HTTPS)
        # since Textile documents may legitimately reference HTTP resources
        # TODO: I don't think that this is very smart, should respect user options.

        network_options = NetworkFetchOptions(require_https=False)
        html_options = HtmlOptions(network=network_options)

        html_converter = HtmlToAstConverter(options=html_options, progress_callback=self.progress_callback)

        # Parse HTML to AST
        document = html_converter.parse(html_content)

        self._emit_progress("item_done", "Converted HTML to AST", current=90, total=100, item_type="ast_conversion")

        # Extract metadata from the Textile content
        # Note: textile doesn't have built-in metadata, but we can try to extract
        # some basic info like title from first heading
        metadata = self.extract_metadata(textile_content)

        # Merge extracted metadata with document metadata
        if metadata.to_dict():
            doc_metadata = document.metadata or {}
            doc_metadata.update(metadata.to_dict())
            document = Document(children=document.children, metadata=doc_metadata)

        self._emit_progress("finished", "Parsing complete", current=100, total=100)

        return document

    @staticmethod
    def _load_textile_content(input_data: Union[str, Path, IO[bytes], bytes]) -> str:
        """Load Textile content from various input types with encoding detection.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            Input data to load

        Returns
        -------
        str
            Textile content as string

        """
        if isinstance(input_data, bytes):
            return read_text_with_encoding_detection(input_data)
        elif isinstance(input_data, Path):
            with open(input_data, "rb") as f:
                return read_text_with_encoding_detection(f.read())
        elif isinstance(input_data, str):
            # Could be file path or Textile content
            path = Path(input_data)
            if path.exists() and path.is_file():
                with open(path, "rb") as f:
                    return read_text_with_encoding_detection(f.read())
            else:
                # Assume it's Textile content
                return input_data
        else:
            # File-like object (handles both binary and text mode)
            input_data.seek(0)
            return normalize_stream_to_text(input_data)

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from Textile document.

        Textile doesn't have standard metadata fields, but we can try to
        extract basic information like title from the first heading.

        Parameters
        ----------
        document : Any
            Document content or AST

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # If document is a string, try to extract title from first h1
        if isinstance(document, str):

            # Try to find h1. Title pattern
            h1_match = re.search(r"^h1\.\s+(.+?)$", document, re.MULTILINE)
            if h1_match:
                metadata.title = h1_match.group(1).strip()

        return metadata


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="textile",
    extensions=[".textile"],
    mime_types=["text/x-textile"],
    magic_bytes=[],  # Textile is plain text, no magic bytes
    parser_class=TextileParser,
    renderer_class="all2md.renderers.textile.TextileRenderer",
    renders_as_string=True,
    parser_required_packages=[("textile", "textile", "")],
    renderer_required_packages=[("textile", "textile", "")],
    optional_packages=[],
    import_error_message="",
    parser_options_class=TextileParserOptions,
    renderer_options_class="all2md.options.textile.TextileRendererOptions",
    description="Parse and render Textile markup format",
    priority=10,
)
