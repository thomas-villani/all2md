"""Constants and default values for mdparse library.

This module centralizes all hardcoded values, magic numbers, and default
configuration constants used across the mdparse library. This improves
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

# Image handling
DEFAULT_CONVERT_IMAGES_TO_BASE64 = False
DEFAULT_REMOVE_IMAGES = False

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

# =============================================================================
# PDF-specific Constants
# =============================================================================

PDF_MIN_PYMUPDF_VERSION = "1.24.0"

# =============================================================================
# HTML to Markdown Constants
# =============================================================================

HTML_EMPHASIS_SYMBOLS = ["*", "_"]
HTML_BULLET_SYMBOLS = "*-+"

# =============================================================================
# Email Processing Constants
# =============================================================================

EMAIL_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %z",
    "%d %b %Y %H:%M:%S %z",
    "%a, %d %b %Y %H:%M:%S",
    "%d %b %Y %H:%M:%S"
]

# =============================================================================
# PDF to Markdown Constants
# =============================================================================

PDF_DEFAULT_PAGE_SIZE = "A4"
PDF_PAGE_SIZES = {
    "A4": (595.0, 842.0),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (842.0, 1191.0),
    "A5": (420.0, 595.0)
}

PDF_DEFAULT_MARGINS = (50, 50, 50, 50)  # top, right, bottom, left

# =============================================================================
# File Extension Lists (from __init__.py)
# =============================================================================

PLAINTEXT_EXTENSIONS = [
    ".adoc", ".asciidoc", ".asm", ".asp", ".aspx", ".atom", ".awk", ".babelrc", ".bash",
    ".bat", ".bazel", ".bib", ".bzl", ".c", ".cfg", ".cjs", ".clj", ".cmake",
    ".cmd", ".coffee", ".conf", ".config", ".cpp", ".cs", ".csh", ".cshtml", ".cson",
    ".css", ".csv", ".cypher", ".d", ".dart", ".desktop", ".diff", ".dockerfile", ".dtd",
    ".editorconfig", ".ejs", ".el", ".elm", ".env", ".erb", ".erl", ".eslintignore", ".eslintrc",
    ".ex", ".exs", ".f", ".f90", ".f95", ".fish", ".for", ".fs", ".gemspec",
    ".geojson", ".gitattributes", ".gitignore", ".gn", ".go", ".gql", ".gradle", ".graphql", ".graphqlrc",
    ".groovy", ".gyp", ".h", ".haml", ".hbs", ".hcl", ".hjson", ".hpp", ".hrl",
    ".hs", ".htaccess", ".htm", ".html", ".htpasswd", ".ics", ".iml", ".inf", ".ini",
    ".ipynb", ".jade", ".java", ".jbuilder", ".jenkinsfile", ".jl", ".js", ".json", ".json5",
    ".jsonld", ".jsx", ".ksh", ".kt", ".kts", ".less", ".liquid", ".lisp", ".log",
    ".lua", ".m", ".mak", ".make", ".markdown", ".md", ".mdown", ".mdwn", ".mdx",
    ".mediawiki", ".mjs", ".mkd", ".mkdn", ".mm", ".mustache", ".nfo", ".nginx", ".nim",
    ".npmrc", ".nsi", ".nt", ".opml", ".org", ".p", ".pas", ".patch", ".php",
    ".pl", ".plist", ".pod", ".podspec", ".pp", ".prettierignore", ".prisma", ".pro", ".properties",
    ".proto", ".ps1", ".pug", ".py", ".pyx", ".r", ".rake", ".rb", ".rdoc",
    ".reg", ".rhtml", ".robots", ".rs", ".rss", ".rst", ".sas", ".sass", ".sbt",
    ".scala", ".scm", ".scss", ".sed", ".sgml", ".sh", ".shtml", ".sitemap", ".sql",
    ".styl", ".stylelintrc", ".svelte", ".svg", ".swift", ".tcl", ".tex", ".textile", ".tf",
    ".thor", ".toml", ".tpl", ".ts", ".tsv", ".tsx", ".ttl", ".twig", ".txt",
    ".v", ".vb", ".vbhtml", ".vcf", ".vhd", ".vim", ".vue", ".webmanifest", ".wiki",
    ".wsdl", ".wsgi", ".xaml", ".xhtml", ".xml", ".xsd", ".yaml", ".yml", ".zsh",
]

DOCUMENT_EXTENSIONS = [
    ".pdf", ".csv", ".xlsx", ".docx", ".pptx", ".eml"
]

IMAGE_EXTENSIONS = [
    ".jpg", ".jpeg", ".png", ".gif"
]
