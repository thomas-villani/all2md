#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options and settings for all2md conversion modules.

This module provides dataclass-based configuration options for all conversion
modules in the all2md library. Using dataclasses provides type safety,
default values, and a clean API for configuring conversion behavior.

Each converter module has its own Options dataclass with module-specific
parameters, plus a shared MarkdownOptions class for common Markdown formatting
settings that apply across multiple parsers.

Options Classes
---------------
- MarkdownOptions: Common Markdown formatting settings
- PdfOptions: PDF-specific conversion settings
- DocxOptions: Word document conversion settings
- HtmlOptions: HTML conversion settings
- PptxOptions: PowerPoint conversion settings
- EmlOptions: Email conversion settings
- Markdown2PdfOptions: Markdown-to-PDF conversion settings
- Markdown2DocxOptions: Markdown-to-Word conversion settings
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Optional, Self, Union

# Sentinel value to detect when user didn't explicitly set unsupported modes
_UNSET = object()

from .constants import (
    DEFAULT_ALLOW_CWD_FILES,
    DEFAULT_ALLOW_LOCAL_FILES,
    DEFAULT_ALLOW_REMOTE_FETCH,
    DEFAULT_ALLOWED_HOSTS,
    DEFAULT_ALT_TEXT_MODE,
    DEFAULT_ATTACHMENT_BASE_URL,
    DEFAULT_ATTACHMENT_MODE,
    DEFAULT_ATTACHMENT_OUTPUT_DIR,
    # HTML-specific constants
    DEFAULT_BULLET_SYMBOLS,
    # Email-specific constants
    DEFAULT_CLEAN_QUOTES,
    DEFAULT_CLEAN_WRAPPED_URLS,
    DEFAULT_COLUMN_GAP_THRESHOLD,
    DEFAULT_COMMENT_MODE,
    DEFAULT_CONVERT_HTML_TO_MARKDOWN,
    DEFAULT_CONVERT_NBSP,
    DEFAULT_DATE_FORMAT_MODE,
    DEFAULT_DATE_STRFTIME_PATTERN,
    DEFAULT_DETECT_COLUMNS,
    DEFAULT_DETECT_MERGED_CELLS,
    DEFAULT_DETECT_REPLY_SEPARATORS,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_EXTRACT_METADATA,
    DEFAULT_EXTRACT_TITLE,
    DEFAULT_HANDLE_ROTATED_TEXT,
    DEFAULT_HEADER_FONT_SIZE_RATIO,
    DEFAULT_HEADER_MAX_LINE_LENGTH,
    # PDF-specific constants
    DEFAULT_HEADER_MIN_OCCURRENCES,
    DEFAULT_HEADER_PERCENTILE_THRESHOLD,
    DEFAULT_HEADER_USE_ALL_CAPS,
    DEFAULT_HEADER_USE_FONT_WEIGHT,
    DEFAULT_IMAGE_PLACEMENT_MARKERS,
    DEFAULT_INCLUDE_IMAGE_CAPTIONS,
    DEFAULT_INCLUDE_PAGE_NUMBERS,
    DEFAULT_TABLE_DETECTION_MODE,
    DEFAULT_IMAGE_FORMAT,
    DEFAULT_IMAGE_QUALITY,
    DEFAULT_TRIM_HEADERS_FOOTERS,
    DEFAULT_HEADER_HEIGHT,
    DEFAULT_FOOTER_HEIGHT,
    DEFAULT_LIST_INDENT_WIDTH,
    DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
    DEFAULT_MAX_DOWNLOAD_BYTES,
    DEFAULT_MAX_IMAGE_SIZE_BYTES,
    DEFAULT_MERGE_HYPHENATED_WORDS,
    DEFAULT_NETWORK_TIMEOUT,
    DEFAULT_NORMALIZE_HEADERS,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_PRESERVE_NESTED_STRUCTURE,
    DEFAULT_PRESERVE_RAW_HEADERS,
    DEFAULT_REQUIRE_HTTPS,
    DEFAULT_SLIDE_NUMBERS,
    DEFAULT_STRIP_DANGEROUS_ELEMENTS,
    DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
    DEFAULT_TABLE_FALLBACK_DETECTION,
    DEFAULT_TABLE_RULING_LINE_THRESHOLD,
    DEFAULT_TRUNCATE_OUTPUT_LINES,
    DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
    DEFAULT_URL_WRAPPERS,
    DEFAULT_USE_HASH_HEADINGS,
    # Markdown rendering constants
    DEFAULT_HEADING_LEVEL_OFFSET,
    DEFAULT_CODE_FENCE_CHAR,
    DEFAULT_CODE_FENCE_MIN,
    DEFAULT_COLLAPSE_BLANK_LINES,
    DEFAULT_LINK_STYLE,
    DEFAULT_TABLE_PIPE_ESCAPE,
    # Type literals
    AltTextMode,
    AttachmentMode,
    CodeFenceChar,
    CommentMode,
    DateFormatMode,
    EmphasisSymbol,
    FlavorType,
    LinkStyleType,
    MathMode,
    MetadataFormatType,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,
    UnsupportedInlineMode,
    UnsupportedTableMode,
    DEFAULT_FLAVOR,
    DEFAULT_INCLUDE_METADATA_FRONTMATTER,
    DEFAULT_MATH_MODE,
    DEFAULT_METADATA_FORMAT,
    # RST-specific constants
    DEFAULT_RST_HEADING_CHARS,
    DEFAULT_RST_TABLE_STYLE,
    DEFAULT_RST_CODE_STYLE,
    DEFAULT_RST_LINE_LENGTH,
    DEFAULT_RST_PARSE_DIRECTIVES,
    DEFAULT_RST_STRICT_MODE,
    DEFAULT_RST_PRESERVE_RAW_DIRECTIVES,
    RstTableStyle,
    RstCodeStyle,
)


class _CloneMixin:
    def create_updated(self, **kwargs: Any) -> Self:
        return replace(self, **kwargs)  # type: ignore


