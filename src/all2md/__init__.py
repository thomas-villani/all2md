"""all2md - A Python document conversion library for bidirectional transformation.

all2md provides a comprehensive solution for converting between various file formats
and Markdown. It supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML),
Excel (XLSX), Jupyter Notebooks (IPYNB), EPUB e-books, images, and 200+ text file formats with
intelligent content extraction and formatting preservation.

The library uses a modular architecture where the main `to_markdown()` function
automatically detects file types and routes to appropriate specialized parsers.
Each converter module handles specific format requirements while maintaining
consistent Markdown output with support for tables, images, and complex formatting.

Key Features
------------
- Advanced PDF parsing with table detection using PyMuPDF
- Word document processing with formatting preservation
- PowerPoint slide-by-slide extraction
- HTML processing with configurable conversion options
- Email chain parsing with attachment handling
- Base64 image embedding support
- Support for 200+ plaintext file formats
- AST-based transformation pipeline for document manipulation
- Plugin system for custom transforms via entry points

Supported Formats
-----------------
- **Documents**: PDF, DOCX, PPTX, HTML, EML, EPUB
- **Notebooks**: IPYNB (Jupyter Notebooks)
- **Spreadsheets**: XLSX, CSV, TSV
- **Images**: PNG, JPEG, GIF (embedded as base64)
- **Text**: 200+ formats including code files, configs, markup

Requirements
------------
- Python 3.12+
- Optional dependencies loaded per format (PyMuPDF, python-docx, etc.)

Examples
--------
Basic usage for file conversion:

    >>> from all2md import to_markdown
    >>> markdown_content = to_markdown('document.pdf')
    >>> print(markdown_content)

Using AST transforms to manipulate documents:

    >>> from all2md import to_markdown
    >>> from all2md.transforms import RemoveImagesTransform, HeadingOffsetTransform
    >>>
    >>> # Apply transforms during conversion
    >>> markdown = to_markdown(
    ...     'document.pdf',
    ...     transforms=[
    ...         RemoveImagesTransform(),
    ...         HeadingOffsetTransform(offset=1)
    ...     ]
    ... )

Working with the AST directly:

    >>> from all2md import to_ast
    >>> from all2md.transforms import render
    >>>
    >>> # Convert to AST
    >>> doc = to_ast('document.pdf')
    >>>
    >>> # Apply transforms and render
    >>> markdown = render(doc, transforms=['remove-images', 'heading-offset'])

See Also
--------
all2md.transforms : AST transformation system
all2md.ast : AST node definitions and utilities

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

# Check Python version before any imports
import sys

if sys.version_info < (3, 12):
    raise ImportError(
        "all2md requires Python 3.12 or later. "
        f"You are using Python {sys.version_info.major}.{sys.version_info.minor}."
    )

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from all2md.ast import Document  # noqa: F401 - used in docstrings

from all2md.api import convert, from_ast, from_markdown, to_ast, to_markdown
from all2md.constants import DocumentFormat

# Extensions lists moved to constants.py - keep references for backward compatibility
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, DependencyError, FormatError, ParsingError
from all2md.options.asciidoc import AsciiDocOptions, AsciiDocRendererOptions
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.chm import ChmOptions
from all2md.options.common import LocalFileAccessOptions, NetworkFetchOptions
from all2md.options.csv import CsvOptions
from all2md.options.docx import DocxOptions, DocxRendererOptions
from all2md.options.eml import EmlOptions
from all2md.options.epub import EpubOptions, EpubRendererOptions
from all2md.options.html import HtmlOptions, HtmlRendererOptions
from all2md.options.ipynb import IpynbOptions, IpynbRendererOptions
from all2md.options.latex import LatexOptions, LatexRendererOptions
from all2md.options.markdown import MarkdownOptions, MarkdownParserOptions
from all2md.options.mediawiki import MediaWikiOptions
from all2md.options.mhtml import MhtmlOptions
from all2md.options.odp import OdpOptions
from all2md.options.ods import OdsSpreadsheetOptions
from all2md.options.odt import OdtOptions
from all2md.options.pdf import PdfOptions, PdfRendererOptions
from all2md.options.plaintext import PlainTextOptions
from all2md.options.pptx import PptxOptions, PptxRendererOptions
from all2md.options.rst import RstParserOptions, RstRendererOptions
from all2md.options.rtf import RtfOptions
from all2md.options.sourcecode import SourceCodeOptions
from all2md.options.xlsx import XlsxOptions
from all2md.options.zip import ZipOptions
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.utils.input_sources import RemoteInputOptions

# Import parsers to trigger registration
# Import AST module for advanced users
from . import (
    ast,  # noqa: F401
    parsers,  # noqa: F401
    transforms,  # noqa: F401
)

logger = logging.getLogger(__name__)

# Options handling helpers


__all__ = [
    "to_markdown",
    "to_ast",
    "from_ast",
    "from_markdown",
    "convert",
    # Registry system
    "registry",
    # Type definitions
    "DocumentFormat",
    # Progress system
    "ProgressCallback",
    "ProgressEvent",
    # Re-exported classes and exceptions for public API
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
    "IpynbRendererOptions",
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
    "RemoteInputOptions",
    # Exceptions
    "DependencyError",
    "All2MdError",
    "FormatError",
    "ParsingError",
    # AST module (for advanced users)
    "ast",
    # Transforms module (for AST transformations)
    "transforms",
]
