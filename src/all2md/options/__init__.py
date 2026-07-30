#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Configuration options and settings for all2md conversion modules.

This module provides dataclass-based configuration options for all conversion
modules in the all2md library. Using dataclasses provides type safety,
default values, and a clean API for configuring conversion behavior.

Each converter module has its own Options dataclass with module-specific
parameters.

Every name below is re-exported lazily. Importing this package used to pull in all
30-odd options submodules, and because ``from all2md.options.base import ...``
executes this ``__init__`` first, *any* options import cost the whole set - which
is how a bare ``import all2md`` ended up loading 31 options modules to reach the
two classes in ``all2md/api.py``. The public API is unchanged: ``from
all2md.options import PdfOptions`` still works, it just no longer drags in
PowerPoint and LaTeX with it.

Adding an export means adding a ``_LAZY_EXPORTS`` entry *and* an ``__all__``
entry; ``tests/unit/test_options_lazy_exports.py`` fails if the two disagree or
if an entry does not resolve.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Imported eagerly for type checkers and IDEs only - at runtime these names
    # are resolved on demand by __getattr__ below.
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

#: Exported name -> the ``all2md.options`` submodule that defines it.
_LAZY_EXPORTS: dict[str, str] = {
    "AsciiDocOptions": "asciidoc",
    "AsciiDocRendererOptions": "asciidoc",
    "AstJsonParserOptions": "ast_json",
    "AstJsonRendererOptions": "ast_json",
    "UNSET": "base",
    "BaseParserOptions": "base",
    "BaseRendererOptions": "base",
    "CloneFrozenMixin": "base",
    "ChmOptions": "chm",
    "AttachmentOptionsMixin": "common",
    "LocalFileAccessOptions": "common",
    "NetworkFetchOptions": "common",
    "CsvOptions": "csv",
    "DocxOptions": "docx",
    "DocxRendererOptions": "docx",
    "DokuWikiOptions": "dokuwiki",
    "DokuWikiParserOptions": "dokuwiki",
    "EmlOptions": "eml",
    "EpubOptions": "epub",
    "EpubRendererOptions": "epub",
    "Fb2Options": "fb2",
    "HtmlOptions": "html",
    "HtmlRendererOptions": "html",
    "IpynbOptions": "ipynb",
    "IpynbRendererOptions": "ipynb",
    "JinjaRendererOptions": "jinja",
    "LatexOptions": "latex",
    "LatexRendererOptions": "latex",
    "MarkdownParserOptions": "markdown",
    "MarkdownRendererOptions": "markdown",
    "MediaWikiOptions": "mediawiki",
    "MhtmlOptions": "mhtml",
    "OdpOptions": "odp",
    "OdpRendererOptions": "odp",
    "OdsSpreadsheetOptions": "ods",
    "OdtOptions": "odt",
    "OdtRendererOptions": "odt",
    "OrgParserOptions": "org",
    "OrgRendererOptions": "org",
    "PdfOptions": "pdf",
    "PdfRendererOptions": "pdf",
    "PlainTextOptions": "plaintext",
    "PptxOptions": "pptx",
    "PptxRendererOptions": "pptx",
    "RstParserOptions": "rst",
    "RstRendererOptions": "rst",
    "RtfOptions": "rtf",
    "RtfRendererOptions": "rtf",
    "SourceCodeOptions": "sourcecode",
    "XlsxOptions": "xlsx",
    "ZipOptions": "zip",
}


def __getattr__(name: str) -> Any:
    """Resolve a re-exported options class on first access (PEP 562).

    The resolved object is cached in module globals, so this runs once per name
    and subsequent lookups go through the normal fast path.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    import importlib

    # nosemgrep: python.lang.security.audit.non-literal-import.non-literal-import
    module = importlib.import_module(f"all2md.options.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include the lazy names in ``dir()`` so tab-completion still finds them."""
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


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