@dataclass(frozen=True)
class BaseRendererOptions(_CloneMixin):
    """Base class for all renderer options.

    This class serves as the foundation for format-specific renderer options.
    Renderers convert AST documents into various output formats (Markdown, DOCX, PDF, etc.).

    Notes
    -----
    Subclasses should define format-specific rendering options as frozen dataclass fields.
    """
    pass


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
        default=DEFAULT_FLAVOR,  # type: ignore[arg-type]
        metadata={
            "help": "Markdown flavor/dialect to use for output",
            "choices": ["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
        }
    )
    unsupported_table_mode: UnsupportedTableMode | Literal[_UNSET] = field(  # type: ignore[valid-type]
        default=_UNSET,  # type: ignore[arg-type]
        metadata={
            "help": "How to handle tables when flavor doesn't support them: "
                    "drop (skip entirely), ascii (render as ASCII art), "
                    "force (render as pipe tables anyway), html (render as HTML table)",
            "choices": ["drop", "ascii", "force", "html"]
        }
    )
    unsupported_inline_mode: UnsupportedInlineMode | Literal[_UNSET] = field(  # type: ignore[valid-type]
        default=_UNSET,  # type: ignore[arg-type]
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
        default=DEFAULT_CODE_FENCE_CHAR,  # type: ignore[arg-type]
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
        default=DEFAULT_LINK_STYLE,  # type: ignore[arg-type]
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
        default=DEFAULT_MATH_MODE,  # type: ignore[arg-type]
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
        default=DEFAULT_METADATA_FORMAT,  # type: ignore[arg-type]
        metadata={
            "help": "Format for metadata frontmatter: yaml, toml, or json",
            "choices": ["yaml", "toml", "json"]
        }
    )

    def __post_init__(self):
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
class DocxRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to DOCX format.

    This dataclass contains settings specific to Word document generation,
    including fonts, styles, and formatting preferences.

    Parameters
    ----------
    default_font : str, default "Calibri"
        Default font name for body text.
    default_font_size : int, default 11
        Default font size in points for body text.
    heading_font_sizes : dict[int, int] or None, default None
        Font sizes for heading levels 1-6. If None, uses built-in Word heading styles.
    use_styles : bool, default True
        Whether to use built-in Word styles vs direct formatting.
    table_style : str or None, default "Light Grid Accent 1"
        Built-in table style name. If None, uses plain table formatting.
    code_font : str, default "Courier New"
        Font name for code blocks and inline code.
    code_font_size : int, default 10
        Font size for code blocks and inline code.
    preserve_formatting : bool, default True
        Whether to preserve text formatting (bold, italic, etc.).
    """

    default_font: str = field(
        default="Calibri",
        metadata={"help": "Default font for body text"}
    )
    default_font_size: int = field(
        default=11,
        metadata={"help": "Default font size in points", "type": int}
    )
    heading_font_sizes: dict[int, int] | None = field(
        default=None,
        metadata={
            "help": "Font sizes for heading levels 1-6 (None = use built-in styles)",
            "exclude_from_cli": True
        }
    )
    use_styles: bool = field(
        default=True,
        metadata={
            "help": "Use built-in Word styles vs direct formatting",
            "cli_name": "no-use-styles"
        }
    )
    table_style: str | None = field(
        default="Light Grid Accent 1",
        metadata={"help": "Built-in table style name (None = plain formatting)"}
    )
    code_font: str = field(
        default="Courier New",
        metadata={"help": "Font for code blocks and inline code"}
    )
    code_font_size: int = field(
        default=10,
        metadata={"help": "Font size for code", "type": int}
    )
    preserve_formatting: bool = field(
        default=True,
        metadata={
            "help": "Preserve text formatting (bold, italic, etc.)",
            "cli_name": "no-preserve-formatting"
        }
    )


@dataclass(frozen=True)
class HtmlRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to HTML format.

    This dataclass contains settings specific to HTML generation,
    including document structure, styling, and feature toggles.

    Parameters
    ----------
    standalone : bool, default True
        Generate complete HTML document with <html>, <head>, <body> tags.
        If False, generates only the content fragment.
    css_style : {"inline", "embedded", "external", "none"}, default "embedded"
        How to include CSS styles:
        - "inline": Add style attributes to elements
        - "embedded": Include <style> block in <head>
        - "external": Reference external CSS file
        - "none": No styling
    css_file : str or None, default None
        Path to external CSS file (used when css_style="external").
    template : str or None, default None
        Path to custom Jinja2 template file. If None, uses built-in template.
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
    """

    standalone: bool = field(
        default=True,
        metadata={
            "help": "Generate complete HTML document (vs content fragment)",
            "cli_name": "no-standalone"
        }
    )
    css_style: Literal["inline", "embedded", "external", "none"] = field(
        default="embedded",
        metadata={
            "help": "CSS inclusion method: inline, embedded, external, or none",
            "choices": ["inline", "embedded", "external", "none"]
        }
    )
    css_file: str | None = field(
        default=None,
        metadata={"help": "Path to external CSS file (when css_style='external')"}
    )
    template: str | None = field(
        default=None,
        metadata={"help": "Path to custom Jinja2 template (None = use built-in)"}
    )
    include_toc: bool = field(
        default=False,
        metadata={"help": "Generate table of contents from headings"}
    )
    syntax_highlighting: bool = field(
        default=True,
        metadata={
            "help": "Add language classes for syntax highlighting",
            "cli_name": "no-syntax-highlighting"
        }
    )
    escape_html: bool = field(
        default=True,
        metadata={
            "help": "Escape HTML special characters in text",
            "cli_name": "no-escape-html"
        }
    )
    math_renderer: Literal["mathjax", "katex", "none"] = field(
        default="mathjax",
        metadata={
            "help": "Math rendering library: mathjax, katex, or none",
            "choices": ["mathjax", "katex", "none"]
        }
    )


@dataclass(frozen=True)
class PdfRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to PDF format.

    This dataclass contains settings specific to PDF generation using ReportLab,
    including page layout, fonts, margins, and formatting preferences.

    Parameters
    ----------
    page_size : {"letter", "a4", "legal"}, default "letter"
        Page size for the PDF document.
    margin_top : float, default 72.0
        Top margin in points (72 points = 1 inch).
    margin_bottom : float, default 72.0
        Bottom margin in points.
    margin_left : float, default 72.0
        Left margin in points.
    margin_right : float, default 72.0
        Right margin in points.
    font_name : str, default "Helvetica"
        Default font for body text. Standard PDF fonts: Helvetica, Times-Roman, Courier.
    font_size : int, default 11
        Default font size in points for body text.
    heading_fonts : dict[int, tuple[str, int]] or None, default None
        Font specifications for headings as {level: (font_name, font_size)}.
        If None, uses scaled versions of default font.
    code_font : str, default "Courier"
        Monospace font for code blocks and inline code.
    line_spacing : float, default 1.2
        Line spacing multiplier (1.0 = single spacing).
    include_page_numbers : bool, default True
        Add page numbers to footer.
    include_toc : bool, default False
        Generate table of contents from headings.
    """

    page_size: Literal["letter", "a4", "legal"] = field(
        default="letter",
        metadata={
            "help": "Page size: letter, a4, or legal",
            "choices": ["letter", "a4", "legal"]
        }
    )
    margin_top: float = field(
        default=72.0,
        metadata={"help": "Top margin in points (72pt = 1 inch)", "type": float}
    )
    margin_bottom: float = field(
        default=72.0,
        metadata={"help": "Bottom margin in points", "type": float}
    )
    margin_left: float = field(
        default=72.0,
        metadata={"help": "Left margin in points", "type": float}
    )
    margin_right: float = field(
        default=72.0,
        metadata={"help": "Right margin in points", "type": float}
    )
    font_name: str = field(
        default="Helvetica",
        metadata={"help": "Default font (Helvetica, Times-Roman, Courier)"}
    )
    font_size: int = field(
        default=11,
        metadata={"help": "Default font size in points", "type": int}
    )
    heading_fonts: dict[int, tuple[str, int]] | None = field(
        default=None,
        metadata={
            "help": "Heading font specs as {level: (font, size)}",
            "exclude_from_cli": True
        }
    )
    code_font: str = field(
        default="Courier",
        metadata={"help": "Monospace font for code"}
    )
    line_spacing: float = field(
        default=1.2,
        metadata={"help": "Line spacing multiplier (1.0 = single)", "type": float}
    )
    include_page_numbers: bool = field(
        default=True,
        metadata={
            "help": "Add page numbers to footer",
            "cli_name": "no-page-numbers"
        }
    )
    include_toc: bool = field(
        default=False,
        metadata={"help": "Generate table of contents"}
    )


@dataclass(frozen=True)
class EpubRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to EPUB format.

    This dataclass contains settings specific to EPUB generation from AST,
    including chapter splitting strategies, metadata, and EPUB structure.

    Parameters
    ----------
    chapter_split_mode : {"separator", "heading", "auto"}, default "auto"
        How to split the AST into chapters:
        - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
        - "heading": Split on specific heading level
        - "auto": Try separator first, fallback to heading-based splitting
    chapter_split_heading_level : int, default 1
        Heading level to use for chapter splits when using heading mode.
        Level 1 (H1) typically represents chapter boundaries.
    title : str or None, default None
        EPUB book title. If None, extracted from document metadata.
    author : str or None, default None
        EPUB book author. If None, extracted from document metadata.
    language : str, default "en"
        EPUB book language code (ISO 639-1).
    identifier : str or None, default None
        Unique identifier (ISBN, UUID, etc.). Auto-generated if None.
    chapter_title_template : str, default "Chapter {num}"
        Template for auto-generated chapter titles. Supports {num} placeholder.
    use_heading_as_chapter_title : bool, default True
        Use first heading in chapter as chapter title in NCX/navigation.
    generate_toc : bool, default True
        Generate table of contents (NCX and nav.xhtml files).
    include_cover : bool, default False
        Include cover image in EPUB package.
    cover_image_path : str or None, default None
        Path to cover image file. Only used if include_cover=True.
    """

    chapter_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Chapter splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"]
        }
    )
    chapter_split_heading_level: int = field(
        default=1,
        metadata={
            "help": "Heading level for chapter splits (H1 = level 1)",
            "type": int
        }
    )
    title: str | None = field(
        default=None,
        metadata={"help": "EPUB book title (None = use document metadata)"}
    )
    author: str | None = field(
        default=None,
        metadata={"help": "EPUB book author (None = use document metadata)"}
    )
    language: str = field(
        default="en",
        metadata={"help": "EPUB language code (ISO 639-1)"}
    )
    identifier: str | None = field(
        default=None,
        metadata={"help": "Unique identifier (ISBN, UUID, etc.)"}
    )
    chapter_title_template: str = field(
        default="Chapter {num}",
        metadata={"help": "Template for auto-generated chapter titles"}
    )
    use_heading_as_chapter_title: bool = field(
        default=True,
        metadata={
            "help": "Use first heading as chapter title in navigation",
            "cli_name": "no-use-heading-as-chapter-title"
        }
    )
    generate_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate table of contents (NCX and nav.xhtml)",
            "cli_name": "no-generate-toc"
        }
    )
    include_cover: bool = field(
        default=False,
        metadata={"help": "Include cover image in EPUB"}
    )
    cover_image_path: str | None = field(
        default=None,
        metadata={"help": "Path to cover image file"}
    )


