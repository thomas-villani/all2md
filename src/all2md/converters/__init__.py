#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the “Software”), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# src/all2md/converters/__init__.py
"""Converters package initialization and auto-registration."""

from all2md.converter_metadata import ConverterMetadata
from all2md.converter_registry import registry

# Import converters that have CONVERTER_METADATA defined
# This will trigger their registration with the registry

try:
    from .html2markdown import CONVERTER_METADATA as html_metadata
    registry.register(html_metadata)
except (ImportError, AttributeError):
    pass

# PDF converter has circular import issues with fitz, register manually
registry.register(ConverterMetadata(
    format_name="pdf",
    extensions=[".pdf"],
    mime_types=["application/pdf", "application/x-pdf"],
    magic_bytes=[
        (b"%PDF", 0),  # PDF signature
    ],
    converter_module="all2md.converters.pdf2markdown",
    converter_function="pdf_to_markdown",
    required_packages=[("pymupdf", ">=1.24.0")],
    import_error_message=(
        "PDF conversion requires 'pymupdf' version 1.24.0 or later. "
        "Install with: pip install 'pymupdf>=1.24.0'"
    ),
    options_class="PdfOptions",
    description="Convert PDF documents to Markdown with advanced table detection",
    priority=10
))

# DOCX converter has similar issues, register manually
registry.register(ConverterMetadata(
    format_name="docx",
    extensions=[".docx"],
    mime_types=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature (docx is ZIP-based)
    ],
    converter_module="all2md.converters.docx2markdown",
    converter_function="docx_to_markdown",
    required_packages=[("python-docx", "")],
    import_error_message=(
        "DOCX conversion requires 'python-docx'. "
        "Install with: pip install python-docx"
    ),
    options_class="DocxOptions",
    description="Convert Microsoft Word DOCX documents to Markdown",
    priority=8
))

# Register converters that don't have metadata yet with basic info
# This provides fallback support for formats

# EML converter - uses standard library, no dependencies
registry.register(ConverterMetadata(
    format_name="eml",
    extensions=[".eml", ".msg"],
    mime_types=["message/rfc822"],
    magic_bytes=[
        (b"Return-Path:", 0),
        (b"Received:", 0),
        (b"From:", 0),
        (b"To:", 0),
        (b"Subject:", 0),
    ],
    converter_module="all2md.converters.eml2markdown",
    converter_function="eml_to_markdown",
    required_packages=[],
    options_class="EmlOptions",
    description="Convert email messages to Markdown",
    priority=6
))

# IPYNB converter - uses standard library json
registry.register(ConverterMetadata(
    format_name="ipynb",
    extensions=[".ipynb"],
    mime_types=["application/json"],
    magic_bytes=[
        (b'{"cells":', 0),
        (b'{ "cells":', 0),
    ],
    converter_module="all2md.converters.ipynb2markdown",
    converter_function="ipynb_to_markdown",
    required_packages=[],
    options_class="IpynbOptions",
    description="Convert Jupyter Notebooks to Markdown",
    priority=7
))

# RTF converter
registry.register(ConverterMetadata(
    format_name="rtf",
    extensions=[".rtf"],
    mime_types=["application/rtf", "text/rtf"],
    magic_bytes=[
        (b"{\\rtf", 0),
    ],
    converter_module="all2md.converters.rtf2markdown",
    converter_function="rtf_to_markdown",
    required_packages=[("pyth", "")],
    import_error_message="RTF conversion requires 'pyth'. Install with: pip install pyth",
    options_class="RtfOptions",
    description="Convert Rich Text Format documents to Markdown",
    priority=4
))

# PPTX converter
registry.register(ConverterMetadata(
    format_name="pptx",
    extensions=[".pptx"],
    mime_types=["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.pptx2markdown",
    converter_function="pptx_to_markdown",
    required_packages=[("python-pptx", "")],
    import_error_message="PPTX conversion requires 'python-pptx'. Install with: pip install python-pptx",
    options_class="PptxOptions",
    description="Convert PowerPoint presentations to Markdown",
    priority=7
))

# EPUB converter
registry.register(ConverterMetadata(
    format_name="epub",
    extensions=[".epub"],
    mime_types=["application/epub+zip"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.epub2markdown",
    converter_function="epub_to_markdown",
    required_packages=[("ebooklib", ""), ("beautifulsoup4", "")],
    import_error_message="EPUB conversion requires 'ebooklib' and 'beautifulsoup4'. Install with: pip install ebooklib beautifulsoup4",
    options_class="EpubOptions",
    description="Convert EPUB e-books to Markdown",
    priority=6
))

# MHTML converter
registry.register(ConverterMetadata(
    format_name="mhtml",
    extensions=[".mhtml", ".mht"],
    mime_types=["multipart/related", "message/rfc822"],
    magic_bytes=[
        (b"MIME-Version:", 0),
    ],
    converter_module="all2md.converters.mhtml2markdown",
    converter_function="mhtml_to_markdown",
    required_packages=[("beautifulsoup4", "")],
    import_error_message="MHTML conversion requires 'beautifulsoup4'. Install with: pip install beautifulsoup4",
    options_class="MhtmlOptions",
    description="Convert MHTML web archives to Markdown",
    priority=5
))

# ODF converter
registry.register(ConverterMetadata(
    format_name="odt",
    extensions=[".odt", ".odp"],
    mime_types=["application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.converters.odf2markdown",
    converter_function="odf_to_markdown",
    required_packages=[("odfpy", "")],
    import_error_message="ODF conversion requires 'odfpy'. Install with: pip install odfpy",
    options_class="OdfOptions",
    description="Convert OpenDocument files to Markdown",
    priority=4
))

# Mark registry as initialized
registry._initialized = True
