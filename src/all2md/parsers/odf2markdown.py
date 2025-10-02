#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/odf2markdown.py
"""OpenDocument to Markdown conversion module.

This module provides functionality to convert OpenDocument Text (ODT) and
Presentation (ODP) files to Markdown. It processes the document's XML
structure to preserve formatting, tables, lists, and images.

The converter uses the odfpy library to parse the OpenDocument format
natively, mapping elements like paragraphs, headings, lists, tables, and
images to their Markdown equivalents.

Key Features
------------
- Text formatting preservation (bold, italic)
- Heading level detection from document structure
- List conversion (bulleted and numbered) with nesting
- Table structure preservation
- Image extraction and handling via the unified attachment system

Dependencies
------------
- odfpy: For parsing OpenDocument file structure
- logging: For debug and error reporting

Examples
--------
Basic conversion:

    >>> from all2md.parsers.odf2markdown import odf_to_markdown
    >>> with open('document.odt', 'rb') as f:
    ...     markdown = odf_to_markdown(f)
    >>> print(markdown)

Note
----
Requires the odfpy package. Some advanced OpenDocument features may not have
direct Markdown equivalents and will be approximated or omitted.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, TYPE_CHECKING, Union

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MarkdownConversionError
from all2md.options import MarkdownOptions, OdfOptions
from all2md.utils.attachments import process_attachment
from all2md.utils.inputs import format_markdown_heading
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled
from all2md.utils.security import validate_zip_archive

# Type checking imports for static analysis without runtime overhead
if TYPE_CHECKING:
    from odf import draw, opendocument, table, text
    from odf.element import Element

logger = logging.getLogger(__name__)


def extract_odf_metadata(doc: opendocument.OpenDocument) -> DocumentMetadata:
    """Extract metadata from ODF document.

    Parameters
    ----------
    doc : opendocument.OpenDocument
        ODF document object from odfpy

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Access document metadata
    if hasattr(doc, 'meta'):
        meta = doc.meta

        # Extract Dublin Core metadata
        if hasattr(meta, 'getElementsByType'):
            from odf.dc import Creator, Description, Language, Subject, Title
            from odf.meta import CreationDate, Generator, InitialCreator, Keyword

            # Title
            titles = meta.getElementsByType(Title)
            if titles:
                metadata.title = str(titles[0]).strip()

            # Creator/Author
            creators = meta.getElementsByType(Creator)
            if creators:
                metadata.author = str(creators[0]).strip()
            else:
                # Try initial creator
                initial_creators = meta.getElementsByType(InitialCreator)
                if initial_creators:
                    metadata.author = str(initial_creators[0]).strip()

            # Description/Subject
            descriptions = meta.getElementsByType(Description)
            if descriptions:
                metadata.subject = str(descriptions[0]).strip()
            else:
                subjects = meta.getElementsByType(Subject)
                if subjects:
                    metadata.subject = str(subjects[0]).strip()

            # Keywords
            keywords = meta.getElementsByType(Keyword)
            if keywords:
                # ODF can have multiple keyword elements
                keyword_list = []
                for kw in keywords:
                    kw_text = str(kw).strip()
                    if kw_text:
                        # Split by common delimiters
                        import re
                        parts = [k.strip() for k in re.split('[,;]', kw_text) if k.strip()]
                        keyword_list.extend(parts)
                if keyword_list:
                    metadata.keywords = keyword_list

            # Creation date
            creation_dates = meta.getElementsByType(CreationDate)
            if creation_dates:
                metadata.creation_date = str(creation_dates[0]).strip()

            # Generator (application)
            generators = meta.getElementsByType(Generator)
            if generators:
                metadata.creator = str(generators[0]).strip()

            # Language
            languages = meta.getElementsByType(Language)
            if languages:
                metadata.language = str(languages[0]).strip()

    # Document type and statistics
    if hasattr(doc, 'mimetype'):
        doc_type = 'presentation' if 'presentation' in doc.mimetype else 'text'
        metadata.custom['document_type'] = doc_type

    # Count pages/slides if it's a presentation
    if hasattr(doc, 'body'):
        try:
            from odf.draw import Page
            pages = doc.body.getElementsByType(Page)
            if pages:
                metadata.custom['page_count'] = len(pages)
        except Exception:
            pass

        # Count paragraphs for text documents
        try:
            from odf.text import P
            paragraphs = doc.body.getElementsByType(P)
            if paragraphs:
                metadata.custom['paragraph_count'] = len(paragraphs)
        except Exception:
            pass

        # Count tables
        try:
            from odf.table import Table
            tables = doc.body.getElementsByType(Table)
            if tables:
                metadata.custom['table_count'] = len(tables)
        except Exception:
            pass

    return metadata


def odf_to_markdown(
        input_data: Union[str, Path, IO[bytes]], options: OdfOptions | None = None
) -> str:
    """Convert OpenDocument file (ODT, ODP) to Markdown format.

    Processes OpenDocument files by parsing their XML structure and converting
    content to well-formatted Markdown, preserving text formatting, tables,
    lists, and embedded images.

    Parameters
    ----------
    input_data : str or file-like object
        OpenDocument file to convert. Can be:
        - String path to ODT/ODP file
        - File-like object containing ODT/ODP data
    options : OdfOptions or None, default None
        Configuration options for ODF conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the OpenDocument file.

    Raises
    ------
    MarkdownConversionError
        If the document cannot be opened or processed.
    """
    # Lazy import of heavy odfpy document parsing classes
    from odf import opendocument

    if options is None:
        options = OdfOptions()

    # Validate ZIP archive security for file-based inputs (only for existing files)
    if isinstance(input_data, (str, Path)) and Path(input_data).exists():
        try:
            validate_zip_archive(input_data)
        except Exception as e:
            raise MarkdownConversionError(
                f"ODF archive failed security validation: {str(e)}",
                conversion_stage="archive_validation",
                original_error=e
            ) from e

    try:
        doc = opendocument.load(input_data)
    except ImportError as e:
        raise MarkdownConversionError(
            "odfpy library is required for ODF conversion. Install with: pip install odfpy",
            conversion_stage="dependency_check",
            original_error=e,
        ) from e
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to open ODF document: {str(e)}", conversion_stage="document_opening", original_error=e
        ) from e

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_odf_metadata(doc)

    # Use AST-based conversion path
    from all2md.parsers.odf import OdfToAstConverter
    from all2md.ast import MarkdownRenderer

    # Convert to AST
    ast_converter = OdfToAstConverter(options)
    ast_converter.doc = doc
    ast_document = ast_converter.convert_to_ast()

    # Render AST to markdown
    md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()
    renderer = MarkdownRenderer(md_opts)
    markdown_content = renderer.render(ast_document)

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(markdown_content.strip(), metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="odf",
    extensions=[".odt", ".odp"],
    mime_types=["application/vnd.oasis.opendocument.text", "application/vnd.oasis.opendocument.presentation"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature
    ],
    converter_module="all2md.parsers.odf2markdown",
    converter_function="odf_to_markdown",
    required_packages=[("odfpy", "odf", "")],
    import_error_message="ODF conversion requires 'odfpy'. Install with: pip install odfpy",
    options_class="OdfOptions",
    description="Convert OpenDocument files to Markdown",
    priority=4
)