@dataclass(frozen=True)
class PptxRendererOptions(BaseRendererOptions):
    """Configuration options for rendering AST to PPTX format.

    This dataclass contains settings specific to PowerPoint presentation
    generation from AST, including slide splitting strategies and layout.

    Parameters
    ----------
    slide_split_mode : {"separator", "heading", "auto"}, default "auto"
        How to split the AST into slides:
        - "separator": Split on ThematicBreak nodes (mirrors parser behavior)
        - "heading": Split on specific heading level
        - "auto": Try separator first, fallback to heading-based splitting
    slide_split_heading_level : int, default 2
        Heading level to use for slide splits when using heading mode.
        Level 2 (H2) is typical (H1 might be document title).
    default_layout : str, default "Title and Content"
        Default slide layout name from template.
    title_slide_layout : str, default "Title Slide"
        Layout name for the first slide.
    use_heading_as_slide_title : bool, default True
        Use first heading in slide content as slide title.
    template_path : str or None, default None
        Path to .pptx template file. If None, uses default blank template.
    default_font : str, default "Calibri"
        Default font for slide content.
    default_font_size : int, default 18
        Default font size in points for body text.
    title_font_size : int, default 44
        Font size for slide titles.
    """

    slide_split_mode: Literal["separator", "heading", "auto"] = field(
        default="auto",
        metadata={
            "help": "Slide splitting strategy: separator, heading, or auto",
            "choices": ["separator", "heading", "auto"]
        }
    )
    slide_split_heading_level: int = field(
        default=2,
        metadata={
            "help": "Heading level for slide splits (H2 = level 2)",
            "type": int
        }
    )
    default_layout: str = field(
        default="Title and Content",
        metadata={"help": "Default slide layout name"}
    )
    title_slide_layout: str = field(
        default="Title Slide",
        metadata={"help": "Layout for first slide"}
    )
    use_heading_as_slide_title: bool = field(
        default=True,
        metadata={
            "help": "Use first heading as slide title",
            "cli_name": "no-use-heading-as-slide-title"
        }
    )
    template_path: str | None = field(
        default=None,
        metadata={"help": "Path to .pptx template file (None = default)"}
    )
    default_font: str = field(
        default="Calibri",
        metadata={"help": "Default font for slide content"}
    )
    default_font_size: int = field(
        default=18,
        metadata={"help": "Default font size for body text", "type": int}
    )
    title_font_size: int = field(
        default=44,
        metadata={"help": "Font size for slide titles", "type": int}
    )


@dataclass(frozen=True)
class NetworkFetchOptions(_CloneMixin):
    """Network security options for remote resource fetching.

    This dataclass contains settings that control how remote resources
    (images, CSS, etc.) are fetched, including security constraints
    to prevent SSRF attacks.

    Parameters
    ----------
    allow_remote_fetch : bool, default False
        Whether to allow fetching remote URLs for images and other resources.
        When False, prevents SSRF attacks by blocking all network requests.
    allowed_hosts : list[str] | None, default None
        List of allowed hostnames or CIDR blocks for remote fetching.
        If None, all hosts are allowed (subject to other security constraints).
    require_https : bool, default False
        Whether to require HTTPS for all remote URL fetching.
    network_timeout : float, default 10.0
        Timeout in seconds for remote URL fetching.
    max_remote_asset_bytes : int, default 20MB
        Maximum allowed size in bytes for downloaded remote assets.
    """

    allow_remote_fetch: bool = field(
        default=DEFAULT_ALLOW_REMOTE_FETCH,
        metadata={
            "help": "Allow fetching remote URLs for images and other resources. "
                    "When False, prevents SSRF attacks by blocking all network requests."
        }
    )
    allowed_hosts: list[str] | None = field(
        default=DEFAULT_ALLOWED_HOSTS,
        metadata={
            "help": "List of allowed hostnames or CIDR blocks for remote fetching. "
                    "If None, all hosts are allowed (subject to other security constraints)."
        }
    )
    require_https: bool = field(
        default=DEFAULT_REQUIRE_HTTPS,
        metadata={"help": "Require HTTPS for all remote URL fetching"}
    )
    network_timeout: float = field(
        default=DEFAULT_NETWORK_TIMEOUT,
        metadata={
            "help": "Timeout in seconds for remote URL fetching",
            "type": float
        }
    )
    max_remote_asset_bytes: int = field(
        default=DEFAULT_MAX_IMAGE_SIZE_BYTES,  # Reuse existing default
        metadata={
            "help": "Maximum allowed size in bytes for downloaded remote assets",
            "type": int
        }
    )
    max_redirects: int = field(
        default=5,
        metadata={
            "help": "Maximum number of HTTP redirects to follow",
            "type": int
        }
    )
    allowed_content_types: tuple[str, ...] | None = field(
        default=("image/",),
        metadata={
            "help": "Allowed content-type prefixes for remote resources (e.g., 'image/', 'text/')",
            "action": "append"
        }
    )


