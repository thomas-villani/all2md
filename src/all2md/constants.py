#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Constants and default values for all2md library.

This module centralizes all hardcoded values, magic numbers, and default
configuration constants used across the all2md library. This improves
maintainability and discoverability of configurable parameters.

Constants are organized by category: formatting, conversion behavior,
file handling, and Markdown flavor specifications.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

# =============================================================================
# Markdown Formatting Constants
# =============================================================================

DEFAULT_PAGE_SEPARATOR = "-----"
DEFAULT_LIST_INDENT_WIDTH = 4
DEFAULT_TABLE_ALIGNMENT = "left"

# Emphasis and formatting symbols
DEFAULT_EMPHASIS_SYMBOL = "*"
DEFAULT_BULLET_SYMBOLS = "*-+"
MARKDOWN_SPECIAL_CHARS = "*_#[]()\\"

# =============================================================================
# Font and Layout Constants (PDF/DOCX)
# =============================================================================

DEFAULT_FONT_SIZE_THRESHOLD_PT = 36
DEFAULT_INDENTATION_PT_PER_LEVEL = 36
DEFAULT_OVERLAP_THRESHOLD_PERCENT = 70
DEFAULT_OVERLAP_THRESHOLD_PX = 5
DEFAULT_LINK_OVERLAP_THRESHOLD = 70.0  # Percentage overlap required for link detection (0-100)

# Word document formatting
DEFAULT_BULLETED_LIST_INDENT = 24

# =============================================================================
# Conversion Behavior Constants
# =============================================================================


# Attachment handling (unified across all parsers) - defined after AttachmentMode type
DEFAULT_ATTACHMENT_OUTPUT_DIR = None
DEFAULT_ATTACHMENT_BASE_URL = None

# Text processing
DEFAULT_ESCAPE_SPECIAL = True
DEFAULT_USE_HASH_HEADINGS = True
DEFAULT_EXTRACT_TITLE = False
DEFAULT_SLIDE_NUMBERS = False
DEFAULT_EXTRACT_METADATA = False
DEFAULT_INCLUDE_METADATA_FRONTMATTER = False

# Boilerplate text removal patterns (used by RemoveBoilerplateTextTransform)
DEFAULT_BOILERPLATE_PATTERNS = [
    r"^CONFIDENTIAL$",
    r"^Page \d+ of \d+$",
    r"^Internal Use Only$",
    r"^\[DRAFT\]$",
    r"^Copyright \d{4}",
    r"^Printed on \d{4}-\d{2}-\d{2}$"
]

# =============================================================================
# Supported Format Types
# =============================================================================

UnderlineMode = Literal["html", "markdown", "ignore"]
SuperscriptMode = Literal["html", "markdown", "ignore"]
SubscriptMode = Literal["html", "markdown", "ignore"]
MathMode = Literal["latex", "mathml", "html"]
EmphasisSymbol = Literal["*", "_"]
AttachmentMode = Literal["skip", "alt_text", "download", "base64"]
AltTextMode = Literal["default", "plain_filename", "strict_markdown", "footnote"]
CommentMode = Literal["html", "blockquote", "ignore"]

