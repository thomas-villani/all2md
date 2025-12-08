"""The major exported API functions for document conversion."""

#  Copyright (c) 2025 Tom Villani, Ph.D.
# src/all2md/api.py
import logging
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import IO, Any, Optional, TypeVar, Union, cast, get_type_hints

import all2md.transforms as transforms_module
from all2md.ast.nodes import Document
from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, FormatError, ParsingError
from all2md.options.base import BaseParserOptions, BaseRendererOptions
from all2md.options.markdown import MarkdownParserOptions, MarkdownRendererOptions
from all2md.progress import ProgressCallback
from all2md.utils.decorators import debug_timer
from all2md.utils.input_sources import (
    DocumentSource,
    DocumentSourceRequest,
    RemoteInputOptions,
    default_loader,
)
from all2md.utils.io_utils import write_content

logger = logging.getLogger(__name__)

# TypeVar for generic options creation
OptionsT = TypeVar("OptionsT", BaseParserOptions, BaseRendererOptions)


def _resolve_document_source(
    source: Union[str, Path, IO[bytes], IO[str], bytes],
    remote_input_options: RemoteInputOptions | None,
    progress_callback: Optional[ProgressCallback] = None,
) -> DocumentSource:
    """Resolve raw input into a DocumentSource using the configured loader.

    Parameters
    ----------
    source : Union[str, Path, IO[bytes], IO[str], bytes]
        Source document data
    remote_input_options : RemoteInputOptions or None
        Options controlling remote document retrieval
    progress_callback : ProgressCallback, optional
        Optional callback for progress updates during source resolution

    Returns
    -------
    DocumentSource
        Resolved document source

    """
    loader = default_loader()
    request = DocumentSourceRequest(
        raw_input=source, remote_options=remote_input_options, progress_callback=progress_callback
    )
    return loader.load(request)


def _get_parser_options_class_for_format(format: DocumentFormat) -> type[BaseParserOptions] | None:
    """Get the parser options class for a given document format from the registry.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseParserOptions] | None
        Parser options class or None for formats that don't have parser options.

    """
    try:
        return registry.get_parser_options_class(format)
    except FormatError:
        return None


def _get_renderer_options_class_for_format(format: DocumentFormat) -> type[BaseRendererOptions] | None:
    """Get the renderer options class for a given document format from the registry.

    Parameters
    ----------
    format : DocumentFormat
        The document format.

    Returns
    -------
    type[BaseRendererOptions] | None
        Renderer options class or None for formats that don't have renderer options.

    """
    try:
        return registry.get_renderer_options_class(format)
    except FormatError:
        return None


def _collect_nested_dataclass_kwargs(
    options_class: type[BaseParserOptions] | type[BaseRendererOptions], kwargs: dict
) -> dict:
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
        if hasattr(field_type, "__origin__"):
            # For Optional[SomeType], get the actual type
            if hasattr(field_type, "__args__"):
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

    return {"nested": nested_kwargs, "remaining": remaining_kwargs}


def _create_options_from_kwargs(
    options_class: type[OptionsT] | None,
    options_type_name: str,
    **kwargs: Any,
) -> OptionsT | None:
    """Create format-specific options object from keyword arguments.

    Parameters
    ----------
    options_class : type[OptionsT] | None
        The options class to instantiate, or None if no options class exists.
    options_type_name : str
        Name of the options type for logging (e.g., "parser" or "renderer").
    **kwargs
        Keyword arguments to use for options creation.

    Returns
    -------
    OptionsT | None
        Options instance or None if options_class is None.

    """
    if not options_class:
        return None

    # Collect nested dataclass kwargs
    nested_info = _collect_nested_dataclass_kwargs(options_class, kwargs)
    nested_dataclass_kwargs = nested_info["nested"]
    flat_kwargs = nested_info["remaining"]

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
            if hasattr(field_type, "__origin__"):
                if hasattr(field_type, "__args__"):
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
        logger.debug(f"Skipping unknown {options_type_name} options: {missing}")
    return options_class(**valid_kwargs)


