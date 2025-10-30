#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for HTML parsing and rendering.

This module defines options for HTML document conversion with sanitization
and security controls.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ALLOW_REMOTE_SCRIPTS,
    DEFAULT_CONVERT_NBSP,
    DEFAULT_CSP_ENABLED,
    DEFAULT_CSP_POLICY,
    DEFAULT_EXTRACT_TITLE,
    DEFAULT_HTML_BR_HANDLING,
    DEFAULT_HTML_COLLAPSE_WHITESPACE,
    DEFAULT_HTML_COMMENT_MODE,
    DEFAULT_HTML_CONTENT_PLACEHOLDER,
    DEFAULT_HTML_CSS_STYLE,
    DEFAULT_HTML_DETAILS_PARSING,
    DEFAULT_HTML_ESCAPE_HTML,
    DEFAULT_HTML_EXTRACT_MICRODATA,
    DEFAULT_HTML_EXTRACT_READABLE,
    DEFAULT_HTML_FIGURES_PARSING,
    DEFAULT_HTML_INCLUDE_TOC,
    DEFAULT_HTML_INJECTION_MODE,
    DEFAULT_HTML_LANGUAGE,
    DEFAULT_HTML_MATH_RENDERER,
    DEFAULT_HTML_PARSER,
    DEFAULT_HTML_PASSTHROUGH_MODE,
    DEFAULT_HTML_STANDALONE,
    DEFAULT_HTML_STRIP_COMMENTS,
    DEFAULT_HTML_SYNTAX_HIGHLIGHTING,
    DEFAULT_HTML_TEMPLATE_SELECTOR,
    DEFAULT_STRIP_DANGEROUS_ELEMENTS,
    DEFAULT_STRIP_FRAMEWORK_ATTRIBUTES,
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
    HTML_PASSTHROUGH_MODES,
    BrHandling,
    CssStyle,
    DetailsParsing,
    FiguresParsing,
    HtmlCommentMode,
    HtmlParser,
    HtmlPassthroughMode,
    InjectionMode,
    MathRenderer,
    TemplateMode,
)
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import AttachmentOptionsMixin, LocalFileAccessOptions, NetworkFetchOptions


