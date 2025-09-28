"""all2md - A Python document conversion library for bidirectional transformation.

all2md provides a comprehensive solution for converting between various file formats
and Markdown. It supports PDF, Word (DOCX), PowerPoint (PPTX), HTML, email (EML),
Excel (XLSX), Jupyter Notebooks (IPYNB), EPUB e-books, images, and 200+ text file formats with
intelligent content extraction and formatting preservation.

The library uses a modular architecture where the main `to_markdown()` function
automatically detects file types and routes to appropriate specialized converters.
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

"""
#  Copyright (c) 2025 Tom Villani, Ph.D.
import copy
import logging
from dataclasses import fields
from io import BytesIO
from pathlib import Path
from typing import IO, Optional, Union

from all2md.constants import DocumentFormat

# Extensions lists moved to constants.py - keep references for backward compatibility
from all2md.converter_registry import registry
from all2md.exceptions import DependencyError, FormatError, InputError, MarkdownConversionError
from all2md.options import (
    BaseOptions,
    DocxOptions,
    EmlOptions,
    EpubOptions,
    HtmlOptions,
    IpynbOptions,
    MarkdownOptions,
    MhtmlOptions,
    OdfOptions,
    PdfOptions,
    PptxOptions,
    RtfOptions,
    SpreadsheetOptions,
    create_updated_options,
)

# Import converters to trigger registration
from . import converters  # noqa: F401

logger = logging.getLogger(__name__)


# Options handling helpers

def _get_options_class_for_format(format: DocumentFormat) -> type[BaseOptions] | None:
    """Get the appropriate Options class for a given document format.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseOptions] | None
        Options class or None for formats that don't use options.
    """
    format_to_class = {
        "pdf": PdfOptions,
        "docx": DocxOptions,
        "pptx": PptxOptions,
        "html": HtmlOptions,
        "mhtml": MhtmlOptions,
        "eml": EmlOptions,
        "ipynb": IpynbOptions,
        "rtf": RtfOptions,
        "odf": OdfOptions,
        "epub": EpubOptions,
        "spreadsheet": SpreadsheetOptions
    }
    return format_to_class.get(format)


def _create_options_from_kwargs(format: DocumentFormat, **kwargs) -> BaseOptions | None:
    """Create format-specific options object from keyword arguments.

    Parameters
    ----------
    format : DocumentFormat
        The document format to create options for.
    **kwargs
        Keyword arguments to use for options creation.

    Returns
    -------
    BaseOptions | None
        Options instance or None for formats that don't use options.
    """
    options_class = _get_options_class_for_format(format)
    if not options_class:
        return None

    # Extract MarkdownOptions fields
    markdown_fields = {field.name for field in fields(MarkdownOptions)}
    markdown_opts = {k: v for k, v in kwargs.items() if k in markdown_fields}

    # Remove markdown fields from main kwargs
    remaining_kwargs = {k: v for k, v in kwargs.items() if k not in markdown_fields}

    # Create MarkdownOptions if we have any markdown-specific options
    markdown_options = MarkdownOptions(**markdown_opts) if markdown_opts else None

    # Add markdown_options to remaining kwargs if created
    if markdown_options:
        remaining_kwargs['markdown_options'] = markdown_options

    option_names = [field.name for field in fields(options_class)]
    valid_kwargs = {k: v for k, v in remaining_kwargs.items() if k in option_names}
    missing = [k for k in remaining_kwargs if k not in valid_kwargs]
    if missing:
        logger.debug(f"Skipping unknown options: {missing}")
    return options_class(**valid_kwargs)


