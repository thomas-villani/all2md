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
- Python 3.10+
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

if sys.version_info < (3, 10):
    raise ImportError(
        f"all2md requires Python 3.10 or later. You are using Python {sys.version_info.major}.{sys.version_info.minor}."
    )

__version__ = "1.11.0"

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Import heavy modules for type checking without runtime overhead
    from all2md import ast, parsers, transforms  # noqa: F401
    from all2md.ast import Document  # noqa: F401 - used in docstrings

    # Import all option classes for type checking
    from all2md.options.archive import ArchiveOptions  # noqa: F401
    from all2md.options.asciidoc import AsciiDocOptions, AsciiDocRendererOptions  # noqa: F401
    from all2md.options.ast_json import AstJsonParserOptions, AstJsonRendererOptions  # noqa: F401
    from all2md.options.bbcode import BBCodeParserOptions  # noqa: F401
    from all2md.options.chm import ChmOptions  # noqa: F401
    from all2md.options.csv import CsvOptions, CsvRendererOptions  # noqa: F401
    from all2md.options.docx import DocxOptions, DocxRendererOptions  # noqa: F401
    from all2md.options.dokuwiki import DokuWikiOptions, DokuWikiParserOptions  # noqa: F401
    from all2md.options.eml import EmlOptions  # noqa: F401
    from all2md.options.enex import EnexOptions  # noqa: F401
    from all2md.options.epub import EpubOptions, EpubRendererOptions  # noqa: F401
    from all2md.options.fb2 import Fb2Options  # noqa: F401
    from all2md.options.html import HtmlOptions, HtmlRendererOptions  # noqa: F401
    from all2md.options.ini import IniParserOptions, IniRendererOptions  # noqa: F401
    from all2md.options.ipynb import IpynbOptions, IpynbRendererOptions  # noqa: F401
    from all2md.options.jinja import JinjaRendererOptions  # noqa: F401
    from all2md.options.json import JsonParserOptions, JsonRendererOptions  # noqa: F401
    from all2md.options.latex import LatexOptions, LatexRendererOptions  # noqa: F401
    from all2md.options.markdown import MarkdownParserOptions, MarkdownRendererOptions  # noqa: F401
    from all2md.options.mbox import MboxOptions  # noqa: F401
    from all2md.options.mediawiki import MediaWikiOptions, MediaWikiParserOptions  # noqa: F401
    from all2md.options.mhtml import MhtmlOptions  # noqa: F401
    from all2md.options.odp import OdpOptions, OdpRendererOptions  # noqa: F401
    from all2md.options.ods import OdsSpreadsheetOptions  # noqa: F401
    from all2md.options.odt import OdtOptions, OdtRendererOptions  # noqa: F401
    from all2md.options.openapi import OpenApiParserOptions  # noqa: F401
    from all2md.options.org import OrgParserOptions, OrgRendererOptions  # noqa: F401
    from all2md.options.outlook import OutlookOptions  # noqa: F401
    from all2md.options.pdf import PdfOptions, PdfRendererOptions  # noqa: F401
    from all2md.options.plaintext import PlainTextOptions, PlainTextParserOptions  # noqa: F401
    from all2md.options.pptx import PptxOptions, PptxRendererOptions  # noqa: F401
    from all2md.options.rst import RstParserOptions, RstRendererOptions  # noqa: F401
    from all2md.options.rtf import RtfOptions, RtfRendererOptions  # noqa: F401
    from all2md.options.sourcecode import SourceCodeOptions  # noqa: F401
    from all2md.options.textile import TextileParserOptions, TextileRendererOptions  # noqa: F401
    from all2md.options.toml import TomlParserOptions, TomlRendererOptions  # noqa: F401
    from all2md.options.webarchive import WebArchiveOptions  # noqa: F401
    from all2md.options.xlsx import XlsxOptions  # noqa: F401
    from all2md.options.yaml import YamlParserOptions, YamlRendererOptions  # noqa: F401
    from all2md.options.zip import ZipOptions  # noqa: F401
    from all2md.utils.input_sources import RemoteInputOptions  # noqa: F401

from all2md.api import (
    chunk,
    confidence_report,
    convert,
    from_ast,
    from_markdown,
    optimizable_formats,
    optimize_options,
    roundtrip_report,
    roundtrippable_formats,
    to_ast,
    to_markdown,
)
from all2md.confidence import ConfidenceReport, DegradedEvent
from all2md.constants import DocumentFormat

# Extensions lists moved to constants.py - keep references for backward compatibility
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, DependencyError, FormatError, ParsingError
from all2md.optimize import Candidate, DocumentMetrics, OptimizationReport

# Keep only base and common option classes that are lightweight and frequently used
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.common import LocalFileAccessOptions, NetworkFetchOptions
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.roundtrip import RoundTripReport, StructuralDelta

# Import parsers to trigger registration (must be eager, not lazy)
from . import parsers  # noqa: F401

