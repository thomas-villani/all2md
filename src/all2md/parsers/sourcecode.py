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
from typing import IO, Union

from all2md.ast import CodeBlock, Document
from all2md.options import SourceCodeOptions

logger = logging.getLogger(__name__)

# Language mapping for file extensions to GitHub-style language identifiers
# Imported from sourcecode2markdown for consistency
from all2md.parsers.sourcecode2markdown import EXTENSION_TO_LANGUAGE, _detect_language_from_extension


class SourceCodeToAstConverter:
    """Convert source code files to AST representation.

    This converter creates a CodeBlock node with the detected language.

    Parameters
    ----------
    options : SourceCodeOptions or None
        Conversion options

    """

    def __init__(self, options: SourceCodeOptions | None = None):
        self.options = options or SourceCodeOptions()

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

        return Document(children=[code_block])
