#  Copyright (c) 2025 Tom Villani, Ph.D.

# all2md/options/textile.py
"""Configuration options for Textile parsing and rendering.

This module defines options classes for Textile format conversion,
supporting both AST parsing and rendering operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_HTML_PASSTHROUGH_MODE,
    DEFAULT_TEXTILE_COMMENT_MODE,
    HTML_PASSTHROUGH_MODES,
    HtmlPassthroughMode,
    TextileCommentMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class TextileParserOptions(BaseParserOptions):
    """Configuration options for Textile-to-AST parsing.

    This dataclass contains settings specific to parsing Textile documents
    into AST representation using the textile library.

    Parameters
    ----------
    strict_mode : bool, default False
        Whether to raise errors on invalid Textile syntax.
        When False, attempts to recover gracefully.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
        How to handle inline HTML in Textile:
        - "pass-through": Preserve HTML unchanged (use only with trusted content)
        - "escape": HTML-escape the content to display as text
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes

    Examples
    --------
    Basic usage:
        >>> options = TextileParserOptions()
        >>> parser = TextileParser(options)

    Strict mode:
        >>> options = TextileParserOptions(strict_mode=True)
        >>> parser = TextileParser(options)

    """

    strict_mode: bool = field(
        default=False, metadata={"help": "Raise errors on invalid Textile syntax", "importance": "advanced"}
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle inline HTML: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class TextileRendererOptions(BaseRendererOptions):
    """Configuration options for AST-to-Textile rendering.

    This dataclass contains settings for rendering AST documents as
    Textile markup output.

    Parameters
    ----------
    use_extended_blocks : bool, default True
        Whether to use extended block notation (bc., bq., etc.).
        When True, uses bc. for code blocks and bq. for block quotes.
        When False, uses simpler syntax where possible.
    line_length : int, default 0
        Target line length for wrapping text (0 = no wrapping).
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes
    comment_mode : {"html", "blockquote", "ignore"}, default "html"
        How to render Comment and CommentInline AST nodes:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "blockquote": Render as Textile blockquote (bq.)
        - "ignore": Skip comments entirely

    Examples
    --------
    Basic usage:
        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.textile import TextileRenderer
        >>> from all2md.options.textile import TextileRendererOptions
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = TextileRendererOptions()
        >>> renderer = TextileRenderer(options)
        >>> textile_text = renderer.render_to_string(doc)

    """

    use_extended_blocks: bool = field(
        default=True,
        metadata={
            "help": "Use extended block notation (bc., bq., etc.)",
            "cli_name": "no-extended-blocks",
            "importance": "core",
        },
    )
    line_length: int = field(
        default=0,
        metadata={"help": "Target line length for wrapping (0 = no wrapping)", "type": int, "importance": "core"},
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )
    comment_mode: TextileCommentMode = field(
        default=DEFAULT_TEXTILE_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: html, blockquote, or ignore",
            "choices": ["html", "blockquote", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