# Lazy loading for heavy modules - only imported when accessed
# This significantly improves CLI startup time by deferring AST and transforms
# Note: parsers must be imported eagerly to trigger auto-discovery
_lazy_modules = {
    "ast": "all2md.ast",
    "transforms": "all2md.transforms",
}

# Lazy loading for option classes - maps class name to (module_path, class_name)
_lazy_options = {
    "ArchiveOptions": ("all2md.options.archive", "ArchiveOptions"),
    "AsciiDocOptions": ("all2md.options.asciidoc", "AsciiDocOptions"),
    "AsciiDocRendererOptions": ("all2md.options.asciidoc", "AsciiDocRendererOptions"),
    "AstJsonParserOptions": ("all2md.options.ast_json", "AstJsonParserOptions"),
    "AstJsonRendererOptions": ("all2md.options.ast_json", "AstJsonRendererOptions"),
    "BBCodeParserOptions": ("all2md.options.bbcode", "BBCodeParserOptions"),
    "ChmOptions": ("all2md.options.chm", "ChmOptions"),
    "CsvOptions": ("all2md.options.csv", "CsvOptions"),
    "CsvRendererOptions": ("all2md.options.csv", "CsvRendererOptions"),
    "DocxOptions": ("all2md.options.docx", "DocxOptions"),
    "DocxRendererOptions": ("all2md.options.docx", "DocxRendererOptions"),
    "DokuWikiOptions": ("all2md.options.dokuwiki", "DokuWikiOptions"),
    "DokuWikiParserOptions": ("all2md.options.dokuwiki", "DokuWikiParserOptions"),
    "EmlOptions": ("all2md.options.eml", "EmlOptions"),
    "EnexOptions": ("all2md.options.enex", "EnexOptions"),
    "EpubOptions": ("all2md.options.epub", "EpubOptions"),
    "EpubRendererOptions": ("all2md.options.epub", "EpubRendererOptions"),
    "Fb2Options": ("all2md.options.fb2", "Fb2Options"),
    "HtmlOptions": ("all2md.options.html", "HtmlOptions"),
    "HtmlRendererOptions": ("all2md.options.html", "HtmlRendererOptions"),
    "IniParserOptions": ("all2md.options.ini", "IniParserOptions"),
    "IniRendererOptions": ("all2md.options.ini", "IniRendererOptions"),
    "IpynbOptions": ("all2md.options.ipynb", "IpynbOptions"),
    "IpynbRendererOptions": ("all2md.options.ipynb", "IpynbRendererOptions"),
    "JinjaRendererOptions": ("all2md.options.jinja", "JinjaRendererOptions"),
    "JsonParserOptions": ("all2md.options.json", "JsonParserOptions"),
    "JsonRendererOptions": ("all2md.options.json", "JsonRendererOptions"),
    "LatexOptions": ("all2md.options.latex", "LatexOptions"),
    "LatexRendererOptions": ("all2md.options.latex", "LatexRendererOptions"),
    "MarkdownParserOptions": ("all2md.options.markdown", "MarkdownParserOptions"),
    "MarkdownRendererOptions": ("all2md.options.markdown", "MarkdownRendererOptions"),
    "MboxOptions": ("all2md.options.mbox", "MboxOptions"),
    "MediaWikiOptions": ("all2md.options.mediawiki", "MediaWikiOptions"),
    "MediaWikiParserOptions": ("all2md.options.mediawiki", "MediaWikiParserOptions"),
    "MhtmlOptions": ("all2md.options.mhtml", "MhtmlOptions"),
    "OdpOptions": ("all2md.options.odp", "OdpOptions"),
    "OdpRendererOptions": ("all2md.options.odp", "OdpRendererOptions"),
    "OdsSpreadsheetOptions": ("all2md.options.ods", "OdsSpreadsheetOptions"),
    "OdtOptions": ("all2md.options.odt", "OdtOptions"),
    "OdtRendererOptions": ("all2md.options.odt", "OdtRendererOptions"),
    "OpenApiParserOptions": ("all2md.options.openapi", "OpenApiParserOptions"),
    "OrgParserOptions": ("all2md.options.org", "OrgParserOptions"),
    "OrgRendererOptions": ("all2md.options.org", "OrgRendererOptions"),
    "OutlookOptions": ("all2md.options.outlook", "OutlookOptions"),
    "PdfOptions": ("all2md.options.pdf", "PdfOptions"),
    "PdfRendererOptions": ("all2md.options.pdf", "PdfRendererOptions"),
    "PlainTextOptions": ("all2md.options.plaintext", "PlainTextOptions"),
    "PlainTextParserOptions": ("all2md.options.plaintext", "PlainTextParserOptions"),
    "PptxOptions": ("all2md.options.pptx", "PptxOptions"),
    "PptxRendererOptions": ("all2md.options.pptx", "PptxRendererOptions"),
    "RstParserOptions": ("all2md.options.rst", "RstParserOptions"),
    "RstRendererOptions": ("all2md.options.rst", "RstRendererOptions"),
    "RtfOptions": ("all2md.options.rtf", "RtfOptions"),
    "RtfRendererOptions": ("all2md.options.rtf", "RtfRendererOptions"),
    "SourceCodeOptions": ("all2md.options.sourcecode", "SourceCodeOptions"),
    "TextileParserOptions": ("all2md.options.textile", "TextileParserOptions"),
    "TextileRendererOptions": ("all2md.options.textile", "TextileRendererOptions"),
    "TomlParserOptions": ("all2md.options.toml", "TomlParserOptions"),
    "TomlRendererOptions": ("all2md.options.toml", "TomlRendererOptions"),
    "WebArchiveOptions": ("all2md.options.webarchive", "WebArchiveOptions"),
    "XlsxOptions": ("all2md.options.xlsx", "XlsxOptions"),
    "YamlParserOptions": ("all2md.options.yaml", "YamlParserOptions"),
    "YamlRendererOptions": ("all2md.options.yaml", "YamlRendererOptions"),
    "ZipOptions": ("all2md.options.zip", "ZipOptions"),
    "RemoteInputOptions": ("all2md.utils.input_sources", "RemoteInputOptions"),
}

