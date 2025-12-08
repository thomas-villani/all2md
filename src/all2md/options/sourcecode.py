#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/sourcecode.py
"""Configuration options for source code parsing.

This module defines options for parsing source code files with syntax highlighting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class SourceCodeOptions(BaseParserOptions):
    """Configuration options for source code to Markdown conversion.

    This dataclass contains settings specific to source code file processing,
    including language detection, formatting options, and output customization.

    Parameters
    ----------
    detect_language : bool, default True
        Whether to automatically detect programming language from file extension.
        When enabled, uses file extension to determine appropriate syntax highlighting
        language identifier for the Markdown code block.
    language_override : str or None, default None
        Manual override for the language identifier. When provided, this language
        will be used instead of automatic detection. Useful for files with
        non-standard extensions or when forcing a specific syntax highlighting.
    include_filename : bool, default False
        Whether to include the original filename as a comment at the top of the
        code block. The comment style is automatically chosen based on the
        detected or specified language.

    """

    detect_language: bool = field(
        default=True,
        metadata={
            "help": "Automatically detect programming language from file extension",
            "cli_name": "no-detect-language",
            "importance": "core",
        },
    )

    language_override: str | None = field(
        default=None,
        metadata={
            "help": "Override language identifier for syntax highlighting",
            "cli_name": "language",
            "importance": "core",
        },
    )

    include_filename: bool = field(
        default=False,
        metadata={
            "help": "Include filename as comment in code block",
            "cli_name": "include-filename",
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
