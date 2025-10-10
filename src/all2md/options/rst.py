#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/rst.py
"""Configuration options for reStructuredText parsing and rendering.

This module defines options for rST document conversion.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_RST_CODE_STYLE,
    DEFAULT_RST_HEADING_CHARS,
    DEFAULT_RST_LINE_LENGTH,
    DEFAULT_RST_PARSE_DIRECTIVES,
    DEFAULT_RST_PRESERVE_RAW_DIRECTIVES,
    DEFAULT_RST_STRICT_MODE,
    DEFAULT_RST_TABLE_STYLE,
    RstCodeStyle,
    RstTableStyle,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class RstParserOptions(BaseParserOptions):
    """Configuration options for reStructuredText-to-AST parsing.

    This dataclass contains settings specific to parsing reStructuredText documents
    into AST representation using docutils.

    Parameters
    ----------
    parse_directives : bool, default True
        Whether to parse RST directives (code-block, image, note, etc.).
        When True, directives are converted to appropriate AST nodes.
        When False, directives are preserved as code blocks.
    strict_mode : bool, default False
        Whether to raise errors on invalid RST syntax.
        When False, attempts to recover gracefully.
    preserve_raw_directives : bool, default False
        Whether to preserve unknown directives as code blocks.
        When True, unknown directives become CodeBlock nodes.
        When False, they are processed through docutils default handling.

    """

    parse_directives: bool = field(
        default=DEFAULT_RST_PARSE_DIRECTIVES,
        metadata={
            "help": "Parse RST directives (code-block, image, etc.)",
            "cli_name": "no-parse-directives"
        }
    )
    strict_mode: bool = field(
        default=DEFAULT_RST_STRICT_MODE,
        metadata={
            "help": "Raise errors on invalid RST syntax (vs. graceful recovery)"
        }
    )
    preserve_raw_directives: bool = field(
        default=DEFAULT_RST_PRESERVE_RAW_DIRECTIVES,
        metadata={
            "help": "Preserve unknown directives as code blocks",
            "cli_name": "preserve-raw-directives"
        }
    )


@dataclass(frozen=True)
class RstRendererOptions(BaseRendererOptions):
    """Configuration options for AST-to-reStructuredText rendering.

    This dataclass contains settings for rendering AST documents as
    reStructuredText output.

    Parameters
    ----------
    heading_chars : str, default "=-~^*"
        Characters to use for heading underlines from h1 to h5.
        First character is for level 1, second for level 2, etc.
    table_style : {"grid", "simple"}, default "grid"
        Table rendering style:
        - "grid": Grid tables with +---+ borders
        - "simple": Simple tables with === separators
    code_directive_style : {"double_colon", "directive"}, default "directive"
        Code block rendering style:
        - "double_colon": Use :: literal blocks
        - "directive": Use .. code-block:: directive
    line_length : int, default 80
        Target line length for wrapping text.

    Notes
    -----
    **Text Escaping:**
        Special RST characters (asterisks, underscores, backticks, brackets, pipes, colons,
        angle brackets) are automatically escaped in text nodes to prevent unintended formatting.

    **Line Breaks:**
        Hard line breaks are rendered using RST line block syntax (newline followed by ``| ``).
        This is the standard approach for preserving line structure in reStructuredText.
        Soft line breaks render as spaces, consistent with RST paragraph semantics.

    **Unsupported Features:**
        - **Strikethrough**: RST has no native strikethrough syntax. Content renders as plain text.
        - **Underline**: RST has no native underline syntax. Content renders as plain text.
        - **Superscript/Subscript**: Rendered using RST role syntax (``:sup:`` and ``:sub:``).

    **Table Limitations:**
        Both grid and simple table styles do not support multi-line content within cells.
        Cell content must be single-line text. Complex cell content (multiple paragraphs,
        nested lists) will be rendered inline, which may cause formatting issues.

    """

    heading_chars: str = field(
        default=DEFAULT_RST_HEADING_CHARS,
        metadata={
            "help": "Characters for heading underlines (h1-h5)"
        }
    )
    table_style: RstTableStyle = field(
        default=DEFAULT_RST_TABLE_STYLE,
        metadata={
            "help": "Table rendering style",
            "choices": ["grid", "simple"]
        }
    )
    code_directive_style: RstCodeStyle = field(
        default=DEFAULT_RST_CODE_STYLE,
        metadata={
            "help": "Code block rendering style",
            "choices": ["double_colon", "directive"]
        }
    )
    line_length: int = field(
        default=DEFAULT_RST_LINE_LENGTH,
        metadata={
            "help": "Target line length for wrapping",
            "type": int
        }
    )