def _create_parser_options_from_kwargs(format: DocumentFormat, **kwargs: Any) -> BaseParserOptions | None:
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
    options_class = _get_parser_options_class_for_format(format)
    return _create_options_from_kwargs(options_class, "parser", **kwargs)


def _create_renderer_options_from_kwargs(format: DocumentFormat, **kwargs: Any) -> BaseRendererOptions | None:
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
    return _create_options_from_kwargs(options_class, "renderer", **kwargs)


def _split_kwargs_for_parser_and_renderer(
    parser_format: DocumentFormat, renderer_format: DocumentFormat, kwargs: dict
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
        for _nested_field_name, nested_dataclass in nested_info["nested"].items():
            for k in nested_dataclass.keys():
                parser_fields.add(k)

    renderer_fields = set()
    if renderer_class:
        renderer_fields = {f.name for f in fields(renderer_class)}
        # Also include nested dataclass fields
        nested_info = _collect_nested_dataclass_kwargs(renderer_class, kwargs)
        for _nested_field_name, nested_dataclass in nested_info["nested"].items():
            for k in nested_dataclass.keys():
                renderer_fields.add(k)

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
    source: Union[str, Path, IO[bytes], bytes, Document],
    *,
    parser_options: Optional[BaseParserOptions] = None,
    renderer_options: Optional[MarkdownRendererOptions] = None,
    source_format: DocumentFormat = "auto",
    flavor: Optional[str] = None,
    transforms: Optional[list] = None,
    hooks: Optional[dict] = None,
    progress_callback: Optional[ProgressCallback] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
    **kwargs: Any,
) -> str:
    """Convert document to Markdown format with enhanced format detection.

    This is the main entry point for the all2md library. It can detect file
    formats from filenames, content analysis, or explicit format specification,
    then routes to the appropriate specialized converter for processing.

    Parameters
    ----------
    source : str, Path, IO[bytes|str], bytes, or Document
        Source document data, which can be a file path, a file-like object, raw bytes,
        or an AST Document object (for cases where you already have a parsed AST).
    parser_options : BaseParserOptions, optional
        Pre-configured parser options for format-specific parsing settings
        (e.g., PdfOptions, DocxOptions, HtmlOptions).
    renderer_options : BaseRendererOptions, optional
        Pre-configured renderer options for Markdown rendering settings
        (e.g., MarkdownOptions).
    source_format : DocumentFormat, default "auto"
        Explicitly specify the source document format. If "auto", the format is
        detected from the filename or content.
    flavor : str, optional
        Markdown flavor/dialect to use for output. Options: "gfm", "commonmark",
        "multimarkdown", "pandoc", "kramdown", "markdown_plus".
        Shorthand for renderer_options=MarkdownOptions(flavor=...).
    transforms : list, optional
        List of AST transforms to apply before rendering. Can be transform names
        (strings) or NodeTransformer instances. Transforms are applied in order.
        See `all2md.transforms` for available transforms.
    hooks : dict, optional
        Transform hooks to execute during processing. Maps hook names to
        callable functions that execute at specific points in the transform pipeline.
    progress_callback : ProgressCallback, optional
        Optional callback function for progress updates. Receives ProgressEvent
        objects with event_type, message, current/total counts, and metadata.
        See all2md.progress for details.
    remote_input_options : RemoteInputOptions, optional
        Controls remote retrieval behaviour (network allowlists, size limits, etc.).
        Defaults to None, which disables remote fetching.
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
    ParsingError
        If file processing fails due to corruption or format issues.

    Examples
    --------
    Basic conversion:
        >>> markdown = to_markdown("document.pdf")

    With parser options:
        >>> pdf_opts = PdfOptions(pages=[0, 1, 2], attachment_mode="save")
        >>> markdown = to_markdown("document.pdf", parser_options=pdf_opts)

    With renderer options:
        >>> md_opts = MarkdownRendererOptions(emphasis_symbol="_", flavor="commonmark")
        >>> markdown = to_markdown("document.pdf", renderer_options=md_opts)

    Using both parser and renderer options:
        >>> markdown = to_markdown("doc.pdf",
        ...     parser_options=PdfOptions(pages=[0, 1]),
        ...     renderer_options=MarkdownRendererOptions(flavor="gfm"))

    Using kwargs (automatically split):
        >>> markdown = to_markdown("doc.pdf", pages=[0, 1], emphasis_symbol="_")

    Using flavor shorthand:
        >>> markdown = to_markdown("document.pdf", flavor="commonmark")

    With transforms:
        >>> markdown = to_markdown("doc.pdf", transforms=["remove-images"])

    From AST Document:
        >>> ast_doc = to_ast("document.pdf")
        >>> # Apply custom processing to ast_doc...
        >>> markdown = to_markdown(ast_doc)

    """
    # If source is already a Document AST, skip parsing and go directly to rendering
    if isinstance(source, Document):
        ast_doc = source

        # Prepare renderer options (handle flavor shorthand)
        if flavor:
            kwargs["flavor"] = flavor

        # Split kwargs for renderer (parser kwargs are irrelevant for AST input)
        _, renderer_kwargs = _split_kwargs_for_parser_and_renderer("markdown", "markdown", kwargs)

        final_renderer_options: MarkdownRendererOptions
        if renderer_kwargs and renderer_options:
            final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
        elif renderer_kwargs:
            result = _create_renderer_options_from_kwargs("markdown", **renderer_kwargs)
            assert result is None or isinstance(result, MarkdownRendererOptions)
            final_renderer_options = result if result else MarkdownRendererOptions()
        elif renderer_options:
            final_renderer_options = renderer_options
        else:
            # Default to GFM flavor
            final_renderer_options = MarkdownRendererOptions()

        # Apply transforms and render using pipeline
        with debug_timer(logger, "Rendering (markdown from AST)"):
            render_result = transforms_module.render(
                ast_doc,
                transforms=transforms or [],
                hooks=hooks or {},
                renderer="markdown",
                options=final_renderer_options,
                progress_callback=progress_callback,
            )

        assert isinstance(render_result, str), "Markdown renderer should return str"
        content = render_result

        return content.replace("\r\n", "\n").replace("\r", "\n")

    # Standard path: parse source document to AST
    resolved_source = _resolve_document_source(source, remote_input_options, progress_callback)
    detection_input = resolved_source.payload

    # Determine format first
    if source_format != "auto":
        actual_format: DocumentFormat = source_format
        logger.debug(f"Using explicitly specified format: {actual_format}")
    else:
        detected = registry.detect_format(detection_input, hint=None)  # type: ignore[arg-type]
        if detected is None:
            raise ValueError("Could not detect format from source")
        actual_format = detected  # type: ignore[assignment]

    # Split kwargs between parser and renderer
    parser_kwargs, renderer_kwargs = _split_kwargs_for_parser_and_renderer(actual_format, "markdown", kwargs)

    # Prepare parser options
    final_parser_options: BaseParserOptions | None
    if parser_kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**parser_kwargs)
    elif parser_kwargs:
        final_parser_options = _create_parser_options_from_kwargs(actual_format, **parser_kwargs)
    else:
        final_parser_options = parser_options

    # Prepare renderer options (handle flavor shorthand)
    if flavor:
        renderer_kwargs["flavor"] = flavor

    if renderer_kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
    elif renderer_kwargs:
        result = _create_renderer_options_from_kwargs("markdown", **renderer_kwargs)
        assert result is None or isinstance(result, MarkdownRendererOptions)
        final_renderer_options = result if result else MarkdownRendererOptions()
    elif renderer_options:
        final_renderer_options = renderer_options
    else:
        # Default to GFM flavor
        final_renderer_options = MarkdownRendererOptions()

    # Convert to AST
    try:
        # Log timing for parsing stage in trace mode
        # Type narrow for to_ast (exclude IO[str])
        ast_input: Union[str, Path, IO[bytes], bytes]
        if isinstance(detection_input, (str, Path, bytes)):
            ast_input = detection_input
        elif hasattr(detection_input, "read"):
            # Cast IO types - we already validated it's not IO[str] above
            ast_input = cast(Union[IO[bytes]], detection_input)
        else:
            raise ValueError("Invalid input type after format detection")

        with debug_timer(logger, f"Parsing ({actual_format})"):
            ast_doc = to_ast(
                ast_input,
                parser_options=final_parser_options,
                source_format=actual_format,
                progress_callback=progress_callback,
                remote_input_options=remote_input_options,
            )
    except All2MdError:
        raise

    # Apply transforms and render using pipeline
    with debug_timer(logger, "Rendering (markdown)"):
        render_result = transforms_module.render(
            ast_doc,
            transforms=transforms or [],
            hooks=hooks or {},
            renderer="markdown",
            options=final_renderer_options,
            progress_callback=progress_callback,
        )

    # Markdown renderer always returns str
    assert isinstance(render_result, str), "Markdown renderer should return str"
    content = render_result

    return content.replace("\r\n", "\n").replace("\r", "\n")


