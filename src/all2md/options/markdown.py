#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options for Markdown parsing and rendering.

This module defines options for Markdown conversion with flavor support.
"""
# src/all2md/options/markdown.py


from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from all2md.constants import (
    DEFAULT_AUTOLINK_BARE_URLS,
    DEFAULT_BULLET_SYMBOLS,
    DEFAULT_CODE_FENCE_CHAR,
    DEFAULT_CODE_FENCE_MIN,
    DEFAULT_COLLAPSE_BLANK_LINES,
    DEFAULT_COMMENT_MODE,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_FLAVOR,
    DEFAULT_HEADING_LEVEL_OFFSET,
    DEFAULT_INCLUDE_METADATA_FRONTMATTER,
    DEFAULT_LINK_STYLE,
    DEFAULT_LIST_INDENT_WIDTH,
    DEFAULT_MARKDOWN_HTML_PASSTHROUGH_MODE,
    DEFAULT_MATH_MODE,
    DEFAULT_METADATA_FORMAT,
    DEFAULT_REFERENCE_LINK_PLACEMENT,
    DEFAULT_TABLE_PIPE_ESCAPE,
    DEFAULT_USE_HASH_HEADINGS,
    HTML_PASSTHROUGH_MODES,
    CodeFenceChar,
    CommentMode,
    EmphasisSymbol,
    FlavorType,
    HtmlPassthroughMode,
    LinkStyleType,
    MathMode,
    MetadataFormatType,
    ReferenceLinkPlacement,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,
    UnsupportedInlineMode,
    UnsupportedTableMode,
)
from all2md.options.base import UNSET, BaseParserOptions, BaseRendererOptions


@dataclass(frozen=True)
class MarkdownParserOptions(BaseParserOptions):
    """Configuration options for Markdown-to-AST parsing.

    This dataclass contains settings specific to parsing Markdown documents
    into AST representation, supporting various Markdown flavors and extensions.

    Parameters
    ----------
    flavor : {"gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"}, default "gfm"
        Markdown flavor to parse. Determines which extensions are enabled.
    parse_tables : bool, default True
        Whether to parse table syntax (GFM pipe tables).
    parse_footnotes : bool, default True
        Whether to parse footnote references and definitions.
    parse_math : bool, default True
        Whether to parse inline ($...$) and block ($$...$$) math.
    parse_task_lists : bool, default True
        Whether to parse task list checkboxes (- [ ] and - [x]).
    parse_definition_lists : bool, default True
        Whether to parse definition lists (term : definition).
    parse_strikethrough : bool, default True
        Whether to parse strikethrough syntax (~~text~~).

    """

    flavor: FlavorType = field(
        default=DEFAULT_FLAVOR,
        metadata={
            "help": "Markdown flavor to parse (determines enabled extensions)",
            "choices": ["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"],
            "importance": "core",
        },
    )
    parse_tables: bool = field(
        default=True,
        metadata={"help": "Parse table syntax (GFM pipe tables)", "cli_name": "no-parse-tables", "importance": "core"},
    )
    parse_footnotes: bool = field(
        default=True,
        metadata={
            "help": "Parse footnote references and definitions",
            "cli_name": "no-parse-footnotes",
            "importance": "core",
        },
    )
    parse_math: bool = field(
        default=True,
        metadata={
            "help": "Parse inline and block math ($...$ and $$...$$)",
            "cli_name": "no-parse-math",
            "importance": "core",
        },
    )
    parse_task_lists: bool = field(
        default=True,
        metadata={
            "help": "Parse task list checkboxes (- [ ] and - [x])",
            "cli_name": "no-parse-task-lists",
            "importance": "core",
        },
    )
    parse_definition_lists: bool = field(
        default=True,
        metadata={
            "help": "Parse definition lists (term : definition)",
            "cli_name": "no-parse-definition-lists",
            "importance": "core",
        },
    )
    parse_strikethrough: bool = field(
        default=True,
        metadata={
            "help": "Parse strikethrough syntax (~~text~~)",
            "cli_name": "no-parse-strikethrough",
            "importance": "core",
        },
    )
    parse_frontmatter: bool = field(
        default=True,
        metadata={
            "help": "Parse YAML/TOML/JSON frontmatter at document start",
            "cli_name": "no-parse-frontmatter",
            "importance": "core",
        },
    )

    def __post_init__(self) -> None:
        """Validate options by calling parent validation."""
        super().__post_init__()


@dataclass(frozen=True)
class MarkdownRendererOptions(BaseRendererOptions):
    r"""Markdown rendering options for converting AST to Markdown text.

    When a flavor is specified, default values for unsupported_table_mode and
    unsupported_inline_mode are automatically set to flavor-appropriate values
    unless explicitly overridden. This is handled via the __new__ method to
    apply flavor-aware defaults before instance creation.

    This dataclass contains settings that control how Markdown output is
    formatted and structured. These options are used by multiple conversion
    modules to ensure consistent Markdown generation.

    Parameters
    ----------
    escape_special : bool, default True
        Whether to escape special Markdown characters in text content.
        When True, characters like \*, \_, #, [, ], (, ), \\ are escaped
        to prevent unintended formatting.
    emphasis_symbol : {"\*", "\_"}, default "\*"
        Symbol to use for emphasis/italic formatting in Markdown.
    bullet_symbols : str, default "\*-+"
        Characters to cycle through for nested bullet lists.
    list_indent_width : int, default 4
        Number of spaces to use for each level of list indentation.
    underline_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle underlined text:
        - "html": Use <u>text</u> tags
        - "markdown": Use __text__ (non-standard)
        - "ignore": Strip underline formatting
    superscript_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle superscript text:
        - "html": Use <sup>text</sup> tags
        - "markdown": Use ^text^ (non-standard)
        - "ignore": Strip superscript formatting
    subscript_mode : {"html", "markdown", "ignore"}, default "html"
        How to handle subscript text:
        - "html": Use <sub>text</sub> tags
        - "markdown": Use ~text~ (non-standard)
        - "ignore": Strip subscript formatting
    use_hash_headings : bool, default True
        Whether to use # syntax for headings instead of underline style.
        When True, generates "# Heading" style. When False, generates
        "Heading\n=======" style for level 1 and "Heading\n-------" for levels 2+.
    flavor : {"gfm", "commonmark", "markdown_plus"}, default "gfm"
        Markdown flavor/dialect to use for output:
        - "gfm": GitHub Flavored Markdown (tables, strikethrough, task lists)
        - "commonmark": Strict CommonMark specification
        - "markdown_plus": All extensions enabled (footnotes, definition lists, etc.)
    unsupported_table_mode : {"drop", "ascii", "force", "html"}, default "force"
        How to handle tables when the selected flavor doesn't support them:
        - "drop": Skip table entirely
        - "ascii": Render as ASCII art table
        - "force": Render as pipe table anyway (may not be valid for flavor)
        - "html": Render as HTML <table>
    unsupported_inline_mode : {"plain", "force", "html"}, default "plain"
        How to handle inline elements unsupported by the selected flavor:
        - "plain": Render content without the unsupported formatting
        - "force": Use markdown syntax anyway (may not be valid for flavor)
        - "html": Use HTML tags (e.g., <u> for underline)
    heading_level_offset : int, default 0
        Shift all heading levels by this amount (positive or negative).
        Useful when collating multiple documents into a parent document with existing structure.
    code_fence_char : {"`", "~"}, default "`"
        Character to use for code fences (backtick or tilde).
    code_fence_min : int, default 3
        Minimum length for code fences (typically 3).
    collapse_blank_lines : bool, default True
        Collapse multiple consecutive blank lines into at most 2 (normalizing whitespace).
    link_style : {"inline", "reference"}, default "inline"
        Link style to use:
        - "inline": [text](url) style links
        - "reference": [text][ref] style with reference definitions at end
    reference_link_placement : {"end_of_document", "after_block"}, default "end_of_document"
        Where to place reference link definitions when using reference-style links:
        - "end_of_document": All reference definitions at document end (current behavior)
        - "after_block": Reference definitions placed after each block-level element
    autolink_bare_urls : bool, default False
        Automatically convert bare URLs (e.g., http://example.com) found in Text nodes
        into Markdown autolinks (<http://example.com>). Ensures all URLs are clickable.
    table_pipe_escape : bool, default True
        Whether to escape pipe characters (|) in table cell content.
    math_mode : {"latex", "mathml", "html"}, default "latex"
        Preferred math representation for flavors that support math. When the
        requested representation is unavailable on a node, the renderer falls
        back to any available representation while preserving flavor
        constraints.
    html_passthrough_mode : {"pass-through", "escape", "drop", "sanitize"}, default "escape"
        How to handle raw HTML content in markdown (HTMLBlock and HTMLInline nodes):
        - "pass-through": Pass HTML through unchanged (use only with trusted content)
        - "escape": HTML-escape the content to show as text (secure default)
        - "drop": Remove HTML content entirely
        - "sanitize": Remove dangerous elements/attributes (requires bleach for best results)
        Note: This does not affect fenced code blocks with language="html", which are
        always rendered as code and are already safe.
    comment_mode : {"html", "blockquote", "ignore"}, default "blockquote"
        How to render Comment and CommentInline AST nodes:
        - "html": Render as HTML comments (<!-- Comment text -->)
        - "blockquote": Render as blockquotes with attribution ([Comment by Author: text])
        - "ignore": Skip comment nodes entirely
        This controls presentation of comments from DOCX reviewer comments, HTML comments,
        and other format-specific annotations.

    """

    escape_special: bool = field(
        default=DEFAULT_ESCAPE_SPECIAL,
        metadata={
            "help": "Escape special Markdown characters (e.g. asterisks) in text content",
            "cli_name": "no-escape-special",  # Since default=True, use --no-* flag
            "importance": "core",
        },
    )
    emphasis_symbol: EmphasisSymbol = field(
        default=DEFAULT_EMPHASIS_SYMBOL,  # type: ignore[arg-type]
        metadata={"help": "Symbol to use for emphasis/italic formatting", "choices": ["*", "_"], "importance": "core"},
    )
    bullet_symbols: str = field(
        default=DEFAULT_BULLET_SYMBOLS,
        metadata={"help": "Characters to cycle through for nested bullet lists", "importance": "advanced"},
    )
    list_indent_width: int = field(
        default=DEFAULT_LIST_INDENT_WIDTH,
        metadata={
            "help": "Number of spaces to use for each level of list indentation",
            "type": int,
            "importance": "advanced",
        },
    )
    underline_mode: UnderlineMode = field(
        default="html",
        metadata={
            "help": "How to handle underlined text",
            "choices": ["html", "markdown", "ignore"],
            "importance": "advanced",
        },
    )
    superscript_mode: SuperscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle superscript text",
            "choices": ["html", "markdown", "ignore"],
            "importance": "advanced",
        },
    )
    subscript_mode: SubscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle subscript text",
            "choices": ["html", "markdown", "ignore"],
            "importance": "advanced",
        },
    )
    use_hash_headings: bool = field(
        default=DEFAULT_USE_HASH_HEADINGS,
        metadata={
            "help": "Use # syntax for headings instead of underline style",
            "cli_name": "no-use-hash-headings",  # default=True, use --no-*
            "importance": "core",
        },
    )
    flavor: FlavorType = field(
        default=DEFAULT_FLAVOR,
        metadata={
            "help": "Markdown flavor/dialect to use for output",
            "choices": ["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"],
            "importance": "core",
        },
    )
    strict_flavor_validation: bool = field(
        default=False,
        metadata={
            "help": "Raise errors on flavor-incompatible options instead of just warnings. "
            "When True, validate_flavor_compatibility warnings become ValueError exceptions.",
            "importance": "advanced",
        },
    )
    unsupported_table_mode: UnsupportedTableMode | object = field(
        default=UNSET,
        metadata={
            "help": "How to handle tables when flavor doesn't support them: "
            "drop (skip entirely), ascii (render as ASCII art), "
            "force (render as pipe tables anyway), html (render as HTML table)",
            "choices": ["drop", "ascii", "force", "html"],
            "importance": "advanced",
        },
    )
    unsupported_inline_mode: UnsupportedInlineMode | object = field(
        default=UNSET,
        metadata={
            "help": "How to handle inline elements unsupported by flavor: "
            "plain (render content without formatting), "
            "force (use markdown syntax anyway), html (use HTML tags)",
            "choices": ["plain", "force", "html"],
            "importance": "advanced",
        },
    )
    pad_table_cells: bool = field(
        default=False,
        metadata={"help": "Pad table cells with spaces for visual alignment in source", "importance": "advanced"},
    )
    prefer_setext_headings: bool = field(
        default=False,
        metadata={"help": "Prefer setext-style headings (underlines) for h1 and h2", "importance": "advanced"},
    )
    max_line_width: int | None = field(
        default=None,
        metadata={"help": "Maximum line width for wrapping (None for no limit)", "type": int, "importance": "advanced"},
    )
    table_alignment_default: str = field(
        default="left",
        metadata={
            "help": "Default alignment for table columns without explicit alignment",
            "choices": ["left", "center", "right"],
            "importance": "advanced",
        },
    )
    heading_level_offset: int = field(
        default=DEFAULT_HEADING_LEVEL_OFFSET,
        metadata={
            "help": "Shift all heading levels by this amount (useful when collating docs)",
            "type": int,
            "importance": "advanced",
        },
    )
    code_fence_char: CodeFenceChar = field(
        default=DEFAULT_CODE_FENCE_CHAR,
        metadata={
            "help": "Character to use for code fences (backtick or tilde)",
            "choices": ["`", "~"],
            "importance": "advanced",
        },
    )
    code_fence_min: int = field(
        default=DEFAULT_CODE_FENCE_MIN,
        metadata={"help": "Minimum length for code fences (typically 3)", "type": int, "importance": "advanced"},
    )
    collapse_blank_lines: bool = field(
        default=DEFAULT_COLLAPSE_BLANK_LINES,
        metadata={
            "help": "Collapse multiple blank lines into at most 2 (normalize whitespace)",
            "cli_name": "no-collapse-blank-lines",
            "importance": "core",
        },
    )
    link_style: LinkStyleType = field(
        default=DEFAULT_LINK_STYLE,
        metadata={
            "help": "Link style: inline [text](url) or reference [text][ref]",
            "choices": ["inline", "reference"],
            "importance": "core",
        },
    )
    reference_link_placement: ReferenceLinkPlacement = field(
        default=DEFAULT_REFERENCE_LINK_PLACEMENT,
        metadata={
            "help": "Where to place reference link definitions: end_of_document or after_block",
            "choices": ["end_of_document", "after_block"],
            "importance": "advanced",
        },
    )
    autolink_bare_urls: bool = field(
        default=DEFAULT_AUTOLINK_BARE_URLS,
        metadata={"help": "Convert bare URLs in text to Markdown autolinks (<http://...>)", "importance": "core"},
    )
    table_pipe_escape: bool = field(
        default=DEFAULT_TABLE_PIPE_ESCAPE,
        metadata={
            "help": "Escape pipe characters in table cells",
            "cli_name": "no-table-pipe-escape",
            "importance": "core",
        },
    )
    math_mode: MathMode = field(
        default=DEFAULT_MATH_MODE,
        metadata={
            "help": "Preferred math representation: latex, mathml, or html",
            "choices": ["latex", "mathml", "html"],
            "importance": "core",
        },
    )
    metadata_frontmatter: bool = field(
        default=DEFAULT_INCLUDE_METADATA_FRONTMATTER,
        metadata={"help": "Render document metadata as YAML frontmatter", "importance": "core"},
    )
    metadata_format: MetadataFormatType = field(
        default=DEFAULT_METADATA_FORMAT,
        metadata={
            "help": "Format for metadata frontmatter: yaml, toml, or json",
            "choices": ["yaml", "toml", "json"],
            "importance": "advanced",
        },
    )
    html_passthrough_mode: HtmlPassthroughMode = field(
        default=DEFAULT_MARKDOWN_HTML_PASSTHROUGH_MODE,
        metadata={
            "help": "How to handle raw HTML content in markdown: "
            "pass-through (allow HTML as-is), escape (show as text), "
            "drop (remove entirely), sanitize (remove dangerous elements). "
            "Default is 'escape' for security. Does not affect code blocks.",
            "choices": HTML_PASSTHROUGH_MODES,
            "importance": "security",
        },
    )
    comment_mode: CommentMode = field(
        default=DEFAULT_COMMENT_MODE,
        metadata={
            "help": "How to render Comment and CommentInline nodes: "
            "html (HTML comments <!-- -->), blockquote (quoted blocks with attribution), "
            "ignore (skip comment nodes entirely). Controls presentation of comments "
            "from DOCX, HTML, and other formats that support annotations.",
            "choices": ["html", "blockquote", "ignore"],
            "importance": "core",
        },
    )

    # Private field to track whether user explicitly set unsupported_inline_mode
    # Used by renderer to implement smart fallback behavior for definition lists
    _unsupported_inline_mode_was_explicit: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Apply flavor-aware defaults and validate flavor compatibility.

        If unsupported_table_mode or unsupported_inline_mode are unset
        (sentinel value), apply flavor-appropriate defaults. If
        strict_flavor_validation is True, validate flavor compatibility
        and raise errors for incompatible configurations.

        Raises
        ------
        ValueError
            If strict_flavor_validation is True and the options are
            incompatible with the selected flavor.

        """
        # Call parent validation
        super().__post_init__()

        flavor_defaults = get_flavor_defaults(self.flavor)

        # Apply flavor defaults for any fields that are still unset
        if self.unsupported_table_mode is UNSET:
            object.__setattr__(self, "unsupported_table_mode", flavor_defaults["unsupported_table_mode"])

        # Track whether user explicitly set unsupported_inline_mode (for smart fallback behavior)
        inline_mode_was_explicit = self.unsupported_inline_mode is not UNSET
        object.__setattr__(self, "_unsupported_inline_mode_was_explicit", inline_mode_was_explicit)

        if self.unsupported_inline_mode is UNSET:
            object.__setattr__(self, "unsupported_inline_mode", flavor_defaults["unsupported_inline_mode"])

        # If strict validation is enabled, check flavor compatibility
        if self.strict_flavor_validation:
            warnings = validate_flavor_compatibility(self.flavor, self)
            if warnings:
                raise ValueError(
                    f"Flavor '{self.flavor}' validation errors:\n" + "\n".join(f"  - {w}" for w in warnings)
                )


def get_flavor_defaults(flavor: FlavorType) -> dict[str, Any]:
    """Get default option values appropriate for a markdown flavor.

    This function returns recommended default values for
    `unsupported_table_mode` and `unsupported_inline_mode` based on
    the specified markdown flavor's capabilities.

    Parameters
    ----------
    flavor : FlavorType
        The markdown flavor to get defaults for.

    Returns
    -------
    dict[str, Any]
        Dictionary with default option values for the flavor, including:
        - unsupported_table_mode: How to handle tables unsupported by flavor
        - unsupported_inline_mode: How to handle inline elements unsupported by flavor

    Examples
    --------
    Get defaults for CommonMark (strict spec):
        >>> defaults = get_flavor_defaults("commonmark")
        >>> defaults["unsupported_table_mode"]
        'html'

    Get defaults for GFM (supports most features):
        >>> defaults = get_flavor_defaults("gfm")
        >>> defaults["unsupported_table_mode"]
        'html'

    Notes
    -----
    The global defaults are "html" for both modes to ensure backward compatibility
    and universal fallback. These flavor-specific defaults provide *optimized*
    settings for each flavor:

    - **CommonMark**: Strict spec, use HTML for unsupported features
        - unsupported_table_mode: "html" (tables not in spec)
        - unsupported_inline_mode: "html" (strikethrough, etc. not in spec)

    - **GFM**: Most features supported, but use HTML for unsupported
        - unsupported_table_mode: "html" (tables supported, but HTML is safer)
        - unsupported_inline_mode: "html" (footnotes not supported)

    - **MultiMarkdown**: Tables and footnotes supported, use HTML for unsupported
        - unsupported_table_mode: "html" (tables supported, but HTML is safer)
        - unsupported_inline_mode: "html" (task lists not supported)

    - **Pandoc/Kramdown**: Comprehensive support, force everything
        - unsupported_table_mode: "force" (all table types supported)
        - unsupported_inline_mode: "force" (most inline elements supported)

    - **MarkdownPlus**: Everything enabled, always force
        - unsupported_table_mode: "force"
        - unsupported_inline_mode: "force"

    """
    # CommonMark: strict spec, use HTML for unsupported features
    if flavor == "commonmark":
        return {
            "unsupported_table_mode": "html",
            "unsupported_inline_mode": "html",
        }

    # MultiMarkdown: tables/footnotes supported, but not task lists/strikethrough
    elif flavor == "multimarkdown":
        return {
            "unsupported_table_mode": "html",  # Tables supported, HTML for safety
            "unsupported_inline_mode": "html",  # Task lists not supported
        }

    # Pandoc and Kramdown: comprehensive support, force everything
    elif flavor in ("pandoc", "kramdown"):
        return {
            "unsupported_table_mode": "force",
            "unsupported_inline_mode": "force",
        }

    # MarkdownPlus: everything enabled, always force
    elif flavor == "markdown_plus":
        return {
            "unsupported_table_mode": "force",
            "unsupported_inline_mode": "force",
        }

    # GFM (default): most features supported, use HTML for safety
    else:  # "gfm" or unknown
        return {
            "unsupported_table_mode": "html",  # Tables supported, HTML for safety
            "unsupported_inline_mode": "html",  # Footnotes not supported
        }


def validate_flavor_compatibility(
    flavor: FlavorType,
    options: MarkdownRendererOptions,
) -> list[str]:
    """Validate option compatibility with markdown flavor and return warnings.

    This function checks if the provided options are compatible with the
    selected markdown flavor's capabilities. It returns a list of warning
    messages for incompatible configurations but does not raise errors,
    allowing users to override flavor defaults when desired.

    Parameters
    ----------
    flavor : FlavorType
        The markdown flavor to validate against.
    options : MarkdownRendererOptions
        The markdown options to validate.

    Returns
    -------
    list[str]
        List of warning messages for incompatible configurations.
        Empty list if all options are compatible.

    Examples
    --------
    Validate CommonMark with table-related options:
        >>> md_opts = MarkdownRendererOptions(flavor="commonmark", pad_table_cells=True)
        >>> warnings = validate_flavor_compatibility("commonmark", md_opts)
        >>> # Will warn if unsupported_table_mode is "drop" with pad_table_cells=True

    No warnings for compatible configuration:
        >>> md_opts = MarkdownRendererOptions(flavor="gfm", pad_table_cells=True)
        >>> warnings = validate_flavor_compatibility("gfm", md_opts)
        >>> len(warnings)
        0

    Notes
    -----
    Common warning scenarios:

    - Using `pad_table_cells=True` when flavor doesn't support tables
      AND `unsupported_table_mode="drop"`
    - Setting table-specific options with CommonMark unless using
      `unsupported_table_mode="force"` or `"html"`

    """
    from all2md.utils.flavors import (
        CommonMarkFlavor,
        GFMFlavor,
        KramdownFlavor,
        MarkdownPlusFlavor,
        MultiMarkdownFlavor,
        PandocFlavor,
    )

    warnings: list[str] = []

    # Get flavor instance
    flavor_map = {
        "gfm": GFMFlavor(),
        "commonmark": CommonMarkFlavor(),
        "multimarkdown": MultiMarkdownFlavor(),
        "pandoc": PandocFlavor(),
        "kramdown": KramdownFlavor(),
        "markdown_plus": MarkdownPlusFlavor(),
    }
    flavor_obj = flavor_map.get(flavor, GFMFlavor())

    # Check table-related options
    if not flavor_obj.supports_tables():
        if options.unsupported_table_mode == "drop":
            if options.pad_table_cells:
                warnings.append(
                    f"Flavor '{flavor}' does not support tables and "
                    f"unsupported_table_mode='drop', but pad_table_cells=True. "
                    f"Tables will be dropped entirely, making pad_table_cells ineffective."
                )
        elif options.unsupported_table_mode == "force":
            warnings.append(
                f"Flavor '{flavor}' does not support tables natively, but "
                f"unsupported_table_mode='force' will render pipe tables anyway. "
                f"The output may not be valid {flavor} markdown."
            )

    # Check strikethrough with CommonMark
    if flavor == "commonmark" and options.unsupported_inline_mode == "force":
        warnings.append(
            "Flavor 'commonmark' does not support strikethrough. "
            "Using unsupported_inline_mode='force' will render ~~text~~ "
            "which is not valid CommonMark."
        )

    # Check task lists with flavors that don't support them
    if not flavor_obj.supports_task_lists():
        if options.unsupported_inline_mode == "force":
            warnings.append(
                f"Flavor '{flavor}' does not support task lists. "
                f"Using unsupported_inline_mode='force' will render [ ] checkboxes "
                f"which may not be supported."
            )

    return warnings
