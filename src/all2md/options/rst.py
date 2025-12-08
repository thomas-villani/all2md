#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/rst.py
"""Configuration options for reStructuredText parsing and rendering.

This module defines options for rST document conversion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_RST_CODE_STYLE,
    DEFAULT_RST_COMMENT_MODE,
    DEFAULT_RST_HARD_LINE_BREAK_FALLBACK_IN_CONTAINERS,
    DEFAULT_RST_HARD_LINE_BREAK_MODE,
    DEFAULT_RST_HEADING_CHARS,
    DEFAULT_RST_LINE_LENGTH,
    DEFAULT_RST_PARSE_ADMONITIONS,
    DEFAULT_RST_STRICT_MODE,
    DEFAULT_RST_STRIP_COMMENTS,
    DEFAULT_RST_TABLE_STYLE,
    RstCodeStyle,
    RstCommentMode,
    RstLineBreakMode,
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
    strict_mode : bool, default False
        Whether to raise errors on invalid RST syntax.
        When False, attempts to recover gracefully.
    parse_admonitions : bool, default True
        Whether to parse RST admonitions (note, warning, tip, important, etc.).
        When True, admonitions are converted to BlockQuote nodes with metadata
        indicating the admonition type. When False, admonitions are skipped.
    strip_comments : bool, default False
        Whether to strip comments from the output.
        When True, RST comments are removed completely.
        When False, comments are preserved as Comment AST nodes with metadata.

    Notes
    -----
    RST directives are always processed by docutils. Directive types like code-block,
    image, and math are converted to their corresponding AST nodes. Admonitions
    (note, warning, tip, etc.) are converted to BlockQuote nodes with metadata
    when parse_admonitions=True.

    """

    strict_mode: bool = field(
        default=DEFAULT_RST_STRICT_MODE,
        metadata={"help": "Raise errors on invalid RST syntax (vs. graceful recovery)", "importance": "advanced"},
    )
    parse_admonitions: bool = field(
        default=DEFAULT_RST_PARSE_ADMONITIONS,
        metadata={
            "help": "Parse admonitions (note, warning, tip, etc.) as BlockQuote with metadata",
            "cli_name": "no-parse-admonitions",
            "importance": "core",
        },
    )
    strip_comments: bool = field(
        default=DEFAULT_RST_STRIP_COMMENTS,
        metadata={
            "help": "Strip comments from output",
            "cli_name": "no-strip-comments",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class RstRendererOptions(BaseRendererOptions):
    r"""Configuration options for AST-to-reStructuredText rendering.

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
        - "double_colon": Use ``::``, literal blocks
        - "directive": Use ``.. code-block::``, directive
    line_length : int, default 80
        Target line length for wrapping text.
    hard_line_break_mode : {"line_block", "raw"}, default "line_block"
        How to render hard line breaks:
        - "line_block": Use RST line block syntax (pipe prefix), the standard approach
        - "raw": Use plain newline, less faithful but simpler in complex containers
    hard_line_break_fallback_in_containers : bool, default True
        Automatically fallback to raw mode for line breaks inside lists or blockquotes.
        When True, prevents semantic changes from line block syntax in containers.
        When False, always uses the configured hard_line_break_mode.
    comment_mode : {"comment", "note", "ignore"}, default "comment"
        How to render Comment and CommentInline AST nodes:
        - "comment": Render as rST comments (.. Comment text)
        - "note": Render as .. note:: directive blocks (visible annotations)
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from source documents.

    Notes
    -----
    **Text Escaping:**
        Special RST characters (asterisks, underscores, backticks, brackets, pipes, colons,
        angle brackets) are automatically escaped in text nodes to prevent unintended formatting.

    **Line Breaks:**
        Hard line breaks behavior depends on the ``hard_line_break_mode`` option:

        - **line_block mode (default)**: Uses RST line block syntax (pipe prefix). This is the
          standard RST approach for preserving line structure. May be surprising inside
          complex containers like lists and block quotes as it changes semantic structure.
        - **raw mode**: Uses plain newlines. Less faithful to RST semantics but simpler
          in complex containers. May not preserve visual line breaks in all RST processors.

        Soft line breaks always render as spaces, consistent with RST paragraph semantics.

        **Recommendation**: Use "raw" mode if line blocks cause formatting issues in
        lists or nested structures. Use "line_block" (default) for maximum RST fidelity.

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
        metadata={"help": "Characters for heading underlines (h1-h5)", "importance": "advanced"},
    )
    table_style: RstTableStyle = field(
        default=DEFAULT_RST_TABLE_STYLE,
        metadata={"help": "Table rendering style", "choices": ["grid", "simple"], "importance": "core"},
    )
    code_directive_style: RstCodeStyle = field(
        default=DEFAULT_RST_CODE_STYLE,
        metadata={"help": "Code block rendering style", "choices": ["double_colon", "directive"], "importance": "core"},
    )
    line_length: int = field(
        default=DEFAULT_RST_LINE_LENGTH,
        metadata={"help": "Target line length for wrapping", "type": int, "importance": "advanced"},
    )
    hard_line_break_mode: RstLineBreakMode = field(
        default=DEFAULT_RST_HARD_LINE_BREAK_MODE,
        metadata={
            "help": "Hard line break rendering mode: line_block (use | syntax) or raw (plain newline)",
            "choices": ["line_block", "raw"],
            "importance": "advanced",
        },
    )
    hard_line_break_fallback_in_containers: bool = field(
        default=DEFAULT_RST_HARD_LINE_BREAK_FALLBACK_IN_CONTAINERS,
        metadata={
            "help": "Automatically fallback to raw mode for line breaks inside lists/blockquotes",
            "cli_name": "no-hard-line-break-fallback-in-containers",
            "importance": "advanced",
        },
    )
    comment_mode: RstCommentMode = field(
        default=DEFAULT_RST_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "comment (.. comments), note (.. note:: directive), "
            "ignore (skip comment nodes entirely). Controls presentation of source document comments.",
            "choices": ["comment", "note", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate RST renderer options.

        Raises
        ------
        ValueError
            If any field value is invalid.

        """
        # Call parent validation
        super().__post_init__()

        # Validate positive line length
        if self.line_length <= 0:
            raise ValueError(f"line_length must be positive, got {self.line_length}")

        # Validate non-empty heading chars
        if not self.heading_chars or len(self.heading_chars) == 0:
            raise ValueError("heading_chars must not be empty")
