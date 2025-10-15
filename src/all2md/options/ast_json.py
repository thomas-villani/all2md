#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/ast_json.py
"""Options for AST JSON parsing and rendering.

This module provides configuration options for parsing and rendering
documents in JSON-serialized AST format.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from all2md.options.base import BaseParserOptions, BaseRendererOptions

# FIXME: these should be `field()` objects

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

    validate_schema: bool = True
    strict_mode: bool = False


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

    indent: Optional[int] = 2
    ensure_ascii: bool = False
    sort_keys: bool = False