# src/all2md/options/html.py
@dataclass(frozen=True)
class HtmlRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to HTML format.

    This dataclass contains settings specific to HTML generation,
    including document structure, styling, templating, and feature toggles.

    Parameters
    ----------
    standalone : bool, default True
        Generate complete HTML document with <html>, <head>, <body> tags.
        If False, generates only the content fragment.
        Ignored when template_mode is not None.
    css_style : {"inline", "embedded", "external", "none"}, default "embedded"
        How to include CSS styles:
        - "inline": Add style attributes to elements
        - "embedded": Include <style> block in <head>
        - "external": Reference external CSS file
        - "none": No styling
    css_file : str or None, default None
        Path to external CSS file (used when css_style="external").
    include_toc : bool, default False
        Generate table of contents from headings.
    syntax_highlighting : bool, default True
        Add language classes to code blocks for syntax highlighting.
    escape_html : bool, default True
        Escape HTML special characters in text content.
    math_renderer : {"mathjax", "katex", "none"}, default "mathjax"
        Math rendering library to use for MathML/LaTeX math:
        - "mathjax": Include MathJax CDN script
        - "katex": Include KaTeX CDN script
        - "none": Render math as plain text
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "pass-through"
        How to handle HTMLBlock and HTMLInline nodes:
        - "pass-through": Pass through unchanged (use only with trusted content)
        - "escape": HTML-escape the content
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
    language : str, default "en"
        Document language code (ISO 639-1) for the <html lang="..."> attribute.
        Can be overridden by document metadata.
    template_mode : {"inject", "replace", "jinja"} or None, default None
        Template mode for rendering HTML:
        - None: Use standalone mode (default behavior)
        - "inject": Inject content into existing HTML file at selector
        - "replace": Replace placeholders in template file
        - "jinja": Use Jinja2 template engine with full context
        When set, standalone is ignored.
    template_file : str or None, default None
        Path to template file (required when template_mode is not None).
    template_selector : str, default "#content"
        CSS selector for injection target (used with template_mode="inject").
    toc_selector : str or None, default None
        CSS selector for separate TOC injection point (used with template_mode="inject").
        If not set, TOC is included with content at template_selector.
        Allows placing TOC in a different location like a sidebar or header.
    injection_mode : {"append", "prepend", "replace"}, default "replace"
        How to inject content at selector (used with template_mode="inject"):
        - "append": Add content after existing content
        - "prepend": Add content before existing content
        - "replace": Replace existing content
    content_placeholder : str, default "{CONTENT}"
        Placeholder string to replace with content (used with template_mode="replace").
    css_class_map : dict[str, str | list[str]] or None, default None
        Map AST node type names to custom CSS classes.
        Example: {"Heading": "article-heading", "CodeBlock": ["code", "highlight"]}
    allow_remote_scripts : bool, default False
        Allow loading remote scripts (e.g., MathJax/KaTeX from CDN).
        Default is False for security - requires explicit opt-in for CDN usage.
        When False and math_renderer != 'none', will raise a warning.
    csp_enabled : bool, default False
        Add Content-Security-Policy meta tag to standalone HTML documents.
        Helps prevent XSS attacks by restricting resource loading.
    csp_policy : str or None, default (secure policy)
        Custom Content-Security-Policy header value.
        If None, uses default: "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"
    comment_mode : {"native", "visible", "ignore"}, default "native"
        How to render Comment and CommentInline AST nodes:
        - "native": Render as HTML comments (<!-- Comment by Author: text -->)
        - "visible": Render as visible <div>/<span> elements with class="comment" and metadata in data attributes
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from DOCX reviewer comments, source HTML comments,
        and other format-specific annotations.

    Examples
    --------
    Inject into existing HTML:
        >>> options = HtmlRendererOptions(
        ...     template_mode="inject",
        ...     template_file="layout.html",
        ...     template_selector="#main-content"
        ... )

    Replace placeholders:
        >>> options = HtmlRendererOptions(
        ...     template_mode="replace",
        ...     template_file="template.html",
        ...     content_placeholder="{CONTENT}"
        ... )

    Use Jinja2 template:
        >>> options = HtmlRendererOptions(
        ...     template_mode="jinja",
        ...     template_file="article.html"
        ... )

    Custom CSS classes:
        >>> options = HtmlRendererOptions(
        ...     css_class_map={"Heading": "prose-heading", "CodeBlock": "code-block"}
        ... )

    """

    standalone: bool = field(
        default=DEFAULT_HTML_STANDALONE,
        metadata={
            "help": "Generate complete HTML document (vs content fragment)",
            "cli_name": "no-standalone",
            "importance": "core",
        },
    )
    css_style: CssStyle = field(
        default=DEFAULT_HTML_CSS_STYLE,
        metadata={
            "help": "CSS inclusion method: inline, embedded, external, or none",
            "choices": ["inline", "embedded", "external", "none"],
            "importance": "core",
        },
    )
    css_file: str | None = field(
        default=None,
        metadata={"help": "Path to external CSS file (when css_style='external')", "importance": "advanced"},
    )
    include_toc: bool = field(
        default=DEFAULT_HTML_INCLUDE_TOC,
        metadata={"help": "Generate table of contents from headings", "importance": "core"},
    )
    syntax_highlighting: bool = field(
        default=DEFAULT_HTML_SYNTAX_HIGHLIGHTING,
        metadata={
            "help": "Add language classes for syntax highlighting",
            "cli_name": "no-syntax-highlighting",
            "importance": "core",
        },
    )
    escape_html: bool = field(
        default=DEFAULT_HTML_ESCAPE_HTML,
        metadata={
            "help": "Escape HTML special characters in text",
            "cli_name": "no-escape-html",
            "importance": "security",
        },
    )
    math_renderer: MathRenderer = field(
        default=DEFAULT_HTML_MATH_RENDERER,
        metadata={
            "help": "Math rendering library: mathjax, katex, or none",
            "choices": ["mathjax", "katex", "none"],
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
    language: str = field(
        default=DEFAULT_HTML_LANGUAGE,
        metadata={"help": "Document language code (ISO 639-1) for HTML lang attribute", "importance": "advanced"},
    )
    template_mode: TemplateMode | None = field(
        default=None,
        metadata={
            "help": "Template mode: inject, replace, jinja, or none",
            "choices": ["inject", "replace", "jinja"],
            "importance": "advanced",
        },
    )
    template_file: str | None = field(
        default=None,
        metadata={"help": "Path to template file (required when template_mode is set)", "importance": "advanced"},
    )
    template_selector: str = field(
        default=DEFAULT_HTML_TEMPLATE_SELECTOR,
        metadata={"help": "CSS selector for injection target (template_mode='inject')", "importance": "advanced"},
    )
    toc_selector: str | None = field(
        default=None,
        metadata={
            "help": "CSS selector for separate TOC injection point (template_mode='inject'). "
            "If not set, TOC is included with content at template_selector.",
            "importance": "advanced",
        },
    )
    injection_mode: InjectionMode = field(
        default=DEFAULT_HTML_INJECTION_MODE,
        metadata={
            "help": "How to inject content: append, prepend, or replace",
            "choices": ["append", "prepend", "replace"],
            "importance": "advanced",
        },
    )
    content_placeholder: str = field(
        default=DEFAULT_HTML_CONTENT_PLACEHOLDER,
        metadata={"help": "Placeholder to replace with content (template_mode='replace')", "importance": "advanced"},
    )
    css_class_map: dict[str, str | list[str]] | None = field(
        default=None,
        metadata={
            "help": 'Map AST node types to custom CSS classes as JSON (e.g., \'{"Heading": "prose-heading"}\')',
            "importance": "advanced",
        },
    )
    allow_remote_scripts: bool = field(
        default=DEFAULT_ALLOW_REMOTE_SCRIPTS,
        metadata={
            "help": "Allow loading remote scripts (e.g., MathJax/KaTeX CDN). "
            "Default is False for security - opt-in required for CDN usage.",
            "importance": "security",
        },
    )
    csp_enabled: bool = field(
        default=DEFAULT_CSP_ENABLED,
        metadata={
            "help": "Add Content-Security-Policy meta tag to standalone HTML documents",
            "importance": "security",
        },
    )
    csp_policy: str | None = field(
        default=DEFAULT_CSP_POLICY,
        metadata={
            "help": "Custom Content-Security-Policy header value. " "If None, uses default secure policy.",
            "importance": "security",
        },
    )
    comment_mode: HtmlCommentMode = field(
        default=DEFAULT_HTML_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "native (HTML comments <!-- -->), visible (visible <div>/<span> elements), "
            "ignore (skip comment nodes entirely). Controls presentation of comments "
            "from DOCX, HTML parsers, and other formats with annotations.",
            "choices": ["native", "visible", "ignore"],
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate dependent field constraints.

        Raises
        ------
        ValueError
            If dependent field constraints are violated.

        """
        # Call parent validation
        super().__post_init__()

        # Validate that template_mode requires template_file
        if self.template_mode is not None and self.template_file is None:
            raise ValueError(f"template_mode='{self.template_mode}' requires template_file to be set")

        # Validate that external CSS requires css_file
        if self.css_style == "external" and self.css_file is None:
            raise ValueError("css_style='external' requires css_file to be set")


