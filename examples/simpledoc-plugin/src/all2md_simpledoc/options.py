# Copyright (c) 2025 All2md Contributors
"""Options classes for SimpleDoc format conversion.

This module defines configuration options for both parsing and rendering
SimpleDoc documents.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import BaseParserOptions, BaseRendererOptions


# Frozen dataclass pattern: Make options immutable for thread safety and clarity
# frozen=True prevents accidental modification after creation
# This is best practice for configuration classes
@dataclass(frozen=True)
class SimpleDocOptions(BaseParserOptions):
    """Options for parsing SimpleDoc documents.

    Parameters
    ----------
    include_frontmatter : bool, default=True
        Whether to parse and include metadata from the frontmatter block.
        If False, frontmatter is ignored.
    parse_code_blocks : bool, default=True
        Whether to parse code blocks (triple backticks).
        If False, code blocks are treated as regular paragraphs.
    parse_lists : bool, default=True
        Whether to parse list items (lines starting with '-').
        If False, list items are treated as regular paragraphs.
    strict_mode : bool, default=False
        If True, raise errors on malformed syntax.
        If False, attempt to parse gracefully with warnings.

    """

    # Field metadata: Enables CLI integration and documentation
    # "help": Description shown in --help
    # "cli_flag": Command-line flag name for this option
    # The CLI system automatically reads this metadata to generate arguments
    include_frontmatter: bool = field(
        default=True,
        metadata={
            "help": "Parse and include metadata from frontmatter block",
            "cli_flag": "--simpledoc-include-frontmatter",
        },
    )
    parse_code_blocks: bool = field(
        default=True,
        metadata={
            "help": "Parse code blocks (triple backticks)",
            "cli_flag": "--simpledoc-parse-code-blocks",
        },
    )
    parse_lists: bool = field(
        default=True,
        metadata={
            "help": "Parse list items (lines starting with '-')",
            "cli_flag": "--simpledoc-parse-lists",
        },
    )
    strict_mode: bool = field(
        default=False,
        metadata={
            "help": "Raise errors on malformed syntax instead of parsing gracefully",
            "cli_flag": "--simpledoc-strict",
        },
    )


# Separate options for renderer: Parser and renderer can have different configuration needs
# This separation of concerns keeps each class focused and maintainable
@dataclass(frozen=True)
class SimpleDocRendererOptions(BaseRendererOptions):
    """Options for rendering SimpleDoc documents.

    Parameters
    ----------
    include_frontmatter : bool, default=True
        Whether to include frontmatter metadata block in output.
        If False, metadata is omitted.
    heading_marker : str, default="@@"
        The marker to use for headings in SimpleDoc output.
    list_marker : str, default="-"
        The marker to use for list items in SimpleDoc output.
    indent_size : int, default=2
        Number of spaces to use for indentation in nested structures.
    newlines_between_blocks : int, default=1
        Number of blank lines between block-level elements.

    """

    include_frontmatter: bool = field(
        default=True,
        metadata={
            "help": "Include frontmatter metadata block in rendered output",
            "cli_flag": "--simpledoc-render-frontmatter",
        },
    )
    heading_marker: str = field(
        default="@@",
        metadata={
            "help": "Marker for headings in SimpleDoc output",
            "cli_flag": "--simpledoc-heading-marker",
        },
    )
    list_marker: str = field(
        default="-",
        metadata={
            "help": "Marker for list items in SimpleDoc output",
            "cli_flag": "--simpledoc-list-marker",
        },
    )
    indent_size: int = field(
        default=2,
        metadata={
            "help": "Number of spaces for indentation",
            "cli_flag": "--simpledoc-indent-size",
        },
    )
    newlines_between_blocks: int = field(
        default=1,
        metadata={
            "help": "Number of blank lines between block elements",
            "cli_flag": "--simpledoc-block-spacing",
        },
    )

    # Validation pattern: Use __post_init__ to validate field values
    # This runs after dataclass __init__, allowing us to validate the complete object
    # frozen=True requires special handling: use object.__setattr__ if you need to set derived fields
    def __post_init__(self) -> None:
        """Validate option values.

        Raises
        ------
        ValueError
            If option values are invalid

        """
        # Always call parent __post_init__ for proper inheritance
        super().__post_init__()

        # Validate numeric constraints
        if self.indent_size < 0:
            raise ValueError(f"indent_size must be non-negative, got {self.indent_size}")

        if self.newlines_between_blocks < 0:
            raise ValueError(f"newlines_between_blocks must be non-negative, got {self.newlines_between_blocks}")

        # Validate string constraints (markers cannot be empty)
        if not self.heading_marker:
            raise ValueError("heading_marker cannot be empty")

        if not self.list_marker:
            raise ValueError("list_marker cannot be empty")
