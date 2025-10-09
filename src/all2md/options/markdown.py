#  Copyright (c) 2025 Tom Villani, Ph.D.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from all2md.options.base import BaseParserOptions, BaseRendererOptions, _UNSET
from all2md.constants import (
    FlavorType, DEFAULT_FLAVOR, DEFAULT_ESCAPE_SPECIAL, EmphasisSymbol, DEFAULT_BULLET_SYMBOLS,
    DEFAULT_LIST_INDENT_WIDTH, UnderlineMode, SuperscriptMode, SubscriptMode, DEFAULT_USE_HASH_HEADINGS,
    UnsupportedTableMode, UnsupportedInlineMode, DEFAULT_HEADING_LEVEL_OFFSET, CodeFenceChar, DEFAULT_CODE_FENCE_CHAR,
    DEFAULT_CODE_FENCE_MIN, DEFAULT_COLLAPSE_BLANK_LINES, LinkStyleType, DEFAULT_LINK_STYLE, DEFAULT_TABLE_PIPE_ESCAPE,
    MathMode, DEFAULT_MATH_MODE, DEFAULT_INCLUDE_METADATA_FRONTMATTER, MetadataFormatType, DEFAULT_METADATA_FORMAT,
)



# src/all2md/options/markdown.py
@dataclass(frozen=True)
class MarkdownOptions(BaseRendererOptions):
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
    table_pipe_escape : bool, default True
        Whether to escape pipe characters (|) in table cell content.
    math_mode : {"latex", "mathml", "html"}, default "latex"
        Preferred math representation for flavors that support math. When the
        requested representation is unavailable on a node, the renderer falls
        back to any available representation while preserving flavor
        constraints.

    """

    escape_special: bool = field(
        default=DEFAULT_ESCAPE_SPECIAL,
        metadata={
            "help": "Escape special Markdown characters in text content",
            "cli_name": "no-escape-special"  # Since default=True, use --no-* flag
        }
    )
    emphasis_symbol: EmphasisSymbol = field(
        default=DEFAULT_EMPHASIS_SYMBOL,  # type: ignore[arg-type]
        metadata={
            "help": "Symbol to use for emphasis/italic formatting",
            "choices": ["*", "_"]
        }
    )
    bullet_symbols: str = field(
        default=DEFAULT_BULLET_SYMBOLS,
        metadata={"help": "Characters to cycle through for nested bullet lists"}
    )
    list_indent_width: int = field(
        default=DEFAULT_LIST_INDENT_WIDTH,
        metadata={
            "help": "Number of spaces to use for each level of list indentation",
            "type": int
        }
    )
    underline_mode: UnderlineMode = field(
        default="html",
        metadata={
            "help": "How to handle underlined text",
            "choices": ["html", "markdown", "ignore"]
        }
    )
    superscript_mode: SuperscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle superscript text",
            "choices": ["html", "markdown", "ignore"]
        }
    )
    subscript_mode: SubscriptMode = field(
        default="html",
        metadata={
            "help": "How to handle subscript text",
            "choices": ["html", "markdown", "ignore"]
        }
    )
    use_hash_headings: bool = field(
        default=DEFAULT_USE_HASH_HEADINGS,
        metadata={
            "help": "Use # syntax for headings instead of underline style",
            "cli_name": "no-use-hash-headings"  # default=True, use --no-*
        }
    )
    flavor: FlavorType = field(
        default=DEFAULT_FLAVOR,
        metadata={
            "help": "Markdown flavor/dialect to use for output",
            "choices": ["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
        }
    )
    unsupported_table_mode: UnsupportedTableMode | object = field(
        default=_UNSET,
        metadata={
            "help": "How to handle tables when flavor doesn't support them: "
                    "drop (skip entirely), ascii (render as ASCII art), "
                    "force (render as pipe tables anyway), html (render as HTML table)",
            "choices": ["drop", "ascii", "force", "html"]
        }
    )
    unsupported_inline_mode: UnsupportedInlineMode | object = field(
        default=_UNSET,
        metadata={
            "help": "How to handle inline elements unsupported by flavor: "
                    "plain (render content without formatting), "
                    "force (use markdown syntax anyway), html (use HTML tags)",
            "choices": ["plain", "force", "html"]
        }
    )
    pad_table_cells: bool = field(
        default=False,
        metadata={
            "help": "Pad table cells with spaces for visual alignment in source"
        }
    )
    prefer_setext_headings: bool = field(
        default=False,
        metadata={
            "help": "Prefer setext-style headings (underlines) for h1 and h2"
        }
    )
    max_line_width: int | None = field(
        default=None,
        metadata={
            "help": "Maximum line width for wrapping (None for no limit)",
            "type": int
        }
    )
    table_alignment_default: str = field(
        default="left",
        metadata={
            "help": "Default alignment for table columns without explicit alignment",
            "choices": ["left", "center", "right"]
        }
    )
    heading_level_offset: int = field(
        default=DEFAULT_HEADING_LEVEL_OFFSET,
        metadata={
            "help": "Shift all heading levels by this amount (useful when collating docs)",
            "type": int
        }
    )
    code_fence_char: CodeFenceChar = field(
        default=DEFAULT_CODE_FENCE_CHAR,
        metadata={
            "help": "Character to use for code fences (backtick or tilde)",
            "choices": ["`", "~"]
        }
    )
    code_fence_min: int = field(
        default=DEFAULT_CODE_FENCE_MIN,
        metadata={
            "help": "Minimum length for code fences (typically 3)",
            "type": int
        }
    )
    collapse_blank_lines: bool = field(
        default=DEFAULT_COLLAPSE_BLANK_LINES,
        metadata={
            "help": "Collapse multiple blank lines into at most 2 (normalize whitespace)",
            "cli_name": "no-collapse-blank-lines"
        }
    )
    link_style: LinkStyleType = field(
        default=DEFAULT_LINK_STYLE,
        metadata={
            "help": "Link style: inline [text](url) or reference [text][ref]",
            "choices": ["inline", "reference"]
        }
    )
    table_pipe_escape: bool = field(
        default=DEFAULT_TABLE_PIPE_ESCAPE,
        metadata={
            "help": "Escape pipe characters in table cells",
            "cli_name": "no-table-pipe-escape"
        }
    )
    math_mode: MathMode = field(
        default=DEFAULT_MATH_MODE,
        metadata={
            "help": "Preferred math representation: latex, mathml, or html",
            "choices": ["latex", "mathml", "html"]
        }
    )
    metadata_frontmatter: bool = field(
        default=DEFAULT_INCLUDE_METADATA_FRONTMATTER,
        metadata={
            "help": "Render document metadata as YAML frontmatter"
        }
    )
    metadata_format: MetadataFormatType = field(
        default=DEFAULT_METADATA_FORMAT,
        metadata={
            "help": "Format for metadata frontmatter: yaml, toml, or json",
            "choices": ["yaml", "toml", "json"]
        }
    )

    def __post_init__(self) -> None:
        """Apply flavor-aware defaults after initialization.

        If unsupported_table_mode or unsupported_inline_mode are unset
        (sentinel value), apply flavor-appropriate defaults.
        """
        flavor_defaults = get_flavor_defaults(self.flavor)

        # Apply flavor defaults for any fields that are still unset
        if self.unsupported_table_mode is _UNSET:
            object.__setattr__(self, 'unsupported_table_mode',
                             flavor_defaults['unsupported_table_mode'])
        if self.unsupported_inline_mode is _UNSET:
            object.__setattr__(self, 'unsupported_inline_mode',
                             flavor_defaults['unsupported_inline_mode'])


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
    strict_parsing : bool, default False
        Whether to raise errors on invalid/ambiguous markdown syntax.
        When False, attempts to recover gracefully.
    preserve_html : bool, default True
        Whether to preserve raw HTML in the AST (HTMLBlock/HTMLInline nodes).
        When False, HTML is stripped.

    """

    flavor: FlavorType = field(
        default=DEFAULT_FLAVOR,
        metadata={
            "help": "Markdown flavor to parse (determines enabled extensions)",
            "choices": ["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
        }
    )
    parse_tables: bool = field(
        default=True,
        metadata={
            "help": "Parse table syntax (GFM pipe tables)",
            "cli_name": "no-parse-tables"
        }
    )
    parse_footnotes: bool = field(
        default=True,
        metadata={
            "help": "Parse footnote references and definitions",
            "cli_name": "no-parse-footnotes"
        }
    )
    parse_math: bool = field(
        default=True,
        metadata={
            "help": "Parse inline and block math ($...$ and $$...$$)",
            "cli_name": "no-parse-math"
        }
    )
    parse_task_lists: bool = field(
        default=True,
        metadata={
            "help": "Parse task list checkboxes (- [ ] and - [x])",
            "cli_name": "no-parse-task-lists"
        }
    )
    parse_definition_lists: bool = field(
        default=True,
        metadata={
            "help": "Parse definition lists (term : definition)",
            "cli_name": "no-parse-definition-lists"
        }
    )
    parse_strikethrough: bool = field(
        default=True,
        metadata={
            "help": "Parse strikethrough syntax (~~text~~)",
            "cli_name": "no-parse-strikethrough"
        }
    )
    strict_parsing: bool = field(
        default=False,
        metadata={
            "help": "Raise errors on invalid markdown syntax (vs. graceful recovery)"
        }
    )
    preserve_html: bool = field(
        default=True,
        metadata={
            "help": "Preserve raw HTML in AST (HTMLBlock/HTMLInline nodes)",
            "cli_name": "no-preserve-html"
        }
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
    options: MarkdownOptions,
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
    options : MarkdownOptions
        The markdown options to validate.

    Returns
    -------
    list[str]
        List of warning messages for incompatible configurations.
        Empty list if all options are compatible.

    Examples
    --------
    Validate CommonMark with table-related options:
        >>> md_opts = MarkdownOptions(flavor="commonmark", pad_table_cells=True)
        >>> warnings = validate_flavor_compatibility("commonmark", md_opts)
        >>> # Will warn if unsupported_table_mode is "drop" with pad_table_cells=True

    No warnings for compatible configuration:
        >>> md_opts = MarkdownOptions(flavor="gfm", pad_table_cells=True)
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
