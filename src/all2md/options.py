"""Configuration options and settings for all2md conversion modules.

This module provides dataclass-based configuration options for all conversion
modules in the all2md library. Using dataclasses provides type safety,
default values, and a clean API for configuring conversion behavior.

Each converter module has its own Options dataclass with module-specific
parameters, plus a shared MarkdownOptions class for common Markdown formatting
settings that apply across multiple converters.

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

from dataclasses import dataclass
from typing import Any

from .constants import (
    DEFAULT_BULLET_SYMBOLS,
    DEFAULT_BULLETED_LIST_INDENT,
    DEFAULT_CONVERT_IMAGES_TO_BASE64,
    DEFAULT_EMPHASIS_SYMBOL,
    DEFAULT_ESCAPE_SPECIAL,
    DEFAULT_EXTRACT_TITLE,
    DEFAULT_LIST_INDENT_WIDTH,
    DEFAULT_PAGE_SEPARATOR,
    DEFAULT_REMOVE_IMAGES,
    DEFAULT_SLIDE_NUMBERS,
    DEFAULT_USE_HASH_HEADINGS,
    PDF_DEFAULT_MARGINS,
    PDF_DEFAULT_PAGE_SIZE,
    EmphasisSymbol,
    SubscriptMode,
    SuperscriptMode,
    UnderlineMode,
)


@dataclass
class MarkdownOptions:
    r"""Common Markdown formatting options used across conversion modules.

    This dataclass contains settings that control how Markdown output is
    formatted and structured. These options are used by multiple conversion
    modules to ensure consistent Markdown generation.

    Parameters
    ----------
    escape_special : bool, default True
        Whether to escape special Markdown characters in text content.
        When True, characters like *, _, #, [, ], (, ), \ are escaped
        to prevent unintended formatting.
    emphasis_symbol : {"*", "_"}, default "*"
        Symbol to use for emphasis/italic formatting in Markdown.
    bullet_symbols : str, default "*-+"
        Characters to cycle through for nested bullet lists.
    page_separator : str, default "-----"
        Text used to separate pages or sections in output.
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
    """

    escape_special: bool = DEFAULT_ESCAPE_SPECIAL
    emphasis_symbol: EmphasisSymbol = DEFAULT_EMPHASIS_SYMBOL
    bullet_symbols: str = DEFAULT_BULLET_SYMBOLS
    page_separator: str = DEFAULT_PAGE_SEPARATOR
    list_indent_width: int = DEFAULT_LIST_INDENT_WIDTH
    underline_mode: UnderlineMode = "html"
    superscript_mode: SuperscriptMode = "html"
    subscript_mode: SubscriptMode = "html"


@dataclass
class PdfOptions:
    """Configuration options for PDF-to-Markdown conversion.

    This dataclass contains settings specific to PDF document processing,
    including page selection, image handling, and formatting preferences.

    Parameters
    ----------
    pages : list[int] or None, default None
        Specific page numbers to convert (0-based indexing).
        If None, converts all pages.
    convert_images_to_base64 : bool, default False
        Whether to embed images as base64-encoded data URLs.
    password : str or None, default None
        Password for encrypted PDF documents.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert only pages 1-3 with base64 images:
        >>> options = PdfOptions(pages=[0, 1, 2], convert_images_to_base64=True)

    Convert with custom Markdown formatting:
        >>> md_opts = MarkdownOptions(emphasis_symbol="_", page_separator="---")
        >>> options = PdfOptions(markdown_options=md_opts)
    """

    pages: list[int] | None = None
    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    password: str | None = None
    markdown_options: MarkdownOptions | None = None


@dataclass
class DocxOptions:
    """Configuration options for DOCX-to-Markdown conversion.

    This dataclass contains settings specific to Word document processing,
    including image handling and formatting preferences.

    Parameters
    ----------
    convert_images_to_base64 : bool, default False
        Whether to embed images as base64-encoded data URLs.
    preserve_tables : bool, default True
        Whether to preserve table formatting in Markdown.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with base64 image embedding:
        >>> options = DocxOptions(convert_images_to_base64=True)

    Convert with custom bullet symbols:
        >>> md_opts = MarkdownOptions(bullet_symbols="•→◦")
        >>> options = DocxOptions(markdown_options=md_opts)
    """

    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    preserve_tables: bool = True
    markdown_options: MarkdownOptions | None = None


@dataclass
class HtmlOptions:
    """Configuration options for HTML-to-Markdown conversion.

    This dataclass contains settings specific to HTML document processing,
    including heading styles, title extraction, and image handling.

    Parameters
    ----------
    use_hash_headings : bool, default True
        Whether to use # syntax for headings instead of underline style.
    extract_title : bool, default False
        Whether to extract and use the HTML <title> element.
    remove_images : bool, default False
        Whether to completely remove images from the output.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with underline-style headings:
        >>> options = HtmlOptions(use_hash_headings=False)

    Convert and extract page title:
        >>> options = HtmlOptions(extract_title=True, remove_images=True)
    """

    use_hash_headings: bool = DEFAULT_USE_HASH_HEADINGS
    extract_title: bool = DEFAULT_EXTRACT_TITLE
    remove_images: bool = DEFAULT_REMOVE_IMAGES
    markdown_options: MarkdownOptions | None = None


@dataclass
class PptxOptions:
    """Configuration options for PPTX-to-Markdown conversion.

    This dataclass contains settings specific to PowerPoint presentation
    processing, including slide numbering and image handling.

    Parameters
    ----------
    convert_images_to_base64 : bool, default False
        Whether to embed images as base64-encoded data URLs.
    slide_numbers : bool, default False
        Whether to include slide numbers in the output.
    include_notes : bool, default True
        Whether to include speaker notes in the conversion.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert with slide numbers and base64 images:
        >>> options = PptxOptions(slide_numbers=True, convert_images_to_base64=True)

    Convert slides only (no notes):
        >>> options = PptxOptions(include_notes=False)
    """

    convert_images_to_base64: bool = DEFAULT_CONVERT_IMAGES_TO_BASE64
    slide_numbers: bool = DEFAULT_SLIDE_NUMBERS
    include_notes: bool = True
    markdown_options: MarkdownOptions | None = None


@dataclass
class EmlOptions:
    """Configuration options for EML-to-Markdown conversion.

    This dataclass contains settings specific to email message processing,
    including thread handling and header extraction.

    Parameters
    ----------
    include_headers : bool, default True
        Whether to include email headers (From, To, Subject, Date) in output.
    include_attachments_info : bool, default True
        Whether to include attachment information in the output.
    preserve_thread_structure : bool, default True
        Whether to maintain email thread/reply chain structure.
    markdown_options : MarkdownOptions or None, default None
        Common Markdown formatting options. If None, uses defaults.

    Examples
    --------
    Convert email with minimal headers:
        >>> options = EmlOptions(include_headers=True, include_attachments_info=False)

    Convert as flat list (no thread structure):
        >>> options = EmlOptions(preserve_thread_structure=False)
    """

    include_headers: bool = True
    include_attachments_info: bool = True
    preserve_thread_structure: bool = True
    markdown_options: MarkdownOptions | None = None


@dataclass
class Markdown2PdfOptions:
    """Configuration options for Markdown-to-PDF conversion.

    This dataclass contains settings for converting Markdown content
    to PDF format, including styling and layout options.

    Parameters
    ----------
    styles : dict[str, dict] or None, default None
        Custom style definitions for PDF elements.
    page_size : str, default "A4"
        Page size for PDF output ("A4", "Letter", "Legal", "A3", "A5").
    margins : tuple[float, float, float, float] or None, default None
        Page margins as (top, right, bottom, left) in points.

    Examples
    --------
    Create PDF with custom margins:
        >>> options = Markdown2PdfOptions(margins=(72, 72, 72, 72))  # 1 inch margins

    Create Letter-sized PDF:
        >>> options = Markdown2PdfOptions(page_size="Letter")
    """

    styles: dict[str, dict] | None = None
    page_size: str = PDF_DEFAULT_PAGE_SIZE
    margins: tuple[float, float, float, float] | None = PDF_DEFAULT_MARGINS


@dataclass
class Markdown2DocxOptions:
    """Configuration options for Markdown-to-DOCX conversion.

    This dataclass contains settings for converting Markdown content
    to Word document format, including styling and document options.

    Parameters
    ----------
    template_document : Any or None, default None
        Existing Word document to use as a template.
    preserve_styles : bool, default True
        Whether to preserve and apply Word document styles.
    bulleted_list_indent : int, default 24
        Indentation amount for bulleted lists in points.

    Examples
    --------
    Convert with custom list indentation:
        >>> options = Markdown2DocxOptions(bulleted_list_indent=36)

    Use existing document as template:
        >>> from docx import Document
        >>> template = Document("template.docx")
        >>> options = Markdown2DocxOptions(template_document=template)
    """

    template_document: Any | None = None
    preserve_styles: bool = True
    bulleted_list_indent: int = DEFAULT_BULLETED_LIST_INDENT

