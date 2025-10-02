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
    MarkdownParserOptions,
    MhtmlOptions,
    OdfOptions,
    PdfOptions,
    PptxOptions,
    RtfOptions,
    SourceCodeOptions,
    SpreadsheetOptions,
    create_updated_options,
)

# Import parsers to trigger registration
from . import parsers  # noqa: F401

# Import AST module for advanced users
from . import ast  # noqa: F401

# Import transforms module for AST transformation
from . import transforms  # noqa: F401

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
        "spreadsheet": SpreadsheetOptions,
        "markdown": MarkdownParserOptions
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


def _prepare_options(
        actual_format: DocumentFormat,
        options: Optional[BaseOptions | MarkdownOptions],
        flavor: Optional[str],
        kwargs: dict
) -> Optional[BaseOptions | MarkdownOptions]:
    """Prepare final options by handling flavor and merging options with kwargs.

    Parameters
    ----------
    actual_format : DocumentFormat
        The detected/specified document format
    options : BaseOptions | MarkdownOptions, optional
        Pre-configured options object
    flavor : str, optional
        Markdown flavor to use
    kwargs : dict
        Additional keyword arguments

    Returns
    -------
    BaseOptions | MarkdownOptions, optional
        Final merged options
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

    # Merge options
    if options is not None and kwargs:
        # Merge provided options with kwargs (kwargs override)
        return _merge_options(options, actual_format, **kwargs)
    elif options is not None:
        # Use provided options as-is
        return options
    elif kwargs:
        # Create options from kwargs only
        return _create_options_from_kwargs(actual_format, **kwargs)
    else:
        # No options provided
        return None


def to_markdown(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        format: DocumentFormat = "auto",
        flavor: Optional[str] = None,
        transforms: Optional[list] = None,
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
    transforms : list, optional
        List of AST transforms to apply before rendering. Can be transform names
        (strings) or NodeTransformer instances. Transforms are applied in order.
        See `all2md.transforms` for available transforms.
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

    Converting an in-memory BytesIO object:
        >>> from io import BytesIO
        >>> with open("document.pdf", "rb") as f:
        ...     data = BytesIO(f.read())
        >>> markdown = to_markdown(data)

    Using pre-configured options:
        >>> pdf_opts = PdfOptions(pages=[0, 1, 2], attachment_mode="download")
        >>> markdown = to_markdown("document.pdf", options=pdf_opts)

    Combining options with selective overrides:
        >>> base_opts = PdfOptions(attachment_mode="download", detect_columns=True)
        >>> markdown = to_markdown("doc.pdf", options=base_opts, attachment_mode="base64")
        # Uses base64 mode but keeps column detection enabled

    Format-specific options - PDF with page selection:
        >>> markdown = to_markdown("document.pdf", pages=[0, 1, 2])
        >>> markdown = to_markdown("large.pdf", pages=range(10, 20))

    Format-specific options - PowerPoint with notes:
        >>> markdown = to_markdown("presentation.pptx", include_notes=True)
        >>> markdown = to_markdown("slides.pptx", include_notes=True, include_comments=True)

    Format-specific options - DOCX with metadata:
        >>> markdown = to_markdown("document.docx", extract_metadata=True)

    Format-specific options - HTML with network resources:
        >>> markdown = to_markdown("page.html", allow_remote_fetch=True, max_fetch_size_mb=10)

    Using MarkdownOptions directly:
        >>> md_opts = MarkdownOptions(emphasis_symbol="_", bullet_symbols="•◦▪")
        >>> markdown = to_markdown("document.pdf", options=md_opts)

    Mixed markdown and format-specific options:
        >>> markdown = to_markdown("doc.pdf", pages=[0, 1], emphasis_symbol="_", bullet_symbols="•◦▪")

    Specifying markdown flavor:
        >>> markdown = to_markdown("document.pdf", flavor="commonmark")
        >>> markdown = to_markdown("document.pdf", flavor="multimarkdown")
    """

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

    # Prepare final options (handles flavor and merging)
    final_options = _prepare_options(actual_format, options, flavor, kwargs)

    # If transforms are provided, use AST pipeline instead of direct conversion
    if transforms:
        # Import transform pipeline
        from all2md.transforms import render as render_with_transforms

        # Convert to AST first
        ast_doc = to_ast(input, options=final_options, format=actual_format)

        # Extract MarkdownOptions for rendering
        if isinstance(final_options, MarkdownOptions):
            markdown_options = final_options
        elif final_options and hasattr(final_options, 'markdown_options'):
            markdown_options = final_options.markdown_options
        else:
            markdown_options = None

        # Apply transforms and render
        content = render_with_transforms(ast_doc, transforms=transforms, options=markdown_options)

        # Normalize line endings and return
        return content.replace("\r\n", "\n").replace("\r", "\n")

    # Process input based on detected/specified format using registry
    try:
        # Use new parser->renderer pattern
        # Get parser class from registry
        parser_class = registry.get_parser(actual_format)

        # Instantiate parser with options
        parser = parser_class(options=final_options)

        # Parse input to AST
        ast_doc = parser.parse(input)

        # Extract MarkdownOptions for rendering
        if isinstance(final_options, MarkdownOptions):
            markdown_options = final_options
        elif final_options and hasattr(final_options, 'markdown_options') and final_options.markdown_options:
            markdown_options = final_options.markdown_options
        else:
            # Create default MarkdownOptions
            markdown_options = MarkdownOptions()

        # Render AST to markdown
        from all2md.renderers.markdown import MarkdownRenderer
        renderer = MarkdownRenderer(options=markdown_options)
        content = renderer.render_to_string(ast_doc)

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

    # Normalize all line endings to \n
    return content.replace("\r\n", "\n").replace("\r", "\n")