@dataclass(frozen=True)
class LocalFileAccessOptions(_CloneMixin):
    """Local file access security options.

    This dataclass contains settings that control access to local files
    via file:// URLs and similar mechanisms.

    Parameters
    ----------
    allow_local_files : bool, default False
        Whether to allow access to local files via file:// URLs.
    local_file_allowlist : list[str] | None, default None
        List of directories allowed for local file access.
        Only applies when allow_local_files=True.
    local_file_denylist : list[str] | None, default None
        List of directories denied for local file access.
    allow_cwd_files : bool, default False
        Whether to allow local files from current working directory and subdirectories.
    """

    allow_local_files: bool = field(
        default=DEFAULT_ALLOW_LOCAL_FILES,
        metadata={"help": "Allow access to local files via file:// URLs (security setting)"}
    )
    local_file_allowlist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories allowed for local file access (when allow_local_files=True)",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    local_file_denylist: list[str] | None = field(
        default=None,
        metadata={
            "help": "List of directories denied for local file access",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    allow_cwd_files: bool = field(
        default=DEFAULT_ALLOW_CWD_FILES,
        metadata={
            "help": "Allow local files from current working directory and subdirectories",
            "cli_name": "allow-cwd-files"  # default=False, use store_true
        }
    )


@dataclass(frozen=True)
class BaseParserOptions(_CloneMixin):
    """Base class for all parser options.

    This class serves as the foundation for format-specific parser options.
    Parsers convert source documents into AST representation.

    Parameters
    ----------
    attachment_mode : AttachmentMode
        How to handle attachments/images during parsing
    alt_text_mode : AltTextMode
        How to render alt-text content
    extract_metadata : bool
        Whether to extract document metadata

    Notes
    -----
    Subclasses should define format-specific parsing options as frozen dataclass fields.
    """
    attachment_mode: AttachmentMode = field(
        default=DEFAULT_ATTACHMENT_MODE,
        metadata={
            "help": "How to handle attachments/images",
            "choices": ["skip", "alt_text", "download", "base64"]
        }
    )
    alt_text_mode: AltTextMode = field(
        default=DEFAULT_ALT_TEXT_MODE,
        metadata={
            "help": "How to render alt-text content when using alt_text attachment mode",
            "choices": ["default", "plain_filename", "strict_markdown", "footnote"]
        }
    )
    attachment_output_dir: str | None = field(
        default=DEFAULT_ATTACHMENT_OUTPUT_DIR,
        metadata={"help": "Directory to save attachments when using download mode"}
    )
    attachment_base_url: str | None = field(
        default=DEFAULT_ATTACHMENT_BASE_URL,
        metadata={"help": "Base URL for resolving attachment references"}
    )
    extract_metadata: bool = field(
        default=DEFAULT_EXTRACT_METADATA,
        metadata={"help": "Extract document metadata as YAML front matter"}
    )
    max_asset_bytes: int = field(
        default=DEFAULT_MAX_DOWNLOAD_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for any single asset/download (global limit)",
            "type": int
        }
    )

    # Advanced attachment handling options
    attachment_filename_template: str = field(
        default="{stem}_{type}{seq}.{ext}",
        metadata={"help": "Template for attachment filenames. Tokens: {stem}, {type}, {seq}, {page}, {ext}"}
    )
    attachment_overwrite: str = field(
        default="unique",
        metadata={
            "help": "File collision strategy: 'unique' (add suffix), 'overwrite', or 'skip'",
            "choices": ["unique", "overwrite", "skip"]
        }
    )
    attachment_deduplicate_by_hash: bool = field(
        default=False,
        metadata={"help": "Avoid saving duplicate attachments by content hash"}
    )
    attachments_footnotes_section: str | None = field(
        default="Attachments",
        metadata={"help": "Section title for footnote-style attachment references (None to disable)"}
    )


@dataclass(frozen=True)
class PdfOptions(BaseParserOptions):
    """Configuration options for PDF-to-Markdown conversion.

    This dataclass contains settings specific to PDF document processing,
    including page selection, image handling, and formatting preferences.

    Parameters
    ----------
    pages : list[int], str, or None, default None
        Pages to convert (1-based indexing, like "page 1, page 2").
        Can be a list [1, 2, 3] or string range "1-3,5,10-".
        If None, converts all pages.
    password : str or None, default None
        Password for encrypted PDF documents.

    # Header detection parameters
    header_sample_pages : int | list[int] | None, default None
        Pages to sample for header font size analysis. If None, samples all pages.
    header_percentile_threshold : float, default 75
        Percentile threshold for header detection (e.g., 75 = top 25% of font sizes).
    header_min_occurrences : int, default 3
        Minimum occurrences of a font size to consider it for headers.
    header_size_allowlist : list[float] | None, default None
        Specific font sizes to always treat as headers.
    header_size_denylist : list[float] | None, default None
        Font sizes to never treat as headers.
    header_use_font_weight : bool, default True
        Consider bold/font weight when detecting headers.
    header_use_all_caps : bool, default True
        Consider all-caps text as potential headers.
    header_font_size_ratio : float, default 1.2
        Minimum ratio between header and body text font size.
    header_max_line_length : int, default 100
        Maximum character length for text to be considered a header.

    # Reading order and layout parameters
    detect_columns : bool, default True
        Enable multi-column layout detection.
    merge_hyphenated_words : bool, default True
        Merge words split by hyphens at line breaks.
    handle_rotated_text : bool, default True
        Process rotated text blocks.
    column_gap_threshold : float, default 20
        Minimum gap between columns in points.

    # Table detection parameters
    enable_table_fallback_detection : bool, default True
        Use heuristic fallback if PyMuPDF table detection fails.
    detect_merged_cells : bool, default True
        Attempt to identify merged cells in tables.
    table_ruling_line_threshold : float, default 0.5
        Threshold for detecting table ruling lines.

    image_placement_markers : bool, default True
        Add markers showing image positions.
    include_image_captions : bool, default True
        Try to extract image captions.

    include_page_numbers : bool, default False
        Include page numbers in output (automatically added to separator).
    page_separator_template : str, default "-----"
        Template for page separators between pages.
        Supports placeholders: {page_num}, {total_pages}.

    table_detection_mode : str, default "both"
        Table detection strategy: "pymupdf", "ruling", "both", or "none".
    image_format : str, default "png"
        Output format for extracted images: "png" or "jpeg".
    image_quality : int, default 90
        JPEG quality (1-100, only used when image_format="jpeg").

    trim_headers_footers : bool, default False
        Remove repeated headers and footers from pages.
    header_height : int, default 0
        Height in points to trim from top of page (requires trim_headers_footers).
    footer_height : int, default 0
        Height in points to trim from bottom of page (requires trim_headers_footers).
    skip_image_extraction : bool, default False
        Skip all image extraction for text-only conversion (improves performance for large PDFs).
    lazy_image_processing : bool, default False
        Placeholder for future lazy image loading support (currently no effect).

    Notes
    -----
    For large PDFs (hundreds of pages), consider using skip_image_extraction=True if you only need
    text content. This significantly reduces memory pressure by avoiding image decoding.
    Parallel processing (CLI --parallel flag) can further improve throughput for multi-file batches,
    but note that each worker process imports dependencies anew, adding startup overhead.

    Examples
    --------
    Convert only pages 1-3 with base64 images:
        >>> options = PdfOptions(pages=[1, 2, 3], attachment_mode="base64")
        >>> # Or using string range:
        >>> options = PdfOptions(pages="1-3", attachment_mode="base64")

    Convert with custom page separators:
        >>> options = PdfOptions(
        ...     page_separator_template="--- Page {page_num} of {total_pages} ---",
        ...     include_page_numbers=True
        ... )

    Configure header detection:
        >>> options = PdfOptions(
        ...     header_sample_pages=[0, 1, 2],
        ...     header_percentile_threshold=80,
        ...     header_use_all_caps=True
        ... )
    """

    pages: list[int] | str | None = field(
        default=None,
        metadata={
            "help": "Pages to convert. Supports ranges: '1-3,5,10-' or list like [1,2,3]. Always 1-based.",
            "type": str
        }
    )
    password: str | None = field(
        default=None,
        metadata={"help": "Password for encrypted PDF documents"}
    )

    # Header detection parameters
    header_sample_pages: int | list[int] | None = field(
        default=None,
        metadata={
            "help": "Pages to sample for header detection",
            "exclude_from_cli": True  # Complex type, exclude for now
        }
    )
    header_percentile_threshold: float = field(
        default=DEFAULT_HEADER_PERCENTILE_THRESHOLD,
        metadata={
            "help": "Percentile threshold for header detection",
            "type": float
        }
    )
    header_min_occurrences: int = field(
        default=DEFAULT_HEADER_MIN_OCCURRENCES,
        metadata={
            "help": "Minimum occurrences of a font size to consider for headers",
            "type": int
        }
    )
    header_size_allowlist: list[float] | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Complex type, exclude for now
    )
    header_size_denylist: list[float] | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Complex type, exclude for now
    )
    header_use_font_weight: bool = field(
        default=DEFAULT_HEADER_USE_FONT_WEIGHT,
        metadata={
            "help": "Consider bold/font weight when detecting headers",
            "cli_name": "no-header-use-font-weight"  # default=True, use --no-*
        }
    )
    header_use_all_caps: bool = field(
        default=DEFAULT_HEADER_USE_ALL_CAPS,
        metadata={
            "help": "Consider all-caps text as potential headers",
            "cli_name": "no-header-use-all-caps"  # default=True, use --no-*
        }
    )
    header_font_size_ratio: float = field(
        default=DEFAULT_HEADER_FONT_SIZE_RATIO,
        metadata={
            "help": "Minimum ratio between header and body text font size",
            "type": float
        }
    )
    header_max_line_length: int = field(
        default=DEFAULT_HEADER_MAX_LINE_LENGTH,
        metadata={
            "help": "Maximum character length for text to be considered a header",
            "type": int
        }
    )

    # Reading order and layout parameters
    detect_columns: bool = field(
        default=DEFAULT_DETECT_COLUMNS,
        metadata={
            "help": "Enable multi-column layout detection",
            "cli_name": "no-detect-columns"  # default=True, use --no-*
        }
    )
    merge_hyphenated_words: bool = field(
        default=DEFAULT_MERGE_HYPHENATED_WORDS,
        metadata={
            "help": "Merge words split by hyphens at line breaks",
            "cli_name": "no-merge-hyphenated-words"  # default=True, use --no-*
        }
    )
    handle_rotated_text: bool = field(
        default=DEFAULT_HANDLE_ROTATED_TEXT,
        metadata={
            "help": "Process rotated text blocks",
            "cli_name": "no-handle-rotated-text"  # default=True, use --no-*
        }
    )
    column_gap_threshold: float = field(
        default=DEFAULT_COLUMN_GAP_THRESHOLD,
        metadata={
            "help": "Minimum gap between columns in points",
            "type": float
        }
    )

    # Table detection parameters
    enable_table_fallback_detection: bool = field(
        default=DEFAULT_TABLE_FALLBACK_DETECTION,
        metadata={
            "help": "Use heuristic fallback if PyMuPDF table detection fails",
            "cli_name": "no-enable-table-fallback-detection"  # default=True, use --no-*
        }
    )
    detect_merged_cells: bool = field(
        default=DEFAULT_DETECT_MERGED_CELLS,
        metadata={
            "help": "Attempt to identify merged cells in tables",
            "cli_name": "no-detect-merged-cells"  # default=True, use --no-*
        }
    )
    table_ruling_line_threshold: float = field(
        default=DEFAULT_TABLE_RULING_LINE_THRESHOLD,
        metadata={
            "help": "Threshold for detecting table ruling lines",
            "type": float
        }
    )

    image_placement_markers: bool = field(
        default=DEFAULT_IMAGE_PLACEMENT_MARKERS,
        metadata={
            "help": "Add markers showing image positions",
            "cli_name": "no-image-placement-markers"  # default=True, use --no-*
        }
    )
    include_image_captions: bool = field(
        default=DEFAULT_INCLUDE_IMAGE_CAPTIONS,
        metadata={
            "help": "Try to extract image captions",
            "cli_name": "no-include-image-captions"  # default=True, use --no-*
        }
    )

    # Page number display and separators
    include_page_numbers: bool = field(
        default=DEFAULT_INCLUDE_PAGE_NUMBERS,
        metadata={
            "help": "Include page numbers in output (e.g., 'Page 1/10')"
        }
    )
    page_separator_template: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={
            "help": "Template for page separators. Supports placeholders: {page_num}, {total_pages}. "
                    "Use plain text without placeholders for simple separators."
        }
    )

    # Table detection mode
    table_detection_mode: str = field(
        default=DEFAULT_TABLE_DETECTION_MODE,
        metadata={
            "help": "Table detection strategy: 'pymupdf', 'ruling', 'both', or 'none'",
            "choices": ["pymupdf", "ruling", "both", "none"]
        }
    )

    # Image format options
    image_format: str = field(
        default=DEFAULT_IMAGE_FORMAT,
        metadata={
            "help": "Output format for extracted images: 'png' or 'jpeg'",
            "choices": ["png", "jpeg"]
        }
    )
    image_quality: int = field(
        default=DEFAULT_IMAGE_QUALITY,
        metadata={
            "help": "JPEG quality (1-100, only used when image_format='jpeg')",
            "type": int
        }
    )

    # Header/footer trimming
    trim_headers_footers: bool = field(
        default=DEFAULT_TRIM_HEADERS_FOOTERS,
        metadata={
            "help": "Remove repeated headers and footers from pages"
        }
    )
    header_height: int = field(
        default=DEFAULT_HEADER_HEIGHT,
        metadata={
            "help": "Height in points to trim from top of page (requires trim_headers_footers)",
            "type": int
        }
    )
    footer_height: int = field(
        default=DEFAULT_FOOTER_HEIGHT,
        metadata={
            "help": "Height in points to trim from bottom of page (requires trim_headers_footers)",
            "type": int
        }
    )

    # Performance optimization options
    skip_image_extraction: bool = field(
        default=False,
        metadata={
            "help": "Completely skip image extraction for text-only conversion (improves performance for large PDFs)"
        }
    )
    lazy_image_processing: bool = field(
        default=False,
        metadata={
            "help": "Placeholder for future lazy image loading support. Note: Full implementation would require "
                    "paginator interface for streaming large PDFs. Currently has no effect."
        }
    )


