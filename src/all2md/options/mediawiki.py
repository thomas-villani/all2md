#  Copyright (c) 2025 Tom Villani, Ph.D.
# all2md/options/mediawiki.py
"""Configuration options for MediaWiki rendering.

This module defines options for rendering AST to MediaWiki format.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_MEDIAWIKI_IMAGE_THUMB,
    DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED,
    HtmlPassthroughMode,
)
from all2md.options.base import BaseRendererOptions


@dataclass(frozen=True)
class MediaWikiOptions(BaseRendererOptions):
    """Configuration options for MediaWiki rendering.

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
        When True, images use |thumb option in MediaWiki syntax.
        When False, images are rendered at full size.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)

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
        }
    )
    image_thumb: bool = field(
        default=DEFAULT_MEDIAWIKI_IMAGE_THUMB,
        metadata={
            "help": "Render images as thumbnails",
            "cli_name": "no-image-thumb",
        }
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default="pass-through",
        metadata={
            "help": "How to handle raw HTML content: pass-through, escape, drop, or sanitize",
            "choices": ["pass-through", "escape", "drop", "sanitize"]
        }
    )