def to_ast(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        format: DocumentFormat = "auto",
        flavor: Optional[str] = None,
        **kwargs
):
    """Convert document to AST (Abstract Syntax Tree) format.

    This function provides advanced users with direct access to the document AST,
    enabling custom processing, transformation, and analysis of document structure.
    The AST can be manipulated using utilities from `all2md.ast.transforms` and
    serialized to JSON using `all2md.ast.serialization`.

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
        Markdown flavor/dialect to use for rendering. Options: "gfm", "commonmark",
        "multimarkdown", "pandoc", "kramdown", "markdown_plus".
        If specified, takes precedence over flavor in options or kwargs.
        Defaults to "gfm" if not specified anywhere.
    kwargs : Any
        Individual conversion options that override settings in the `options`
        parameter. These are mapped to the appropriate format-specific
        options class and take precedence over the same fields in `options`.

    Returns
    -------
    Document
        AST Document node representing the document structure

    Raises
    ------
    FormatError
        If the format cannot be detected or is unsupported
    DependencyError
        If required dependencies for the format are not installed
    MarkdownConversionError
        If conversion fails

    Examples
    --------
    Get AST from a document:
        >>> from all2md import to_ast
        >>> ast_doc = to_ast("document.pdf")

    Manipulate AST and convert to markdown:
        >>> from all2md.ast import transforms, MarkdownRenderer
        >>> ast_doc = to_ast("document.pdf")
        >>> filtered_doc = transforms.filter_nodes(ast_doc, lambda n: not isinstance(n, Image))
        >>> renderer = MarkdownRenderer()
        >>> markdown = renderer.render(filtered_doc)

    Extract specific nodes:
        >>> from all2md.ast import transforms, Heading
        >>> ast_doc = to_ast("document.docx")
        >>> headings = transforms.extract_nodes(ast_doc, Heading)

    Serialize to JSON:
        >>> from all2md.ast import serialization
        >>> ast_doc = to_ast("document.html")
        >>> json_str = serialization.ast_to_json(ast_doc, indent=2)

    """
    from all2md.ast import Document

    # Use the same format detection and options merging as to_markdown()
    # Get the markdown string first, then parse it to AST
    # For formats with native AST parsers, use those directly

    # Detect format
    actual_format = format if format != "auto" else registry.detect_format(input)

    # Get converter metadata
    metadata = registry.get_format_info(actual_format)
    if not metadata:
        raise FormatError(f"Unknown format: {actual_format}")

    # Check and prepare options (same logic as to_markdown())
    final_options = _prepare_options(actual_format, options, flavor, kwargs)

    # Map of formats to their AST converter functions
    ast_converters = {
        "pdf": "all2md.parsers.pdf.pdf_to_ast",
        "docx": "all2md.parsers.docx.docx_to_ast",
        "html": "all2md.parsers.html.html_to_ast",
        "pptx": "all2md.parsers.pptx.pptx_to_ast",
        "ipynb": "all2md.parsers.ipynb.ipynb_to_ast",
        "eml": "all2md.parsers.eml.eml_to_ast",
        "odf": "all2md.parsers.odf.odf_to_ast",
        "rtf": "all2md.parsers.rtf.rtf_to_ast",
        "sourcecode": "all2md.parsers.sourcecode.sourcecode_to_ast",
        "spreadsheet": "all2md.parsers.spreadsheet.spreadsheet_to_ast",
        "markdown": "all2md.parsers.markdown.markdown_to_ast",
    }

    converter_path = ast_converters.get(actual_format)

    if converter_path:
        # Load the AST converter function
        module_path, func_name = converter_path.rsplit(".", 1)
        try:
            import importlib

            module = importlib.import_module(module_path)
            converter_func = getattr(module, func_name)
        except (ImportError, AttributeError) as e:
            raise FormatError(f"AST converter not available for format: {actual_format}") from e

        # Call the converter
        try:
            if isinstance(input, (str, Path)):
                # For markdown, read file content as string
                if actual_format == "markdown":
                    if isinstance(input, Path):
                        markdown_content = input.read_text(encoding="utf-8")
                    else:
                        # Assume string is a path
                        markdown_content = Path(input).read_text(encoding="utf-8")
                    ast_doc = converter_func(markdown_content, options=final_options)
                else:
                    ast_doc = converter_func(input, options=final_options)
            elif isinstance(input, bytes):
                if actual_format in ("html", "markdown"):
                    content = input.decode("utf-8", errors="replace")
                    ast_doc = converter_func(content, options=final_options)
                else:
                    from io import BytesIO

                    file = BytesIO(input)
                    ast_doc = converter_func(file, options=final_options)
            else:
                # File-like object
                file = input  # type: ignore
                if actual_format in ("html", "markdown"):
                    file.seek(0)
                    content = file.read().decode("utf-8", errors="replace")
                    ast_doc = converter_func(content, options=final_options)
                else:
                    file.seek(0)
                    ast_doc = converter_func(file, options=final_options)

            return ast_doc

        except DependencyError:
            raise
        except Exception as e:
            raise MarkdownConversionError(f"AST conversion failed: {e}") from e

    else:
        # For formats without AST support, fall back to markdown conversion
        # then parse the markdown to AST (future enhancement)
        raise FormatError(
            f"Direct AST conversion not yet supported for format: {actual_format}. "
            f"Use to_markdown() instead."
        )