# Options handling helpers


__all__ = [
    "__version__",
    "to_markdown",
    "to_ast",
    "from_ast",
    "from_markdown",
    "convert",
    "chunk",
    # Conversion confidence ("quality card")
    "confidence_report",
    "ConfidenceReport",
    "DegradedEvent",
    # Round-trip fidelity scoring
    "roundtrip_report",
    "roundtrippable_formats",
    "RoundTripReport",
    "StructuralDelta",
    # Conversion optimizer
    "optimize_options",
    "optimizable_formats",
    "OptimizationReport",
    "Candidate",
    "DocumentMetrics",
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
    "ArchiveOptions",
    "AsciiDocOptions",
    "AsciiDocRendererOptions",
    "AstJsonParserOptions",
    "AstJsonRendererOptions",
    "BBCodeParserOptions",
    "ChmOptions",
    "CsvOptions",
    "CsvRendererOptions",
    "DocxOptions",
    "DocxRendererOptions",
    "DokuWikiOptions",
    "DokuWikiParserOptions",
    "EmlOptions",
    "EnexOptions",
    "EpubOptions",
    "EpubRendererOptions",
    "Fb2Options",
    "HtmlOptions",
    "HtmlRendererOptions",
    "IniParserOptions",
    "IniRendererOptions",
    "IpynbOptions",
    "IpynbRendererOptions",
    "JinjaRendererOptions",
    "JsonParserOptions",
    "JsonRendererOptions",
    "LatexOptions",
    "LatexRendererOptions",
    "MarkdownParserOptions",
    "MarkdownRendererOptions",
    "MboxOptions",
    "MediaWikiOptions",
    "MediaWikiParserOptions",
    "MhtmlOptions",
    "OdpOptions",
    "OdpRendererOptions",
    "OdsSpreadsheetOptions",
    "OdtOptions",
    "OdtRendererOptions",
    "OpenApiParserOptions",
    "OrgParserOptions",
    "OrgRendererOptions",
    "OutlookOptions",
    "PdfOptions",
    "PdfRendererOptions",
    "PlainTextOptions",
    "PlainTextParserOptions",
    "PptxOptions",
    "PptxRendererOptions",
    "RstParserOptions",
    "RstRendererOptions",
    "RtfOptions",
    "RtfRendererOptions",
    "SourceCodeOptions",
    "TextileParserOptions",
    "TextileRendererOptions",
    "TomlParserOptions",
    "TomlRendererOptions",
    "WebArchiveOptions",
    "XlsxOptions",
    "YamlParserOptions",
    "YamlRendererOptions",
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


def __getattr__(name: str) -> Any:
    """Lazy load heavy modules and option classes on first access.

    This function is called when an attribute is not found in the module namespace.
    It allows us to defer importing heavy modules (ast, parsers, transforms) and
    option classes until they are actually accessed, significantly improving CLI
    startup time.

    Parameters
    ----------
    name : str
        The name of the attribute being accessed

    Returns
    -------
    Any
        The requested module, class, or attribute

    Raises
    ------
    AttributeError
        If the attribute is not found and is not a lazy-loadable item

    """
    import importlib

    # Check if it's a lazy-loaded module
    if name in _lazy_modules:
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
        module = importlib.import_module(_lazy_modules[name])
        # Cache the module in this module's namespace for faster future access
        globals()[name] = module
        return module

    # Check if it's a lazy-loaded option class
    if name in _lazy_options:
        module_path, class_name = _lazy_options[name]
        # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        # Cache the class in this module's namespace for faster future access
        globals()[name] = cls
        return cls

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
