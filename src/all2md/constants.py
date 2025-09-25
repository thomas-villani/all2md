"""Constants and default values for all2md library.

This module centralizes all hardcoded values, magic numbers, and default
configuration constants used across the all2md library. This improves
maintainability and discoverability of configurable parameters.

Constants are organized by category: formatting, conversion behavior,
file handling, and Markdown flavor specifications.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

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
MARKDOWN_SPECIAL_CHARS = r"*_#[]()\\"

# =============================================================================
# Font and Layout Constants (PDF/DOCX)
# =============================================================================

DEFAULT_FONT_SIZE_THRESHOLD_PT = 36
DEFAULT_INDENTATION_PT_PER_LEVEL = 36
DEFAULT_OVERLAP_THRESHOLD_PERCENT = 70
DEFAULT_OVERLAP_THRESHOLD_PX = 5

# Word document formatting
DEFAULT_BULLETED_LIST_INDENT = 24

# =============================================================================
# Conversion Behavior Constants
# =============================================================================


# Attachment handling (unified across all converters) - defined after AttachmentMode type
DEFAULT_ATTACHMENT_OUTPUT_DIR = None
DEFAULT_ATTACHMENT_BASE_URL = None

# Text processing
DEFAULT_ESCAPE_SPECIAL = True
DEFAULT_USE_HASH_HEADINGS = True
DEFAULT_EXTRACT_TITLE = False
DEFAULT_SLIDE_NUMBERS = False

# =============================================================================
# Supported Format Types
# =============================================================================

UnderlineMode = Literal["html", "markdown", "ignore"]
SuperscriptMode = Literal["html", "markdown", "ignore"]
SubscriptMode = Literal["html", "markdown", "ignore"]
EmphasisSymbol = Literal["*", "_"]
AttachmentMode = Literal["skip", "alt_text", "download", "base64"]

# Attachment handling defaults - defined here after AttachmentMode type
DEFAULT_ATTACHMENT_MODE: AttachmentMode = "alt_text"

# =============================================================================
# PDF-specific Constants
# =============================================================================

PDF_MIN_PYMUPDF_VERSION = "1.24.0"

# Header detection constants
DEFAULT_HEADER_MIN_OCCURRENCES = 3
DEFAULT_HEADER_USE_FONT_WEIGHT = True
DEFAULT_HEADER_USE_ALL_CAPS = True
DEFAULT_HEADER_PERCENTILE_THRESHOLD = 75  # Top 25% of font sizes considered headers

# Column detection constants
DEFAULT_DETECT_COLUMNS = True
DEFAULT_MERGE_HYPHENATED_WORDS = True
DEFAULT_HANDLE_ROTATED_TEXT = True
DEFAULT_COLUMN_GAP_THRESHOLD = 20  # Minimum gap between columns in points

# Table detection fallback constants
DEFAULT_TABLE_FALLBACK_DETECTION = True
DEFAULT_DETECT_MERGED_CELLS = True
DEFAULT_TABLE_RULING_LINE_THRESHOLD = 0.5  # Minimum line length ratio for table ruling

DEFAULT_IMAGE_PLACEMENT_MARKERS = True
DEFAULT_INCLUDE_IMAGE_CAPTIONS = True

# Page separator constants
DEFAULT_PAGE_SEPARATOR_FORMAT = "-----"
DEFAULT_INCLUDE_PAGE_NUMBERS = False

# =============================================================================
# HTML to Markdown Constants
# =============================================================================

HTML_EMPHASIS_SYMBOLS = ["*", "_"]
HTML_BULLET_SYMBOLS = "*-+"

# HTML entity handling
DEFAULT_PRESERVE_NBSP = False
HTML_ENTITIES_TO_PRESERVE = ["nbsp"]  # Entities that might need special handling


# Content sanitization
DEFAULT_STRIP_DANGEROUS_ELEMENTS = False
DANGEROUS_HTML_ELEMENTS = {"script", "style", "object", "embed", "form", "input", "iframe"}
DANGEROUS_HTML_ATTRIBUTES = {"onclick", "onload", "onerror", "onmouseover", "onfocus", "onblur", "javascript:"}

# Block structure
DEFAULT_PRESERVE_NESTED_STRUCTURE = True

# Code block handling
MIN_CODE_FENCE_LENGTH = 3
MAX_CODE_FENCE_LENGTH = 10

# Table handling
DEFAULT_TABLE_ALIGNMENT_AUTO_DETECT = True
TABLE_ALIGNMENT_MAPPING = {"left": ":---", "center": ":---:", "right": "---:", "justify": ":---"}

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
    "protect-links.mimecast.com"
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
# File Extension Lists (from __init__.py)
# =============================================================================

PLAINTEXT_EXTENSIONS = [
    ".adoc",
    ".asciidoc",
    ".asm",
    ".asp",
    ".aspx",
    ".atom",
    ".awk",
    ".babelrc",
    ".bash",
    ".bat",
    ".bazel",
    ".bib",
    ".bzl",
    ".c",
    ".cfg",
    ".cjs",
    ".clj",
    ".cmake",
    ".cmd",
    ".coffee",
    ".conf",
    ".config",
    ".cpp",
    ".cs",
    ".csh",
    ".cshtml",
    ".cson",
    ".css",
    ".csv",
    ".cypher",
    ".d",
    ".dart",
    ".desktop",
    ".diff",
    ".dockerfile",
    ".dtd",
    ".editorconfig",
    ".ejs",
    ".el",
    ".elm",
    ".env",
    ".erb",
    ".erl",
    ".eslintignore",
    ".eslintrc",
    ".ex",
    ".exs",
    ".f",
    ".f90",
    ".f95",
    ".fish",
    ".for",
    ".fs",
    ".gemspec",
    ".geojson",
    ".gitattributes",
    ".gitignore",
    ".gn",
    ".go",
    ".gql",
    ".gradle",
    ".graphql",
    ".graphqlrc",
    ".groovy",
    ".gyp",
    ".h",
    ".haml",
    ".hbs",
    ".hcl",
    ".hjson",
    ".hpp",
    ".hrl",
    ".hs",
    ".htaccess",
    ".htm",
    ".html",
    ".htpasswd",
    ".ics",
    ".iml",
    ".inf",
    ".ini",
    ".ipynb",
    ".jade",
    ".java",
    ".jbuilder",
    ".jenkinsfile",
    ".jl",
    ".js",
    ".json",
    ".json5",
    ".jsonld",
    ".jsx",
    ".ksh",
    ".kt",
    ".kts",
    ".less",
    ".liquid",
    ".lisp",
    ".log",
    ".lua",
    ".m",
    ".mak",
    ".make",
    ".markdown",
    ".md",
    ".mdown",
    ".mdwn",
    ".mdx",
    ".mediawiki",
    ".mjs",
    ".mkd",
    ".mkdn",
    ".mm",
    ".mustache",
    ".nfo",
    ".nginx",
    ".nim",
    ".npmrc",
    ".nsi",
    ".nt",
    ".opml",
    ".org",
    ".p",
    ".pas",
    ".patch",
    ".php",
    ".pl",
    ".plist",
    ".pod",
    ".podspec",
    ".pp",
    ".prettierignore",
    ".prisma",
    ".pro",
    ".properties",
    ".proto",
    ".ps1",
    ".pug",
    ".py",
    ".pyx",
    ".r",
    ".rake",
    ".rb",
    ".rdoc",
    ".reg",
    ".rhtml",
    ".robots",
    ".rs",
    ".rss",
    ".rst",
    ".sas",
    ".sass",
    ".sbt",
    ".scala",
    ".scm",
    ".scss",
    ".sed",
    ".sgml",
    ".sh",
    ".shtml",
    ".sitemap",
    ".sql",
    ".styl",
    ".stylelintrc",
    ".svelte",
    ".svg",
    ".swift",
    ".tcl",
    ".tex",
    ".textile",
    ".tf",
    ".thor",
    ".toml",
    ".tpl",
    ".ts",
    ".tsv",
    ".tsx",
    ".ttl",
    ".twig",
    ".txt",
    ".v",
    ".vb",
    ".vbhtml",
    ".vcf",
    ".vhd",
    ".vim",
    ".vue",
    ".webmanifest",
    ".wiki",
    ".wsdl",
    ".wsgi",
    ".xaml",
    ".xhtml",
    ".xml",
    ".xsd",
    ".yaml",
    ".yml",
    ".zsh",
]

DOCUMENT_EXTENSIONS = [".pdf", ".csv", ".xlsx", ".docx", ".pptx", ".eml"]

IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".gif"]
