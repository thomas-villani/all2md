#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Constants and default values for all2md library.

This module centralizes all hardcoded values, magic numbers, and default
configuration constants used across the all2md library. This improves
maintainability and discoverability of configurable parameters.

Constants are organized by category: formatting, conversion behavior,
file handling, and Markdown flavor specifications.
"""

from __future__ import annotations

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
    r"^Printed on \d{4}-\d{2}-\d{2}$",
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

# Markdown flavor and unsupported element handling
FlavorType = Literal["gfm", "commonmark", "multimarkdown", "pandoc", "kramdown", "markdown_plus"]
UnsupportedTableMode = Literal["drop", "ascii", "force", "html"]
UnsupportedInlineMode = Literal["plain", "force", "html"]
LinkStyleType = Literal["inline", "reference"]
ReferenceLinkPlacement = Literal["end_of_document", "after_block"]
CodeFenceChar = Literal["`", "~"]
MetadataFormatType = Literal["yaml", "toml", "json"]

PageSize = Literal["letter", "a4", "legal"]
HtmlPassthroughMode = Literal["pass-through", "escape", "drop", "sanitize"]
HTML_PASSTHROUGH_MODES = ["pass-through", "escape", "drop", "sanitize"]
DEFAULT_HTML_PASSTHROUGH_MODE: HtmlPassthroughMode = "escape"

HeaderCaseOption = Literal["preserve", "title", "upper", "lower"]

ColumnDetectionMode = Literal["auto", "force_single", "force_multi", "disabled"]
TableExtractionMode = Literal["none", "grid", "text_clustering"]
TableDetectionMode = Literal["pymupdf", "ruling", "both", "none"]
ImageFormat = Literal["png", "jpeg"]
OCRMode = Literal["auto", "force", "off"]

# ==============================================================================


# Attachment handling defaults - defined here after AttachmentMode type
DEFAULT_ATTACHMENT_MODE: AttachmentMode = "alt_text"
DEFAULT_ALT_TEXT_MODE: AltTextMode = "default"
DEFAULT_COMMENT_MODE: CommentMode = "blockquote"
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
DEFAULT_COMMENT_RENDER_MODE: CommentRenderMode = "preserve"

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
DEFAULT_REFERENCE_LINK_PLACEMENT: ReferenceLinkPlacement = "end_of_document"
DEFAULT_AUTOLINK_BARE_URLS = False
DEFAULT_TABLE_PIPE_ESCAPE = True
DEFAULT_MARKDOWN_HTML_SANITIZATION: HtmlPassthroughMode = "escape"  # Secure by default

DEFAULT_USER_AGENT = "all2md-fetcher/1.0"

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
DEFAULT_COLUMN_DETECTION_MODE: ColumnDetectionMode = "auto"
DEFAULT_USE_COLUMN_CLUSTERING = False  # Use k-means clustering for column detection
DEFAULT_COLUMN_SPANNING_THRESHOLD = 0.65  # Width ratio threshold for detecting blocks that span columns

# Table detection fallback constants
DEFAULT_TABLE_FALLBACK_DETECTION = True
DEFAULT_DETECT_MERGED_CELLS = True
DEFAULT_TABLE_RULING_LINE_THRESHOLD = 0.5  # Minimum line length ratio for table ruling
DEFAULT_TABLE_FALLBACK_EXTRACTION_MODE: TableExtractionMode = "grid"

DEFAULT_IMAGE_PLACEMENT_MARKERS = True
DEFAULT_INCLUDE_IMAGE_CAPTIONS = True

# Page separator constants
DEFAULT_INCLUDE_PAGE_NUMBERS = False

# Table detection mode constants
DEFAULT_TABLE_DETECTION_MODE: TableDetectionMode = "both"

# Image format constants
DEFAULT_IMAGE_FORMAT: ImageFormat = "png"
DEFAULT_IMAGE_QUALITY = 90  # JPEG quality (1-100)

# Header/footer trimming constants
DEFAULT_TRIM_HEADERS_FOOTERS = False
DEFAULT_AUTO_TRIM_HEADERS_FOOTERS = False
DEFAULT_HEADER_HEIGHT = 0  # Height in points to trim from top
DEFAULT_FOOTER_HEIGHT = 0  # Height in points to trim from bottom

DEFAULT_PDF_PAGE_SIZE: PageSize = "letter"
DEFAULT_PDF_MARGIN = 72.0
DEFAULT_PDF_FONT_FAMILY = "Helvetica"
DEFAULT_PDF_FONT_SIZE = 12
DEFAULT_PDF_CODE_FONT = "Courier"
DEFAULT_PDF_LINE_SPACING = 1.2

# OCR-related constants for PDF parsing
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
# HTML to Markdown Constants
# =============================================================================

HTML_EMPHASIS_SYMBOLS = ["*", "_"]
HTML_BULLET_SYMBOLS = "*-+"

# HTML entity handling
DEFAULT_CONVERT_NBSP = False
HTML_ENTITIES_TO_PRESERVE = ["nbsp"]  # Entities that might need special handling

# Content sanitization
DEFAULT_STRIP_DANGEROUS_ELEMENTS = False
DEFAULT_STRIP_FRAMEWORK_ATTRIBUTES = False

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

# Asset size limit for security (applies to downloads, attachments, images, etc.)
DEFAULT_MAX_ASSET_SIZE_BYTES = 50 * 1024 * 1024  # 50MB maximum per asset

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
# Email Archive (MBOX/Outlook) Constants
# =============================================================================

# Output structure modes
OutputStructureMode = Literal["flat", "hierarchical"]
DEFAULT_OUTPUT_STRUCTURE: OutputStructureMode = "flat"

# Mailbox format detection
MailboxFormatType = Literal["auto", "mbox", "maildir", "mh", "babyl", "mmdf"]
DEFAULT_MAILBOX_FORMAT: MailboxFormatType = "auto"

# Default folders to skip for PST/OST
DEFAULT_OUTLOOK_SKIP_FOLDERS = ["Deleted Items", "Junk Email", "Trash", "Drafts"]

# Message processing defaults
DEFAULT_MAX_MESSAGES = None  # None means no limit
DEFAULT_INCLUDE_SUBFOLDERS = True

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
RstLineBreakMode = Literal["line_block", "raw"]

DEFAULT_RST_HEADING_CHARS = "=-~^*"
DEFAULT_RST_TABLE_STYLE: RstTableStyle = "grid"
DEFAULT_RST_CODE_STYLE: RstCodeStyle = "directive"
DEFAULT_RST_LINE_LENGTH = 80
DEFAULT_RST_HARD_LINE_BREAK_MODE: RstLineBreakMode = "line_block"
DEFAULT_RST_HARD_LINE_BREAK_FALLBACK_IN_CONTAINERS = True
DEFAULT_RST_PARSE_DIRECTIVES = True
DEFAULT_RST_STRICT_MODE = False
DEFAULT_RST_PRESERVE_RAW_DIRECTIVES = False
DEFAULT_RST_STRIP_COMMENTS = False

# =============================================================================
# MediaWiki Constants
# =============================================================================

MediaWikiImageCaptionMode = Literal["auto", "alt_only", "caption_only"]

DEFAULT_MEDIAWIKI_USE_HTML_FOR_UNSUPPORTED = True
DEFAULT_MEDIAWIKI_IMAGE_THUMB = True
DEFAULT_MEDIAWIKI_IMAGE_CAPTION_MODE: MediaWikiImageCaptionMode = "alt_only"

# MediaWiki Parser Options
DEFAULT_MEDIAWIKI_PARSE_TEMPLATES = False
DEFAULT_MEDIAWIKI_PARSE_TAGS = True
DEFAULT_MEDIAWIKI_STRIP_COMMENTS = True

# =============================================================================
# DokuWiki Constants
# =============================================================================

DEFAULT_DOKUWIKI_USE_HTML_FOR_UNSUPPORTED = True
DEFAULT_DOKUWIKI_MONOSPACE_FENCE = False

# DokuWiki Parser Options
DEFAULT_DOKUWIKI_PARSE_PLUGINS = False
DEFAULT_DOKUWIKI_STRIP_COMMENTS = True
DEFAULT_DOKUWIKI_PARSE_INTERWIKI = True

# =============================================================================
# Org-Mode Constants
# =============================================================================

OrgHeadingStyle = Literal["stars"]
OrgTodoKeywordSet = Literal["default", "custom"]

DEFAULT_ORG_HEADING_STYLE: OrgHeadingStyle = "stars"
DEFAULT_ORG_TODO_KEYWORDS = ["TODO", "DONE"]
DEFAULT_ORG_PARSE_DRAWERS = True
DEFAULT_ORG_PARSE_PROPERTIES = True
DEFAULT_ORG_PARSE_TAGS = True
DEFAULT_ORG_PARSE_SCHEDULING = True
DEFAULT_ORG_PRESERVE_DRAWERS = False
DEFAULT_ORG_PRESERVE_PROPERTIES = True
DEFAULT_ORG_PRESERVE_TAGS = True

# =============================================================================
# BBCode Constants
# =============================================================================

BBCodeUnknownTagMode = Literal["preserve", "strip", "escape"]

DEFAULT_BBCODE_UNKNOWN_TAG_MODE: BBCodeUnknownTagMode = "strip"
DEFAULT_BBCODE_PARSE_COLOR_SIZE = True
DEFAULT_BBCODE_PARSE_ALIGNMENT = True
DEFAULT_BBCODE_STRICT_MODE = False

# =============================================================================
# File Extension Lists
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
    "epub",
    "fb2",
    "html",
    "ipynb",
    "jinja",
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
    "webarchive",
    "xlsx",
    "zip",
]
