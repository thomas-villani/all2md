#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/ast_json.py
"""Options for AST JSON parsing and rendering.

This module provides configuration options for parsing and rendering
documents in JSON-serialized AST format.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_AST_JSON_ENSURE_ASCII,
    DEFAULT_AST_JSON_INDENT,
    DEFAULT_AST_JSON_SORT_KEYS,
    DEFAULT_AST_JSON_STRICT_MODE,
    DEFAULT_AST_JSON_VALIDATE_SCHEMA,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class AstJsonParserOptions(BaseParserOptions):
    """Options for parsing JSON AST documents.

    Parameters
    ----------
    validate_schema : bool, default = True
        Whether to validate the schema version during parsing
    strict_mode : bool, default = False
        Whether to fail on unknown node types or attributes

    """

    validate_schema: bool = field(
        default=DEFAULT_AST_JSON_VALIDATE_SCHEMA,
        metadata={"help": "Validate schema version during parsing", "importance": "core"},
    )
    strict_mode: bool = field(
        default=DEFAULT_AST_JSON_STRICT_MODE,
        metadata={"help": "Fail on unknown node types or attributes", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class AstJsonRendererOptions(BaseRendererOptions):
    """Options for rendering documents to JSON AST format.

    Parameters
    ----------
    indent : int or None, default = 2
        Number of spaces for JSON indentation. None for compact output.
    ensure_ascii : bool, default = False
        Whether to escape non-ASCII characters in JSON output
    sort_keys : bool, default = False
        Whether to sort JSON object keys alphabetically

    Examples
    --------
    Compact JSON output:
        >>> options = AstJsonRendererOptions(indent=None)

    Pretty-printed JSON with sorted keys:
        >>> options = AstJsonRendererOptions(indent=2, sort_keys=True)

    ASCII-only output:
        >>> options = AstJsonRendererOptions(ensure_ascii=True)

    """

    indent: int | None = field(
        default=DEFAULT_AST_JSON_INDENT,
        metadata={"help": "JSON indentation spaces (None for compact)", "type": int, "importance": "core"},
    )
    ensure_ascii: bool = field(
        default=DEFAULT_AST_JSON_ENSURE_ASCII,
        metadata={"help": "Escape non-ASCII characters in JSON", "importance": "advanced"},
    )
    sort_keys: bool = field(
        default=DEFAULT_AST_JSON_SORT_KEYS,
        metadata={"help": "Sort JSON object keys alphabetically", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
