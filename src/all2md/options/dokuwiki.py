#  Copyright (c) 2025 Tom Villani, Ph.D.
# all2md/options/dokuwiki.py
"""Configuration options for DokuWiki parsing and rendering.

This module defines options for parsing DokuWiki markup to AST and
rendering AST to DokuWiki format.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_DOKUWIKI_COMMENT_MODE,
    DEFAULT_DOKUWIKI_MONOSPACE_FENCE,
    DEFAULT_DOKUWIKI_PARSE_INTERWIKI,
    DEFAULT_DOKUWIKI_PARSE_PLUGINS,
    DEFAULT_DOKUWIKI_RENDERER_HTML_PASSTHROUGH_MODE,
    DEFAULT_DOKUWIKI_STRIP_COMMENTS,
    DEFAULT_DOKUWIKI_USE_HTML_FOR_UNSUPPORTED,
    DEFAULT_HTML_PASSTHROUGH_MODE,
    HTML_PASSTHROUGH_MODES,
    DokuWikiCommentMode,
    HtmlPassthroughMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class DokuWikiOptions(BaseRendererOptions):
    """Configuration options for DokuWiki rendering.

    This dataclass contains settings for rendering AST documents as
    DokuWiki markup, suitable for DokuWiki-based wikis.

    Parameters
    ----------
    use_html_for_unsupported : bool, default True
        Whether to use HTML tags as fallback for unsupported elements.
        When True, unsupported formatting uses HTML tags (e.g., ``<del>strikethrough</del>``).
        When False, unsupported formatting is stripped.
    monospace_fence : bool, default False
        Whether to use fence syntax for monospace text.
        When True, inline code uses ``<code>text</code>``.
        When False, inline code uses double single quotes (DokuWiki native).
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    comment_mode : {"html", "visible", "ignore"}, default "html"
        How to render Comment and CommentInline AST nodes:
        - "html": Use HTML/C-style comments (default)
        - "visible": Render as visible text
        - "ignore": Skip comments entirely

    Examples
    --------
    Basic DokuWiki rendering:
        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.dokuwiki import DokuWikiRenderer
        >>> from all2md.options.dokuwiki import DokuWikiOptions
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = DokuWikiOptions()
        >>> renderer = DokuWikiRenderer(options)
        >>> wiki_text = renderer.render_to_string(doc)

    """

    use_html_for_unsupported: bool = field(
        default=DEFAULT_DOKUWIKI_USE_HTML_FOR_UNSUPPORTED,
        metadata={
            "help": "Use HTML tags for unsupported elements",
            "cli_name": "no-use-html-for-unsupported",
            "importance": "core",
        },
    )
    monospace_fence: bool = field(
        default=DEFAULT_DOKUWIKI_MONOSPACE_FENCE,
        metadata={
            "help": "Use <code> tags instead of '' for inline code",
            "cli_name": "monospace-fence",
            "importance": "core",
        },
    )

    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_DOKUWIKI_RENDERER_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )
    comment_mode: DokuWikiCommentMode = field(
        default=DEFAULT_DOKUWIKI_COMMENT_MODE,
        metadata={
            "help": "Comment rendering mode: html, visible, or ignore",
            "choices": ["html", "visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class DokuWikiParserOptions(BaseParserOptions):
    """Configuration options for DokuWiki-to-AST parsing.

    This dataclass contains settings specific to parsing DokuWiki markup documents
    into AST representation using custom regex-based parsing.

    Parameters
    ----------
    parse_plugins : bool, default False
        Whether to parse plugin syntax (e.g., ``<WRAP>``, ``<button>``) or strip them.
        When True, plugin tags are converted to HTMLInline/HTMLBlock nodes.
        When False, plugin tags are completely removed from the output.
    strip_comments : bool, default True
        Whether to strip comments from the output.
        Strips both C-style (``/* ... */``) and HTML (``<!-- ... -->``) comments.
        When True, comments are removed completely.
        When False, comments are preserved as HTMLInline nodes.
    parse_interwiki : bool, default True
        Whether to parse interwiki links (e.g., ``[[wp>Article]]``).
        When True, interwiki links are preserved in Link nodes.
        When False, interwiki syntax is treated as regular internal links.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
        How to handle inline HTML in DokuWiki markup:
        - "pass-through": Preserve HTML unchanged (use only with trusted content)
        - "escape": HTML-escape the content to display as text
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes

    Examples
    --------
    Basic usage:
        >>> options = DokuWikiParserOptions()
        >>> parser = DokuWikiParser(options)

    Parse plugin syntax as HTML:
        >>> options = DokuWikiParserOptions(parse_plugins=True)
        >>> parser = DokuWikiParser(options)

    """

    parse_plugins: bool = field(
        default=DEFAULT_DOKUWIKI_PARSE_PLUGINS,
        metadata={
            "help": "Parse plugin syntax (e.g., <WRAP>) or strip them",
            "cli_name": "parse-plugins",
            "importance": "core",
        },
    )
    strip_comments: bool = field(
        default=DEFAULT_DOKUWIKI_STRIP_COMMENTS,
        metadata={
            "help": "Strip comments from output",
            "cli_name": "no-strip-comments",
            "importance": "core",
        },
    )
    parse_interwiki: bool = field(
        default=DEFAULT_DOKUWIKI_PARSE_INTERWIKI,
        metadata={
            "help": "Parse interwiki links (e.g., [[wp>Article]])",
            "cli_name": "no-parse-interwiki",
            "importance": "core",
        },
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
