#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options and settings for all2md conversion modules.

This module provides dataclass-based configuration options for all conversion
modules in the all2md library. Using dataclasses provides type safety,
default values, and a clean API for configuring conversion behavior.

Each converter module has its own Options dataclass with module-specific
parameters.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from all2md.options.asciidoc import AsciiDocOptions, AsciiDocRendererOptions
from all2md.options.ast_json import AstJsonParserOptions, AstJsonRendererOptions
from all2md.options.base import UNSET, BaseParserOptions, BaseRendererOptions, CloneFrozenMixin
from all2md.options.chm import ChmOptions
from all2md.options.common import AttachmentOptionsMixin, LocalFileAccessOptions, NetworkFetchOptions
from all2md.options.csv import CsvOptions
from all2md.options.docx import DocxOptions, DocxRendererOptions
from all2md.options.dokuwiki import DokuWikiOptions, DokuWikiParserOptions
from all2md.options.eml import EmlOptions
from all2md.options.epub import EpubOptions, EpubRendererOptions
from all2md.options.fb2 import Fb2Options
from all2md.options.html import HtmlOptions, HtmlRendererOptions
from all2md.options.ipynb import IpynbOptions, IpynbRendererOptions
from all2md.options.jinja import JinjaRendererOptions
from all2md.options.latex import LatexOptions, LatexRendererOptions
from all2md.options.markdown import MarkdownParserOptions, MarkdownRendererOptions
from all2md.options.mediawiki import MediaWikiOptions
from all2md.options.mhtml import MhtmlOptions
from all2md.options.odp import OdpOptions, OdpRendererOptions
from all2md.options.ods import OdsSpreadsheetOptions
from all2md.options.odt import OdtOptions, OdtRendererOptions
from all2md.options.org import OrgParserOptions, OrgRendererOptions
from all2md.options.pdf import PdfOptions, PdfRendererOptions
from all2md.options.plaintext import PlainTextOptions
from all2md.options.pptx import PptxOptions, PptxRendererOptions
from all2md.options.rst import RstParserOptions, RstRendererOptions
from all2md.options.rtf import RtfOptions, RtfRendererOptions
from all2md.options.sourcecode import SourceCodeOptions
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
    "CloneFrozenMixin",
    "BaseRendererOptions",
    "BaseParserOptions",
    "AttachmentOptionsMixin",
    "NetworkFetchOptions",
    "LocalFileAccessOptions",
    "AsciiDocRendererOptions",
    "AsciiDocOptions",
    "AstJsonParserOptions",
    "AstJsonRendererOptions",
    "ChmOptions",
    "CsvOptions",
    "DocxOptions",
    "DocxRendererOptions",
    "DokuWikiOptions",
    "DokuWikiParserOptions",
    "EmlOptions",
    "EpubOptions",
    "EpubRendererOptions",
    "Fb2Options",
    "HtmlRendererOptions",
    "HtmlOptions",
    "IpynbOptions",
    "IpynbRendererOptions",
    "JinjaRendererOptions",
    "LatexRendererOptions",
    "LatexOptions",
    "MarkdownRendererOptions",
    "MarkdownParserOptions",
    "MediaWikiOptions",
    "MhtmlOptions",
    "OdpOptions",
    "OdpRendererOptions",
    "OdsSpreadsheetOptions",
    "OdtOptions",
    "OdtRendererOptions",
    "OrgParserOptions",
    "OrgRendererOptions",
    "PdfOptions",
    "PdfRendererOptions",
    "PptxOptions",
    "PptxRendererOptions",
    "RstParserOptions",
    "RstRendererOptions",
    "RtfRendererOptions",
    "RtfOptions",
    "SourceCodeOptions",
    "PlainTextOptions",
    "UNSET",
    "XlsxOptions",
    "ZipOptions",
    "create_updated_options",
]