@dataclass(frozen=True)
class DocxOptions(BaseParserOptions):
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.

    Examples
    --------
    Convert with base64 image embedding:
        >>> options = DocxOptions(attachment_mode="base64")

    Convert with custom bullet symbols:
        >>> md_opts = MarkdownOptions(bullet_symbols="•→◦")
        >>> options = DocxOptions(markdown_options=md_opts)
    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )

    # Advanced DOCX options
    include_footnotes: bool = field(
        default=True,
        metadata={
            "help": "Include footnotes in output",
            "cli_name": "no-include-footnotes"
        }
    )
    include_endnotes: bool = field(
        default=True,
        metadata={
            "help": "Include endnotes in output",
            "cli_name": "no-include-endnotes"
        }
    )
    include_comments: bool = field(
        default=False,
        metadata={"help": "Include document comments in output"}
    )
    comments_position: Literal["inline", "footnotes"] = field(
        default="footnotes",
        metadata={
            "help": "Render comments inline or at document end",
            "choices": ["inline", "footnotes"],
        },
    )
    comment_mode: CommentMode = field(
        default=DEFAULT_COMMENT_MODE,
        metadata={
            "help": "How to render comments: html (HTML comments), blockquote (quoted blocks), ignore (skip)",
            "choices": ["html", "blockquote", "ignore"]
        }
    )
    include_image_captions: bool = field(
        default=True,
        metadata={
            "help": "Include image captions/descriptions in output",
            "cli_name": "no-include-image-captions"
        }
    )
    list_numbering_style: str = field(
        default="detect",
        metadata={
            "help": "List numbering style: detect, decimal, lowerroman, upperroman, loweralpha, upperalpha"
        }
    )


