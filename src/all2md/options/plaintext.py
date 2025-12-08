#  Copyright (c) 2025 Tom Villani, Ph.D.
# all2md/options/plaintext.py
"""Configuration options for plain text rendering.

This module defines options for rendering AST to plain text format.
"""

from dataclasses import dataclass, field

from all2md.constants import DEFAULT_PLAINTEXT_COMMENT_MODE, PlainTextCommentMode
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class PlainTextParserOptions(BaseParserOptions):
    """Configuration options for plain text parsing.

    Parameters
    ----------
    preserve_single_newlines : bool, default False
        Preserve single newlines characters in text

    """

    preserve_single_newlines: bool = field(
        default=False,
        metadata={
            "help": "Preserve single newlines characters in text",
            "type": bool,
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class PlainTextOptions(BaseRendererOptions):
    r"""Configuration options for plain text rendering.

    This dataclass contains settings for rendering AST documents as
    plain, unformatted text. All formatting (bold, italic, headings, etc.)
    is stripped, leaving only the text content.

    Parameters
    ----------
    max_line_width : int or None, default 80
        Maximum line width for wrapping text. Set to None to disable wrapping.
        When enabled, long lines will be wrapped at word boundaries.
    table_cell_separator : str, default " | "
        Separator string to use between table cells.
    include_table_headers : bool, default True
        Whether to include table headers in the output.
        When False, only table body rows are rendered.
    paragraph_separator : str, default "\n\n"
        Separator string to use between paragraphs and block elements.
    list_item_prefix : str, default "- "
        Prefix to use for list items (both ordered and unordered).
    preserve_code_blocks : bool, default True
        Whether to preserve code block content with original formatting.
        When False, code blocks are treated like regular paragraphs.
    preserve_blank_lines : bool, default True
        Whether to preserve consecutive blank lines in the output.
        When False, consecutive blank lines are collapsed according to
        paragraph_separator. When True, provides literal pass-through of
        blank lines for consumers that need exact whitespace preservation.
    comment_mode : {"visible", "ignore"}, default "ignore"
        How to render Comment and CommentInline AST nodes:
        - "visible": Render as bracketed text
        - "ignore": Skip comments entirely (default)

    Examples
    --------
    Basic plain text rendering:
        >>> from all2md.ast import Document, Paragraph, Text
        >>> from all2md.renderers.plaintext import PlainTextRenderer
        >>> from all2md.options import PlainTextOptions
        >>> doc = Document(children=[
        ...     Paragraph(content=[Text(content="Hello world")])
        ... ])
        >>> options = PlainTextOptions(max_line_width=None)
        >>> renderer = PlainTextRenderer(options)
        >>> text = renderer.render_to_string(doc)

    """

    max_line_width: int | None = field(
        default=80,
        metadata={"help": "Maximum line width for wrapping (None = no wrapping)", "type": int, "importance": "core"},
    )
    table_cell_separator: str = field(
        default=" | ", metadata={"help": "Separator between table cells", "type": str, "importance": "advanced"}
    )
    include_table_headers: bool = field(
        default=True,
        metadata={
            "help": "Include table headers in output",
            "cli_name": "no-include-table-headers",
            "importance": "core",
        },
    )
    paragraph_separator: str = field(
        default="\n\n", metadata={"help": "Separator between paragraphs", "type": str, "importance": "advanced"}
    )
    list_item_prefix: str = field(
        default="- ", metadata={"help": "Prefix for list items", "type": str, "importance": "advanced"}
    )
    preserve_code_blocks: bool = field(
        default=True,
        metadata={
            "help": "Preserve code block formatting",
            "cli_name": "no-preserve-code-blocks",
            "importance": "core",
        },
    )
    preserve_blank_lines: bool = field(
        default=True,
        metadata={
            "help": "Preserve consecutive blank lines in output",
            "cli_name": "no-preserve-blank-lines",
            "importance": "core",
        },
    )
    comment_mode: PlainTextCommentMode = field(
        default=DEFAULT_PLAINTEXT_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: visible or ignore",
            "choices": ["visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