def _merge_options(
        base_options: BaseOptions | MarkdownOptions | None, format: DocumentFormat, **kwargs
) -> BaseOptions | None:
    """Merge base options with additional kwargs.

    Parameters
    ----------
    base_options : BaseOptions | None
        Existing options object to use as base.
    format : DocumentFormat
        Document format for creating new options if base_options is None.
    **kwargs
        Additional keyword arguments to merge/override.

    Returns
    -------
    BaseOptions | None
        Merged options object or None for formats that don't use options.
    """
    if base_options is None:
        return _create_options_from_kwargs(format, **kwargs)
    elif isinstance(base_options, MarkdownOptions):
        options_instance = _create_options_from_kwargs(format, **kwargs)

        if options_instance.markdown_options is None:
            options_instance = create_updated_options(options_instance, markdown_options=base_options)
        else:
            # Update existing MarkdownOptions by merging fields
            merged_md_options = options_instance.markdown_options
            for field in fields(base_options):
                field_value = getattr(base_options, field.name)
                merged_md_options = create_updated_options(merged_md_options, **{field.name: field_value})
            options_instance = create_updated_options(options_instance, markdown_options=merged_md_options)
        return options_instance

    # Create a copy of the base options
    merged_options = copy.deepcopy(base_options)

    # Extract MarkdownOptions fields from kwargs
    markdown_fields = {field.name for field in fields(MarkdownOptions)}
    markdown_kwargs = {k: v for k, v in kwargs.items() if k in markdown_fields}
    other_kwargs = {k: v for k, v in kwargs.items() if k not in markdown_fields}

    # Handle MarkdownOptions merging with field-wise preservation
    if markdown_kwargs:
        # Start with existing markdown_options or create default
        new_md = merged_options.markdown_options or MarkdownOptions()
        # Apply only the kwargs fields that are present, preserving existing fields
        for k, v in markdown_kwargs.items():
            new_md = create_updated_options(new_md, **{k: v})
        merged_options = merged_options.create_updated(markdown_options=new_md)

    if other_kwargs:
        merged_options = merged_options.create_updated(**other_kwargs)

    return merged_options


# Main conversion function starts here


