#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/docx2markdown.py
"""Word document to Markdown conversion module.

This module provides functionality to convert Microsoft Word documents (DOCX format)
to Markdown while preserving formatting, structure, and embedded content. It handles
complex document elements including tables, lists, hyperlinks, images, and various
text formatting options.

The converter processes Word documents by analyzing their internal structure,
extracting styled content, and converting it to equivalent Markdown syntax.
Special attention is paid to preserving document hierarchy, list structures,
and table layouts.

Key Features
------------
- Comprehensive text formatting preservation (bold, italic, underline, etc.)
- Intelligent list detection and conversion (bulleted and numbered)
- Table structure preservation with Markdown table syntax
- Hyperlink extraction and conversion
- Image embedding as base64 data URIs
- Document structure preservation (headers, paragraphs)
- Style-based formatting detection

Supported Elements
------------------
- Text formatting (bold, italic, underline, strikethrough)
- Headers (converted to Markdown headers)
- Lists (bulleted, numbered, with proper nesting)
- Tables (with cell content and basic formatting)
- Hyperlinks (internal and external)
- Images (embedded as base64)
- Line breaks and paragraph separation

Dependencies
------------
- python-docx: For parsing Word document structure
- logging: For debug and error reporting

Examples
--------
Basic conversion:

    >>> from all2md.converters.docx2markdown import docx_to_markdown
    >>> with open('document.docx', 'rb') as f:
    ...     markdown = docx_to_markdown(f)
    >>> print(markdown)

Note
----
Requires python-docx package. Some advanced Word features may not have
direct Markdown equivalents and will be approximated or omitted.
"""

import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Union

if TYPE_CHECKING:
    import docx
    import docx.document

# Make Hyperlink available for testing while maintaining lazy loading
try:
    from docx.text.hyperlink import Hyperlink
except ImportError:
    Hyperlink = None  # type: ignore

from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MarkdownConversionError
from all2md.options import DocxOptions, MarkdownOptions
from all2md.utils.attachments import create_attachment_sequencer
from all2md.utils.metadata import (
    OFFICE_FIELD_MAPPING,
    DocumentMetadata,
    map_properties_to_metadata,
    prepend_metadata_if_enabled,
)
from all2md.utils.security import validate_zip_archive

logger = logging.getLogger(__name__)

# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="docx",
    extensions=[".docx"],
    mime_types=["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    magic_bytes=[
        (b"PK\x03\x04", 0),  # ZIP signature (docx is ZIP-based)
    ],
    converter_module="all2md.converters.docx2markdown",
    converter_function="docx_to_markdown",
    required_packages=[("python-docx", "")],
    optional_packages=[],
    import_error_message=(
        "DOCX conversion requires 'python-docx'. "
        "Install with: pip install python-docx"
    ),
    options_class="DocxOptions",
    description="Convert Microsoft Word DOCX documents to Markdown",
    priority=8
)


def extract_docx_metadata(doc: "docx.document.Document") -> DocumentMetadata:
    """Extract metadata from DOCX document.

    Parameters
    ----------
    doc : docx.document.Document
        python-docx Document object

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    if not hasattr(doc, 'core_properties'):
        return DocumentMetadata()

    props = doc.core_properties

    # Use the utility function for standard metadata extraction
    metadata = map_properties_to_metadata(props, OFFICE_FIELD_MAPPING)

    # Add DOCX-specific custom metadata
    custom_properties = ['last_modified_by', 'revision', 'version', 'comments']
    for prop_name in custom_properties:
        if hasattr(props, prop_name):
            value = getattr(props, prop_name)
            if value:
                metadata.custom[prop_name] = value

    return metadata


def docx_to_markdown(
        input_data: Union[str, Path, "docx.document.Document", IO[bytes]], options: DocxOptions | None = None
) -> str:
    """Convert Word document (DOCX) to Markdown format.

    Processes Microsoft Word documents and converts them to well-formatted
    Markdown while preserving text formatting, document structure, tables,
    lists, and embedded images. Handles complex document elements and
    maintains hierarchical organization.

    Parameters
    ----------
    input_data : str, file-like object, or docx.Document
        Word document to convert. Can be:
        - String path to DOCX file
        - File-like object containing DOCX data
        - Already opened python-docx Document object
    options : DocxOptions or None, default None
        Configuration options for DOCX conversion. If None, uses default settings.

    Returns
    -------
    str
        Markdown representation of the Word document with preserved
        formatting, structure, and content.

    Raises
    ------
    InputError
        If input type is not supported or document cannot be opened
    MarkdownConversionError
        If document processing fails

    Examples
    --------
    Convert a Word file to Markdown:

        >>> with open('document.docx', 'rb') as f:
        ...     markdown = docx_to_markdown(f)
        >>> print(markdown)

    Convert with embedded images:

        >>> markdown = docx_to_markdown('document.docx', convert_images_to_base64=True)

    Notes
    -----
    - Preserves text formatting (bold, italic, underline, strikethrough)
    - Converts lists with proper nesting and numbering
    - Handles tables with Markdown table syntax
    - Processes hyperlinks and converts to Markdown link format
    - Maintains document structure with appropriate heading levels
    """
    # Handle backward compatibility and merge options
    try:
        import docx
        import docx.document
        from docx.table import Table
        from docx.text.hyperlink import Hyperlink  # noqa: F401
        from docx.text.paragraph import Paragraph
    except ImportError as e:
        from all2md.exceptions import DependencyError
        raise DependencyError(
            converter_name="docx",
            missing_packages=[("python-docx", "")],
        ) from e

    if options is None:
        options = DocxOptions()

    # Extract base filename for standardized attachment naming
    if isinstance(input_data, (str, Path)):
        base_filename = Path(input_data).stem
    else:
        # For non-file inputs, use a default name
        base_filename = "document"

    # Validate ZIP archive security for file-based inputs
    if isinstance(input_data, (str, Path)):
        try:
            validate_zip_archive(input_data)
        except Exception as e:
            raise MarkdownConversionError(
                f"DOCX archive failed security validation: {str(e)}",
                conversion_stage="archive_validation",
                original_error=e
            ) from e

    # Validate and convert input - for now use simplified approach
    try:
        if isinstance(input_data, docx.document.Document):
            doc = input_data
        elif isinstance(input_data, Path):
            doc = docx.Document(str(input_data))
        else:
            doc = docx.Document(input_data)
    except Exception as e:
        raise MarkdownConversionError(
            f"Failed to open DOCX document: {str(e)}", conversion_stage="document_opening", original_error=e
        ) from e

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_docx_metadata(doc)

    # Use new AST-based conversion path
    from all2md.converters.docx2ast import DocxToAstConverter
    from all2md.ast import MarkdownRenderer

    # Create attachment sequencer for consistent filename generation
    attachment_sequencer = create_attachment_sequencer()

    # Convert DOCX to AST
    ast_converter = DocxToAstConverter(
        options=options,
        doc=doc,
        base_filename=base_filename,
        attachment_sequencer=attachment_sequencer,
    )
    ast_document = ast_converter.convert_to_ast(doc)

    # Get MarkdownOptions (use provided or create default)
    md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()

    # Render AST to markdown using MarkdownOptions directly
    renderer = MarkdownRenderer(md_opts)
    markdown = renderer.render(ast_document)

    # Prepend metadata if enabled
    markdown = prepend_metadata_if_enabled(markdown.strip(), metadata, options.extract_metadata)

    return markdown
