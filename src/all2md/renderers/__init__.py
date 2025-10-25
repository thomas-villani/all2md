#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/renderers/__init__.py
"""AST renderers for converting documents to various output formats.

This package provides renderers for converting the unified AST representation
to different output formats. Renderers are registered dynamically via the
converter registry system, enabling lazy loading and proper dependency handling.

Available renderers include:
- MarkdownRenderer: Render to Markdown text (always available)
- MediaWikiRenderer: Render to MediaWiki markup (always available)
- PlainTextRenderer: Render to plain text (always available)
- HtmlRenderer: Render to HTML
- DocxRenderer: Render to Microsoft Word .docx (requires python-docx)
- PdfRenderer: Render to PDF (requires reportlab)
- EpubRenderer: Render to EPUB ebook format (requires ebooklib)
- PptxRenderer: Render to PowerPoint .pptx (requires python-pptx)
- AsciiDocRenderer: Render to AsciiDoc (always available)
- LatexRenderer: Render to LaTeX (always available)
- RestructuredTextRenderer: Render to reStructuredText (always available)
- JinjaRenderer: Render using custom Jinja2 templates (requires jinja2)

Renderers with optional dependencies are loaded on-demand via the registry.
Use `all2md.converter_registry.registry.get_renderer(format_name)` to
dynamically load a renderer class with automatic dependency checking.

Examples
--------
Convert AST to Markdown:

    >>> from all2md.ast import Document, Heading, Text
    >>> from all2md.renderers import MarkdownRenderer
    >>> from all2md.options import MarkdownRendererOptions
    >>> doc = Document(children=[
    ...     Heading(level=1, content=[Text(content="Title")])
    ... ])
    >>> renderer = MarkdownRenderer(MarkdownRendererOptions())
    >>> markdown = renderer.render_to_string(doc)

Convert AST to HTML (with dynamic loading):

    >>> from all2md.options.html import HtmlRendererOptions    >>> from all2md.converter_registry import registry
    >>> HtmlRenderer = registry.get_renderer("html")
    >>> renderer = HtmlRenderer(HtmlRendererOptions(standalone=True))
    >>> html = renderer.render_to_string(doc)

Convert AST to DOCX (with dynamic loading):

    >>> from all2md.options.docx import DocxRendererOptions    >>> from all2md.converter_registry import registry
    >>> DocxRenderer = registry.get_renderer("docx")
    >>> renderer = DocxRenderer(DocxRendererOptions())
    >>> renderer.render(doc, "output.docx")

"""

from all2md.renderers.base import BaseRenderer, InlineContentMixin
from all2md.renderers.ipynb import IpynbRenderer
from all2md.renderers.jinja import JinjaRenderer
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer
from all2md.renderers.plaintext import PlainTextRenderer

__all__ = [
    "BaseRenderer",
    "InlineContentMixin",
    "IpynbRenderer",
    "JinjaRenderer",
    "MarkdownRenderer",
    "MediaWikiRenderer",
    "PlainTextRenderer",
]
