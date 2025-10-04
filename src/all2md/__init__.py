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
import logging
from dataclasses import fields
from io import BytesIO
from pathlib import Path
from typing import IO, Any, Optional, Union, get_type_hints
from dataclasses import is_dataclass

from all2md.constants import DocumentFormat

# Extensions lists moved to constants.py - keep references for backward compatibility
from all2md.converter_registry import registry
from all2md.exceptions import DependencyError, FormatError, InputError, MarkdownConversionError, All2MdError
from all2md.options import (
    BaseParserOptions,
    BaseRendererOptions,
    DocxOptions,
    EmlOptions,
    CsvOptions,
    EpubOptions,
    HtmlOptions,
    IpynbOptions,
    MarkdownOptions,
    MarkdownParserOptions,
    MhtmlOptions,
    OdpOptions,
    OdsSpreadsheetOptions,
    OdtOptions,
    PdfOptions,
    PptxOptions,
    RtfOptions,
    SourceCodeOptions,
    XlsxOptions,
    create_updated_options,
)

# Import parsers to trigger registration
from . import parsers  # noqa: F401

# Import AST module for advanced users
from . import ast  # noqa: F401

# Import transforms module for AST transformation
from . import transforms as transforms_module  # noqa: F401

logger = logging.getLogger(__name__)


# Options handling helpers
# TODO: this should use the registry rather than be hardcoded.
def _get_parser_options_class_for_format(format: DocumentFormat) -> type[BaseParserOptions] | None:
    """Get the parser options class for a given document format.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseParserOptions] | None
        Parser options class or None for formats that don't have parser options.
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
        "odt": OdtOptions,
        "odp": OdpOptions,
        "epub": EpubOptions,
        "sourcecode": SourceCodeOptions,
        "xlsx": XlsxOptions,
        "ods": OdsSpreadsheetOptions,
        "csv": CsvOptions,
        "tsv": CsvOptions,  # TSV uses same options as CSV
        "markdown": MarkdownParserOptions
    }
    return format_to_class.get(format)


def _get_renderer_options_class_for_format(format: DocumentFormat) -> type[BaseRendererOptions] | None:
    """Get the renderer options class for a given document format.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseRendererOptions] | None
        Renderer options class or None for formats that don't have renderer options.
    """
    # Currently only markdown has a renderer
    if format == "markdown":
        return MarkdownOptions
    return None


def _collect_nested_dataclass_kwargs(options_class: type[BaseParserOptions] | type[BaseRendererOptions], kwargs: dict) -> dict:
    """Collect kwargs that belong to nested dataclass fields.

    This function inspects the options class for nested dataclass fields
    (e.g., network: NetworkFetchOptions) and groups kwargs that match
    those nested fields' internal field names.

    Parameters
    ----------
    options_class : type[BaseParserOptions] | type[BaseRendererOptions]
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


def _create_parser_options_from_kwargs(format: DocumentFormat, **kwargs) -> BaseParserOptions | None:
    """Create format-specific parser options object from keyword arguments.

    Parameters
    ----------
    format : DocumentFormat
        The document format to create parser options for.
    **kwargs
        Keyword arguments to use for parser options creation.

    Returns
    -------
    BaseParserOptions | None
        Parser options instance or None for formats that don't use parser options.
    """
    from dataclasses import is_dataclass

    options_class = _get_parser_options_class_for_format(format)
    if not options_class:
        return None

    # Collect nested dataclass kwargs
    nested_info = _collect_nested_dataclass_kwargs(options_class, kwargs)
    nested_dataclass_kwargs = nested_info['nested']
    flat_kwargs = nested_info['remaining']

    # Use get_type_hints to properly resolve types
    from typing import get_type_hints
    try:
        type_hints = get_type_hints(options_class)
    except Exception:
        type_hints = {}

    # Create instances of nested dataclasses
    for nested_field_name, nested_kwargs in nested_dataclass_kwargs.items():
        field_type = type_hints.get(nested_field_name)
        if not field_type:
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
                flat_kwargs[nested_field_name] = nested_class(**nested_kwargs)  # type: ignore[operator]

    # Filter to only valid top-level kwargs
    option_names = [field.name for field in fields(options_class)]
    valid_kwargs = {k: v for k, v in flat_kwargs.items() if k in option_names}
    missing = [k for k in flat_kwargs if k not in valid_kwargs]
    if missing:
        logger.debug(f"Skipping unknown parser options: {missing}")
    return options_class(**valid_kwargs)


