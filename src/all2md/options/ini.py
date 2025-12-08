#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/ini.py
"""Options for INI parsing and rendering.

This module defines configuration options for converting between INI and AST.
The parser converts INI structures to readable document format, while the
renderer extracts section-based data from documents back to INI format.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class IniParserOptions(BaseParserOptions):
    """Configuration options for INI to AST parsing.

    The parser converts INI structures into human-readable document format:
    - Sections become headings
    - Key-value pairs become definition lists (bullet lists with bold keys)
    - Comments are preserved

    Parameters
    ----------
    pretty_format_numbers : bool, default = True
        If True, format large numbers with thousand separators for readability.
    preserve_case : bool, default = True
        If True, preserve the case of section names and keys. If False, convert
        to lowercase (configparser default behavior).
    allow_no_value : bool, default = False
        If True, allow keys without values (e.g., standalone flags).
    literal_block : bool, default = False
        If True, render INI as a literal code block instead of converting to
        structured document format. Useful when you want to preserve the original
        INI formatting or show it as example code.

    """

    literal_block: bool = field(
        default=False,
        metadata={"help": "Render as code block instead of structured document", "importance": "core"},
    )
    pretty_format_numbers: bool = field(
        default=True,
        metadata={"help": "Format large numbers with thousand separators", "importance": "core"},
    )
    preserve_case: bool = field(
        default=True,
        metadata={"help": "Preserve case of section names and keys", "importance": "advanced"},
    )
    allow_no_value: bool = field(
        default=False,
        metadata={"help": "Allow keys without values", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class IniRendererOptions(BaseRendererOptions):
    """Configuration options for AST to INI rendering.

    The renderer extracts section-based data from markdown documents and
    converts it to INI format. Since INI is flat (no nesting), only top-level
    sections with key-value pairs are extracted.

    Parameters
    ----------
    type_inference : bool, default = True
        If True, automatically detect and convert types (numbers, booleans).
        If False, all values remain as strings. Note: INI format stores all
        values as strings, but type inference helps with readability.
    section_from_headings : bool, default = True
        If True, use level-1 headings as section names. If False, extract
        from definition lists only.
    preserve_case : bool, default = True
        If True, preserve the case of section names and keys.
    allow_no_value : bool, default = False
        If True, allow keys without values (e.g., boolean flags set to empty).

    """

    type_inference: bool = field(
        default=True,
        metadata={"help": "Auto-detect types (numbers, booleans)", "importance": "core"},
    )
    section_from_headings: bool = field(
        default=True,
        metadata={"help": "Use level-1 headings as section names", "importance": "core"},
    )
    preserve_case: bool = field(
        default=True,
        metadata={"help": "Preserve case of section names and keys", "importance": "advanced"},
    )
    allow_no_value: bool = field(
        default=False,
        metadata={"help": "Allow keys without values", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