@dataclass(frozen=True)
class HtmlOptions(BaseParserOptions, AttachmentOptionsMixin):
    """Configuration options for HTML-to-Markdown conversion.

    This dataclass contains settings specific to HTML document processing,
    including heading styles, title extraction, image handling, content
    sanitization, and advanced formatting options. Inherits attachment
    handling from AttachmentOptionsMixin for images and embedded media.

    Parameters
    ----------
    extract_title : bool, default False
        Whether to extract and use the HTML <title> element.
    convert_nbsp : bool, default False
        Whether to convert non-breaking spaces (&nbsp;) to regular spaces in the output.
    strip_dangerous_elements : bool, default False
        Whether to remove potentially dangerous HTML elements (script, style, etc.) and
        event handler attributes (onclick, onload, etc.).
    strip_framework_attributes : bool, default False
        Whether to remove JavaScript framework attributes (Alpine.js x-*, Vue.js v-*,
        Angular ng-*, HTMX hx-*, etc.) that can execute code in framework contexts.
        Only needed if output HTML will be rendered in browsers with these frameworks.
    detect_table_alignment : bool, default True
        Whether to automatically detect table column alignment from CSS/attributes.
    preserve_nested_structure : bool, default True
        Whether to maintain proper nesting for blockquotes and other elements.
    allowed_attributes : tuple[str, ...] | dict[str, tuple[str, ...]] | None, default None
        Whitelist of allowed HTML attributes. Supports two modes:
        - Global allowlist: tuple of attribute names applied to all elements
        - Per-element allowlist: dict mapping element names to tuples of allowed attributes
        Note: When using CLI, pass complex dict structures as JSON strings for proper parsing.
    base_url : str or None, default None
        Base URL for resolving relative hrefs in <a> tags. This is separate from
        attachment_base_url (used for images/assets). Allows precise control over
        navigational link URLs vs. resource URLs.

    Examples
    --------
    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True)

    Convert with content sanitization:
        >>> options = HtmlOptions(strip_dangerous_elements=True, convert_nbsp=True)

    Use global attribute allowlist:
        >>> options = HtmlOptions(allowed_attributes=('class', 'id', 'href', 'src'))

    Use per-element attribute allowlist:
        >>> options = HtmlOptions(allowed_attributes={
        ...     'img': ('src', 'alt', 'title'),
        ...     'a': ('href', 'title'),
        ...     'div': ('class', 'id')
        ... })

    Extract only the readable article content:
        >>> options = HtmlOptions(extract_readable=True)

    """

    extract_title: bool = field(
        default=DEFAULT_EXTRACT_TITLE,
        metadata={"help": "Extract and use HTML <title> element as main heading", "importance": "core"},
    )
    convert_nbsp: bool = field(
        default=DEFAULT_CONVERT_NBSP,
        metadata={"help": "Convert non-breaking spaces (&nbsp;) to regular spaces", "importance": "core"},
    )
    strip_dangerous_elements: bool = field(
        default=DEFAULT_STRIP_DANGEROUS_ELEMENTS,
        metadata={"help": "Remove potentially dangerous HTML elements (script, style, etc.)", "importance": "security"},
    )
    strip_framework_attributes: bool = field(
        default=DEFAULT_STRIP_FRAMEWORK_ATTRIBUTES,
        metadata={
            "help": "Remove JavaScript framework attributes (x-*, v-*, ng-*, hx-*, etc.) "
            "that can execute code in framework contexts. "
            "Only needed if output HTML will be rendered in browsers with these frameworks installed.",
            "importance": "security",
        },
    )
    detect_table_alignment: bool = field(
        default=DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
        metadata={
            "help": "Automatically detect table column alignment from CSS/attributes",
            "cli_name": "no-detect-table-alignment",  # default=True, use --no-*
            "importance": "advanced",
        },
    )

    # Network security options
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote resource fetching",
            "cli_flatten": True,  # Nested, handled separately
        },
    )

    # Local file access options
    local_files: LocalFileAccessOptions = field(
        default_factory=LocalFileAccessOptions,
        metadata={"help": "Local file access security settings", "cli_flatten": True},  # Nested, handled separately
    )

    # preserve_nested_structure: bool = field(
    #     default=DEFAULT_PRESERVE_NESTED_STRUCTURE,
    #     metadata={
    #         "help": "Maintain proper nesting for blockquotes and other elements",
    #         "cli_name": "no-preserve-nested-structure",  # default=True, use --no-*
    #         "importance": "advanced",
    #     },
    # )

    # Advanced HTML processing options
    strip_comments: bool = field(
        default=DEFAULT_HTML_STRIP_COMMENTS,
        metadata={
            "help": "Remove HTML comments from output",
            "cli_name": "no-strip-comments",
            "importance": "advanced",
        },
    )
    collapse_whitespace: bool = field(
        default=DEFAULT_HTML_COLLAPSE_WHITESPACE,
        metadata={
            "help": "Collapse multiple spaces/newlines into single spaces",
            "cli_name": "no-collapse-whitespace",
            "importance": "advanced",
        },
    )
    extract_readable: bool = field(
        default=DEFAULT_HTML_EXTRACT_READABLE,
        metadata={
            "help": "Extract main article content by stripping navigation and other non-readable content "
            "using readability-lxml",
            "importance": "advanced",
        },
    )
    br_handling: BrHandling = field(
        default=DEFAULT_HTML_BR_HANDLING,
        metadata={
            "help": "How to handle <br> tags: 'newline' or 'space'",
            "choices": ["newline", "space"],
            "importance": "advanced",
        },
    )
    allowed_elements: tuple[str, ...] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML elements (if set, only these are processed)",
            "action": "append",
            "importance": "security",
        },
    )
    allowed_attributes: tuple[str, ...] | dict[str, tuple[str, ...]] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML attributes. Can be a tuple of attribute names "
            "(global allowlist) or a dict mapping element names to tuples of allowed "
            "attributes (per-element allowlist). Examples: ('class', 'id') or "
            "{'img': ('src', 'alt', 'title'), 'a': ('href', 'title')}. "
            "CLI note: For complex dict structures, pass as JSON string: "
            '--allowed-attributes \'{"img": ["src", "alt"], "a": ["href"]}\'',
            "action": "append",
            "importance": "security",
        },
    )
    figures_parsing: FiguresParsing = field(
        default=DEFAULT_HTML_FIGURES_PARSING,
        metadata={
            "help": (
                "How to parse <figure> elements: blockquote, paragraph, image_with_caption, " "caption_only, html, skip"
            ),
            "choices": ["blockquote", "paragraph", "image_with_caption", "caption_only", "html", "skip"],
            "importance": "advanced",
        },
    )
    details_parsing: DetailsParsing = field(
        default=DEFAULT_HTML_DETAILS_PARSING,
        metadata={
            "help": "How to render <details>/<summary> elements: blockquote, html, skip",
            "choices": ["blockquote", "html", "skip"],
            "importance": "advanced",
        },
    )
    extract_microdata: bool = field(
        default=DEFAULT_HTML_EXTRACT_MICRODATA,
        metadata={
            "help": "Extract microdata and structured data to metadata",
            "cli_name": "no-extract-microdata",
            "importance": "advanced",
        },
    )
    base_url: str | None = field(
        default=None,
        metadata={
            "help": "Base URL for resolving relative hrefs in <a> tags (separate from attachment_base_url for images)",
            "importance": "advanced",
        },
    )
    html_parser: HtmlParser = field(
        default=DEFAULT_HTML_PARSER,
        metadata={
            "help": (
                "BeautifulSoup parser to use: 'html.parser' (built-in, fast, may differ from browsers), "
                "'html5lib' (standards-compliant, slower, matches browser behavior), "
                "'lxml' (fast, requires C library). "
                "For security-critical applications, consider 'html5lib' for more consistent parsing."
            ),
            "choices": ["html.parser", "html5lib", "lxml"],
            "importance": "advanced",
        },
    )