def _create_renderer_options_from_kwargs(format: DocumentFormat, **kwargs) -> BaseRendererOptions | None:
    """Create format-specific renderer options object from keyword arguments.

    Parameters
    ----------
    format : DocumentFormat
        The document format to create renderer options for.
    **kwargs
        Keyword arguments to use for renderer options creation.

    Returns
    -------
    BaseRendererOptions | None
        Renderer options instance or None for formats that don't have renderer options.
    """
    options_class = _get_renderer_options_class_for_format(format)
    if not options_class:
        return None

    # Filter to only valid kwargs for this options class
    option_names = [field.name for field in fields(options_class)]
    valid_kwargs = {k: v for k, v in kwargs.items() if k in option_names}
    missing = [k for k in kwargs if k not in valid_kwargs]
    if missing:
        logger.debug(f"Skipping unknown renderer options: {missing}")
    return options_class(**valid_kwargs)


def _split_kwargs_for_parser_and_renderer(
    parser_format: DocumentFormat,
    renderer_format: DocumentFormat,
    kwargs: dict
) -> tuple[dict, dict]:
    """Split kwargs between parser and renderer based on their field names.

    Parameters
    ----------
    parser_format : DocumentFormat
        Parser format to determine which kwargs belong to parser
    renderer_format : DocumentFormat
        Renderer format to determine which kwargs belong to renderer
    kwargs : dict
        Keyword arguments to split

    Returns
    -------
    tuple[dict, dict]
        (parser_kwargs, renderer_kwargs)
    """
    parser_class = _get_parser_options_class_for_format(parser_format)
    renderer_class = _get_renderer_options_class_for_format(renderer_format)

    parser_kwargs = {}
    renderer_kwargs = {}
    unmatched = []

    # Get field names for both classes
    parser_fields = set()
    if parser_class:
        parser_fields = {f.name for f in fields(parser_class)}
        # Also include nested dataclass fields
        nested_info = _collect_nested_dataclass_kwargs(parser_class, kwargs)
        for nested_field_name, nested_dataclass in nested_info['nested'].items():
            for k in nested_dataclass.keys():
                parser_fields.add(k)

    renderer_fields = set()
    if renderer_class:
        renderer_fields = {f.name for f in fields(renderer_class)}

    # Split kwargs
    for k, v in kwargs.items():
        if k in parser_fields:
            parser_kwargs[k] = v
        elif k in renderer_fields:
            renderer_kwargs[k] = v
        else:
            unmatched.append(k)

    if unmatched:
        logger.debug(f"Kwargs don't match parser or renderer fields: {unmatched}")

    return parser_kwargs, renderer_kwargs


