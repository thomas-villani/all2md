#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ast_json.py
"""JSON AST to Document converter.

This module provides a parser for converting JSON-serialized AST
back into Document objects. This enables programmatic document generation
and manipulation through the AST JSON format.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import Document
from all2md.ast.serialization import json_to_ast
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.options.ast_json import AstJsonParserOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _is_ast_json_content(content: bytes) -> bool:
    """Detect if content is AST JSON format.

    This function uses a memory-efficient approach by sampling only the first
    256 KB of content for detection, which is sufficient for identifying AST
    JSON structure markers. The full content parsing is handled by the parser.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be AST JSON

    """
    # Sample first 256 KB for detection (sufficient for structure detection)
    MAX_SAMPLE_SIZE = 262144  # 256 KB
    sample = content[:MAX_SAMPLE_SIZE]

    try:
        # Decode sample to text for fast string searches
        text = sample.decode("utf-8", errors="ignore")

        # Fast preliminary check: look for key AST JSON indicators
        # before attempting JSON parsing
        if "node_type" not in text:
            return False

        # If we have node_type, try parsing the sample as JSON
        # This is more efficient than parsing potentially large files
        data = json.loads(text)

        # Check for AST JSON markers
        if isinstance(data, dict):
            # Must have node_type field (all AST nodes have this)
            if "node_type" not in data:
                return False
            # Should have schema_version at root level
            if "schema_version" in data:
                return True
            # Or it might be a Document node (root AST node)
            if data.get("node_type") == "Document":
                return True

        return False
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return False


class AstJsonParser(BaseParser):
    """Convert JSON AST format to Document objects.

    This parser reads JSON-serialized AST and converts it back to
    Document objects using the ast.serialization module.

    Parameters
    ----------
    options : AstJsonParserOptions or None
        Parser options
    progress_callback : ProgressCallback or None
        Progress callback for parsing events

    Examples
    --------
    Parse AST JSON from file:
        >>> from all2md.parsers.ast_json import AstJsonParser
        >>> parser = AstJsonParser()
        >>> doc = parser.parse("document.ast")

    Parse AST JSON from string:
        >>> import json
        >>> ast_json = json.dumps({
        ...     "schema_version": 1,
        ...     "node_type": "Document",
        ...     "children": [],
        ...     "metadata": {}
        ... })
        >>> doc = parser.parse(ast_json.encode('utf-8'))

    """

    def __init__(
        self, options: AstJsonParserOptions | None = None, progress_callback: Optional[ProgressCallback] = None
    ):
        """Initialize the AST JSON parser."""
        BaseParser._validate_options_type(options, AstJsonParserOptions, "ast")
        options = options or AstJsonParserOptions()
        super().__init__(options, progress_callback)
        self.options: AstJsonParserOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse JSON AST input into a Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input JSON AST to parse

        Returns
        -------
        Document
            AST Document node

        Raises
        ------
        ParsingError
            If parsing fails due to invalid JSON or AST structure

        """
        self._emit_progress("started", "Parsing AST JSON", total=1)

        try:
            # Read JSON content based on input type
            if isinstance(input_data, (str, Path)):
                # Read from file path
                with open(input_data, "r", encoding="utf-8") as f:
                    json_str = f.read()
            elif isinstance(input_data, bytes):
                # Decode bytes directly
                json_str = input_data.decode("utf-8")
            elif hasattr(input_data, "read"):
                # Handle file-like object (IO[bytes])
                raw_content = input_data.read()
                json_str = raw_content.decode("utf-8") if isinstance(raw_content, bytes) else str(raw_content)
            else:
                raise ValueError(f"Unsupported input type: {type(input_data)}")

            # Parse JSON to AST using serialization module with optional validation
            try:
                doc = json_to_ast(
                    json_str, validate_schema=self.options.validate_schema, strict_mode=self.options.strict_mode
                )
            except json.JSONDecodeError as e:
                raise ParsingError(
                    f"Invalid JSON in AST file: {e}", parsing_stage="json_parsing", original_error=e
                ) from e
            except ValueError as e:
                # This could be from schema version validation or unknown node types
                # (only when validation is enabled)
                raise ParsingError(
                    f"Invalid AST structure: {e}", parsing_stage="ast_deserialization", original_error=e
                ) from e

            # Validate it's a Document node
            if not isinstance(doc, Document):
                raise ParsingError(
                    f"Invalid AST structure: AST root must be a Document node, got {type(doc).__name__}",
                    parsing_stage="ast_validation",
                )

            self._emit_progress("finished", "AST JSON parsing complete", current=1, total=1)
            return doc

        except ParsingError:
            # Re-raise ParsingError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            raise ParsingError(
                f"Failed to parse AST JSON: {e}", parsing_stage="ast_json_parsing", original_error=e
            ) from e

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from AST Document.

        Parameters
        ----------
        document : Document
            The parsed Document node

        Returns
        -------
        DocumentMetadata
            Extracted metadata from Document.metadata

        """
        # Document objects already have metadata dict
        if isinstance(document, Document) and document.metadata:
            # Convert Document.metadata dict to DocumentMetadata
            return DocumentMetadata(
                title=document.metadata.get("title"),
                author=document.metadata.get("author"),
                subject=document.metadata.get("subject"),
                keywords=document.metadata.get("keywords"),
                creation_date=document.metadata.get("creation_date"),
                modification_date=document.metadata.get("modification_date"),
                language=document.metadata.get("language"),
                custom=document.metadata.get("custom", {}),
            )

        return DocumentMetadata()


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ast",
    extensions=[".ast"],  # Use .ast extension to avoid conflicts with regular .json files
    mime_types=["application/json"],
    magic_bytes=[],  # JSON has no specific magic bytes
    content_detector=_is_ast_json_content,
    parser_class=AstJsonParser,
    renderer_class="all2md.renderers.ast_json.AstJsonRenderer",
    renders_as_string=True,
    parser_required_packages=[],  # No dependencies - pure Python
    renderer_required_packages=[],
    optional_packages=[],
    import_error_message="",
    parser_options_class=AstJsonParserOptions,
    renderer_options_class="all2md.options.ast_json.AstJsonRendererOptions",
    description="Parse and render documents in JSON-serialized AST format for programmatic access.",
    priority=5,  # Higher priority to check AST format before generic text
)
