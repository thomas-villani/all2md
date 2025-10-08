#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/renderers/__init__.py
"""AST renderers for converting documents to various output formats.

This package provides renderers for converting the unified AST representation
to different output formats:

- MarkdownRenderer: Render to Markdown text
- HtmlRenderer: Render to HTML (standalone or fragment)
- DocxRenderer: Render to Microsoft Word (.docx)
- PdfRenderer: Render to PDF using ReportLab
- EpubRenderer: Render to EPUB ebook format
- PptxRenderer: Render to PowerPoint (.pptx) presentation
- RstRenderer: Render to reStructuredText

Each renderer implements the visitor pattern to traverse the AST and generate
format-specific output.

Examples
--------
Convert AST to Markdown:

    >>> from all2md.ast import Document, Heading, Text
    >>> from all2md.renderers import MarkdownRenderer
    >>> from all2md.options import MarkdownOptions
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")])
    ... ])
    >>> renderer = MarkdownRenderer(MarkdownOptions())
    >>> markdown = renderer.render_to_string(doc)

Convert AST to HTML:

    >>> from all2md.renderers import HtmlRenderer
    >>> from all2md.options import HtmlRendererOptions
    >>> renderer = HtmlRenderer(HtmlRendererOptions(standalone=True))
    >>> html = renderer.render_to_string(doc)

Convert AST to DOCX:

    >>> from all2md.renderers import DocxRenderer
    >>> from all2md.options import DocxRendererOptions
    >>> renderer = DocxRenderer(DocxRendererOptions())
    >>> renderer.render(doc, "output.docx")

Convert AST to PDF:

    >>> from all2md.renderers import PdfRenderer
    >>> from all2md.options import PdfRendererOptions
    >>> renderer = PdfRenderer(PdfRendererOptions())
    >>> renderer.render(doc, "output.pdf")

"""

from all2md.renderers.base import BaseRenderer
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer
from all2md.renderers.plaintext import PlainTextRenderer

# MediaWiki and PlainText renderers are always available (no optional dependencies)
MEDIAWIKI_AVAILABLE = True
PLAINTEXT_AVAILABLE = True

# Import renderers with optional dependencies
try:
    from all2md.renderers.docx import DocxRenderer
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    DocxRenderer = None  # type: ignore[assignment,misc]

try:
    from all2md.renderers.html import HtmlRenderer
    HTML_AVAILABLE = True
except ImportError:
    HTML_AVAILABLE = False
    HtmlRenderer = None  # type: ignore[assignment,misc]

try:
    from all2md.renderers.pdf import PdfRenderer
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    PdfRenderer = None  # type: ignore[assignment,misc]

try:
    from all2md.renderers.epub import EpubRenderer
    EPUB_AVAILABLE = True
except ImportError:
    EPUB_AVAILABLE = False
    EpubRenderer = None  # type: ignore[assignment,misc]

try:
    from all2md.renderers.pptx import PptxRenderer
    PPTX_RENDERER_AVAILABLE = True
except ImportError:
    PPTX_RENDERER_AVAILABLE = False
    PptxRenderer = None  # type: ignore[assignment,misc]

try:
    from all2md.renderers.rst import RestructuredTextRenderer as RstRenderer
    RST_AVAILABLE = True
except ImportError:
    RST_AVAILABLE = False
    RstRenderer = None  # type: ignore[assignment,misc]

__all__ = [
    'BaseRenderer',
    'MarkdownRenderer',
    'MediaWikiRenderer',
    'PlainTextRenderer',
    'DocxRenderer',
    'HtmlRenderer',
    'PdfRenderer',
    'EpubRenderer',
    'PptxRenderer',
    'RstRenderer',
    'MEDIAWIKI_AVAILABLE',
    'PLAINTEXT_AVAILABLE',
    'DOCX_AVAILABLE',
    'HTML_AVAILABLE',
    'PDF_AVAILABLE',
    'EPUB_AVAILABLE',
    'PPTX_RENDERER_AVAILABLE',
    'RST_AVAILABLE',
]