# TODO: should also allow `markdown` to be a path or file.
def from_markdown(
        markdown: Union[str, Path, IO[bytes], IO[str]],
        target_format: str,
        output: Union[str, Path],
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        **kwargs
) -> None:
    """Convert Markdown to a target document format.

    This function enables bidirectional conversion by parsing Markdown into AST
    and rendering it to various output formats.

    Parameters
    ----------
    markdown : str
        Markdown content to convert
    target_format : str
        Target format (e.g., "docx", "pdf", "html")
    output : str or Path
        Output file path
    options : BaseOptions | MarkdownOptions, optional
        Pre-configured options object for the target format
    kwargs : Any
        Additional format-specific options

    Raises
    ------
    FormatError
        If target format is not supported or has no renderer
    DependencyError
        If required dependencies are not installed
    MarkdownConversionError
        If conversion fails

    Examples
    --------
    Convert Markdown to DOCX:
        >>> from_markdown("# Hello\\n\\nWorld", "docx", "output.docx")

    With options:
        >>> from all2md.options import DocxOptions
        >>> opts = DocxOptions(preserve_tables=True)
        >>> from_markdown(markdown_text, "docx", "output.docx", options=opts)

    """
    # Parse markdown to AST
    from all2md.parsers.markdown import MarkdownToAstConverter
    from all2md.options import MarkdownParserOptions

    parser = MarkdownToAstConverter(MarkdownParserOptions())
    doc_ast = parser.parse(markdown)

    # Get renderer for target format
    try:
        renderer_class = registry.get_renderer(target_format)
    except FormatError:
        raise FormatError(
            f"No renderer available for format '{target_format}'. "
            f"Only markdown format is currently supported for rendering."
        )

    # Prepare options for renderer
    final_options = _prepare_options(target_format, options, None, kwargs)

    # Create renderer and render
    renderer = renderer_class(final_options)
    renderer.render(doc_ast, output)


def convert(
        source: Union[str, Path, IO[bytes], bytes],
        output: Union[str, Path, None] = None,
        *,
        options: Optional[BaseOptions | MarkdownOptions] = None,
        source_format: DocumentFormat = "auto",
        target_format: DocumentFormat = "auto",
        **kwargs
) -> None | IO[bytes]:
    """Convert a document from one format to another.

    This is a general-purpose conversion function that handles
    format-to-format conversion via the AST intermediate representation.

    Parameters
    ----------
    source : str, Path, IO[bytes], or bytes
        Source document (file path, file-like object, or bytes)
    output : str or Path
        Output file path
    options : BaseOptions | MarkdownOptions, optional
        Pre-configured options object
    target_format : DocumentFormat, default "auto"
        Target format (e.g., "markdown", "docx", "pdf")
    source_format : DocumentFormat, default "auto"
        Source format (auto-detected if not specified)
    kwargs : Any
        Additional conversion options

    Raises
    ------
    FormatError
        If source/target format is not supported
    DependencyError
        If required dependencies are not installed
    MarkdownConversionError
        If conversion fails

    Examples
    --------
    Convert PDF to DOCX:
        >>> convert("input.pdf", "docx", "output.docx")

    Convert HTML to Markdown file:
        >>> convert("page.html", "markdown", "output.md")

    With format hint:
        >>> convert(data_bytes, "markdown", "output.md", format="html")

    """
    # Detect source format
    actual_format = source_format if source_format != "auto" else registry.detect_format(source)

    # Parse source to AST
    parser_class = registry.get_parser(actual_format)
    parser_options = _prepare_options(actual_format, options, None, kwargs)
    parser = parser_class(parser_options)
    doc_ast = parser.parse(source)

    # Get renderer for target format
    renderer_class = registry.get_renderer(target_format)
    renderer_options = _prepare_options(target_format, options, None, kwargs)
    renderer = renderer_class(renderer_options)

    # Render to output
    renderer.render(doc_ast, output)


__all__ = [
    "to_markdown",
    "to_ast",
    "from_markdown",
    "convert",
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
    # AST module (for advanced users)
    "ast",
    # Transforms module (for AST transformations)
    "transforms",
]
