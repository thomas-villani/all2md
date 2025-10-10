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

from dataclasses import replace
from typing import Any

from all2md.options.asciidoc import AsciiDocOptions, AsciiDocRendererOptions
from all2md.options.base import _UNSET, BaseParserOptions, BaseRendererOptions, CloneFrozenMixin
from all2md.options.chm import ChmOptions
from all2md.options.common import LocalFileAccessOptions, NetworkFetchOptions
from all2md.options.csv import CsvOptions
from all2md.options.docx import DocxOptions, DocxRendererOptions
from all2md.options.eml import EmlOptions
from all2md.options.epub import EpubOptions, EpubRendererOptions
from all2md.options.html import HtmlOptions, HtmlRendererOptions
from all2md.options.ipynb import IpynbOptions
from all2md.options.latex import LatexOptions, LatexRendererOptions
from all2md.options.markdown import MarkdownOptions, MarkdownParserOptions
from all2md.options.mediawiki import MediaWikiOptions
from all2md.options.mhtml import MhtmlOptions
from all2md.options.odp import OdpOptions
from all2md.options.ods import OdsSpreadsheetOptions
from all2md.options.odt import OdtOptions
from all2md.options.pdf import PdfOptions, PdfRendererOptions
from all2md.options.pptx import PptxOptions, PptxRendererOptions
from all2md.options.rst import RstParserOptions, RstRendererOptions
from all2md.options.rtf import RtfOptions
from all2md.options.sourcecode import SourceCodeOptions
from all2md.options.txt import PlainTextOptions
from all2md.options.xlsx import XlsxOptions
from all2md.options.zip import ZipOptions


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

__all__ = [
    "_UNSET",
    "CloneFrozenMixin",
    "BaseRendererOptions",
    "BaseParserOptions",
    "NetworkFetchOptions",
    "LocalFileAccessOptions",
    "AsciiDocRendererOptions",
    "AsciiDocOptions",
    "ChmOptions",
    "CsvOptions",
    "DocxOptions",
    "DocxRendererOptions",
    "EmlOptions",
    "EpubOptions",
    "EpubRendererOptions",
    "HtmlRendererOptions",
    "HtmlOptions",
    "IpynbOptions",
    "LatexRendererOptions",
    "LatexOptions",
    "MarkdownOptions",
    "MarkdownParserOptions",
    "MediaWikiOptions",
    "MhtmlOptions",
    "OdpOptions",
    "OdsSpreadsheetOptions",
    "OdtOptions",
    "PdfOptions",
    "PdfRendererOptions",
    "PptxOptions",
    "PptxRendererOptions",
    "RstParserOptions",
    "RstRendererOptions",
    "RtfOptions",
    "SourceCodeOptions",
    "PlainTextOptions",
    "XlsxOptions",
    "ZipOptions",
    "create_updated_options"
]