def to_markdown(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        parser_options: Optional[BaseParserOptions] = None,
        renderer_options: Optional[MarkdownOptions] = None,
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
    parser_options : BaseParserOptions, optional
        Pre-configured parser options for format-specific parsing settings
        (e.g., PdfOptions, DocxOptions, HtmlOptions).
    renderer_options : BaseRendererOptions, optional
        Pre-configured renderer options for Markdown rendering settings
        (e.g., MarkdownOptions).
    format : DocumentFormat, default "auto"
        Explicitly specify the document format. If "auto", the format is
        detected from the filename or content.
    flavor : str, optional
        Markdown flavor/dialect to use for output. Options: "gfm", "commonmark",
        "multimarkdown", "pandoc", "kramdown", "markdown_plus".
        Shorthand for renderer_options=MarkdownOptions(flavor=...).
    transforms : list, optional
        List of AST transforms to apply before rendering. Can be transform names
        (strings) or NodeTransformer instances. Transforms are applied in order.
        See `all2md.transforms` for available transforms.
    kwargs : Any
        Individual conversion options. Kwargs are intelligently split between
        parser and renderer based on field names. Parser-related kwargs override
        fields in parser_options, renderer-related kwargs override fields in
        renderer_options.

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

    Examples
    --------
    Basic conversion:
        >>> markdown = to_markdown("document.pdf")

    With parser options:
        >>> pdf_opts = PdfOptions(pages=[0, 1, 2], attachment_mode="download")
        >>> markdown = to_markdown("document.pdf", parser_options=pdf_opts)

    With renderer options:
        >>> md_opts = MarkdownOptions(emphasis_symbol="_", flavor="commonmark")
        >>> markdown = to_markdown("document.pdf", renderer_options=md_opts)

    Using both parser and renderer options:
        >>> markdown = to_markdown("doc.pdf",
        ...     parser_options=PdfOptions(pages=[0, 1]),
        ...     renderer_options=MarkdownOptions(flavor="gfm"))

    Using kwargs (automatically split):
        >>> markdown = to_markdown("doc.pdf", pages=[0, 1], emphasis_symbol="_")

    Using flavor shorthand:
        >>> markdown = to_markdown("document.pdf", flavor="commonmark")

    With transforms:
        >>> markdown = to_markdown("doc.pdf", transforms=["remove-images"])
    """
    if "options" in kwargs:
        raise ValueError("`options` is deprecated! Use `parse_options` or `renderer_options`")
    # Determine format first
    if format != "auto":
        actual_format = format
        logger.debug(f"Using explicitly specified format: {actual_format}")
    elif isinstance(input, (str, Path)):
        actual_format = registry.detect_format(input, hint=None)
    else:
        if isinstance(input, bytes):
            file: IO[bytes] = BytesIO(input)
        else:
            file: IO[bytes] = input  # type: ignore
        actual_format = registry.detect_format(file, hint=None)

    # Split kwargs between parser and renderer
    parser_kwargs, renderer_kwargs = _split_kwargs_for_parser_and_renderer(
        actual_format, "markdown", kwargs
    )

    # Prepare parser options
    if parser_kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**parser_kwargs)
    elif parser_kwargs:
        final_parser_options = _create_parser_options_from_kwargs(actual_format, **parser_kwargs)
    else:
        final_parser_options = parser_options

    # Prepare renderer options (handle flavor shorthand)
    if flavor:
        renderer_kwargs['flavor'] = flavor

    if renderer_kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
    elif renderer_kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs("markdown", **renderer_kwargs)
    elif renderer_options:
        final_renderer_options = renderer_options
    else:
        # Default to GFM flavor
        final_renderer_options = MarkdownOptions()

    # Convert to AST
    try:
        # Log timing for parsing stage in trace mode
        if logger.isEnabledFor(logging.DEBUG):
            import time
            start_time = time.perf_counter()
            ast_doc = to_ast(input, parser_options=final_parser_options, format=actual_format)
            parse_time = time.perf_counter() - start_time
            logger.debug(f"Parsing ({actual_format}) completed in {parse_time:.2f}s")
        else:
            ast_doc = to_ast(input, parser_options=final_parser_options, format=actual_format)
    except DependencyError:
        raise
    except FormatError as e:
        # Handle unknown formats by falling back to text
        if actual_format not in ["txt", "image"]:
            logger.warning(f"Unknown format '{actual_format}', falling back to text")
            actual_format = "txt"

        if actual_format == "image":
            raise FormatError("Invalid input type: `image` not supported.") from e
        else:
            # Plain text handling - return content directly without AST
            if isinstance(input, (str, Path)):
                try:
                    with open(input, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()
                except Exception as exc:
                    raise MarkdownConversionError(f"Could not read file as UTF-8: {input}") from exc
            elif isinstance(input, bytes):
                try:
                    content = input.decode("utf-8", errors="replace")
                except Exception as exc:
                    raise MarkdownConversionError("Could not decode bytes as UTF-8") from exc
            else:
                file = input  # type: ignore
                file.seek(0)
                try:
                    file_content = file.read()
                    if isinstance(file_content, bytes):
                        content = file_content.decode("utf-8", errors="replace")
                    else:
                        content = file_content
                except Exception as exc:
                    raise MarkdownConversionError("Could not decode file as UTF-8") from exc

            return content.replace("\r\n", "\n").replace("\r", "\n")

    # Apply transforms and render using pipeline
    if logger.isEnabledFor(logging.DEBUG):
        import time
        start_time = time.perf_counter()
        content = transforms_module.render(
            ast_doc,
            transforms=transforms or [],
            renderer="markdown",
            options=final_renderer_options
        )
        render_time = time.perf_counter() - start_time
        logger.debug(f"Rendering (markdown) completed in {render_time:.2f}s")
    else:
        content = transforms_module.render(
            ast_doc,
            transforms=transforms or [],
            renderer="markdown",
            options=final_renderer_options
        )

    return content.replace("\r\n", "\n").replace("\r", "\n")


def to_ast(
        input: Union[str, Path, IO[bytes], bytes],
        *,
        parser_options: Optional[BaseParserOptions] = None,
        format: DocumentFormat = "auto",
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
    parser_options : BaseParserOptions, optional
        Pre-configured parser options for format-specific parsing settings
        (e.g., PdfOptions, DocxOptions, HtmlOptions).
    format : DocumentFormat, default "auto"
        Explicitly specify the document format. If "auto", the format is
        detected from the filename or content.
    kwargs : Any
        Individual parser options that override settings in parser_options.

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
        >>> from all2md.ast import transforms
        >>> from all2md.renderers.markdown import MarkdownRenderer
        >>> ast_doc = to_ast("document.pdf")
        >>> filtered_doc = transforms.filter_nodes(ast_doc, lambda n: not isinstance(n, Image))
        >>> renderer = MarkdownRenderer()
        >>> markdown = renderer.render_to_string(filtered_doc)

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

    # Detect format
    actual_format = format if format != "auto" else registry.detect_format(input)

    # Get converter metadata
    metadata = registry.get_format_info(actual_format)
    if not metadata:
        raise FormatError(f"Unknown format: {actual_format}")

    # Prepare parser options
    if kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**kwargs)
    elif kwargs:
        final_parser_options = _create_parser_options_from_kwargs(actual_format, **kwargs)
    else:
        final_parser_options = parser_options

    # Use the parser class system to convert to AST
    try:
        parser_class = registry.get_parser(actual_format)
        parser = parser_class(options=final_parser_options)
        ast_doc = parser.parse(input)
        return ast_doc

    except All2MdError:
        raise
    except Exception as e:
        raise MarkdownConversionError(f"AST conversion failed: {e}") from e

def from_ast(
        ast_doc: "Document",
        target_format: DocumentFormat,
        output: Union[str, Path, IO[bytes], None] = None,
        *,
        renderer_options: Optional[BaseRendererOptions] = None,
        transforms: Optional[list] = None,
        hooks: Optional[dict] = None,
        **kwargs
) -> Union[None, str, bytes]:
    """Render AST document to a target format.

    Parameters
    ----------
    ast_doc : Document
        AST Document node to render
    target_format : DocumentFormat
        Target format name (e.g., "markdown", "docx", "pdf")
    output : str, Path, IO[bytes], or None, optional
        Output destination. If None, returns rendered content as string or bytes
    renderer_options : BaseRendererOptions, optional
        Renderer options for the target format
    transforms : list, optional
        AST transforms to apply before rendering
    hooks : dict, optional
        Transform hooks to execute during processing
    kwargs : Any
        Additional renderer options that override renderer_options

    Returns
    -------
    None, str, or bytes
        None if output was specified, otherwise the rendered content

    Examples
    --------
    Render AST to markdown string:
        >>> ast_doc = to_ast("document.pdf")
        >>> markdown = from_ast(ast_doc, "markdown")

    Render AST to file:
        >>> from_ast(ast_doc, "markdown", output="output.md")

    With renderer options:
        >>> md_opts = MarkdownOptions(flavor="commonmark")
        >>> markdown = from_ast(ast_doc, "markdown", renderer_options=md_opts)
    """

    # Prepare renderer options
    if kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**kwargs)
    elif kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs(target_format, **kwargs)
    else:
        final_renderer_options = renderer_options

    # Use transform pipeline to render
    content = transforms_module.render(
        ast_doc,
        transforms=transforms or [],
        hooks=hooks or {},
        renderer=target_format,
        options=final_renderer_options
    )

    # Handle output
    if output is None:
        return content
    elif isinstance(output, (str, Path)):
        Path(output).write_text(content, encoding="utf-8")
        return None
    else:
        # File-like object
        if hasattr(output, 'mode') and 'b' in output.mode:
            output.write(content.encode('utf-8'))
        else:
            output.write(content)
        return None


def from_markdown(
        markdown: Union[str, Path, IO[bytes], IO[str]],
        target_format: DocumentFormat,
        output: Union[str, Path, IO[bytes], None] = None,
        *,
        parser_options: Optional[MarkdownParserOptions] = None,
        renderer_options: Optional[BaseRendererOptions] = None,
        transforms: Optional[list] = None,
        hooks: Optional[dict] = None,
        **kwargs
) -> Union[None, str, bytes]:
    """Convert Markdown content to another format.

    Parameters
    ----------
    markdown : str, Path, IO[bytes], or IO[str]
        Markdown content as string, file path, or file-like object
    target_format : DocumentFormat
        Target format name (e.g., "docx", "pdf", "html")
    output : str, Path, IO[bytes], or None, optional
        Output destination. If None, returns rendered content
    parser_options : MarkdownParserOptions, optional
        Options for parsing Markdown
    renderer_options : BaseRendererOptions, optional
        Options for rendering to target format
    transforms : list, optional
        AST transforms to apply
    hooks : dict, optional
        Transform hooks to execute
    kwargs : Any
        Additional options split between parser and renderer

    Returns
    -------
    None, str, or bytes
        None if output specified, otherwise rendered content

    Examples
    --------
    Convert markdown string to HTML:
        >>> html = from_markdown("# Title\\n\\nContent", "html")

    Convert markdown file to DOCX:
        >>> from_markdown("input.md", "docx", output="output.docx")

    With options:
        >>> from_markdown("input.md", "html",
        ...     parser_options=MarkdownParserOptions(flavor="gfm"),
        ...     renderer_options=HtmlOptions(...))
    """
    return convert(
        markdown,
        output=output,
        parser_options=parser_options,
        renderer_options=renderer_options,
        source_format="markdown",
        target_format=target_format,
        transforms=transforms,
        hooks=hooks,
        **kwargs,
    )

def convert(
        source: Union[str, Path, IO[bytes], IO[str], bytes],
        output: Union[str, Path, IO[bytes], IO[str], None] = None,
        *,
        parser_options: Optional[BaseParserOptions] = None,
        renderer_options: Optional[BaseRendererOptions] = None,
        source_format: DocumentFormat = "auto",
        target_format: DocumentFormat = "auto",
        transforms: Optional[list] = None,
        hooks: Optional[dict] = None,
        renderer: Optional[Union[str, type, object]] = None,
        flavor: Optional[str] = None,
        **kwargs
) -> Union[None, str, bytes]:
    """Convert between document formats.

    Parameters
    ----------
    source : str, Path, IO[bytes], IO[str], or bytes
        Source document (file path, file-like object, or content)
    output : str, Path, IO[bytes], IO[str], or None, optional
        Output destination. If None, returns content
    parser_options : BaseParserOptions, optional
        Options for parsing source format
    renderer_options : BaseRendererOptions, optional
        Options for rendering target format
    source_format : DocumentFormat, default "auto"
        Source format (auto-detected if "auto")
    target_format : DocumentFormat, default "auto"
        Target format (inferred from output or defaults to "markdown")
    transforms : list, optional
        AST transforms to apply
    hooks : dict, optional
        Transform hooks to execute
    renderer : str, type, or object, optional
        Custom renderer (overrides target_format)
    flavor : str, optional
        Markdown flavor shorthand for renderer_options
    kwargs : Any
        Additional options split between parser and renderer

    Returns
    -------
    None, str, or bytes
        None if output specified, otherwise rendered content

    Examples
    --------
    Convert PDF to markdown:
        >>> markdown = convert("doc.pdf", target_format="markdown")

    Convert with options:
        >>> convert("doc.pdf", "output.md",
        ...     parser_options=PdfOptions(pages=[0, 1]),
        ...     renderer_options=MarkdownOptions(flavor="commonmark"))

    Bidirectional with transforms:
        >>> convert("input.docx", "output.md",
        ...     transforms=["remove-images", "heading-offset"])
    """
    transforms = transforms or []
    hooks = hooks or {}

    # Detect source format
    actual_source_format = (
        source_format if source_format != "auto" else registry.detect_format(source)
    )

    # Determine target format
    if target_format != "auto":
        actual_target_format = target_format
    elif isinstance(renderer, str):
        actual_target_format = renderer
    elif isinstance(output, (str, Path)):
        inferred = registry.detect_format(output)
        actual_target_format = inferred if inferred != "txt" else "markdown"
    else:
        actual_target_format = "markdown"

    # Split kwargs between parser and renderer
    parser_kwargs, renderer_kwargs = _split_kwargs_for_parser_and_renderer(
        actual_source_format, actual_target_format, kwargs
    )

    # Parse to AST
    if parser_kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**parser_kwargs)
    elif parser_kwargs:
        final_parser_options = _create_parser_options_from_kwargs(actual_source_format, **parser_kwargs)
    else:
        final_parser_options = parser_options

    ast_document = to_ast(
        source,
        parser_options=final_parser_options,
        format=actual_source_format,
    )

    # Prepare renderer options
    if flavor:
        renderer_kwargs['flavor'] = flavor

    if renderer_kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
    elif renderer_kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs(actual_target_format, **renderer_kwargs)
    else:
        final_renderer_options = renderer_options

    # Render AST to target format
    renderer_spec = renderer or actual_target_format

    rendered = transforms_module.render(
        ast_document,
        transforms=transforms,
        hooks=hooks,
        renderer=renderer_spec,
        options=final_renderer_options,
    )

    # Handle output
    if output is None:
        return rendered

    if isinstance(output, (str, Path)):
        output_path = Path(output)
        if isinstance(rendered, str):
            output_path.write_text(rendered, encoding='utf-8')
        else:
            output_path.write_bytes(rendered)
        return None

    if hasattr(output, 'write'):
        if isinstance(rendered, str):
            mode = getattr(output, 'mode', '')
            if isinstance(mode, str) and 'b' in mode:
                output.write(rendered.encode('utf-8'))  # type: ignore[arg-type]
            else:
                output.write(rendered)  # type: ignore[arg-type]
        else:
            output.write(rendered)  # type: ignore[arg-type]
        return None

    raise ValueError("Unsupported output destination provided to convert().")


__all__ = [
    "to_markdown",
    "to_ast",
    "from_ast",
    "from_markdown",
    "convert",
    # Registry system
    "registry",
    # Type definitions
    "DocumentFormat",
    # Re-exported classes and exceptions for public API
    "BaseParserOptions",
    "BaseRendererOptions",
    "CsvOptions",
    "DocxOptions",
    "EmlOptions",
    "EpubOptions",
    "HtmlOptions",
    "IpynbOptions",
    "MarkdownOptions",
    "MarkdownParserOptions",
    "MhtmlOptions",
    "OdpOptions",
    "OdsSpreadsheetOptions",
    "OdtOptions",
    "PdfOptions",
    "PptxOptions",
    "RtfOptions",
    "SourceCodeOptions",
    "XlsxOptions",
    "MarkdownConversionError",
    "InputError",
    "DependencyError",
    # AST module (for advanced users)
    "ast",
    # Transforms module (for AST transformations)
    "transforms",
]