@dataclass(frozen=True)
class HtmlOptions(BaseParserOptions):
    """Configuration options for HTML-to-Markdown conversion.

    This dataclass contains settings specific to HTML document processing,
    including heading styles, title extraction, image handling, content
    sanitization, and advanced formatting options.

    Parameters
    ----------
    extract_title : bool, default False
        Whether to extract and use the HTML <title> element.
    convert_nbsp : bool, default False
        Whether to convert non-breaking spaces (&nbsp;) to regular spaces in the output.
    strip_dangerous_elements : bool, default False
        Whether to remove potentially dangerous HTML elements (script, style, etc.).
    detect_table_alignment : bool, default True
        Whether to automatically detect table column alignment from CSS/attributes.
    preserve_nested_structure : bool, default True
        Whether to maintain proper nesting for blockquotes and other elements.

    Examples
    --------
    Convert with underline-style headings:
        >>> md_opts = MarkdownOptions(use_hash_headings=False)
        >>> options = HtmlOptions(markdown_options=md_opts)

    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True)

    Convert with content sanitization:
        >>> options = HtmlOptions(strip_dangerous_elements=True, convert_nbsp=True)
    """

    extract_title: bool = field(
        default=DEFAULT_EXTRACT_TITLE,
        metadata={"help": "Extract and use HTML <title> element as main heading"}
    )
    convert_nbsp: bool = field(
        default=DEFAULT_CONVERT_NBSP,
        metadata={"help": "Convert non-breaking spaces (&nbsp;) to regular spaces"}
    )
    strip_dangerous_elements: bool = field(
        default=DEFAULT_STRIP_DANGEROUS_ELEMENTS,
        metadata={"help": "Remove potentially dangerous HTML elements (script, style, etc.)"}
    )
    detect_table_alignment: bool = field(
        default=DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT,
        metadata={
            "help": "Automatically detect table column alignment from CSS/attributes",
            "cli_name": "no-detect-table-alignment"  # default=True, use --no-*
        }
    )

    # Network security options
    network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for remote resource fetching",
            "exclude_from_cli": True  # Handled via flattened fields
        }
    )

    # Local file access options
    local_files: LocalFileAccessOptions = field(
        default_factory=LocalFileAccessOptions,
        metadata={
            "help": "Local file access security settings",
            "exclude_from_cli": True  # Handled via flattened fields
        }
    )

    preserve_nested_structure: bool = field(
        default=DEFAULT_PRESERVE_NESTED_STRUCTURE,
        metadata={
            "help": "Maintain proper nesting for blockquotes and other elements",
            "cli_name": "no-preserve-nested-structure"  # default=True, use --no-*
        }
    )

    # Advanced HTML processing options
    strip_comments: bool = field(
        default=True,
        metadata={
            "help": "Remove HTML comments from output",
            "cli_name": "no-strip-comments"
        },
    )
    collapse_whitespace: bool = field(
        default=True,
        metadata={
            "help": "Collapse multiple spaces/newlines into single spaces",
            "cli_name": "no-collapse-whitespace"
        }
    )
    br_handling: str = field(
        default="newline",
        metadata={"help": "How to handle <br> tags: 'newline' or 'space'"}
    )
    allowed_elements: tuple[str, ...] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML elements (if set, only these are processed)",
            "action": "append"
        }
    )
    allowed_attributes: tuple[str, ...] | None = field(
        default=None,
        metadata={
            "help": "Whitelist of allowed HTML attributes (if set, only these are processed)",
            "action": "append"
        }
    )
    figure_rendering: str = field(
        default="blockquote",
        metadata={
            "help": "How to render <figure> elements: blockquote, image_with_caption, html",
            "choices": ["blockquote", "image_with_caption", "html"]
        }
    )
    details_rendering: str = field(
        default="blockquote",
        metadata={
            "help": "How to render <details>/<summary> elements: blockquote, html, ignore",
            "choices": ["blockquote", "html", "ignore"]
        }
    )
    extract_microdata: bool = field(
        default=True,
        metadata={
            "help": "Extract microdata and structured data to metadata",
            "cli_name": "no-extract-microdata"
        }
    )


@dataclass(frozen=True)
class PptxOptions(BaseParserOptions):
    """Configuration options for PPTX-to-Markdown conversion.

    This dataclass contains settings specific to PowerPoint presentation
    processing, including slide numbering and image handling.

    Parameters
    ----------
    include_slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(include_slide_numbers=True, attachment_mode="base64")

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)
    """

    include_slide_numbers: bool = field(
        default=DEFAULT_SLIDE_NUMBERS,
        metadata={"help": "Include slide numbers in output"}
    )
    include_notes: bool = field(
        default=True,
        metadata={
            "help": "Include speaker notes from slides",
            "cli_name": "no-include-notes"
        }
    )
    page_separator_template: str = field(
        default=DEFAULT_PAGE_SEPARATOR,
        metadata={
            "help": "Template for slide separators. Supports placeholders: {page_num}, {total_pages}."
        }
    )

    # Advanced PPTX options
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)"}
    )
    charts_mode: str = field(
        default="data",
        metadata={
            "help": "Chart conversion mode: 'data' (tables), 'image' (screenshots), 'mermaid', or 'both'"
        }
    )
    include_titles_as_h2: bool = field(
        default=True,
        metadata={
            "help": "Include slide titles as H2 headings",
            "cli_name": "no-include-titles-as-h2"
        }
    )


@dataclass(frozen=True)
class EmlOptions(BaseParserOptions):
    """Configuration options for EML-to-Markdown conversion.

    This dataclass contains settings specific to email message processing,
    including robust parsing, date handling, quote processing, and URL cleaning.

    Parameters
    ----------
    include_headers : bool, default True
        Whether to include email headers (From, To, Subject, Date) in output.
    preserve_thread_structure : bool, default True
        Whether to maintain email thread/reply chain structure.
    date_format_mode : {"iso8601", "locale", "strftime"}, default "strftime"
        How to format dates in output:
        - "iso8601": Use ISO 8601 format (2023-01-01T10:00:00Z)
        - "locale": Use system locale-aware formatting
        - "strftime": Use custom strftime pattern
    date_strftime_pattern : str, default "%m/%d/%y %H:%M"
        Custom strftime pattern when date_format_mode is "strftime".
    convert_html_to_markdown : bool, default False
        Whether to convert HTML content to Markdown using html2markdown.
        When True, HTML parts are converted to Markdown; when False, HTML is preserved as-is.
    clean_quotes : bool, default True
        Whether to clean and normalize quoted content ("> " prefixes, etc.).
    detect_reply_separators : bool, default True
        Whether to detect common reply separators like "On <date>, <name> wrote:".
    normalize_headers : bool, default True
        Whether to normalize header casing and whitespace.
    preserve_raw_headers : bool, default False
        Whether to preserve both raw and decoded header values.
    clean_wrapped_urls : bool, default True
        Whether to clean URL defense/safety wrappers from links.
    url_wrappers : list[str], default from constants
        List of URL wrapper domains to clean (urldefense.com, safelinks, etc.).

    Examples
    --------
    Convert email with ISO 8601 date formatting:
        >>> options = EmlOptions(date_format_mode="iso8601")

    Convert with HTML-to-Markdown conversion enabled:
        >>> options = EmlOptions(convert_html_to_markdown=True)

    Disable quote cleaning and URL unwrapping:
        >>> options = EmlOptions(clean_quotes=False, clean_wrapped_urls=False)
    """

    include_headers: bool = field(
        default=True,
        metadata={
            "help": "Include email headers (From, To, Subject, Date) in output",
            "cli_name": "no-include-headers"
        }
    )
    preserve_thread_structure: bool = field(
        default=True,
        metadata={
            "help": "Maintain email thread/reply chain structure",
            "cli_name": "no-preserve-thread-structure"
        }
    )
    date_format_mode: DateFormatMode = field(
        default=DEFAULT_DATE_FORMAT_MODE,
        metadata={"help": "Date formatting mode: iso8601, locale, or strftime"}
    )
    date_strftime_pattern: str = field(
        default=DEFAULT_DATE_STRFTIME_PATTERN,
        metadata={"help": "Custom strftime pattern for date formatting"}
    )
    convert_html_to_markdown: bool = field(
        default=DEFAULT_CONVERT_HTML_TO_MARKDOWN,
        metadata={"help": "Convert HTML content to Markdown"}
    )
    clean_quotes: bool = field(
        default=DEFAULT_CLEAN_QUOTES,
        metadata={"help": "Clean and normalize quoted content"}
    )
    detect_reply_separators: bool = field(
        default=DEFAULT_DETECT_REPLY_SEPARATORS,
        metadata={"help": "Detect common reply separators"}
    )
    normalize_headers: bool = field(
        default=DEFAULT_NORMALIZE_HEADERS,
        metadata={"help": "Normalize header casing and whitespace"}
    )
    preserve_raw_headers: bool = field(
        default=DEFAULT_PRESERVE_RAW_HEADERS,
        metadata={"help": "Preserve both raw and decoded header values"}
    )
    clean_wrapped_urls: bool = field(
        default=DEFAULT_CLEAN_WRAPPED_URLS,
        metadata={"help": "Clean URL defense/safety wrappers from links"}
    )
    url_wrappers: list[str] | None = field(default_factory=lambda: DEFAULT_URL_WRAPPERS.copy())

    # Network security options for HTML conversion (when convert_html_to_markdown=True)
    html_network: NetworkFetchOptions = field(
        default_factory=NetworkFetchOptions,
        metadata={
            "help": "Network security settings for HTML part conversion",
            "exclude_from_cli": True  # Handled via flattened fields
        }
    )

    max_email_attachment_bytes: int = field(
        default=DEFAULT_MAX_ATTACHMENT_SIZE_BYTES,
        metadata={
            "help": "Maximum allowed size in bytes for email attachments",
            "type": int
        }
    )

    # Advanced EML options
    sort_order: str = field(
        default="asc",
        metadata={"help": "Email chain sort order: 'asc' (oldest first) or 'desc' (newest first)"}
    )
    subject_as_h1: bool = field(
        default=True,
        metadata={
            "help": "Include subject line as H1 heading",
            "cli_name": "no-subject-as-h1"
        }
    )
    include_attach_section_heading: bool = field(
        default=True,
        metadata={
            "help": "Include heading before attachments section",
            "cli_name": "no-include-attach-section-heading"
        }
    )
    attach_section_title: str = field(
        default="Attachments",
        metadata={"help": "Title for attachments section heading"}
    )
    include_html_parts: bool = field(
        default=True,
        metadata={
            "help": "Include HTML content parts from emails",
            "cli_name": "no-include-html-parts"
        }
    )
    include_plain_parts: bool = field(
        default=True,
        metadata={
            "help": "Include plain text content parts from emails",
            "cli_name": "no-include-plain-parts"
        }
    )