# Markdown flavor and unsupported element handling
FlavorType = Literal["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
UnsupportedTableMode = Literal["drop", "ascii", "force", "html"]
UnsupportedInlineMode = Literal["plain", "force", "html"]
LinkStyleType = Literal["inline", "reference"]
CodeFenceChar = Literal["`", "~"]
MetadataFormatType = Literal["yaml", "toml", "json"]

PageSize = Literal["letter", "a4", "legal"]
HtmlPassthroughMode = Literal["pass-through", "escape", "drop", "sanitize"]

# ==============================================================================


# Attachment handling defaults - defined here after AttachmentMode type
DEFAULT_ATTACHMENT_MODE: AttachmentMode = "alt_text"
DEFAULT_ALT_TEXT_MODE: AltTextMode = "default"
DEFAULT_COMMENT_MODE: CommentMode = "blockquote"

# Flavor and unsupported element defaults
DEFAULT_FLAVOR: FlavorType = "gfm"
# Use "force" as flavor-naive default (most markdown-like, works in most parsers)
# Flavor-specific defaults are applied via get_flavor_defaults() when flavor is chosen
DEFAULT_UNSUPPORTED_TABLE_MODE: UnsupportedTableMode = "force"
DEFAULT_UNSUPPORTED_INLINE_MODE: UnsupportedInlineMode = "force"
DEFAULT_MATH_MODE: MathMode = "latex"
DEFAULT_METADATA_FORMAT: MetadataFormatType = "yaml"

# Markdown rendering defaults
DEFAULT_HEADING_LEVEL_OFFSET = 0
DEFAULT_CODE_FENCE_CHAR: CodeFenceChar = "`"
DEFAULT_CODE_FENCE_MIN = 3
DEFAULT_COLLAPSE_BLANK_LINES = True
DEFAULT_LINK_STYLE: LinkStyleType = "inline"
DEFAULT_TABLE_PIPE_ESCAPE = True

# =============================================================================
# PDF-specific Constants
# =============================================================================

PDF_MIN_PYMUPDF_VERSION = "1.26.4"

# Header detection constants
DEFAULT_HEADER_MIN_OCCURRENCES = 5  # Increased from 3 to reduce false positives
DEFAULT_HEADER_USE_FONT_WEIGHT = True
DEFAULT_HEADER_USE_ALL_CAPS = True
DEFAULT_HEADER_PERCENTILE_THRESHOLD = 75  # Top 25% of font sizes considered headers
DEFAULT_HEADER_FONT_SIZE_RATIO = 1.2  # Minimum ratio between header and body text font size
DEFAULT_HEADER_MAX_LINE_LENGTH = 100  # Maximum character length for text to be considered a header
DEFAULT_HEADER_DEBUG_OUTPUT = False  # Enable debug output for header detection analysis

# Column detection constants
DEFAULT_DETECT_COLUMNS = True
DEFAULT_MERGE_HYPHENATED_WORDS = True
DEFAULT_HANDLE_ROTATED_TEXT = True
DEFAULT_COLUMN_GAP_THRESHOLD = 20  # Minimum gap between columns in points
DEFAULT_COLUMN_DETECTION_MODE = "auto"  # Options: "auto", "force_single", "force_multi", "disabled"
DEFAULT_USE_COLUMN_CLUSTERING = False  # Use k-means clustering for column detection
DEFAULT_COLUMN_SPANNING_THRESHOLD = 0.65  # Width ratio threshold for detecting blocks that span columns

# Table detection fallback constants
DEFAULT_TABLE_FALLBACK_DETECTION = True
DEFAULT_DETECT_MERGED_CELLS = True
DEFAULT_TABLE_RULING_LINE_THRESHOLD = 0.5  # Minimum line length ratio for table ruling
DEFAULT_TABLE_FALLBACK_EXTRACTION_MODE = "grid"  # Options: "none", "grid", "text_clustering"

DEFAULT_IMAGE_PLACEMENT_MARKERS = True
DEFAULT_INCLUDE_IMAGE_CAPTIONS = True

# Page separator constants
DEFAULT_INCLUDE_PAGE_NUMBERS = False

# Table detection mode constants
DEFAULT_TABLE_DETECTION_MODE = "both"  # Options: "pymupdf", "ruling", "both", "none"

# Image format constants
DEFAULT_IMAGE_FORMAT = "png"  # Options: "png", "jpeg"
DEFAULT_IMAGE_QUALITY = 90  # JPEG quality (1-100)

# Header/footer trimming constants
DEFAULT_TRIM_HEADERS_FOOTERS = False
DEFAULT_HEADER_HEIGHT = 0  # Height in points to trim from top
DEFAULT_FOOTER_HEIGHT = 0  # Height in points to trim from bottom

DEFAULT_PDF_PAGE_SIZE = "letter"
DEFAULT_PDF_MARGIN = 72.0
DEFAULT_PDF_FONT_FAMILY = "Helvetica"
DEFAULT_PDF_FONT_SIZE = 12
DEFAULT_PDF_CODE_FONT = "Courier"
DEFAULT_PDF_LINE_SPACING = 1.2


# =============================================================================
# HTML to Markdown Constants
# =============================================================================

HTML_EMPHASIS_SYMBOLS = ["*", "_"]
HTML_BULLET_SYMBOLS = "*-+"

# HTML entity handling
DEFAULT_CONVERT_NBSP = False
HTML_ENTITIES_TO_PRESERVE = ["nbsp"]  # Entities that might need special handling

# Content sanitization
DEFAULT_STRIP_DANGEROUS_ELEMENTS = False
DANGEROUS_HTML_ELEMENTS = {"script", "style", "object", "embed", "form", "input", "iframe"}
DANGEROUS_HTML_ATTRIBUTES = {"onclick", "onload", "onerror", "onmouseover", "onfocus", "onblur"}
DANGEROUS_SCHEMES = {
    "javascript:",
    "vbscript:",
    "data:text/html",
    "data:text/javascript",
    "data:application/javascript",
    "data:application/x-javascript",
}
SAFE_LINK_SCHEMES = frozenset({"http", "https", "mailto", "ftp", "ftps", "tel", "sms", ""})

# Block structure
DEFAULT_PRESERVE_NESTED_STRUCTURE = True

# Code block handling
MIN_CODE_FENCE_LENGTH = 3
MAX_CODE_FENCE_LENGTH = 10

# Code fence language identifier security (markdown injection prevention)
SAFE_LANGUAGE_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9_+\-]+$"
MAX_LANGUAGE_IDENTIFIER_LENGTH = 50

