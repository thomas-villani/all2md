#  Copyright (c) 2025 Tom Villani, Ph.D.
# all2md/options/mediawiki.py
"""Configuration options for MediaWiki rendering.

This module defines options for rendering AST to MediaWiki format.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_HTML_PASSTHROUGH_MODE,
    DEFAULT_MEDIAWIKI_COMMENT_MODE,
    DEFAULT_MEDIAWIKI_IMAGE_CAPTION_MODE,
    DEFAULT_MEDIAWIKI_IMAGE_THUMB,
    DEFAULT_MEDIAWIKI_PARSE_TAGS,
    DEFAULT_MEDIAWIKI_PARSE_TEMPLATES,
    DEFAULT_MEDIAWIKI_STRIP_COMMENTS,
    DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED,
    HTML_PASSTHROUGH_MODES,
    HtmlPassthroughMode,
    MediaWikiCommentMode,
    MediaWikiImageCaptionMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class MediaWikiOptions(BaseRendererOptions):
    r"""Configuration options for MediaWiki rendering.

    This dataclass contains settings for rendering AST documents as
    MediaWiki markup, suitable for Wikipedia and other MediaWiki-based wikis.

    Parameters
    ----------
    use_html_for_unsupported : bool, default True
        Whether to use HTML tags as fallback for unsupported elements.
        When True, unsupported formatting uses HTML tags (e.g., <u>underline</u>).
        When False, unsupported formatting is stripped.
    image_thumb : bool, default True
        Whether to render images as thumbnails.
        When True, images use \|thumb option in MediaWiki syntax.
        When False, images are rendered at full size.
    image_caption_mode : {"auto", "alt_only", "caption_only"}, default "alt_only"
        How to render image captions when image_thumb is True:
        - "auto": Use alt_text as caption, with alt attribute when available
        - "alt_only": Only render alt attribute, no caption text (default, backward compatible)
        - "caption_only": Only render caption text, no alt attribute
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    comment_mode : {"html", "visible", "ignore"}, default "html"
        How to render Comment and CommentInline AST nodes:
        - "html": Use HTML comment syntax <!-- --> (default)
        - "visible": Render as visible text
        - "ignore": Skip comments entirely

    Examples
    --------
    Basic MediaWiki rendering:
        >>> from all2md.ast import Document, Heading, Text
        >>> from all2md.renderers.mediawiki import MediaWikiRenderer
        >>> from all2md.options.mediawiki import MediaWikiOptions
        >>> doc = Document(children=[
        ...     Heading(level=1, content=[Text(content="Title")])
        ... ])
        >>> options = MediaWikiOptions()
        >>> renderer = MediaWikiRenderer(options)
        >>> wiki_text = renderer.render_to_string(doc)

    """

    use_html_for_unsupported: bool = field(
        default=DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED,
        metadata={
            "help": "Use HTML tags for unsupported elements",
            "cli_name": "no-use-html-for-unsupported",
            "importance": "core",
        },
    )
    image_thumb: bool = field(
        default=DEFAULT_MEDIAWIKI_IMAGE_THUMB,
        metadata={"help": "Render images as thumbnails", "cli_name": "no-image-thumb", "importance": "core"},
    )
    image_caption_mode: MediaWikiImageCaptionMode = field(
        default=DEFAULT_MEDIAWIKI_IMAGE_CAPTION_MODE,
        metadata={
            "help": "How to render image captions: auto (use alt_text as caption), alt_only, caption_only",
            "choices": ["auto", "alt_only", "caption_only"],
            "importance": "core",
        },
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )
    comment_mode: MediaWikiCommentMode = field(
        default=DEFAULT_MEDIAWIKI_COMMENT_MODE,
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
class MediaWikiParserOptions(BaseParserOptions):
    """Configuration options for MediaWiki-to-AST parsing.

    This dataclass contains settings specific to parsing MediaWiki/WikiText documents
    into AST representation using mwparserfromhell.

    Parameters
    ----------
    parse_templates : bool, default False
        Whether to parse templates or strip them entirely.
        When True, templates are converted to HTMLInline nodes.
        When False, templates are completely removed from the output.
    parse_tags : bool, default True
        Whether to parse parser tags (e.g., <ref>, <nowiki>).
        When True, tags are processed and included in the AST.
        When False, tags are stripped from the output.
    strip_comments : bool, default True
        Whether to strip HTML comments from the output.
        When True, comments are removed completely.
        When False, comments are preserved as HTMLInline nodes.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
        How to handle inline HTML in WikiText:
        - "pass-through": Preserve HTML unchanged (use only with trusted content)
        - "escape": HTML-escape the content to display as text
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes

    Examples
    --------
    Basic usage:
        >>> options = MediaWikiParserOptions()
        >>> parser = MediaWikiParser(options)

    Parse templates as HTML:
        >>> options = MediaWikiParserOptions(parse_templates=True)
        >>> parser = MediaWikiParser(options)

    """

    parse_templates: bool = field(
        default=DEFAULT_MEDIAWIKI_PARSE_TEMPLATES,
        metadata={
            "help": "Parse templates or strip them",
            "cli_name": "parse-templates",
            "importance": "core",
        },
    )
    parse_tags: bool = field(
        default=DEFAULT_MEDIAWIKI_PARSE_TAGS,
        metadata={
            "help": "Parse parser tags (e.g., <ref>, <nowiki>)",
            "cli_name": "no-parse-tags",
            "importance": "core",
        },
    )
    strip_comments: bool = field(
        default=DEFAULT_MEDIAWIKI_STRIP_COMMENTS,
        metadata={
            "help": "Strip HTML comments from output",
            "cli_name": "no-strip-comments",
            "importance": "core",
        },
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle inline HTML: pass-through, escape, drop, or sanitize",
            "choices": ["pass-through", "escape", "drop", "sanitize"],
            "importance": "security",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()
