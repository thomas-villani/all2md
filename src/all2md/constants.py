#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Constants and default values for all2md library.

This module centralizes all hardcoded values, magic numbers, and default
configuration constants used across the all2md library. This improves
maintainability and discoverability of configurable parameters.

Constants are organized by category:
1. Type Definitions - All Literal types and type aliases
2. General Markdown Formatting - Basic markdown output settings
3. Conversion Behavior - General conversion options
4. Security Constants - Security and sanitization settings
5. Format-Specific Constants - Settings for each supported format
6. File Extensions and Format Detection - File type identification
"""

from __future__ import annotations

from typing import Literal

# =============================================================================
# Type Definitions - All Literal Types and Type Aliases
# =============================================================================

# Markdown formatting types
EmphasisSymbol = Literal["*", "_"]
UnderlineMode = Literal["html", "markdown", "ignore"]
SuperscriptMode = Literal["html", "markdown", "ignore"]
SubscriptMode = Literal["html", "markdown", "ignore"]
MathMode = Literal["latex", "mathml", "html"]
LinkStyleType = Literal["inline", "reference"]
ReferenceLinkPlacement = Literal["end_of_document", "after_block"]
CodeFenceChar = Literal["`", "~"]

# Markdown flavor and compatibility types
FlavorType = Literal["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
UnsupportedTableMode = Literal["drop", "ascii", "force", "html"]
UnsupportedInlineMode = Literal["plain", "force", "html"]
HtmlPassthroughMode = Literal["pass-through", "escape", "drop", "sanitize"]
MetadataFormatType = Literal["yaml", "toml", "json"]
HeaderCaseOption = Literal["preserve", "title", "upper", "lower"]

# Asset and attachment handling types
AttachmentMode = Literal["skip", "alt_text", "save", "base64"]
AltTextMode = Literal["default", "plain_filename", "strict_markdown", "footnote"]

# Network security - robots.txt policy types
RobotsTxtPolicy = Literal["strict", "warn", "ignore"]

# Comment handling types (general and format-specific)
CommentMode = Literal["html", "blockquote", "ignore"]
HtmlCommentMode = Literal["native", "visible", "ignore"]
DocxCommentMode = Literal["native", "visible", "ignore"]
LatexCommentMode = Literal["percent", "todonotes", "marginnote", "ignore"]
OdtCommentMode = Literal["native", "visible", "ignore"]
PptxCommentMode = Literal["speaker_notes", "visible", "ignore"]
PptxParserCommentMode = Literal["content", "comment", "ignore"]
OdpCommentMode = Literal["native", "visible", "ignore"]
RtfCommentMode = Literal["bracketed", "ignore"]
AsciiDocCommentMode = Literal["comment", "note", "ignore"]
RstCommentMode = Literal["comment", "note", "ignore"]
OrgCommentMode = Literal["comment", "drawer", "ignore"]
MediaWikiCommentMode = Literal["html", "visible", "ignore"]
TextileCommentMode = Literal["html", "blockquote", "ignore"]
DokuWikiCommentMode = Literal["html", "visible", "ignore"]
PlainTextCommentMode = Literal["visible", "ignore"]
PdfCommentMode = Literal["visible", "ignore"]
CommentType = Literal["html", "docx_review", "latex", "code", "wiki", "generic"]
CommentRenderMode = Literal["preserve", "convert", "strip"]

# PDF-specific types
PageSize = Literal["letter", "a4", "legal"]
ColumnDetectionMode = Literal["auto", "force_single", "force_multi", "disabled"]
TableExtractionMode = Literal["none", "grid", "text_clustering"]
TableDetectionMode = Literal["pymupdf", "ruling", "both", "none"]
ImageFormat = Literal["png", "jpeg"]
OCRMode = Literal["auto", "force", "off"]

# Email-specific types
DateFormatMode = Literal["iso8601", "locale", "strftime"]
OutputStructureMode = Literal["flat", "hierarchical"]
MailboxFormatType = Literal["auto", "mbox", "maildir", "mh", "babyl", "mmdf"]

# Evernote (ENEX) types
TagsFormatMode = Literal["frontmatter", "inline", "heading", "skip"]
NoteSortMode = Literal["created", "updated", "title", "none"]

# Wiki markup types
MediaWikiImageCaptionMode = Literal["auto", "alt_only", "caption_only"]

# Org-Mode types
OrgHeadingStyle = Literal["stars"]
OrgTodoKeywordSet = Literal["default", "custom"]

# reStructuredText types
RstTableStyle = Literal["grid", "simple"]
RstCodeStyle = Literal["double_colon", "directive"]
RstLineBreakMode = Literal["line_block", "raw"]

# BBCode types
BBCodeUnknownTagMode = Literal["preserve", "strip", "escape"]

# Email types
EmailSortOrder = Literal["asc", "desc"]

# AsciiDoc types
AttributeMissingPolicy = Literal["keep", "blank", "warn"]
TableHeaderDetection = Literal["first-row", "attribute-based", "auto"]

# RTF types
RtfFontFamily = Literal["roman", "swiss"]

# LaTeX types
LatexMathRenderMode = Literal["inline", "display"]

# Jinja types
JinjaEscapeStrategy = Literal["xml", "html", "latex", "yaml", "markdown", "none", "custom"]
JinjaRenderFormat = Literal["markdown", "plain", "html"]

# Jupyter Notebook (IPYNB) types
IpynbOutputType = Literal["stream", "execute_result", "display_data", "error"]

# CSV types
MultiTableMode = Literal["first", "all", "error"]
CsvQuotingMode = Literal["minimal", "all", "nonnumeric", "none"]
MergedCellHandling = Literal["repeat", "blank", "placeholder"]

# DOCX types
DocxCommentsPosition = Literal["inline", "footnotes"]

# AST JSON types
AstJsonIndent = int | None

# Archive types
AttachmentOverwriteMode = Literal["unique", "overwrite", "skip"]

# PPTX types
SlideSplitMode = Literal["separator", "heading", "auto"]
ChartsMode = Literal["data", "mermaid", "both"]

# Spreadsheet types
ChartMode = Literal["data", "skip"]
MergedCellMode = Literal["spans", "flatten", "skip"]
TrimEmptyMode = Literal["none", "leading", "trailing", "both"]

# HTML renderer types
CssStyle = Literal["inline", "embedded", "external", "none"]
MathRenderer = Literal["mathjax", "katex", "none"]
TemplateMode = Literal["inject", "replace", "jinja"]
InjectionMode = Literal["append", "prepend", "replace"]

# HTML parser types
FiguresParsing = Literal["blockquote", "paragraph", "image_with_caption", "caption_only", "html", "skip"]
DetailsParsing = Literal["blockquote", "paragraph", "html", "skip"]
BrHandling = Literal["newline", "space"]
HtmlParser = Literal["html.parser", "html5lib", "lxml"]

# Auto-generated from converter registry.
# To update: python scripts/update_document_formats.py --update
# Used for type hints, CLI autocomplete, and API documentation
DocumentFormat = Literal[
    "auto",
    "archive",
    "asciidoc",
    "ast",
    "bbcode",
    "chm",
    "csv",
    "docx",
    "dokuwiki",
    "eml",
    "enex",
    "epub",
    "fb2",
    "html",
    "ini",
    "ipynb",
    "jinja",
    "json",
    "latex",
    "markdown",
    "mbox",
    "mediawiki",
    "mhtml",
    "odp",
    "ods",
    "odt",
    "openapi",
    "org",
    "outlook",
    "pdf",
    "plaintext",
    "pptx",
    "rst",
    "rtf",
    "sourcecode",
    "textile",
    "toml",
    "webarchive",
    "xlsx",
    "yaml",
    "zip",
]

# =============================================================================
# Dependency Specifications for @requires_dependencies decorator
# =============================================================================
# Each spec is a list of tuples: (pip_package, import_name, version_constraint)
# These are used with the @requires_dependencies decorator to check for optional deps

# Document parsers
DEPS_CHM = [("pychm", "chm", "")]
DEPS_DOCX = [("python-docx", "docx", "")]
DEPS_EPUB = [("ebooklib", "ebooklib", "")]
DEPS_HTML = [("beautifulsoup4", "bs4", ">=4.14.2")]
DEPS_HTML_READABILITY = [("readability-lxml", "readability", ">=0.8.1")]
DEPS_MARKDOWN = [("mistune", "mistune", ">=3.0.0")]
DEPS_MEDIAWIKI = [("mwparserfromhell", "mwparserfromhell", "")]
DEPS_MHTML = [("beautifulsoup4", "bs4", "")]
DEPS_ODF = [("odfpy", "odf", "")]  # Used by ODP, ODS, ODT
DEPS_OPENAPI = [("PyYAML", "yaml", ">=5.1")]
DEPS_ORG = [("orgparse", "orgparse", "")]
DEPS_OUTLOOK = [("extract-msg", "extract_msg", "")]
DEPS_PDF = [("pymupdf", "fitz", ">=1.26.4")]
DEPS_PPTX = [("python-pptx", "pptx", ">=1.0.2")]
DEPS_RST = [("docutils", "docutils", ">=0.18")]
DEPS_RTF = [("pyth3", "pyth", "")]
DEPS_TEXTILE = [("textile", "textile", "")]
DEPS_TOML = [("tomli-w", "tomli_w", ">=1.0.0")]
DEPS_WEBARCHIVE = [("beautifulsoup4", "bs4", "")]
DEPS_XLSX = [("openpyxl", "openpyxl", "")]
DEPS_YAML = [("pyyaml", "yaml", ">=6.0")]
DEPS_FB2 = [("lxml", "lxml", "")]
DEPS_ENEX = [("lxml", "lxml", "")]

# PDF-specific optional dependencies (beyond base pymupdf)
DEPS_PDF_LANGDETECT = [("langdetect", "langdetect", ">=1.0.9")]
DEPS_PDF_OCR = [("pytesseract", "pytesseract", ">=0.3.10"), ("Pillow", "PIL", ">=9.0.0")]

# Document renderers (may have different version requirements than parsers)
DEPS_DOCX_RENDER = [("python-docx", "docx", ">=1.2.0")]
DEPS_EPUB_RENDER = [("ebooklib", "ebooklib", ">=0.17")]
DEPS_ODF_RENDER = [("odfpy", "odf", "")]  # Used by ODP and ODT renderers
DEPS_PDF_RENDER = [("reportlab", "reportlab", ">=4.0.0")]
DEPS_PPTX_RENDER = [("python-pptx", "pptx", ">=0.6.21")]
DEPS_RTF_RENDER = [("pyth3", "pyth", ">=0.7"), ("six", "six", ">=1.16.0")]

# Utilities
DEPS_JINJA = [("jinja2", "jinja2", ">=3.1.0")]
DEPS_NETWORK = [("httpx", "httpx", ">=0.28.1")]

# Search backends
DEPS_SEARCH_BM25 = [("rank-bm25", "rank_bm25", ">=0.2.2")]

DEPS_SEARCH_VECTOR = [
    ("faiss-cpu", "faiss", ""),
    ("sentence-transformers", "sentence_transformers", ">=2.2.0"),
    ("numpy", "numpy", ">=1.24.0"),
]

# =============================================================================
# General Markdown Formatting Constants
# =============================================================================

# Basic formatting defaults
DEFAULT_PAGE_SEPARATOR = "-----"
DEFAULT_LIST_INDENT_WIDTH = 4
DEFAULT_TABLE_ALIGNMENT = "left"

# Emphasis and special character handling
DEFAULT_EMPHASIS_SYMBOL = "*"
DEFAULT_BULLET_SYMBOLS = "*-+"
MARKDOWN_SPECIAL_CHARS = "*_#[]()\\"

# Heading and structure defaults
DEFAULT_USE_HASH_HEADINGS = True
DEFAULT_HEADING_LEVEL_OFFSET = 0
DEFAULT_PRESERVE_NESTED_STRUCTURE = True

# Code block formatting
DEFAULT_CODE_FENCE_CHAR: CodeFenceChar = "`"
DEFAULT_CODE_FENCE_MIN = 3
MIN_CODE_FENCE_LENGTH = 3
MAX_CODE_FENCE_LENGTH = 10

# Code fence language identifier security (markdown injection prevention)
SAFE_LANGUAGE_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_+\-]+$"
MAX_LANGUAGE_IDENTIFIER_LENGTH = 50

# Link formatting
DEFAULT_LINK_STYLE: LinkStyleType = "inline"
DEFAULT_REFERENCE_LINK_PLACEMENT: ReferenceLinkPlacement = "end_of_document"
DEFAULT_AUTOLINK_BARE_URLS = False

# Table formatting
DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT = True
DEFAULT_TABLE_PIPE_ESCAPE = True
TABLE_ALIGNMENT_MAPPING = {"left": ":---", "center": ":---:", "right": "---:", "justify": ":---"}

# Text processing
DEFAULT_COLLAPSE_BLANK_LINES = True
DEFAULT_ESCAPE_SPECIAL = True

# Font and layout thresholds (for format detection in PDF/DOCX)
DEFAULT_FONT_SIZE_THRESHOLD_PT = 36
DEFAULT_INDENTATION_PT_PER_LEVEL = 36
DEFAULT_OVERLAP_THRESHOLD_PERCENT = 70
DEFAULT_OVERLAP_THRESHOLD_PX = 5
DEFAULT_LINK_OVERLAP_THRESHOLD = 70.0  # Percentage overlap required for link detection (0-100)

# =============================================================================
# Conversion Behavior Constants
# =============================================================================

# Metadata handling
DEFAULT_EXTRACT_TITLE = False
DEFAULT_EXTRACT_METADATA = False
DEFAULT_INCLUDE_METADATA_FRONTMATTER = False
DEFAULT_METADATA_FORMAT: MetadataFormatType = "yaml"

# Asset and attachment handling
DEFAULT_ATTACHMENT_MODE: AttachmentMode = "alt_text"
DEFAULT_ALT_TEXT_MODE: AltTextMode = "default"
DEFAULT_ATTACHMENT_OUTPUT_DIR = None
DEFAULT_ATTACHMENT_BASE_URL = None

# Comment handling defaults (general)
DEFAULT_COMMENT_MODE: CommentMode = "blockquote"
DEFAULT_COMMENT_RENDER_MODE: CommentRenderMode = "preserve"

# Comment handling defaults (format-specific)
DEFAULT_HTML_COMMENT_MODE: HtmlCommentMode = "native"
DEFAULT_DOCX_COMMENT_MODE: DocxCommentMode = "native"
DEFAULT_LATEX_COMMENT_MODE: LatexCommentMode = "percent"
DEFAULT_ODT_COMMENT_MODE: OdtCommentMode = "native"
DEFAULT_PPTX_COMMENT_MODE: PptxCommentMode = "speaker_notes"
DEFAULT_PPTX_PARSER_COMMENT_MODE: PptxParserCommentMode = "content"
DEFAULT_ODP_COMMENT_MODE: OdpCommentMode = "native"
DEFAULT_RTF_COMMENT_MODE: RtfCommentMode = "bracketed"
DEFAULT_ASCIIDOC_COMMENT_MODE: AsciiDocCommentMode = "comment"
DEFAULT_RST_COMMENT_MODE: RstCommentMode = "comment"
DEFAULT_ORG_COMMENT_MODE: OrgCommentMode = "comment"
DEFAULT_MEDIAWIKI_COMMENT_MODE: MediaWikiCommentMode = "html"
DEFAULT_TEXTILE_COMMENT_MODE: TextileCommentMode = "html"
DEFAULT_DOKUWIKI_COMMENT_MODE: DokuWikiCommentMode = "html"
DEFAULT_PLAINTEXT_COMMENT_MODE: PlainTextCommentMode = "ignore"
DEFAULT_PDF_COMMENT_MODE: PdfCommentMode = "ignore"

# Flavor and compatibility settings
DEFAULT_FLAVOR: FlavorType = "gfm"
# Use "force" as flavor-naive default (most markdown-like, works in most parsers)
# Flavor-specific defaults are applied via get_flavor_defaults() when flavor is chosen
DEFAULT_UNSUPPORTED_TABLE_MODE: UnsupportedTableMode = "force"
DEFAULT_UNSUPPORTED_INLINE_MODE: UnsupportedInlineMode = "force"
DEFAULT_MATH_MODE: MathMode = "latex"
DEFAULT_HTML_PASSTHROUGH_MODE: HtmlPassthroughMode = "escape"
HTML_PASSTHROUGH_MODES = ["pass-through", "escape", "drop", "sanitize"]
DEFAULT_MARKDOWN_HTML_PASSTHROUGH_MODE: HtmlPassthroughMode = "escape"  # Secure by default

# Boilerplate text removal patterns (used by RemoveBoilerplateTextTransform)
DEFAULT_BOILERPLATE_PATTERNS = [
    r"^CONFIDENTIAL$",
    r"^Page \d+ of \d+$",
    r"^Internal Use Only$",
    r"^\[DRAFT\]$",
    r"^Copyright \d{4}",
    r"^Printed on \d{4}-\d{2}-\d{2}$",
]

# Network and remote resource handling
DEFAULT_USER_AGENT = "all2md-fetcher/1.0"

# robots.txt handling
ROBOTS_TXT_POLICY_CHOICES = ("strict", "warn", "ignore")
DEFAULT_ROBOTS_TXT_POLICY: RobotsTxtPolicy = "strict"
DEFAULT_ROBOTS_TXT_CACHE_DURATION = 3600  # 1 hour in seconds

# =============================================================================
# Security Constants
# =============================================================================

# HTML security - Dangerous elements and attributes
DANGEROUS_HTML_ELEMENTS = {"script", "style", "object", "embed", "form", "input", "iframe"}

# HTML5 Event Handler Attributes - Comprehensive list of all on* attributes
# These can execute JavaScript and pose XSS risks if user-controlled
# See: https://developer.mozilla.org/en-US/docs/Web/Events
DANGEROUS_HTML_ATTRIBUTES = frozenset(
    {
        # Original set (preserved for backward compatibility documentation)
        "onclick",
        "onload",
        "onerror",
        "onmouseover",
        "onfocus",
        "onblur",
        # Window Events
        "onafterprint",
        "onbeforeprint",
        "onbeforeunload",
        "onhashchange",
        "onmessage",
        "onoffline",
        "ononline",
        "onpagehide",
        "onpageshow",
        "onpopstate",
        "onstorage",
        "onunload",
        # Form Events
        "onchange",
        "oninput",
        "oninvalid",
        "onreset",
        "onsearch",
        "onselect",
        "onsubmit",
        # Keyboard Events
        "onkeydown",
        "onkeypress",
        "onkeyup",
        # Mouse Events
        "onmousedown",
        "onmouseenter",
        "onmouseleave",
        "onmousemove",
        "onmouseout",
        "onmouseup",
        "onmousewheel",
        "onwheel",
        "oncontextmenu",
        # Drag Events
        "ondrag",
        "ondragend",
        "ondragenter",
        "ondragleave",
        "ondragover",
        "ondragstart",
        "ondrop",
        # Clipboard Events
        "oncopy",
        "oncut",
        "onpaste",
        # Media Events
        "onabort",
        "oncanplay",
        "oncanplaythrough",
        "oncuechange",
        "ondurationchange",
        "onemptied",
        "onended",
        "onloadeddata",
        "onloadedmetadata",
        "onloadstart",
        "onpause",
        "onplay",
        "onplaying",
        "onprogress",
        "onratechange",
        "onseeked",
        "onseeking",
        "onstalled",
        "onsuspend",
        "ontimeupdate",
        "onvolumechange",
        "onwaiting",
        # Animation/Transition Events
        "onanimationend",
        "onanimationiteration",
        "onanimationstart",
        "ontransitionend",
        # Other Events
        "onscroll",
        "onresize",
        "ontoggle",
        "onshow",
        "onclose",
    }
)

# Framework-specific attributes that can execute code in JavaScript framework contexts
# These are only dangerous if the HTML will be rendered in a browser with these frameworks
# By default, these are NOT stripped unless strip_framework_attributes=True
FRAMEWORK_ATTRIBUTES = frozenset(
    {
        # Alpine.js attributes
        "x-data",
        "x-init",
        "x-show",
        "x-bind",
        "x-on",
        "x-text",
        "x-html",
        "x-model",
        "x-if",
        "x-for",
        "x-transition",
        "x-effect",
        "x-ignore",
        "x-ref",
        "x-cloak",
        "x-teleport",
        "x-modelable",
        # Vue.js attributes (v-* and shorthand @:)
        "v-bind",
        "v-on",
        "v-model",
        "v-if",
        "v-else",
        "v-else-if",
        "v-for",
        "v-show",
        "v-html",
        "v-text",
        "v-once",
        "v-pre",
        "v-cloak",
        "v-slot",
        # Angular attributes
        "ng-app",
        "ng-bind",
        "ng-bind-html",
        "ng-bind-template",
        "ng-blur",
        "ng-change",
        "ng-checked",
        "ng-class",
        "ng-click",
        "ng-controller",
        "ng-copy",
        "ng-cut",
        "ng-dblclick",
        "ng-disabled",
        "ng-focus",
        "ng-form",
        "ng-hide",
        "ng-href",
        "ng-if",
        "ng-include",
        "ng-init",
        "ng-keydown",
        "ng-keypress",
        "ng-keyup",
        "ng-list",
        "ng-model",
        "ng-mousedown",
        "ng-mouseenter",
        "ng-mouseleave",
        "ng-mousemove",
        "ng-mouseover",
        "ng-mouseup",
        "ng-non-bindable",
        "ng-paste",
        "ng-readonly",
        "ng-repeat",
        "ng-selected",
        "ng-show",
        "ng-src",
        "ng-style",
        "ng-submit",
        "ng-switch",
        "ng-transclude",
        "ng-value",
        # HTMX attributes
        "hx-get",
        "hx-post",
        "hx-put",
        "hx-patch",
        "hx-delete",
        "hx-trigger",
        "hx-target",
        "hx-swap",
        "hx-vals",
        "hx-boost",
        "hx-push-url",
        "hx-select",
        "hx-indicator",
        "hx-params",
        "hx-headers",
        "hx-confirm",
        "hx-on",
    }
)

# Attribute prefixes that indicate framework-specific bindings
# Used for pattern matching (e.g., @click, :href, [attr], (event))
FRAMEWORK_ATTRIBUTE_PREFIXES = frozenset(
    {
        "x-",  # Alpine.js
        "v-",  # Vue.js
        "@",  # Vue.js shorthand for v-on
        ":",  # Vue.js shorthand for v-bind
        "ng-",  # Angular
        "[",  # Angular property binding
        "(",  # Angular event binding
        "hx-",  # HTMX
        "data-x-",  # Alpine.js with data prefix
        "data-v-",  # Vue.js with data prefix
        "data-ng-",  # Angular with data prefix
        "data-hx-",  # HTMX with data prefix
    }
)

# URL scheme security
DANGEROUS_SCHEMES = {
    "javascript:",
    "vbscript:",
    "data:text/html",
    "data:text/javascript",
    "data:application/javascript",
    "data:application/x-javascript",
}
SAFE_LINK_SCHEMES = frozenset({"http", "https", "mailto", "ftp", "ftps", "tel", "sms", ""})

# Content sanitization defaults
DEFAULT_STRIP_DANGEROUS_ELEMENTS = False
DEFAULT_STRIP_FRAMEWORK_ATTRIBUTES = False

# HTML rendering security defaults
DEFAULT_ALLOW_REMOTE_SCRIPTS = False  # Secure by default - require opt-in for CDN scripts
DEFAULT_CSP_ENABLED = True  # Secure by default - enable CSP protection for standalone HTML
DEFAULT_CSP_POLICY = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';"

# Local file security
DEFAULT_ALLOW_LOCAL_FILES = False
DEFAULT_ALLOW_CWD_FILES = False

# Network security (SSRF protection)
DEFAULT_ALLOW_REMOTE_FETCH = False
DEFAULT_ALLOWED_HOSTS = None
DEFAULT_REQUIRE_HTTPS = True
DEFAULT_REQUIRE_HEAD_SUCCESS = True
DEFAULT_NETWORK_TIMEOUT = 10.0
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_REQUESTS_PER_SECOND = 10.0  # Rate limit for network requests
DEFAULT_MAX_CONCURRENT_REQUESTS = 5  # Maximum concurrent network requests

# Asset size limits (applies to downloads, attachments, images, etc.)
DEFAULT_MAX_ASSET_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum per asset

# Document creator/producer metadata
DEFAULT_CREATOR = "all2md"  # Creator application name for rendered documents

# HTML parser security limits (DoS protection)
MAX_META_TAG_CONTENT_LENGTH = 10 * 1024  # 10KB maximum per meta tag content
MAX_JSON_LD_SIZE_BYTES = 1024 * 1024  # 1MB maximum per JSON-LD script

# Dangerous null-like and zero-width characters that can bypass XSS filters
# These characters should be removed from HTML content for security
DANGEROUS_NULL_LIKE_CHARS = [
    "\x00",  # NULL
    "\ufeff",  # BOM/Zero Width No-Break Space
    "\u200b",  # Zero Width Space
    "\u200c",  # Zero Width Non-Joiner
    "\u200d",  # Zero Width Joiner
    "\u2060",  # Word Joiner
]

# ZIP archive security
DEFAULT_MAX_COMPRESSION_RATIO = 100.0  # Maximum compression ratio (uncompressed/compressed)
DEFAULT_MAX_UNCOMPRESSED_SIZE = 1024 * 1024 * 1024  # 1GB maximum uncompressed size
DEFAULT_MAX_ZIP_ENTRIES = 10000  # Maximum number of entries in a ZIP archive

# Regex security (ReDoS protection)
MAX_REGEX_PATTERN_LENGTH = 500  # Maximum length for user-supplied regex patterns
MAX_URL_LENGTH = 2048  # Maximum URL length for regex matching
MAX_TEXT_LENGTH_FOR_REGEX = 10000  # Maximum text length for regex matching

# Dangerous regex patterns that can cause catastrophic backtracking (ReDoS)
# These patterns are checked against user-supplied regex patterns
DANGEROUS_REGEX_PATTERNS = [
    r"\([^)]*[*+][^)]*\)[*+]",  # Nested quantifiers like (a+)+ or (a*)*
    r"\([^)]*[*+][^)]*\)\{[0-9,]+\}",  # Quantified groups with inner quantifiers like (a+){2,}
    r"\(\?[^)]*[*+][^)]*\)[*+]",  # Non-capturing groups with nested quantifiers like (?:a+)+
    r"\(\?[=!][^)]*\)[*+]",  # Lookahead/lookbehind with quantifiers like (?=.*)+
    r"\(\?[=!][^)]*[*+][^)]*\)",  # Lookahead/lookbehind containing quantifiers like (?=.*a)
    r"\([^)]*\|[^)]*\)[*+]{1,2}",  # Alternations in quantified groups like (a|ab)*
    r"\(\([^)]*[*+]",  # Multiple nested groups with quantifiers like ((a+)
    r"\.\*[*+]",  # Greedy wildcard with quantifier like .*+
    r"\.\+\*",  # .+* pattern (greedy followed by star)
]

# =============================================================================
# Format-Specific Constants - PDF
# =============================================================================

# Version requirements
PDF_MIN_PYMUPDF_VERSION = "1.26.4"

# Header detection
DEFAULT_HEADER_MIN_OCCURRENCES = 5  # Increased from 3 to reduce false positives
DEFAULT_HEADER_USE_FONT_WEIGHT = True
DEFAULT_HEADER_USE_ALL_CAPS = True
DEFAULT_HEADER_PERCENTILE_THRESHOLD = 75  # Top 25% of font sizes considered headers
DEFAULT_HEADER_FONT_SIZE_RATIO = 1.2  # Minimum ratio between header and body text font size
DEFAULT_HEADER_MAX_LINE_LENGTH = 100  # Maximum character length for text to be considered a header
DEFAULT_HEADER_DEBUG_OUTPUT = False  # Enable debug output for header detection analysis

# Column detection
DEFAULT_DETECT_COLUMNS = True
DEFAULT_MERGE_HYPHENATED_WORDS = True
DEFAULT_HANDLE_ROTATED_TEXT = True
DEFAULT_COLUMN_GAP_THRESHOLD = 20  # Minimum gap between columns in points
DEFAULT_COLUMN_DETECTION_MODE: ColumnDetectionMode = "auto"
DEFAULT_USE_COLUMN_CLUSTERING = False  # Use k-means clustering for column detection
DEFAULT_COLUMN_SPANNING_THRESHOLD = 0.65  # Width ratio threshold for detecting blocks that span columns

# Column detection algorithm parameters (internal use)
PDF_COLUMN_X_TOLERANCE = 5.0  # Points tolerance for grouping blocks by x0 position
PDF_COLUMN_GAP_QUANTIZATION = 5.0  # Points resolution for quantizing gap positions
PDF_COLUMN_MIN_FREQ_COUNT = 2  # Minimum frequency count for column boundary detection
PDF_COLUMN_FREQ_THRESHOLD_RATIO = 0.3  # Ratio of max frequency for gap detection threshold
PDF_COLUMN_MIN_BLOCKS_FOR_WIDTH_CHECK = 3  # Minimum blocks to perform median width check
PDF_COLUMN_SINGLE_COLUMN_WIDTH_RATIO = 0.6  # Width ratio threshold for single column detection

# Table detection and extraction
DEFAULT_TABLE_DETECTION_MODE: TableDetectionMode = "both"
DEFAULT_TABLE_FALLBACK_DETECTION = True
DEFAULT_DETECT_MERGED_CELLS = True
DEFAULT_TABLE_RULING_LINE_THRESHOLD = 0.5  # Minimum line length ratio for table ruling
DEFAULT_TABLE_FALLBACK_EXTRACTION_MODE: TableExtractionMode = "grid"

# Image handling
DEFAULT_IMAGE_PLACEMENT_MARKERS = True
DEFAULT_INCLUDE_IMAGE_CAPTIONS = True
DEFAULT_IMAGE_FORMAT: ImageFormat = "png"
DEFAULT_IMAGE_QUALITY = 90  # JPEG quality (1-100)

# Page structure
DEFAULT_INCLUDE_PAGE_NUMBERS = False

# Header/footer trimming
DEFAULT_TRIM_HEADERS_FOOTERS = False
DEFAULT_AUTO_TRIM_HEADERS_FOOTERS = False
DEFAULT_HEADER_HEIGHT = 0  # Height in points to trim from top
DEFAULT_FOOTER_HEIGHT = 0  # Height in points to trim from bottom

# PDF rendering defaults (for Markdown to PDF conversion)
DEFAULT_PDF_PAGE_SIZE: PageSize = "letter"
DEFAULT_PDF_MARGIN = 72.0
DEFAULT_PDF_FONT_FAMILY = "Helvetica"
DEFAULT_PDF_FONT_SIZE = 12
DEFAULT_PDF_CODE_FONT = "Courier"
DEFAULT_PDF_LINE_SPACING = 1.2

# PDF page size definitions
PDF_DEFAULT_PAGE_SIZE = "A4"
PDF_PAGE_SIZES = {
    "A4": (595.0, 842.0),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (842.0, 1191.0),
    "A5": (420.0, 595.0),
}
PDF_DEFAULT_MARGINS = (50, 50, 50, 50)  # top, right, bottom, left

# OCR settings
DEFAULT_OCR_ENABLED = False
DEFAULT_OCR_MODE = "auto"
DEFAULT_OCR_LANGUAGES = "eng"
DEFAULT_OCR_AUTO_DETECT_LANGUAGE = False
DEFAULT_OCR_DPI = 300
DEFAULT_OCR_TEXT_THRESHOLD = 50  # Minimum characters to consider page as text-based
DEFAULT_OCR_IMAGE_AREA_THRESHOLD = 0.5  # Ratio of image area to page area to trigger OCR
DEFAULT_OCR_PRESERVE_EXISTING_TEXT = False
DEFAULT_OCR_TESSERACT_CONFIG = ""

# =============================================================================
# Format-Specific Constants - HTML
# =============================================================================

# HTML emphasis and formatting
HTML_EMPHASIS_SYMBOLS = ["*", "_"]
HTML_BULLET_SYMBOLS = "*-+"

# HTML entity handling
DEFAULT_CONVERT_NBSP = False
HTML_ENTITIES_TO_PRESERVE = ["nbsp"]  # Entities that might need special handling

# =============================================================================
# Format-Specific Constants - Email (EML)
# =============================================================================

# Date handling
EMAIL_DATE_FORMATS = ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S", "%d %b %Y %H:%M:%S"]
DEFAULT_DATE_FORMAT_MODE: DateFormatMode = "strftime"
DEFAULT_DATE_STRFTIME_PATTERN = "%m/%d/%y %H:%M"
DEFAULT_CONVERT_HTML_TO_MARKDOWN = False

# Quote and reply processing
DEFAULT_CLEAN_QUOTES = True
DEFAULT_DETECT_REPLY_SEPARATORS = True
DEFAULT_NORMALIZE_HEADERS = True

# URL cleaning (security wrapper removal)
DEFAULT_CLEAN_WRAPPED_URLS = True
DEFAULT_URL_WRAPPERS = [
    "urldefense.com",
    "safelinks.protection.outlook.com",
    "urldefense.proofpoint.com",
    "protect-links.mimecast.com",
]

# Header processing
DEFAULT_PRESERVE_RAW_HEADERS = False

# Email display options
DEFAULT_EMAIL_SORT_ORDER: EmailSortOrder = "asc"
DEFAULT_EML_SUBJECT_AS_H1 = True
DEFAULT_EML_INCLUDE_ATTACH_SECTION_HEADING = True
DEFAULT_EML_ATTACH_SECTION_TITLE = "Attachments"
DEFAULT_EML_INCLUDE_HTML_PARTS = True
DEFAULT_EML_INCLUDE_PLAIN_PARTS = True

# =============================================================================
# Format-Specific Constants - Email Archives (MBOX/Outlook)
# =============================================================================

# Output structure
DEFAULT_OUTPUT_STRUCTURE: OutputStructureMode = "flat"

# Mailbox format detection
DEFAULT_MAILBOX_FORMAT: MailboxFormatType = "auto"

# Default folders to skip for PST/OST
DEFAULT_OUTLOOK_SKIP_FOLDERS = ["Deleted Items", "Junk Email", "Trash", "Drafts"]

# Message processing
DEFAULT_MAX_MESSAGES = None  # None means no limit
DEFAULT_INCLUDE_SUBFOLDERS = True

# =============================================================================
# Format-Specific Constants - Evernote (ENEX)
# =============================================================================

# Tag rendering
DEFAULT_TAGS_FORMAT_MODE: TagsFormatMode = "inline"

# Note sorting
DEFAULT_NOTE_SORT_MODE: NoteSortMode = "none"

# Note title and metadata
DEFAULT_NOTE_TITLE_LEVEL = 1
DEFAULT_INCLUDE_NOTE_METADATA = True
DEFAULT_INCLUDE_TAGS = True
DEFAULT_NOTEBOOK_AS_HEADING = False
DEFAULT_NOTES_SECTION_TITLE = "Notes"

# =============================================================================
# Format-Specific Constants - Jupyter Notebooks (IPYNB)
# =============================================================================

DEFAULT_TRUNCATE_OUTPUT_LINES = None
DEFAULT_TRUNCATE_OUTPUT_MESSAGE = "\n... (output truncated) ...\n"

# MIME types to check for in notebook outputs, in order of preference
IPYNB_SUPPORTED_IMAGE_MIMETYPES = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
]

# IPYNB parser options
DEFAULT_IPYNB_INCLUDE_INPUTS = True
DEFAULT_IPYNB_INCLUDE_OUTPUTS = True
DEFAULT_IPYNB_SKIP_EMPTY_CELLS = True
DEFAULT_IPYNB_SHOW_EXECUTION_COUNT = False
DEFAULT_IPYNB_OUTPUT_TYPES = ("stream", "execute_result", "display_data")

# IPYNB renderer options
DEFAULT_IPYNB_NBFORMAT: int | Literal["auto"] = 4
DEFAULT_IPYNB_NBFORMAT_MINOR: int | Literal["auto"] = "auto"
DEFAULT_IPYNB_DEFAULT_LANGUAGE = "python"
DEFAULT_IPYNB_DEFAULT_KERNEL_NAME = "python3"
DEFAULT_IPYNB_DEFAULT_KERNEL_DISPLAY_NAME = "Python 3"
DEFAULT_IPYNB_INFER_LANGUAGE_FROM_DOCUMENT = True
DEFAULT_IPYNB_INFER_KERNEL_FROM_DOCUMENT = True
DEFAULT_IPYNB_INCLUDE_TRUSTED_METADATA = False
DEFAULT_IPYNB_INCLUDE_UI_METADATA = False
DEFAULT_IPYNB_PRESERVE_UNKNOWN_METADATA = True
DEFAULT_IPYNB_INLINE_ATTACHMENTS = True

# =============================================================================
# Format-Specific Constants - Word Documents (DOCX)
# =============================================================================

# Word document layout
DEFAULT_BULLETED_LIST_INDENT = 24

# DOCX rendering defaults (for Markdown to DOCX conversion)
DEFAULT_DOCX_FONT = "Calibri"
DEFAULT_DOCX_FONT_SIZE = 11
DEFAULT_DOCX_CODE_FONT = "Courier New"
DEFAULT_DOCX_CODE_FONT_SIZE = 10
DEFAULT_DOCX_TABLE_STYLE = "Light Grid Accent 1"

# DOCX parser options
DEFAULT_DOCX_COMMENTS_POSITION: DocxCommentsPosition = "footnotes"
DEFAULT_DOCX_INCLUDE_FOOTNOTES = True
DEFAULT_DOCX_INCLUDE_ENDNOTES = True
DEFAULT_DOCX_INCLUDE_COMMENTS = False
DEFAULT_DOCX_INCLUDE_IMAGE_CAPTIONS = True

# =============================================================================
# Format-Specific Constants - CSV
# =============================================================================

# CSV parser options
DEFAULT_CSV_DETECT_DIALECT = True
DEFAULT_CSV_DIALECT_SAMPLE_SIZE = 4096
DEFAULT_CSV_HAS_HEADER = True
DEFAULT_CSV_TRUNCATION_INDICATOR = "..."
DEFAULT_CSV_SKIP_EMPTY_ROWS = True
DEFAULT_CSV_STRIP_WHITESPACE = False

# CSV renderer options
DEFAULT_CSV_MULTI_TABLE_MODE: MultiTableMode = "first"
DEFAULT_CSV_TABLE_INDEX = 0
DEFAULT_CSV_TABLE_SEPARATOR = "\n\n"
DEFAULT_CSV_DELIMITER = ","
DEFAULT_CSV_QUOTING: CsvQuotingMode = "minimal"
DEFAULT_CSV_INCLUDE_TABLE_HEADINGS = False
DEFAULT_CSV_LINE_TERMINATOR = "\n"
DEFAULT_CSV_MERGED_CELL_HANDLING: MergedCellHandling = "repeat"
DEFAULT_CSV_QUOTE_CHAR = '"'
DEFAULT_CSV_ESCAPE_CHAR = None
DEFAULT_CSV_INCLUDE_BOM = False

# =============================================================================
# Format-Specific Constants - PowerPoint (PPTX)
# =============================================================================

DEFAULT_SLIDE_NUMBERS = False

# PPTX renderer options
DEFAULT_PPTX_SLIDE_SPLIT_MODE: SlideSplitMode = "auto"
DEFAULT_PPTX_SLIDE_SPLIT_HEADING_LEVEL = 2
DEFAULT_PPTX_DEFAULT_LAYOUT = "Title and Content"
DEFAULT_PPTX_TITLE_SLIDE_LAYOUT = "Title Slide"
DEFAULT_PPTX_USE_HEADING_AS_SLIDE_TITLE = True
DEFAULT_PPTX_DEFAULT_FONT = "Calibri"
DEFAULT_PPTX_DEFAULT_FONT_SIZE = 18
DEFAULT_PPTX_TITLE_FONT_SIZE = 44
DEFAULT_PPTX_LIST_NUMBER_SPACING = 1
DEFAULT_PPTX_LIST_INDENT_PER_LEVEL = 0.5
DEFAULT_PPTX_TABLE_LEFT = 0.5
DEFAULT_PPTX_TABLE_TOP = 2.0
DEFAULT_PPTX_TABLE_WIDTH = 9.0
DEFAULT_PPTX_TABLE_HEIGHT_PER_ROW = 0.5
DEFAULT_PPTX_IMAGE_LEFT = 1.0
DEFAULT_PPTX_IMAGE_TOP = 2.5
DEFAULT_PPTX_IMAGE_WIDTH = 4.0
DEFAULT_PPTX_INCLUDE_NOTES = True
DEFAULT_PPTX_FORCE_TEXTBOX_BULLETS = True

# PPTX parser options
DEFAULT_PPTX_CHARTS_MODE: ChartsMode = "data"
DEFAULT_PPTX_INCLUDE_TITLES_AS_H2 = True
DEFAULT_PPTX_STRICT_LIST_DETECTION = False

# =============================================================================
# Format-Specific Constants - reStructuredText (RST)
# =============================================================================

DEFAULT_RST_HEADING_CHARS = "=-~^*"
DEFAULT_RST_TABLE_STYLE: RstTableStyle = "grid"
DEFAULT_RST_CODE_STYLE: RstCodeStyle = "directive"
DEFAULT_RST_LINE_LENGTH = 80
DEFAULT_RST_HARD_LINE_BREAK_MODE: RstLineBreakMode = "line_block"
DEFAULT_RST_HARD_LINE_BREAK_FALLBACK_IN_CONTAINERS = True
DEFAULT_RST_STRICT_MODE = False
DEFAULT_RST_STRIP_COMMENTS = False
DEFAULT_RST_PARSE_ADMONITIONS = True

# =============================================================================
# Format-Specific Constants - RTF
# =============================================================================

DEFAULT_RTF_FONT_FAMILY: RtfFontFamily = "roman"
DEFAULT_RTF_BOLD_HEADINGS = True

# =============================================================================
# Format-Specific Constants - MediaWiki
# =============================================================================

DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED = True
DEFAULT_MEDIAWIKI_IMAGE_THUMB = True
DEFAULT_MEDIAWIKI_IMAGE_CAPTION_MODE: MediaWikiImageCaptionMode = "alt_only"

# MediaWiki parser options
DEFAULT_MEDIAWIKI_PARSE_TEMPLATES = False
DEFAULT_MEDIAWIKI_PARSE_TAGS = True
DEFAULT_MEDIAWIKI_STRIP_COMMENTS = True

# =============================================================================
# Format-Specific Constants - DokuWiki
# =============================================================================

DEFAULT_DOKUWIKI_USE_HTML_FOR_UNSUPPORTED = True
DEFAULT_DOKUWIKI_MONOSPACE_FENCE = False

# DokuWiki renderer options (escape by default for security)
DEFAULT_DOKUWIKI_RENDERER_HTML_PASSTHROUGH_MODE: HtmlPassthroughMode = "escape"

# DokuWiki parser options
DEFAULT_DOKUWIKI_PARSE_PLUGINS = False
DEFAULT_DOKUWIKI_STRIP_COMMENTS = True
DEFAULT_DOKUWIKI_PARSE_INTERWIKI = True

# =============================================================================
# Format-Specific Constants - Org-Mode
# =============================================================================

DEFAULT_ORG_HEADING_STYLE: OrgHeadingStyle = "stars"
DEFAULT_ORG_TODO_KEYWORDS = ["TODO", "DONE"]
DEFAULT_ORG_PARSE_DRAWERS = True
DEFAULT_ORG_PARSE_PROPERTIES = True
DEFAULT_ORG_PARSE_TAGS = True
DEFAULT_ORG_PARSE_SCHEDULING = True
DEFAULT_ORG_PARSE_LOGBOOK = True
DEFAULT_ORG_PARSE_CLOCK = True
DEFAULT_ORG_PARSE_CLOSED = True
DEFAULT_ORG_PRESERVE_TIMESTAMP_METADATA = True
DEFAULT_ORG_PRESERVE_DRAWERS = False
DEFAULT_ORG_PRESERVE_PROPERTIES = True
DEFAULT_ORG_PRESERVE_TAGS = True
DEFAULT_ORG_PRESERVE_LOGBOOK = True
DEFAULT_ORG_PRESERVE_CLOCK = True
DEFAULT_ORG_PRESERVE_CLOSED = True

# =============================================================================
# Format-Specific Constants - BBCode
# =============================================================================

DEFAULT_BBCODE_UNKNOWN_TAG_MODE: BBCodeUnknownTagMode = "strip"
DEFAULT_BBCODE_PARSE_COLOR_SIZE = True
DEFAULT_BBCODE_PARSE_ALIGNMENT = True
DEFAULT_BBCODE_STRICT_MODE = False

# =============================================================================
# Format-Specific Constants - AsciiDoc
# =============================================================================

# AsciiDoc parser options
DEFAULT_ASCIIDOC_PARSE_ATTRIBUTES = True
DEFAULT_ASCIIDOC_PARSE_ADMONITIONS = True
DEFAULT_ASCIIDOC_PARSE_INCLUDES = False
DEFAULT_ASCIIDOC_STRICT_MODE = False
DEFAULT_ASCIIDOC_RESOLVE_ATTRIBUTE_REFS = True
DEFAULT_ASCIIDOC_ATTRIBUTE_MISSING_POLICY: AttributeMissingPolicy = "keep"
DEFAULT_ASCIIDOC_SUPPORT_UNCONSTRAINED_FORMATTING = True
DEFAULT_ASCIIDOC_TABLE_HEADER_DETECTION: TableHeaderDetection = "attribute-based"
DEFAULT_ASCIIDOC_HONOR_HARD_BREAKS = True
DEFAULT_ASCIIDOC_PARSE_TABLE_SPANS = True
DEFAULT_ASCIIDOC_STRIP_COMMENTS = False

# AsciiDoc renderer options
DEFAULT_ASCIIDOC_LIST_INDENT = 2
DEFAULT_ASCIIDOC_USE_ATTRIBUTES = True
DEFAULT_ASCIIDOC_LINE_LENGTH = 0

# =============================================================================
# Format-Specific Constants - HTML
# =============================================================================

# HTML parser options
DEFAULT_HTML_EXTRACT_READABLE = False
DEFAULT_HTML_BR_HANDLING: BrHandling = "newline"
DEFAULT_HTML_STRIP_COMMENTS = True
DEFAULT_HTML_COLLAPSE_WHITESPACE = True
DEFAULT_HTML_FIGURES_PARSING: FiguresParsing = "blockquote"
DEFAULT_HTML_DETAILS_PARSING: DetailsParsing = "blockquote"
DEFAULT_HTML_EXTRACT_MICRODATA = True
DEFAULT_HTML_PARSER: HtmlParser = "html.parser"

# HTML renderer options
DEFAULT_HTML_STANDALONE = True
DEFAULT_HTML_CSS_STYLE: CssStyle = "embedded"
DEFAULT_HTML_INCLUDE_TOC = False
DEFAULT_HTML_SYNTAX_HIGHLIGHTING = True
DEFAULT_HTML_ESCAPE_HTML = True
DEFAULT_HTML_MATH_RENDERER: MathRenderer = "mathjax"
DEFAULT_HTML_LANGUAGE = "en"
DEFAULT_HTML_TEMPLATE_SELECTOR = "#content"
DEFAULT_HTML_INJECTION_MODE: InjectionMode = "replace"
DEFAULT_HTML_CONTENT_PLACEHOLDER = "{CONTENT}"

# =============================================================================
# Format-Specific Constants - Archive (TAR/7Z/RAR)
# =============================================================================

DEFAULT_ARCHIVE_CREATE_SECTION_HEADINGS = True
DEFAULT_ARCHIVE_PRESERVE_DIRECTORY_STRUCTURE = True
DEFAULT_ARCHIVE_EXTRACT_RESOURCE_FILES = True
DEFAULT_ARCHIVE_SKIP_EMPTY_FILES = True
DEFAULT_ARCHIVE_INCLUDE_RESOURCE_MANIFEST = True
DEFAULT_ARCHIVE_ENABLE_PARALLEL_PROCESSING = False
DEFAULT_ARCHIVE_PARALLEL_THRESHOLD = 10

# =============================================================================
# Format-Specific Constants - AST JSON
# =============================================================================

DEFAULT_AST_JSON_INDENT: AstJsonIndent = 2
DEFAULT_AST_JSON_ENSURE_ASCII = False
DEFAULT_AST_JSON_SORT_KEYS = False
DEFAULT_AST_JSON_VALIDATE_SCHEMA = True
DEFAULT_AST_JSON_STRICT_MODE = False

# =============================================================================
# Format-Specific Constants - Spreadsheets (XLSX/ODS)
# =============================================================================

DEFAULT_SPREADSHEET_INCLUDE_SHEET_TITLES = True
DEFAULT_SPREADSHEET_RENDER_FORMULAS = True
DEFAULT_SPREADSHEET_PRESERVE_NEWLINES_IN_CELLS = False
DEFAULT_SPREADSHEET_TRIM_EMPTY: TrimEmptyMode = "trailing"
DEFAULT_SPREADSHEET_CHART_MODE: ChartMode = "skip"
DEFAULT_SPREADSHEET_MERGED_CELL_MODE: MergedCellMode = "flatten"

# =============================================================================
# Format-Specific Constants - OpenAPI
# =============================================================================

DEFAULT_OPENAPI_INCLUDE_SERVERS = True
DEFAULT_OPENAPI_INCLUDE_SCHEMAS = True
DEFAULT_OPENAPI_INCLUDE_EXAMPLES = True
DEFAULT_OPENAPI_GROUP_BY_TAG = True
DEFAULT_OPENAPI_MAX_SCHEMA_DEPTH = 3
DEFAULT_OPENAPI_CODE_BLOCK_LANGUAGE = "json"
DEFAULT_OPENAPI_VALIDATE_SPEC = False
DEFAULT_OPENAPI_INCLUDE_DEPRECATED = True
DEFAULT_OPENAPI_EXPAND_REFS = True

# =============================================================================
# Format-Specific Constants - ODP (OpenDocument Presentation)
# =============================================================================

DEFAULT_ODP_PRESERVE_TABLES = True
DEFAULT_ODP_INCLUDE_SLIDE_NUMBERS = False
DEFAULT_ODP_INCLUDE_NOTES = True
DEFAULT_ODP_SLIDE_SPLIT_HEADING_LEVEL = 2
DEFAULT_ODP_DEFAULT_LAYOUT = "Default"
DEFAULT_ODP_TITLE_SLIDE_LAYOUT = "Title"
DEFAULT_ODP_USE_HEADING_AS_SLIDE_TITLE = True
DEFAULT_ODP_DEFAULT_FONT = "Liberation Sans"
DEFAULT_ODP_DEFAULT_FONT_SIZE = 18
DEFAULT_ODP_TITLE_FONT_SIZE = 44

# =============================================================================
# Format-Specific Constants - ODT (OpenDocument Text)
# =============================================================================

DEFAULT_ODT_PRESERVE_TABLES = True
DEFAULT_ODT_DEFAULT_FONT = "Liberation Sans"
DEFAULT_ODT_DEFAULT_FONT_SIZE = 11
DEFAULT_ODT_USE_STYLES = True
DEFAULT_ODT_CODE_FONT = "Liberation Mono"
DEFAULT_ODT_CODE_FONT_SIZE = 10
DEFAULT_ODT_PRESERVE_FORMATTING = True

# =============================================================================
# Format-Specific Constants - LaTeX
# =============================================================================

# LaTeX parser options
DEFAULT_LATEX_PARSE_PREAMBLE = True
DEFAULT_LATEX_PARSE_MATH = True
DEFAULT_LATEX_PARSE_CUSTOM_COMMANDS = False
DEFAULT_LATEX_STRICT_MODE = False
DEFAULT_LATEX_ENCODING = "utf-8"
DEFAULT_LATEX_PRESERVE_COMMENTS = False

# LaTeX renderer options
DEFAULT_LATEX_DOCUMENT_CLASS = "article"
DEFAULT_LATEX_INCLUDE_PREAMBLE = True
DEFAULT_LATEX_PACKAGES = ["amsmath", "graphicx", "hyperref"]
DEFAULT_LATEX_MATH_RENDER_MODE: LatexMathRenderMode = "display"
DEFAULT_LATEX_LINE_WIDTH = 0
DEFAULT_LATEX_ESCAPE_SPECIAL = True
DEFAULT_LATEX_USE_UNICODE = True

# =============================================================================
# Format-Specific Constants - Jinja
# =============================================================================

DEFAULT_JINJA_ESCAPE_STRATEGY: JinjaEscapeStrategy | None = None
DEFAULT_JINJA_AUTOESCAPE = False
DEFAULT_JINJA_ENABLE_RENDER_FILTER = True
DEFAULT_JINJA_ENABLE_ESCAPE_FILTERS = True
DEFAULT_JINJA_ENABLE_TRAVERSAL_HELPERS = True
DEFAULT_JINJA_RENDER_FORMAT: JinjaRenderFormat = "markdown"
DEFAULT_JINJA_STRICT_UNDEFINED = True

# =============================================================================
# Format-Specific Constants - Common (shared across formats)
# =============================================================================

DEFAULT_ATTACHMENT_FILENAME_TEMPLATE = "{stem}_{type}{seq}.{ext}"
DEFAULT_ATTACHMENT_OVERWRITE: AttachmentOverwriteMode = "unique"
DEFAULT_ATTACHMENT_DEDUPLICATE_BY_HASH = False
DEFAULT_ATTACHMENTS_FOOTNOTES_SECTION = "Attachments"

# =============================================================================
# File Extensions and Format Detection
# =============================================================================

# NOTE: Supported document and plaintext extensions are now dynamically
# determined by the converter registry. Use:
#   from all2md.converter_registry import registry
#   extensions = registry.get_all_extensions()
#
# This ensures new parsers (including plugins) are automatically recognized
# without requiring manual constant updates.
#
# The _plaintext-exts.json file is still used by the sourcecode parser to
# populate its CONVERTER_METADATA extensions list.

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif"]

RESOURCE_FILE_EXTENSIONS = [
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".svg",
    ".webp",
    ".ico",
    ".tiff",
    ".tif",
    # Stylesheets
    ".css",
    ".scss",
    ".sass",
    ".less",
    # Scripts (may be parsed as sourcecode, but often better as resources in archives)
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    # Media
    ".mp4",
    ".mp3",
    ".wav",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".ogg",
    ".flac",
    ".m4a",
    # Fonts
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    # Binary/compiled files
    ".bin",
    ".dat",
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".class",
]
