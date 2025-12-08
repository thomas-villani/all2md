#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/bbcode.py
"""Configuration options for BBCode parsing.

This module defines options classes for BBCode (Bulletin Board Code) format conversion,
supporting parsing from legacy bulletin board systems and forums.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_BBCODE_PARSE_ALIGNMENT,
    DEFAULT_BBCODE_PARSE_COLOR_SIZE,
    DEFAULT_BBCODE_STRICT_MODE,
    DEFAULT_BBCODE_UNKNOWN_TAG_MODE,
    DEFAULT_HTML_PASSTHROUGH_MODE,
    BBCodeUnknownTagMode,
    HtmlPassthroughMode,
)
from all2md.options.base import BaseParserOptions


@dataclass(frozen=True)
class BBCodeParserOptions(BaseParserOptions):
    """Configuration options for BBCode-to-AST parsing.

    This dataclass contains settings specific to parsing BBCode documents
    from bulletin boards and forums into AST representation.

    Parameters
    ----------
    strict_mode : bool, default False
        Whether to raise errors on malformed BBCode syntax.
        When False, attempts to recover gracefully from parsing errors.
    unknown_tag_mode : {"preserve", "strip", "escape"}, default "strip"
        How to handle unknown or vendor-specific BBCode tags:
        - "preserve": Keep unknown tags as HTMLInline nodes for round-trip
        - "strip": Remove unknown tags but preserve their content as text
        - "escape": Escape the tag brackets to display as literal text
    parse_color_size : bool, default True
        Whether to preserve color and size attributes in styled text.
        When True, color/size info is stored in node metadata.
        When False, color and size tags are treated as regular text emphasis.
    parse_alignment : bool, default True
        Whether to preserve text alignment (center, left, right).
        When True, alignment is stored in paragraph metadata.
        When False, alignment tags are ignored.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
        How to handle any embedded HTML in BBCode:
        - "pass-through": Preserve HTML unchanged (use only with trusted content)
        - "escape": HTML-escape the content to display as text
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes

    Examples
    --------
    Basic usage:
        >>> from all2md.parsers.bbcode import BBCodeParser
        >>> from all2md.options.bbcode import BBCodeParserOptions
        >>> options = BBCodeParserOptions()
        >>> parser = BBCodeParser(options)
        >>> doc = parser.parse("[b]Bold text[/b]")

    Strict mode for validation:
        >>> options = BBCodeParserOptions(strict_mode=True)
        >>> parser = BBCodeParser(options)

    Preserve all tags including unknown ones:
        >>> options = BBCodeParserOptions(unknown_tag_mode="preserve")
        >>> parser = BBCodeParser(options)

    """

    strict_mode: bool = field(
        default=DEFAULT_BBCODE_STRICT_MODE,
        metadata={"help": "Raise errors on malformed BBCode syntax", "importance": "advanced"},
    )
    unknown_tag_mode: BBCodeUnknownTagMode = field(
        default=DEFAULT_BBCODE_UNKNOWN_TAG_MODE,
        metadata={
            "help": "How to handle unknown BBCode tags: preserve, strip, or escape",
            "choices": ["preserve", "strip", "escape"],
            "importance": "core",
        },
    )
    parse_color_size: bool = field(
        default=DEFAULT_BBCODE_PARSE_COLOR_SIZE,
        metadata={
            "help": "Preserve color and size attributes in metadata",
            "cli_name": "no-parse-color-size",
            "importance": "advanced",
        },
    )
    parse_alignment: bool = field(
        default=DEFAULT_BBCODE_PARSE_ALIGNMENT,
        metadata={
            "help": "Preserve text alignment (center, left, right)",
            "cli_name": "no-parse-alignment",
            "importance": "advanced",
        },
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle embedded HTML: pass-through, escape, drop, or sanitize",
            "choices": ["pass-through", "escape", "drop", "sanitize"],
            "importance": "security",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
