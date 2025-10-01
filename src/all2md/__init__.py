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
    SourceCodeOptions,
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
        "sourcecode": SourceCodeOptions,
        "spreadsheet": SpreadsheetOptions
    }
    return format_to_class.get(format)


def _collect_nested_dataclass_kwargs(options_class: type[BaseOptions], kwargs: dict) -> dict:
    """Collect kwargs that belong to nested dataclass fields.

    This function inspects the options class for nested dataclass fields
    (e.g., network: NetworkFetchOptions) and groups kwargs that match
    those nested fields' internal field names.

    Parameters
    ----------
    options_class : type[BaseOptions]
        The options class to inspect.
    kwargs : dict
        Flat keyword arguments that may contain nested dataclass fields.

    Returns
    -------
    dict
        Dictionary mapping nested field names to dictionaries of their kwargs.
        Also includes remaining kwargs that don't belong to nested dataclasses.

    Examples
    --------
    For HtmlOptions with kwargs like {'allow_remote_fetch': True, 'extract_title': False}:
    Returns: {
        'network': {'allow_remote_fetch': True},
        'remaining': {'extract_title': False}
    }
    """
    from dataclasses import is_dataclass
    from typing import get_type_hints

    nested_kwargs = {}
    remaining_kwargs = {}

    # Use get_type_hints to properly resolve string annotations
    try:
        type_hints = get_type_hints(options_class)
    except Exception:
        # Fallback if type hints can't be resolved
        type_hints = {}

    # Build a mapping of field_name -> nested_dataclass_type
    nested_fields = {}
    for field in fields(options_class):
        # Get resolved type from hints, fallback to field.type
        field_type = type_hints.get(field.name, field.type)

        # Handle Optional and Union types
        if hasattr(field_type, '__origin__'):
            # For Optional[SomeType], get the actual type
            if hasattr(field_type, '__args__'):
                for arg in field_type.__args__:
                    if arg is not type(None) and is_dataclass(arg):
                        nested_fields[field.name] = arg
                        break
        elif is_dataclass(field_type):
            nested_fields[field.name] = field_type

    # For each nested field, collect kwargs that match its internal fields
    for nested_field_name, nested_dataclass in nested_fields.items():
        nested_field_names = {f.name for f in fields(nested_dataclass)}
        matching_kwargs = {}

        for kwarg_name, kwarg_value in kwargs.items():
            if kwarg_name in nested_field_names:
                matching_kwargs[kwarg_name] = kwarg_value

        if matching_kwargs:
            nested_kwargs[nested_field_name] = matching_kwargs

    # Collect remaining kwargs that aren't in any nested field
    all_nested_field_names: set[str] = set()
    for nested_dataclass in nested_fields.values():
        all_nested_field_names.update(f.name for f in fields(nested_dataclass))

    for kwarg_name, kwarg_value in kwargs.items():
        if kwarg_name not in all_nested_field_names:
            remaining_kwargs[kwarg_name] = kwarg_value

    return {'nested': nested_kwargs, 'remaining': remaining_kwargs}


def _create_options_from_kwargs(format: DocumentFormat, **kwargs) -> BaseOptions | None:
    """Create format-specific options object from keyword arguments.

    This function handles flat kwargs and assembles nested dataclass instances
    as needed. For example, flat keys like 'allow_remote_fetch' are grouped
    and used to create a NetworkFetchOptions instance for HtmlOptions.network.

    Parameters
    ----------
    format : DocumentFormat
        The document format to create options for.
    **kwargs
        Keyword arguments to use for options creation. Can include flat keys
        that map to nested dataclass fields.

    Returns
    -------
    BaseOptions | None
        Options instance or None for formats that don't use options.
    """
    from dataclasses import is_dataclass

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

    # Collect nested dataclass kwargs
    nested_info = _collect_nested_dataclass_kwargs(options_class, remaining_kwargs)
    nested_dataclass_kwargs = nested_info['nested']
    flat_remaining_kwargs = nested_info['remaining']

    # Add markdown_options to flat kwargs if created
    if markdown_options:
        flat_remaining_kwargs['markdown_options'] = markdown_options

    # Use get_type_hints to properly resolve types
    from typing import get_type_hints
    try:
        type_hints = get_type_hints(options_class)
    except Exception:
        type_hints = {}

    # Create instances of nested dataclasses
    for nested_field_name, nested_kwargs in nested_dataclass_kwargs.items():
        # Find the nested dataclass type using type hints
        field_type = type_hints.get(nested_field_name)
        if not field_type:
            # Fallback to field.type
            for field in fields(options_class):
                if field.name == nested_field_name:
                    field_type = field.type
                    break

        if field_type:
            # Handle Optional types
            nested_class = None
            if hasattr(field_type, '__origin__'):
                if hasattr(field_type, '__args__'):
                    for arg in field_type.__args__:
                        if arg is not type(None) and is_dataclass(arg):
                            nested_class = arg
                            break
            elif is_dataclass(field_type):
                nested_class = field_type

            if nested_class:
                # Create instance of nested dataclass
                flat_remaining_kwargs[nested_field_name] = nested_class(**nested_kwargs)  # type: ignore[operator]

    # Filter to only valid top-level kwargs
    option_names = [field.name for field in fields(options_class)]
    valid_kwargs = {k: v for k, v in flat_remaining_kwargs.items() if k in option_names}
    missing = [k for k in flat_remaining_kwargs if k not in valid_kwargs]
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

        # Handle case where format doesn't use options (returns None)
        if options_instance is None:
            return None

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
        # Handle nested dataclass kwargs
        from dataclasses import is_dataclass
        from typing import get_type_hints

        options_class = type(base_options)
        nested_info = _collect_nested_dataclass_kwargs(options_class, other_kwargs)
        nested_dataclass_kwargs = nested_info['nested']
        flat_other_kwargs = nested_info['remaining']

        # Use get_type_hints to properly resolve types
        try:
            type_hints = get_type_hints(options_class)
        except Exception:
            type_hints = {}

        # For nested dataclasses, merge with existing values
        for nested_field_name, nested_kwargs in nested_dataclass_kwargs.items():
            # Get existing nested instance
            existing_nested = getattr(merged_options, nested_field_name, None)

            if existing_nested is not None:
                # Merge with existing nested dataclass
                updated_nested = create_updated_options(existing_nested, **nested_kwargs)
                flat_other_kwargs[nested_field_name] = updated_nested
            else:
                # Create new nested dataclass instance using type hints
                field_type = type_hints.get(nested_field_name)
                if not field_type:
                    # Fallback to field.type
                    for field in fields(options_class):
                        if field.name == nested_field_name:
                            field_type = field.type
                            break

                if field_type:
                    nested_class = None
                    if hasattr(field_type, '__origin__'):
                        if hasattr(field_type, '__args__'):
                            for arg in field_type.__args__:
                                if arg is not type(None) and is_dataclass(arg):
                                    nested_class = arg
                                    break
                    elif is_dataclass(field_type):
                        nested_class = field_type

                    if nested_class:
                        flat_other_kwargs[nested_field_name] = nested_class(**nested_kwargs)  # type: ignore[operator]

        # Filter to only valid top-level kwargs before passing to create_updated
        option_field_names = {field.name for field in fields(options_class)}
        valid_other_kwargs = {k: v for k, v in flat_other_kwargs.items() if k in option_field_names}

        # Apply all updates
        if valid_other_kwargs:
            merged_options = merged_options.create_updated(**valid_other_kwargs)

    return merged_options