# Table handling
DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT = True
TABLE_ALIGNMENT_MAPPING = {"left": ":---", "center": ":---:", "right": "---:", "justify": ":---"}

# Local file security
DEFAULT_ALLOW_LOCAL_FILES = False
DEFAULT_ALLOW_CWD_FILES = False

# Network security (SSRF protection)
DEFAULT_ALLOW_REMOTE_FETCH = False
DEFAULT_ALLOWED_HOSTS = None
DEFAULT_REQUIRE_HTTPS = True
DEFAULT_REQUIRE_HEAD_SUCCESS = True
DEFAULT_NETWORK_TIMEOUT = 10.0
DEFAULT_MAX_IMAGE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_REQUESTS_PER_SECOND = 10.0  # Rate limit for network requests
DEFAULT_MAX_CONCURRENT_REQUESTS = 5  # Maximum concurrent network requests

# Download size limits for security
DEFAULT_MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024  # 100MB maximum per download
DEFAULT_MAX_ATTACHMENT_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum per attachment

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
    r'\([^)]*[*+][^)]*\)[*+]',  # Nested quantifiers like (a+)+ or (a*)*
    r'\([^)]*[*+][^)]*\)\{[0-9,]+\}',  # Quantified groups with inner quantifiers like (a+){2,}
    r'\(\?[^)]*[*+][^)]*\)[*+]',  # Non-capturing groups with nested quantifiers like (?:a+)+
    r'\(\?[=!][^)]*\)[*+]',  # Lookahead/lookbehind with quantifiers like (?=.*)+
    r'\(\?[=!][^)]*[*+][^)]*\)',  # Lookahead/lookbehind containing quantifiers like (?=.*a)
    r'\([^)]*\|[^)]*\)[*+]{1,2}',  # Alternations in quantified groups like (a|ab)*
    r'\(\([^)]*[*+]',  # Multiple nested groups with quantifiers like ((a+)
    r'\.\*[*+]',  # Greedy wildcard with quantifier like .*+
    r'\.\+\*',  # .+* pattern (greedy followed by star)
]

# =============================================================================
# Email Processing Constants
# =============================================================================

EMAIL_DATE_FORMATS = ["%a, %d %b %Y %H:%M:%S %z", "%d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S", "%d %b %Y %H:%M:%S"]

# Email date handling defaults
DateFormatMode = Literal["iso8601", "locale", "strftime"]
DEFAULT_DATE_FORMAT_MODE: DateFormatMode = "strftime"
DEFAULT_DATE_STRFTIME_PATTERN = "%m/%d/%y %H:%M"
DEFAULT_CONVERT_HTML_TO_MARKDOWN = False

# Quote processing defaults
DEFAULT_CLEAN_QUOTES = True
DEFAULT_DETECT_REPLY_SEPARATORS = True
DEFAULT_NORMALIZE_HEADERS = True

# URL cleaning defaults
DEFAULT_CLEAN_WRAPPED_URLS = True
DEFAULT_URL_WRAPPERS = [
    "urldefense.com",
    "safelinks.protection.outlook.com",
    "urldefense.proofpoint.com",
    "protect-links.mimecast.com",
]