def to_markdown(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        format: DocumentFormat = "auto",
        **kwargs
) -> str:
    """Convert document to Markdown format with enhanced format detection.

    This is the main entry point for the all2md library. It can detect file
    formats from filenames, content analysis, or explicit format specification,
    then routes to the appropriate specialized converter for processing.

    Parameters
    ----------
    input : str, Path, IO[bytes], or bytes
        Input data, which can be a file path, a file-like object, or raw bytes.
    options : BaseOptions | MarkdownOptions, optional
        A pre-configured options object for format-specific settings.
        See the classes in `all2md.options` for details. When provided
        alongside `kwargs`, the kwargs will override matching fields in
        the options object, allowing for selective customization.
    format : DocumentFormat, default "auto"
        Explicitly specify the document format. If "auto", the format is
        detected from the filename or content.
    kwargs : Any
        Individual conversion options that override settings in the `options`
        parameter. These are mapped to the appropriate format-specific
        options class and take precedence over the same fields in `options`.
        For a full list of available options, please refer to the documentation
        for the :mod:`all2md.options` module and the specific `...Options`
        classes (e.g., `PdfOptions`, `HtmlOptions`).

    Returns
    -------
    str
        Document content converted to Markdown format.

    Raises
    ------
    DependencyError
        If required dependencies for a specific format are not installed.
    MarkdownConversionError
        If file processing fails due to corruption or format issues.
    InputError
        If input parameters are invalid or the file cannot be accessed.

    Notes
    -----
    **Options Merging Logic:**

    The function supports flexible configuration through three approaches:

    1. **Options only**: Pass a pre-configured options object
        >>> options = PdfOptions(pages=[0, 1], attachment_mode="base64")
        >>> to_markdown("doc.pdf", options=options)

    2. **Kwargs only**: Pass individual options as keyword arguments
        >>> to_markdown("doc.pdf", pages=[0, 1], attachment_mode="base64")

    3. **Combined (recommended)**: Use options as base with kwargs overrides
        >>> base_options = PdfOptions(attachment_mode="download")
        >>> to_markdown("doc.pdf", options=base_options, attachment_mode="base64")
        # Results in base64 mode (kwargs override options)

    When both `options` and `kwargs` are provided, kwargs take precedence for
    matching field names. This allows you to define reusable base configurations
    and selectively override specific settings per conversion.

    **MarkdownOptions Handling:**

    MarkdownOptions can be provided either:
    - Directly as the `options` parameter (creates format-specific options with those markdown settings)
    - Embedded in format-specific options via the `markdown_options` field
    - As individual kwargs prefixed implicitly (e.g., `emphasis_symbol="_"`)

    Examples
    --------
    Basic conversion with auto-detection:
        >>> markdown = to_markdown("document.pdf")

    Using pre-configured options:
        >>> pdf_opts = PdfOptions(pages=[0, 1, 2], attachment_mode="download")
        >>> markdown = to_markdown("document.pdf", options=pdf_opts)

    Combining options with selective overrides:
        >>> base_opts = PdfOptions(attachment_mode="download", detect_columns=True)
        >>> markdown = to_markdown("doc.pdf", options=base_opts, attachment_mode="base64")
        # Uses base64 mode but keeps column detection enabled

    Using MarkdownOptions directly:
        >>> md_opts = MarkdownOptions(emphasis_symbol="_", bullet_symbols="•◦▪")
        >>> markdown = to_markdown("document.pdf", options=md_opts)

    Mixed markdown and format-specific options:
        >>> to_markdown("doc.pdf", pages=[0, 1], emphasis_symbol="_", bullet_symbols="•◦▪")
    """

    # Handle input parameter - convert to file object and get filename
    if isinstance(input, (str, Path)):
        filename = str(input)
        with open(input, 'rb') as file:
            return to_markdown(file, options=options, format=format, _filename=filename, **kwargs)
    elif isinstance(input, bytes):
        file: IO[bytes] = BytesIO(input)
        filename = "unknown"
    else:
        # File-like object case
        file: IO[bytes] = input  # type: ignore
        filename = getattr(file, 'name', kwargs.pop('_filename', 'unknown'))

    # Determine the actual format to use
    if format == "auto":
        # Use registry-based detection
        actual_format = registry.detect_format(file, hint=None)
    else:
        # Use explicitly specified format
        actual_format = format
        logger.debug(f"Using explicitly specified format: {actual_format}")

    # Create or merge options based on parameters
    if options is not None and kwargs:
        # Merge provided options with kwargs (kwargs override)
        final_options = _merge_options(options, actual_format, **kwargs)
    elif options is not None:
        # Use provided options as-is
        final_options = options
    elif kwargs:
        # Create options from kwargs only
        final_options = _create_options_from_kwargs(actual_format, **kwargs)
    else:
        # No options provided
        final_options = None

    # Process file based on detected/specified format using registry
    try:
        # Get converter function from registry
        converter_func, options_class = registry.get_converter(actual_format)

        # Handle special cases for different input types
        if actual_format == "html":
            file.seek(0)
            html_content = file.read().decode("utf-8", errors="replace")
            content = converter_func(html_content, options=final_options)
        else:
            # Standard converter call
            file.seek(0)
            content = converter_func(file, options=final_options)

    except DependencyError:
        # Re-raise dependency errors as-is
        raise
    except FormatError:
        # Handle unknown formats by falling back to text
        if actual_format not in ["txt", "image"]:
            logger.warning(f"Unknown format '{actual_format}', falling back to text")
            actual_format = "txt"

        if actual_format == "image":
            raise FormatError("Invalid input type: `image` not supported.") from None
        else:
            # Plain text handling
            file.seek(0)
            try:
                content = file.read().decode("utf-8", errors="replace")
            except Exception as e:
                raise MarkdownConversionError(f"Could not decode file as UTF-8: {filename}") from e

    # Fix windows newlines and return
    return content.replace("\r\n", "\n")


__all__ = [
    "to_markdown",
    # Registry system
    "registry",
    # Type definitions
    "DocumentFormat",
    # Re-exported classes and exceptions for public API
    "BaseOptions",
    "DocxOptions",
    "EmlOptions",
    "HtmlOptions",
    "IpynbOptions",
    "MarkdownOptions",
    "OdfOptions",
    "PdfOptions",
    "PptxOptions",
    "MarkdownConversionError",
    "InputError",
    "DependencyError",
]