@dataclass(frozen=True)
class RtfOptions(BaseParserOptions):
    """Configuration options for RTF-to-Markdown conversion.

    This dataclass contains settings specific to Rich Text Format processing,
    primarily for handling embedded images and other attachments.

    Parameters
    ----------
    Inherited from `BaseParserOptions`
    """
    pass


@dataclass(frozen=True)
class IpynbOptions(BaseParserOptions):
    """Configuration options for IPYNB-to-Markdown conversion.

    This dataclass contains settings specific to Jupyter Notebook processing,
    including output handling and image conversion preferences.

    Parameters
    ----------
    include_inputs : bool, default True
        Whether to include cell input (source code) in output.
    include_outputs : bool, default True
        Whether to include cell outputs in the markdown.
    show_execution_count : bool, default False
        Whether to show execution counts for code cells.
    output_types : list[str] or None, default ["stream", "execute_result", "display_data"]
        Types of outputs to include. Valid types: "stream", "execute_result", "display_data", "error".
        If None, includes all output types.
    image_format : str, default "png"
        Preferred image format for notebook outputs. Options: "png", "jpeg".
    image_quality : int, default 85
        JPEG quality setting (1-100) when converting images to JPEG format.
    truncate_long_outputs : int or None, default DEFAULT_TRUNCATE_OUTPUT_LINES
        Maximum number of lines for text outputs before truncating.
        If None, outputs are not truncated.
    truncate_output_message : str or None, default DEFAULT_TRUNCATE_OUTPUT_MESSAGE
        The message to place to indicate truncated output.
    """

    include_inputs: bool = field(
        default=True,
        metadata={
            "help": "Include cell input (source code) in output",
            "cli_name": "no-include-inputs"
        }
    )
    include_outputs: bool = field(
        default=True,
        metadata={
            "help": "Include cell outputs in the markdown",
            "cli_name": "no-include-outputs"
        }
    )
    show_execution_count: bool = field(
        default=False,
        metadata={"help": "Show execution counts for code cells"}
    )
    output_types: tuple[str, ...] | None = field(
        default=("stream", "execute_result", "display_data"),
        metadata={
            "help": "Types of outputs to include (stream, execute_result, display_data, error)",
            "action": "append"
        }
    )
    image_format: str = field(
        default="png",
        metadata={"help": "Preferred image format for notebook outputs (png, jpeg)"}
    )
    image_quality: int = field(
        default=85,
        metadata={"help": "JPEG quality setting (1-100) for image conversion"}
    )
    truncate_long_outputs: int | None = DEFAULT_TRUNCATE_OUTPUT_LINES
    truncate_output_message: str | None = DEFAULT_TRUNCATE_OUTPUT_MESSAGE