# Header processing defaults
DEFAULT_PRESERVE_RAW_HEADERS = False

# =============================================================================
# PDF to Markdown Constants
# =============================================================================

PDF_DEFAULT_PAGE_SIZE = "A4"
PDF_PAGE_SIZES = {
    "A4": (595.0, 842.0),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (842.0, 1191.0),
    "A5": (420.0, 595.0),
}

PDF_DEFAULT_MARGINS = (50, 50, 50, 50)  # top, right, bottom, left

# =============================================================================
# Jupyter Notebook (IPYNB) Constants
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

# =============================================================================
# .docx Constants
# =============================================================================

DEFAULT_DOCX_FONT = "Calibri"
DEFAULT_DOCX_FONT_SIZE = 11
DEFAULT_DOCX_CODE_FONT = "Courier New"
DEFAULT_DOCX_CODE_FONT_SIZE = 10
DEFAULT_DOCX_TABLE_STYLE = "Light Grid Accent 1"


# =============================================================================
# reStructuredText (RST) Constants
# =============================================================================

RstTableStyle = Literal["grid", "simple"]
RstCodeStyle = Literal["double_colon", "directive"]

DEFAULT_RST_HEADING_CHARS = "=-~^*"
DEFAULT_RST_TABLE_STYLE: RstTableStyle = "grid"
DEFAULT_RST_CODE_STYLE: RstCodeStyle = "directive"
DEFAULT_RST_LINE_LENGTH = 80
DEFAULT_RST_PARSE_DIRECTIVES = True
DEFAULT_RST_STRICT_MODE = False
DEFAULT_RST_PRESERVE_RAW_DIRECTIVES = False

# =============================================================================
# MediaWiki Constants
# =============================================================================

DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED = True
DEFAULT_MEDIAWIKI_IMAGE_THUMB = True

# =============================================================================
# File Extension Lists
# =============================================================================
_PLAINTEXT_EXTENSIONS_JSON_FILE = Path(__file__).parent / "_plaintext-exts.json"
if _PLAINTEXT_EXTENSIONS_JSON_FILE.exists():
    PLAINTEXT_EXTENSIONS = json.loads(_PLAINTEXT_EXTENSIONS_JSON_FILE.read_text(encoding="utf-8"))
else:
    # Fallback to most common
    PLAINTEXT_EXTENSIONS = [
        ".js",
        ".json",
        ".html",
        ".css",
        ".py",
        ".java",
        ".cpp",
        ".c",
        ".h",
        ".ts",
        ".md",
        ".xml",
        ".sh",
        ".rb",
        ".go",
        ".php",
        ".swift",
        ".rs",
        ".yaml",
        ".yml",
        ".txt",
        ".jsx",
        ".tsx",
        ".json5",
        ".m",
        ".pl",
        ".bat",
        ".ps1",
        ".lua",
        ".coffee",
        ".dart",
        ".scss",
        ".sass",
        ".less",
        ".vue",
        ".graphql",
        ".gradle",
        ".toml",
        ".ini",
        ".conf",
        ".dockerfile",
    ]

DOCUMENT_EXTENSIONS = [
    ".pdf",
    ".csv",
    ".xlsx",
    ".docx",
    ".pptx",
    ".eml",
    ".rtf",
    ".ipynb",
    ".odt",
    ".odp",
    ".epub",
    ".mht",
    ".mhtml",
]

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif"]
DocumentFormat = Literal[
    "auto",  # Auto-detect from filename/content
    "pdf",  # PDF documents
    "docx",  # Word documents
    "pptx",  # PowerPoint presentations
    "html",  # HTML documents
    "mhtml",  # MHTML single-file web archives
    "rtf",  # Rich Text Format
    "spreadsheet",  # CSV, TSV, XLSX
    "sourcecode",  # Source code files with syntax highlighting
    "txt",  # Plain text
    "markdown",  # Markdown documents
    "eml",  # Email messages
    "image",  # Image files (PNG, JPEG, GIF)
    "ipynb",  # Jupyter Notebooks
    "odf",  # OpenDocument Format
    "epub",  # EPUB e-books
]