def to_ast(
    source: Union[str, Path, IO[bytes], bytes],
    *,
    parser_options: Optional[BaseParserOptions] = None,
    source_format: DocumentFormat = "auto",
    progress_callback: Optional[ProgressCallback] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
    **kwargs: Any,
) -> "Document":
    """Convert document to AST (Abstract Syntax Tree) format.

    This function provides advanced users with direct access to the document AST,
    enabling custom processing, transformation, and analysis of document structure.
    The AST can be manipulated using utilities from `all2md.ast.transforms` and
    serialized to JSON using `all2md.ast.serialization`.

    Parameters
    ----------
    source : str, Path, IO[bytes], or bytes
        Source document data, which can be a file path, a file-like object, or raw bytes.
    parser_options : BaseParserOptions, optional
        Pre-configured parser options for format-specific parsing settings
        (e.g., PdfOptions, DocxOptions, HtmlOptions).
    source_format : DocumentFormat, default "auto"
        Explicitly specify the source document format. If "auto", the format is
        detected from the filename or content.
    progress_callback : ProgressCallback, optional
        Optional callback function for progress updates. Receives ProgressEvent
        objects with event_type, message, current/total counts, and metadata.
        See all2md.progress for details.
    remote_input_options : RemoteInputOptions, optional
        Controls remote retrieval behaviour for the source input. Defaults to None
        (remote fetching disabled).
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
    ParsingError
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
    resolved_source = _resolve_document_source(source, remote_input_options, progress_callback)
    resolved_payload = resolved_source.payload

    # Detect format
    # Type narrow to exclude IO[str] for detect_format
    actual_format: DocumentFormat
    if source_format != "auto":
        actual_format = source_format
    else:
        # Accept: str, Path, bytes, BytesIO, NamedBytesIO, or any binary stream
        if isinstance(resolved_payload, (str, Path, bytes)):
            actual_format = cast(DocumentFormat, registry.detect_format(resolved_payload))
        elif hasattr(resolved_payload, "read") and hasattr(resolved_payload, "seek"):
            # Binary stream (has read+seek) - let registry.detect_format handle it
            # This includes BytesIO, NamedBytesIO, and file objects
            # Type ignore: resolved_payload could be IO[str] but we assume IO[bytes] for auto-detection
            actual_format = cast(DocumentFormat, registry.detect_format(resolved_payload))  # type: ignore[arg-type]
        else:
            raise ValueError(
                "Cannot auto-detect format from text-mode stream. Please specify source_format explicitly."
            )

    # Get converter metadata (returns a list, we just check if it exists)
    metadata_list = registry.get_format_info(actual_format)
    if not metadata_list or len(metadata_list) == 0:
        raise FormatError(f"Unknown format: {actual_format}")

    # Prepare parser options
    final_parser_options: BaseParserOptions | None
    if kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**kwargs)
    elif kwargs:
        opts = _create_parser_options_from_kwargs(actual_format, **kwargs)
        if opts is None:
            raise FormatError(f"Could not create parser options for format: {actual_format}")
        final_parser_options = opts
    elif parser_options:
        final_parser_options = parser_options
    else:
        # No options provided - use None (parser will use defaults)
        final_parser_options = None

    # Use the parser class system to convert to AST
    try:
        parser_class = registry.get_parser(actual_format)
        parser = parser_class(options=final_parser_options, progress_callback=progress_callback)
        ast_doc = parser.parse(resolved_payload)
        return ast_doc

    except All2MdError:
        raise
    except Exception as e:
        raise ParsingError(f"AST conversion failed: {e!r}", parsing_stage="ast_conversion", original_error=e) from e


def from_ast(
    ast_doc: Document,
    target_format: DocumentFormat,
    output: Union[str, Path, IO[bytes], IO[str], None] = None,
    *,
    renderer_options: Optional[BaseRendererOptions] = None,
    transforms: Optional[list] = None,
    hooks: Optional[dict] = None,
    progress_callback: Optional[ProgressCallback] = None,
    **kwargs: Any,
) -> Union[None, str, bytes]:
    """Render AST document to a target format.

    Parameters
    ----------
    ast_doc : Document
        AST Document node to render
    target_format : DocumentFormat
        Target format name (e.g., "markdown", "docx", "pdf")
    output : str, Path, IO[bytes], IO[str], or None, optional
        Output destination. If None, returns rendered content directly.
        Can be:
        - None: Returns str (for text formats) or bytes (for binary formats)
        - str or Path: Writes content to file at that path
        - IO[bytes]: Writes content to binary file-like object
        - IO[str]: Writes content to text file-like object
    renderer_options : BaseRendererOptions, optional
        Renderer options for the target format
    transforms : list, optional
        AST transforms to apply before rendering
    hooks : dict, optional
        Transform hooks to execute during processing
    progress_callback : ProgressCallback, optional
        Optional callback function for progress updates. Receives ProgressEvent
        objects with event_type, message, current/total counts, and metadata.
        See all2md.progress for details.
    kwargs : Any
        Additional renderer options that override renderer_options

    Returns
    -------
    None, str, or bytes
        - None if output was specified (content written to output)
        - str if output=None and format is text-based (markdown, html, rst, etc.)
        - bytes if output=None and format is binary (docx, pdf, epub, etc.)

    Notes
    -----
    If you need a file-like object instead of direct content, pass a StringIO
    or BytesIO instance to the `output` parameter:

        >>> from io import StringIO, BytesIO
        >>> buffer = StringIO()
        >>> from_ast(doc, "markdown", output=buffer)  # Returns None, buffer populated
        >>> markdown_text = buffer.getvalue()

    Examples
    --------
    Render AST to string (text formats):
        >>> ast_doc = to_ast("document.pdf")
        >>> markdown_text = from_ast(ast_doc, "markdown")
        >>> isinstance(markdown_text, str)
        True

    Render AST to bytes (binary formats):
        >>> pdf_bytes = from_ast(ast_doc, "pdf")
        >>> isinstance(pdf_bytes, bytes)
        True

    Render AST to file:
        >>> from_ast(ast_doc, "markdown", output="output.md")

    With renderer options:
        >>> md_opts = MarkdownRendererOptions(flavor="commonmark")
        >>> markdown_text = from_ast(ast_doc, "markdown", renderer_options=md_opts)

    """
    # Prepare renderer options
    final_renderer_options: Optional[BaseRendererOptions]
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
        options=final_renderer_options,
        progress_callback=progress_callback,
    )

    result = write_content(content, output)

    # Auto-unwrap file-like objects for better UX
    if result is not None:
        return result.getvalue()  # Extract str/bytes from StringIO/BytesIO
    return None


def from_markdown(
    source: Union[str, Path, IO[bytes], IO[str]],
    target_format: DocumentFormat,
    output: Union[str, Path, IO[bytes], IO[str], None] = None,
    *,
    parser_options: Optional[MarkdownParserOptions] = None,
    renderer_options: Optional[BaseRendererOptions] = None,
    transforms: Optional[list] = None,
    hooks: Optional[dict] = None,
    progress_callback: Optional[ProgressCallback] = None,
    **kwargs: Any,
) -> Union[None, str, bytes]:
    r"""Convert Markdown content to another format.

    Parameters
    ----------
    source : str, Path, IO[bytes], or IO[str]
        Markdown source content as string, file path, or file-like object
    target_format : DocumentFormat
        Target format name (e.g., "docx", "pdf", "html")
    output : str, Path, IO[bytes], IO[str], or None, optional
        Output destination. If None, returns rendered content.
        Can be:
        - None: Returns str (for text formats) or bytes (for binary formats)
        - str or Path: Writes content to file at that path
        - IO[bytes]: Writes content to binary file-like object
        - IO[str]: Writes content to text file-like object
    parser_options : MarkdownParserOptions, optional
        Options for parsing Markdown
    renderer_options : BaseRendererOptions, optional
        Options for rendering to target format
    transforms : list, optional
        AST transforms to apply
    hooks : dict, optional
        Transform hooks to execute
    progress_callback : ProgressCallback, optional
        Optional callback function for progress updates. Receives ProgressEvent
        objects with event_type, message, current/total counts, and metadata.
        See all2md.progress for details.
    kwargs : Any
        Additional options split between parser and renderer

    Returns
    -------
    None, str, or bytes
        - None if output was specified (content written to output)
        - str if output=None and format is text-based (html, rst, etc.)
        - bytes if output=None and format is binary (docx, pdf, epub, etc.)

    Notes
    -----
    If you need a file-like object instead of direct content, pass a StringIO
    or BytesIO instance to the `output` parameter:

        >>> from io import StringIO, BytesIO
        >>> buffer = StringIO()
        >>> from_markdown("# Title", "html", output=buffer)  # Returns None
        >>> html_text = buffer.getvalue()

    Examples
    --------
    Convert markdown string to HTML:
        >>> html_text = from_markdown("# Title\\n\\nContent", "html")
        >>> isinstance(html_text, str)
        True

    Convert markdown to binary format:
        >>> pdf_bytes = from_markdown("# Title", "pdf")
        >>> isinstance(pdf_bytes, bytes)
        True

    Convert markdown file to DOCX file:
        >>> from_markdown("input.md", "docx", output="output.docx")

    With options:
        >>> html_content = from_markdown("input.md", "html",
        ...     parser_options=MarkdownParserOptions(flavor="gfm"),
        ...     renderer_options=HtmlOptions(...))

    """
    return convert(
        source,
        output=output,
        parser_options=parser_options,
        renderer_options=renderer_options,
        source_format="markdown",
        target_format=target_format,
        transforms=transforms,
        hooks=hooks,
        progress_callback=progress_callback,
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
    progress_callback: Optional[ProgressCallback] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
    **kwargs: Any,
) -> Union[None, str, bytes]:
    """Convert between document formats.

    Parameters
    ----------
    source : str, Path, IO[bytes], IO[str], or bytes
        Source document (file path, file-like object, or content)
    output : str, Path, IO[bytes], IO[str], or None, optional
        Output destination. If None, returns rendered content.
        Can be:
        - None: Returns str (for text formats) or bytes (for binary formats)
        - str or Path: Writes content to file at that path
        - IO[bytes]: Writes content to binary file-like object
        - IO[str]: Writes content to text file-like object
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
    progress_callback : ProgressCallback, optional
        Optional callback function for progress updates. Receives ProgressEvent
        objects with event_type, message, current/total counts, and metadata.
        See all2md.progress for details.
    remote_input_options : RemoteInputOptions, optional
        Controls remote retrieval behaviour for the source input. Defaults to None
        (remote fetching disabled).
    kwargs : Any
        Additional options split between parser and renderer

    Returns
    -------
    None, str, or bytes
        - None if output was specified (content written to output)
        - str if output=None and format is text-based (markdown, html, rst, etc.)
        - bytes if output=None and format is binary (docx, pdf, epub, etc.)

    Notes
    -----
    If you need a file-like object instead of direct content, pass a StringIO
    or BytesIO instance to the `output` parameter:

        >>> from io import StringIO, BytesIO
        >>> buffer = StringIO()
        >>> convert("doc.pdf", output=buffer, target_format="markdown")  # Returns None
        >>> markdown_text = buffer.getvalue()

    Examples
    --------
    Convert PDF to markdown:
        >>> markdown_text = convert("doc.pdf", target_format="markdown")
        >>> isinstance(markdown_text, str)
        True

    Convert to binary format:
        >>> pdf_bytes = convert("input.md", target_format="pdf")
        >>> isinstance(pdf_bytes, bytes)
        True

    Convert with output file:
        >>> convert("doc.pdf", "output.md",
        ...     parser_options=PdfOptions(pages=[0, 1]),
        ...     renderer_options=MarkdownRendererOptions(flavor="commonmark"))

    Bidirectional with transforms:
        >>> convert("input.docx", "output.md",
        ...     transforms=["remove-images", "heading-offset"])

    """
    transforms = transforms or []
    hooks = hooks or {}

    resolved_source = _resolve_document_source(source, remote_input_options, progress_callback)
    resolved_payload = resolved_source.payload

    # Detect source format
    # Type narrow to exclude IO[str] for detect_format
    actual_source_format: str
    if source_format != "auto":
        actual_source_format = source_format
    else:
        # Accept: str, Path, bytes, BytesIO, NamedBytesIO, or any binary stream
        if isinstance(resolved_payload, (str, Path, bytes)):
            actual_source_format = registry.detect_format(resolved_payload)
        elif hasattr(resolved_payload, "read") and hasattr(resolved_payload, "seek"):
            # Binary stream (has read+seek) - let registry.detect_format handle it
            # This includes BytesIO, NamedBytesIO, and file objects
            # Type ignore: resolved_payload could be IO[str] but we assume IO[bytes] for auto-detection
            actual_source_format = registry.detect_format(resolved_payload)  # type: ignore[arg-type]
        else:
            raise ValueError(
                "Cannot auto-detect format from text-mode stream. Please specify source_format explicitly."
            )

    # Determine target format
    actual_target_format: str
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
        cast(DocumentFormat, actual_source_format),
        cast(DocumentFormat, actual_target_format),
        kwargs,
    )

    # Parse to AST
    final_parser_options: Optional[BaseParserOptions]
    if parser_kwargs and parser_options:
        final_parser_options = parser_options.create_updated(**parser_kwargs)
    elif parser_kwargs:
        final_parser_options = _create_parser_options_from_kwargs(
            cast(DocumentFormat, actual_source_format), **parser_kwargs
        )
    else:
        final_parser_options = parser_options

    ast_document = to_ast(
        cast(Union[str, Path, IO[bytes], bytes], resolved_payload),
        parser_options=final_parser_options,
        source_format=cast(DocumentFormat, actual_source_format),
        progress_callback=progress_callback,
        remote_input_options=remote_input_options,
    )

    # Prepare renderer options
    if flavor:
        renderer_kwargs["flavor"] = flavor

    final_renderer_options: Optional[BaseRendererOptions]
    if renderer_kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
    elif renderer_kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs(
            cast(DocumentFormat, actual_target_format), **renderer_kwargs
        )
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
        progress_callback=progress_callback,
    )

    # Handle output using centralized I/O utility
    result = write_content(rendered, output)

    # Auto-unwrap file-like objects for better UX
    if result is not None:
        return result.getvalue()  # Extract str/bytes from StringIO/BytesIO
    return None