@dataclass(frozen=True)
class OdtOptions(BaseParserOptions):
    """Configuration options for ODT-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Text (ODT)
    processing, including table preservation, footnotes, and comments.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    preserve_comments : bool, default False
        Whether to include document comments in output.
    include_footnotes : bool, default True
        Whether to include footnotes in output.
    include_endnotes : bool, default True
        Whether to include endnotes in output.
    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )
    preserve_comments: bool = field(
        default=False,
        metadata={"help": "Include document comments in output"}
    )
    include_footnotes: bool = field(
        default=True,
        metadata={
            "help": "Include footnotes in output",
            "cli_name": "no-include-footnotes"
        }
    )
    include_endnotes: bool = field(
        default=True,
        metadata={
            "help": "Include endnotes in output",
            "cli_name": "no-include-endnotes"
        }
    )


@dataclass(frozen=True)
class OdpOptions(BaseParserOptions):
    """Configuration options for ODP-to-Markdown conversion.

    This dataclass contains settings specific to OpenDocument Presentation (ODP)
    processing, including slide selection, numbering, and notes.

    Parameters
    ----------
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    include_slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    page_separator_template : str, default "---"
        Template for slide separators. Supports placeholders: {page_num}, {total_pages}.
    slides : str or None, default None
        Slide selection (e.g., "1,3-5,8" for slides 1, 3-5, and 8).
    """

    preserve_tables: bool = field(
        default=True,
        metadata={
            "help": "Preserve table formatting in Markdown",
            "cli_name": "no-preserve-tables"
        }
    )
    include_slide_numbers: bool = field(
        default=False,
        metadata={"help": "Include slide numbers in output"}
    )
    include_notes: bool = field(
        default=True,
        metadata={
            "help": "Include speaker notes from slides",
            "cli_name": "no-include-notes"
        }
    )
    page_separator_template: str = field(
        default="---",
        metadata={
            "help": "Template for slide separators. Supports placeholders: {page_num}, {total_pages}."
        }
    )
    slides: str | None = field(
        default=None,
        metadata={"help": "Slide selection (e.g., '1,3-5,8' for slides 1, 3-5, and 8)"}
    )


@dataclass(frozen=True)
class EpubOptions(BaseParserOptions):
    """Configuration options for EPUB-to-Markdown conversion.

    This dataclass contains settings specific to EPUB document processing,
    including chapter handling, table of contents generation, and image handling.

    Parameters
    ----------
    merge_chapters : bool, default True
        Whether to merge chapters into a single continuous document. If False,
        a separator is placed between chapters.
    include_toc : bool, default True
        Whether to generate and prepend a Markdown Table of Contents.
    """

    merge_chapters: bool = field(
        default=True,
        metadata={
            "help": "Merge chapters into a single continuous document",
            "cli_name": "no-merge-chapters"
        }
    )
    include_toc: bool = field(
        default=True,
        metadata={
            "help": "Generate and prepend a Markdown Table of Contents",
            "cli_name": "no-include-toc"
        }
    )

    html_options: HtmlOptions | None = field(
        default=None,
        metadata={"exclude_from_cli": True}  # Special field, handled separately
    )


@dataclass(frozen=True)
class MhtmlOptions(HtmlOptions):
    """Configuration options for MHTML-to-Markdown conversion.

    This dataclass contains settings specific to MHTML file processing,
    primarily for handling embedded assets like images and local file security.

    Parameters
    ----------
    Inherited from HtmlOptions
    """
    pass


@dataclass(frozen=True)
class XlsxOptions(BaseParserOptions):
    """Configuration options for XLSX spreadsheet conversion.

    This dataclass contains settings specific to Excel XLSX file processing,
    including sheet selection, cell formatting, and data limits.

    Parameters
    ----------
    sheets : list[str] | str | None, default None
        List of exact sheet names to include or a regex pattern.
        If None, includes all sheets.
    include_sheet_titles : bool, default True
        Prepend each sheet with a '## {sheet_name}' heading.
    render_formulas : bool, default True
        When True, uses stored values (data_only=True). When False, shows formulas.
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    preserve_newlines_in_cells : bool, default False
        Preserve line breaks within cells as <br> tags.
    trim_empty : str, default "trailing"
        Trim empty rows/columns: none, leading, trailing, or both.
    header_case : str, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    detect_merged_cells : bool, default True
        Attempt to handle merged cells.
    """

    sheets: Union[list[str], str, None] = None
    include_sheet_titles: bool = True
    render_formulas: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."

    preserve_newlines_in_cells: bool = field(
        default=False,
        metadata={"help": "Preserve line breaks within cells as <br> tags"}
    )
    trim_empty: str = field(
        default="trailing",
        metadata={"help": "Trim empty rows/columns: none, leading, trailing, or both"}
    )
    header_case: str = field(
        default="preserve",
        metadata={"help": "Transform header case: preserve, title, upper, or lower"}
    )
    detect_merged_cells: bool = field(
        default=True,
        metadata={"help": "Attempt to handle merged cells"}
    )


@dataclass(frozen=True)
class OdsSpreadsheetOptions(BaseParserOptions):
    """Configuration options for ODS spreadsheet conversion.

    This dataclass contains settings specific to OpenDocument Spreadsheet
    file processing, including sheet selection and data limits.

    Parameters
    ----------
    sheets : list[str] | str | None, default None
        List of exact sheet names to include or a regex pattern.
        If None, includes all sheets.
    include_sheet_titles : bool, default True
        Prepend each sheet with a '## {sheet_name}' heading.
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    preserve_newlines_in_cells : bool, default False
        Preserve line breaks within cells as <br> tags.
    trim_empty : str, default "trailing"
        Trim empty rows/columns: none, leading, trailing, or both.
    header_case : str, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    has_header : bool, default True
        Whether the first row contains column headers.
    """

    sheets: Union[list[str], str, None] = None
    include_sheet_titles: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."
    has_header: bool = True

    preserve_newlines_in_cells: bool = field(
        default=False,
        metadata={"help": "Preserve line breaks within cells as <br> tags"}
    )
    trim_empty: str = field(
        default="trailing",
        metadata={"help": "Trim empty rows/columns: none, leading, trailing, or both"}
    )
    header_case: str = field(
        default="preserve",
        metadata={"help": "Transform header case: preserve, title, upper, or lower"}
    )


@dataclass(frozen=True)
class CsvOptions(BaseParserOptions):
    """Configuration options for CSV/TSV conversion.

    This dataclass contains settings specific to delimiter-separated value
    file processing, including dialect detection and data limits.

    Parameters
    ----------
    detect_csv_dialect : bool, default True
        Enable csv.Sniffer-based dialect detection (ignored if csv_delimiter is set).
    csv_delimiter : str | None, default None
        Override CSV/TSV delimiter (e.g., ',', '\\t', ';', '|').
        When set, disables dialect detection.
    has_header : bool, default True
        Whether the first row contains column headers.
        When False, generates generic headers (Column 1, Column 2, etc.).
    max_rows : int | None, default None
        Maximum number of data rows per table (excluding header). None = unlimited.
    max_cols : int | None, default None
        Maximum number of columns per table. None = unlimited.
    truncation_indicator : str, default "..."
        Appended note when rows/columns are truncated.
    header_case : str, default "preserve"
        Transform header case: preserve, title, upper, or lower.
    skip_empty_rows : bool, default True
        Whether to skip completely empty rows.
    strip_whitespace : bool, default False
        Whether to strip leading/trailing whitespace from all cells.
    """

    detect_csv_dialect: bool = True
    csv_delimiter: Optional[str] = None
    has_header: bool = True
    max_rows: Optional[int] = None
    max_cols: Optional[int] = None
    truncation_indicator: str = "..."

    header_case: str = field(
        default="preserve",
        metadata={"help": "Transform header case: preserve, title, upper, or lower"}
    )
    skip_empty_rows: bool = field(
        default=True,
        metadata={"help": "Skip completely empty rows"}
    )
    strip_whitespace: bool = field(
        default=False,
        metadata={"help": "Strip leading/trailing whitespace from all cells"}
    )


@dataclass(frozen=True)
class SourceCodeOptions(BaseParserOptions):
    """Configuration options for source code to Markdown conversion.

    This dataclass contains settings specific to source code file processing,
    including language detection, formatting options, and output customization.

    Parameters
    ----------
    detect_language : bool, default True
        Whether to automatically detect programming language from file extension.
        When enabled, uses file extension to determine appropriate syntax highlighting
        language identifier for the Markdown code block.
    language_override : str or None, default None
        Manual override for the language identifier. When provided, this language
        will be used instead of automatic detection. Useful for files with
        non-standard extensions or when forcing a specific syntax highlighting.
    include_filename : bool, default False
        Whether to include the original filename as a comment at the top of the
        code block. The comment style is automatically chosen based on the
        detected or specified language.
    """

    detect_language: bool = field(
        default=True,
        metadata={
            "help": "Automatically detect programming language from file extension",
            "cli_name": "no-detect-language"
        }
    )

    language_override: Optional[str] = field(
        default=None,
        metadata={
            "help": "Override language identifier for syntax highlighting",
            "cli_name": "language"
        }
    )

    include_filename: bool = field(
        default=False,
        metadata={
            "help": "Include filename as comment in code block",
            "cli_name": "include-filename"
        }
    )


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
        default=DEFAULT_FLAVOR,  # type: ignore[arg-type]
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
    """

    heading_chars: str = field(
        default=DEFAULT_RST_HEADING_CHARS,
        metadata={
            "help": "Characters for heading underlines (h1-h5)"
        }
    )
    table_style: RstTableStyle = field(
        default=DEFAULT_RST_TABLE_STYLE,  # type: ignore[arg-type]
        metadata={
            "help": "Table rendering style",
            "choices": ["grid", "simple"]
        }
    )
    code_directive_style: RstCodeStyle = field(
        default=DEFAULT_RST_CODE_STYLE,  # type: ignore[arg-type]
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
            f"Flavor 'commonmark' does not support strikethrough. "
            f"Using unsupported_inline_mode='force' will render ~~text~~ "
            f"which is not valid CommonMark."
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


def create_updated_options(options: Any, **kwargs: Any) -> Any:
    """Create a new options instance with updated values.

    This helper function supports the immutable pattern for frozen dataclasses.
    It creates a new instance of the options with the specified fields updated,
    rather than modifying the existing instance.

    Parameters
    ----------
    options : Any
        The original options instance (must be a dataclass)
    **kwargs
        Keyword arguments with the field names and new values to update

    Returns
    -------
    Any
        A new options instance with the updated values

    Examples
    --------
    >>> original = PdfOptions(pages=[1, 2, 3])
    >>> updated = create_updated_options(original, attachment_mode="base64", pages=[1])
    >>> # original remains unchanged, updated has new values
    """
    return replace(options, **kwargs)
