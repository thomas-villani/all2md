#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/sourcecode.py
"""Source code to AST converter.

This module provides conversion from source code files to AST representation.
It creates CodeBlock nodes with appropriate language identifiers.

"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import IO, Union, Any

from all2md.ast import CodeBlock, Document
from all2md.converter_metadata import ConverterMetadata
from all2md.options import SourceCodeOptions
from all2md.parsers.base import BaseParser
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)

# Language mapping for file extensions to GitHub-style language identifiers
# Imported from sourcecode2markdown for consistency
from all2md.parsers.sourcecode2markdown import EXTENSION_TO_LANGUAGE, _detect_language_from_extension


class SourceCodeToAstConverter(BaseParser):
    """Convert source code files to AST representation.

    This converter creates a CodeBlock node with the detected language.

    Parameters
    ----------
    options : SourceCodeOptions or None
        Conversion options

    """

    def __init__(self, options: SourceCodeOptions | None = None):
        super().__init__(options or SourceCodeOptions())

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse source code input into an AST Document.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input source code to parse

        Returns
        -------
        Document
            AST Document node with CodeBlock

        Raises
        ------
        MarkdownConversionError
            If parsing fails

        """
        from all2md.exceptions import MarkdownConversionError
        from all2md.utils.inputs import is_path_like

        # Extract filename for language detection
        filename = None
        if is_path_like(input_data):
            filename = str(input_data)
        elif hasattr(input_data, "name") and input_data.name:
            filename = input_data.name

        # Read content based on input type
        try:
            if isinstance(input_data, (str, Path)):
                # Read from file path
                with open(input_data, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            elif isinstance(input_data, bytes):
                # Decode bytes directly
                content = input_data.decode("utf-8", errors="replace")
            else:
                # Handle file-like object
                if hasattr(input_data, "read"):
                    raw_content = input_data.read()
                    if isinstance(raw_content, bytes):
                        content = raw_content.decode("utf-8", errors="replace")
                    else:
                        content = str(raw_content)
                else:
                    raise ValueError(f"Unsupported input type: {type(input_data)}")
        except Exception as e:
            raise MarkdownConversionError(f"Failed to read source code: {e}") from e

        return self.convert_to_ast(content, filename=filename)

    def convert_to_ast(self, content: str, filename: str | None = None, language: str | None = None) -> Document:
        """Convert source code content to AST Document.

        Parameters
        ----------
        content : str
            Source code content
        filename : str | None
            Filename for language detection
        language : str | None
            Override language identifier

        Returns
        -------
        Document
            AST document with CodeBlock node

        """
        # Strip content
        content = content.strip()

        # Determine language
        if language:
            detected_lang = language
            logger.debug(f"Using provided language: {detected_lang}")
        elif self.options.language_override:
            detected_lang = self.options.language_override
            logger.debug(f"Using language override: {detected_lang}")
        elif self.options.detect_language and filename:
            detected_lang = _detect_language_from_extension(filename)
            logger.debug(f"Detected language from extension: {detected_lang}")
        else:
            detected_lang = "text"
            logger.debug("Using default language: text")

        # Add filename comment if requested
        if self.options.include_filename and filename:
            # Get base filename
            base_filename = os.path.basename(filename)

            # Determine comment style
            comment_styles = {
                "python": "#",
                "bash": "#",
                "ruby": "#",
                "perl": "#",
                "yaml": "#",
                "javascript": "//",
                "typescript": "//",
                "java": "//",
                "c": "//",
                "cpp": "//",
                "csharp": "//",
                "go": "//",
                "rust": "//",
                "swift": "//",
                "html": "<!--",
                "xml": "<!--",
                "css": "/*",
                "scss": "/*",
                "less": "/*",
                "sql": "--",
                "lua": "--",
                "haskell": "--",
            }

            comment_prefix = comment_styles.get(detected_lang, "#")
            comment_suffix = ""

            if comment_prefix in ["<!--", "/*"]:
                comment_suffix = " -->" if comment_prefix == "<!--" else " */"

            filename_comment = f"{comment_prefix} {base_filename}{comment_suffix}"
            content = f"{filename_comment}\n{content}"

        # Create CodeBlock node
        code_block = CodeBlock(
            language=detected_lang,
            content=content,
            metadata={"filename": filename} if filename else {}
        )

        # Extract and attach metadata
        metadata = self.extract_metadata(None)
        return Document(children=[code_block], metadata=metadata.to_dict())

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from source code document.

        Parameters
        ----------
        document : Any
            Source code document (not used)

        Returns
        -------
        DocumentMetadata
            Empty metadata (source code files don't have standard metadata)

        Notes
        -----
        Source code files typically do not contain structured metadata.
        Information like language and filename is handled through the
        conversion options and file context, not as document metadata.

        """
        return DocumentMetadata()


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="sourcecode",
    extensions=EXTENSION_TO_LANGUAGE.keys(),
    mime_types=[
        "text/plain",
        "text/x-python",
        "text/x-java-source",
        "text/x-c",
        "text/x-c++src",
        "text/x-csharp",
        "text/x-javascript",
        "text/x-typescript",
        "text/x-go",
        "text/x-rust",
        "text/x-swift",
        "text/x-php",
        "text/x-ruby",
        "text/x-perl",
        "text/x-shellscript",
        "text/x-sql",
        "application/x-javascript",
        "application/javascript",
        "application/typescript",
        "application/x-python-code",
        "application/x-java-source",
        "application/x-csh",
        "application/x-sh",
        "application/x-shellscript",
    ],
    magic_bytes=[],  # No specific magic bytes - rely on extension detection
    parser_class="SourceCodeToAstConverter",
    renderer_class=None,
    required_packages=[],  # No external dependencies
    optional_packages=[],
    import_error_message="",  # No dependencies required
    options_class="SourceCodeOptions",
    description="Convert source code files to Markdown with syntax highlighting",
    priority=1,  # Lower priority than specialized parsers, higher than txt fallback
)