# Main conversion function starts here


def to_markdown(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        format: DocumentFormat = "auto",
        flavor: Optional[str] = None,
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
    flavor : str, optional
        Markdown flavor/dialect to use for output. Options: "gfm", "commonmark",
        "multimarkdown", "pandoc", "kramdown", "markdown_plus".
        If specified, takes precedence over flavor in options or kwargs.
        Defaults to "gfm" if not specified anywhere.
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

    Specifying markdown flavor:
        >>> markdown = to_markdown("document.pdf", flavor="commonmark")
        >>> markdown = to_markdown("document.pdf", flavor="multimarkdown")
    """

    # Handle flavor parameter priority: flavor param > kwargs > options
    if flavor is not None:
        # Flavor parameter takes highest priority
        kwargs['flavor'] = flavor
    elif 'flavor' not in kwargs and options is not None:
        # Use flavor from options if not in kwargs
        if isinstance(options, MarkdownOptions) and hasattr(options, 'flavor'):
            kwargs.setdefault('flavor', options.flavor)
        elif hasattr(options, 'markdown_options') and options.markdown_options is not None:
            kwargs.setdefault('flavor', options.markdown_options.flavor)

    # Determine format first, before opening files
    if format != "auto":
        # Format explicitly specified
        actual_format = format
        logger.debug(f"Using explicitly specified format: {actual_format}")
    elif isinstance(input, (str, Path)):
        # Try to detect format from filename first (won't open the file)
        actual_format = registry.detect_format(input, hint=None)
        # Registry already logs the detection method, no need to duplicate
    else:
        # For bytes or file-like objects, we need to inspect content
        if isinstance(input, bytes):
            file: IO[bytes] = BytesIO(input)
        else:
            file: IO[bytes] = input  # type: ignore
        actual_format = registry.detect_format(file, hint=None)
        # Registry already logs the detection method

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

    # Process input based on detected/specified format using registry
    try:
        # Get converter function from registry
        converter_func, options_class = registry.get_converter(actual_format)

        # Now handle the actual input
        if isinstance(input, (str, Path)):
            # Pass filename directly to converter - let it handle file opening
            # This is more efficient and preserves filename context
            if actual_format == "html":
                # HTML converter expects string content
                with open(input, 'r', encoding='utf-8', errors='replace') as f:
                    content = converter_func(f.read(), options=final_options)
            else:
                # Most converters can handle filename/path directly
                content = converter_func(input, options=final_options)

        elif isinstance(input, bytes):
            # Create BytesIO for bytes input
            file = BytesIO(input)
            if actual_format == "html":
                html_content = input.decode("utf-8", errors="replace")
                content = converter_func(html_content, options=final_options)
            else:
                content = converter_func(file, options=final_options)

        else:
            # File-like object
            file = input  # type: ignore
            if actual_format == "html":
                file.seek(0)
                html_content = file.read().decode("utf-8", errors="replace")
                content = converter_func(html_content, options=final_options)
            else:
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
            if isinstance(input, (str, Path)):
                try:
                    with open(input, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except Exception as e:
                    raise MarkdownConversionError(f"Could not read file as UTF-8: {input}") from e
            elif isinstance(input, bytes):
                try:
                    content = input.decode("utf-8", errors="replace")
                except Exception as e:
                    raise MarkdownConversionError("Could not decode bytes as UTF-8") from e
            else:
                # File-like object
                file = input  # type: ignore
                file.seek(0)
                try:
                    content = file.read()
                    if isinstance(content, bytes):
                        content = content.decode("utf-8", errors="replace")
                except Exception as e:
                    raise MarkdownConversionError("Could not decode file as UTF-8") from e

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
    "SourceCodeOptions",
    "MarkdownConversionError",
    "InputError",
    "DependencyError",
]
