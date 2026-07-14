"""The major exported API functions for document conversion."""

#  Copyright (c) 2025 Tom Villani, Ph.D.
# src/all2md/api.py
import logging
import warnings
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, Optional, TypeVar, Union, cast, get_type_hints

from all2md.ast.nodes import Document
from all2md.constants import DocumentFormat
from all2md.conversion_cache import get_active_cache, make_cache_key
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, FormatError, ParsingError, ValidationError
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

if TYPE_CHECKING:
    from all2md.chunking import ProvenanceChunk
    from all2md.confidence import ConfidenceReport
    from all2md.optimize import OptimizationReport
    from all2md.roundtrip import RoundTripReport

logger = logging.getLogger(__name__)


def _transforms() -> Any:
    """Lazily import the transforms package.

    The transforms package (pipeline + all built-in transforms) is only needed
    when actually rendering, not at import time. Deferring it keeps ``import
    all2md`` fast for callers that never render. ``sys.modules`` caches the
    module, so repeated calls are cheap.
    """
    import all2md.transforms as transforms_module

    return transforms_module


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
        warnings.warn(
            f"Unrecognized keyword arguments were ignored: {unmatched}. "
            "Check the API documentation for valid parameter names.",
            UserWarning,
            stacklevel=4,
        )

    return parser_kwargs, renderer_kwargs


def to_markdown(
    source: Union[str, Path, IO[bytes], bytes, Document],
    *,
    parser_options: Optional[BaseParserOptions] = None,
    renderer_options: Optional[MarkdownRendererOptions] = None,
    options: Optional[BaseParserOptions] = None,
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
    options : BaseParserOptions, optional
        .. deprecated::
            Use ``parser_options`` instead.

        Deprecated alias for ``parser_options``. Cannot be used together
        with ``parser_options``.
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
    # Handle deprecated 'options' alias for 'parser_options'
    if options is not None:
        if parser_options is not None:
            raise TypeError("Cannot specify both 'options' and 'parser_options'")
        warnings.warn(
            "The 'options' parameter is deprecated. Use 'parser_options' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        parser_options = options

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
            render_result = _transforms().render(
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
        render_result = _transforms().render(
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

    # Consult the opt-in conversion cache before the expensive parse. Only local
    # file sources are cacheable (a stable path + stat signature); streams, bytes,
    # and remote URLs fall through to a normal parse. The loader already validated
    # and resolved local paths to a ``Path`` payload (LocalPathRetriever is the
    # only retriever that yields one), so we key off that rather than re-statting
    # the caller-supplied ``source`` directly.
    cache = get_active_cache()
    cache_key: str | None = None
    if cache is not None and isinstance(resolved_payload, Path):
        cache_key = make_cache_key(
            str(resolved_payload), source_format=actual_format, options_repr=repr(final_parser_options)
        )
        cached_doc = cache.get(cache_key)
        if cached_doc is not None:
            _record_source_path(cached_doc, source)
            return cached_doc

    # Use the parser class system to convert to AST
    try:
        parser_class = registry.get_parser(actual_format)
        parser = parser_class(options=final_parser_options, progress_callback=progress_callback)
        ast_doc = parser.parse(resolved_payload)
        # Attach the conversion confidence report ("quality card") assembled from
        # the sanity signals and degraded-content incidents the parser collected
        # during parse(). Stashed here (rather than inside each parser's parse())
        # so every format gets it uniformly and it lands before the cache put.
        _attach_confidence_report(ast_doc, parser)
        # Auto-stash the originating file path on the document so callers
        # (including LLM-driven edit workflows) can round-trip back to the
        # same format using preserve_formatting=True without manually
        # threading the path through. Skipped for streams and bytes.
        _record_source_path(ast_doc, source)
        if cache is not None and cache_key is not None:
            cache.put(cache_key, ast_doc)
        return ast_doc

    except All2MdError:
        raise
    except Exception as e:
        raise ParsingError(f"AST conversion failed: {e!r}", parsing_stage="ast_conversion", original_error=e) from e


def _derive_chunk_identity(source: Any, ast_doc: "Document", document_id: Optional[str]) -> tuple[str, Optional[str]]:
    """Derive ``(document_id, document_path)`` for chunking from the source.

    Reuses the ``source_path`` ``to_ast`` stashes for file inputs; falls back to a
    generic id (or the caller-supplied ``document_id``) for streams/bytes.
    """
    source_path = ast_doc.metadata.get("source_path") if ast_doc.metadata else None
    if source_path:
        path = Path(source_path)
        return document_id or path.stem, path.as_posix()
    return document_id or "document", None


def chunk(
    source: Union[str, Path, IO[bytes], bytes],
    *,
    strategy: str = "semantic",
    max_tokens: int = 512,
    overlap: int = 0,
    min_tokens: int = 0,
    include_preamble: bool = True,
    heading_merge: bool = True,
    max_heading_level: Optional[int] = None,
    avoid_table_split: bool = False,
    avoid_code_split: bool = False,
    elide_data_uris: bool = True,
    drop_elements: Optional[list[str]] = None,
    token_counter: str = "auto",
    document_id: Optional[str] = None,
    source_format: DocumentFormat = "auto",
    **converter_options: Any,
) -> "list[ProvenanceChunk]":
    """Convert a document and split it into provenance-carrying chunks in one call.

    The one-call equivalent of ``to_ast`` + ``all2md.chunking.chunk_ast``: convert
    ``source`` (a path, bytes, or file-like object) to an AST, optionally strip node
    types, and return chunks each carrying its section heading/level and — where the
    source format records it — the originating page span. Ideal for RAG / LLM
    pipelines.

    Parameters
    ----------
    source : str, Path, IO[bytes], or bytes
        Document to chunk (any supported format).
    strategy : str
        Chunking strategy; see ``all2md.chunking.STRATEGIES`` (``semantic`` default).
    max_tokens, overlap, min_tokens : int
        Size controls — token budget per chunk, window overlap, and a floor below
        which chunks are dropped.
    include_preamble, heading_merge : bool
        Structure toggles (emit pre-heading content; prepend each heading to its
        section's chunks).
    max_heading_level : int, optional
        For fine strategies, only descend into sections at or above this level.
    avoid_table_split, avoid_code_split : bool
        Keep tables / fenced code blocks whole (one atomic chunk each).
    elide_data_uris : bool
        Replace long base64 ``data:`` URIs with a short placeholder (default True).
    drop_elements : list of str, optional
        AST node types to strip before chunking (e.g. ``["image", "table"]``).
    token_counter : {"auto", "tiktoken", "whitespace"}
        Token-counting backend.
    document_id : str, optional
        Identifier woven into chunk ids; defaults to the file stem (or ``"document"``).
    source_format : DocumentFormat, default "auto"
        Explicit source format, or auto-detect.
    converter_options : Any
        Extra options forwarded to :func:`to_ast` (e.g. ``attachment_mode="skip"``,
        ``pages=[1, 2]``).

    Returns
    -------
    list of ProvenanceChunk
        Chunks in reading order, with ``prev``/``next`` ids linked. Call
        ``chunk.to_dict()`` for a JSON-serializable record.

    Examples
    --------
    >>> import all2md
    >>> chunks = all2md.chunk("report.pdf", strategy="semantic", max_tokens=512, overlap=64)
    >>> chunks[0].section_heading, chunks[0].page, chunks[0].token_count  # doctest: +SKIP

    """
    from all2md.chunking import chunk_ast

    doc = to_ast(source, source_format=source_format, **converter_options)

    if drop_elements:
        from all2md.transforms.builtin import RemoveNodesTransform

        doc = cast("Document", RemoveNodesTransform(node_types=list(drop_elements)).transform(doc))

    doc_id, doc_path = _derive_chunk_identity(source, doc, document_id)

    return chunk_ast(
        doc,
        strategy=strategy,
        max_tokens=max_tokens,
        overlap=overlap,
        min_tokens=min_tokens,
        include_preamble=include_preamble,
        heading_merge=heading_merge,
        max_heading_level=max_heading_level,
        avoid_table_split=avoid_table_split,
        avoid_code_split=avoid_code_split,
        elide_data_uris=elide_data_uris,
        token_counter=token_counter,
        document_id=doc_id,
        document_path=doc_path,
    )


def _attach_confidence_report(ast_doc: "Document", parser: Any) -> None:
    """Stash the parser's conversion confidence report on the AST.

    Populates ``ast_doc.metadata['confidence']`` with the JSON-safe quality card
    (score, band, signals, degraded events) assembled from what the parser
    observed during ``parse``. Best-effort: a failure here must never break an
    otherwise-successful conversion, so any error is swallowed with a debug log.
    """
    builder = getattr(parser, "build_confidence_report", None)
    if builder is None:
        return
    try:
        ast_doc.metadata["confidence"] = builder(ast_doc)
    except Exception as exc:  # noqa: BLE001 - reporting is auxiliary; never fail the parse
        logger.debug("Confidence report assembly failed: %r", exc)


def confidence_report(
    source: Union[str, Path, IO[bytes], bytes, Document],
    *,
    parser_options: Optional[BaseParserOptions] = None,
    source_format: DocumentFormat = "auto",
    progress_callback: Optional[ProgressCallback] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
    **kwargs: Any,
) -> "ConfidenceReport":
    """Convert a document and return its conversion confidence report ("quality card").

    A reference-free read on how much to trust a conversion, built from the
    sanity signals converters already compute (meaningful-text density, OCR
    reliance, rejected tables, dropped images) plus discrete degraded-content
    incidents. The single ``0-100`` ``score`` doubles as an optimizer fitness
    function.

    Parameters
    ----------
    source : str, Path, IO[bytes], bytes, or Document
        Document to inspect. A pre-parsed ``Document`` is read directly (its
        report was attached when it was first parsed via :func:`to_ast`).
    parser_options : BaseParserOptions, optional
        Pre-configured parser options.
    source_format : DocumentFormat, default "auto"
        Explicit source format, or auto-detect.
    progress_callback : ProgressCallback, optional
        Optional progress callback forwarded to parsing.
    remote_input_options : RemoteInputOptions, optional
        Controls remote retrieval behaviour. Defaults to None (disabled).
    kwargs : Any
        Individual parser options forwarded to :func:`to_ast`.

    Returns
    -------
    ConfidenceReport
        The scored quality card. Formats that produce no signals and record no
        degraded events yield a perfect ``score`` of 100 (band ``"high"``).

    Examples
    --------
        >>> from all2md import confidence_report
        >>> report = confidence_report("scan.pdf")
        >>> report.score, report.band  # doctest: +SKIP
        (72, 'medium')

    """
    from all2md.confidence import ConfidenceReport

    if isinstance(source, Document):
        ast_doc = source
    else:
        ast_doc = to_ast(
            source,
            parser_options=parser_options,
            source_format=source_format,
            progress_callback=progress_callback,
            remote_input_options=remote_input_options,
            **kwargs,
        )
    raw = ast_doc.metadata.get("confidence") if ast_doc.metadata else None
    if isinstance(raw, dict):
        return ConfidenceReport.from_dict(raw)
    # No report attached (e.g. a hand-built Document): report a clean card.
    return ConfidenceReport(score=100, band="high", producer="", signals={}, degraded_events=[])


def roundtrippable_formats() -> list[str]:
    """Return the formats that can be both rendered to and parsed back from.

    These are the formats accepted by :func:`roundtrip_report`'s ``via``
    parameter: a round trip needs a renderer to get there and a parser to get
    back.
    """
    formats = []
    for name in registry.list_formats():
        entries = registry.get_format_info(name) or []
        if any(entry.parser_class and entry.renderer_class for entry in entries):
            formats.append(name)
    return sorted(formats)


def roundtrip_report(
    source: Union[str, Path, IO[bytes], bytes, Document],
    *,
    via: DocumentFormat = "markdown",
    source_format: DocumentFormat = "auto",
    parser_options: Optional[BaseParserOptions] = None,
    renderer_options: Optional[BaseRendererOptions] = None,
    progress_callback: Optional[ProgressCallback] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
    **kwargs: Any,
) -> "RoundTripReport":
    """Round-trip a document through ``via`` and score what survived.

    Renders the parsed document to the ``via`` format, parses the result straight
    back, and compares the two ASTs structurally. Unlike
    :func:`confidence_report`, this has a ground truth to measure against -- the
    source AST -- so a clean document round-tripping through a lossless format
    scores exactly ``100`` and any drift is a real defect.

    Parameters
    ----------
    source : str, Path, IO[bytes], bytes, or Document
        Document to round-trip. A pre-parsed ``Document`` is used directly as the
        ground truth, in which case ``source_format`` is only a label.
    via : DocumentFormat, default "markdown"
        Intermediate format to round-trip through. Must have both a renderer and
        a parser -- see :func:`roundtrippable_formats`.
    source_format : DocumentFormat, default "auto"
        Explicit source format, or auto-detect.
    parser_options : BaseParserOptions, optional
        Options for parsing the source. The intermediate is always parsed with
        that format's defaults, since it is machine-generated.
    renderer_options : BaseRendererOptions, optional
        Options for rendering to ``via``.
    progress_callback : ProgressCallback, optional
        Optional progress callback forwarded to the initial parse.
    remote_input_options : RemoteInputOptions, optional
        Controls remote retrieval behaviour. Defaults to None (disabled).
    kwargs : Any
        Individual options, split between the source parser and the ``via`` renderer.

    Returns
    -------
    RoundTripReport
        The ``0-100`` fidelity score, per-dimension metrics, and the concrete
        structural differences found.

    Raises
    ------
    FormatError
        If ``via`` cannot be both rendered to and parsed back from.

    Examples
    --------
        >>> from all2md import roundtrip_report
        >>> report = roundtrip_report("report.docx")  # doctest: +SKIP
        >>> report.score, report.metrics["structure"]  # doctest: +SKIP
        (94, 91)

    Check what a conversion to reStructuredText would cost:
        >>> report = roundtrip_report("notes.md", via="rst")  # doctest: +SKIP

    """
    from all2md.roundtrip import build_report

    if via not in roundtrippable_formats():
        raise FormatError(
            f"Cannot round-trip through {via!r}: it needs both a renderer and a parser. "
            f"Available: {', '.join(roundtrippable_formats())}"
        )

    if isinstance(source, Document):
        original = source
        actual_source_format: str = source_format if source_format != "auto" else "ast"
    else:
        resolved_payload = _resolve_document_source(source, remote_input_options, progress_callback).payload
        if source_format != "auto":
            actual_source_format = source_format
        elif isinstance(resolved_payload, (str, Path, bytes)) or (
            hasattr(resolved_payload, "read") and hasattr(resolved_payload, "seek")
        ):
            actual_source_format = registry.detect_format(resolved_payload)  # type: ignore[arg-type]
        else:
            raise FormatError("Cannot auto-detect format from text-mode stream. Please specify source_format.")

        parser_kwargs, _ = _split_kwargs_for_parser_and_renderer(
            cast(DocumentFormat, actual_source_format), via, dict(kwargs)
        )
        original = to_ast(
            cast(Union[str, Path, IO[bytes], bytes], resolved_payload),
            parser_options=parser_options,
            source_format=cast(DocumentFormat, actual_source_format),
            progress_callback=progress_callback,
            **parser_kwargs,
        )

    _, renderer_kwargs = _split_kwargs_for_parser_and_renderer(
        cast(DocumentFormat, actual_source_format), via, dict(kwargs)
    )
    final_renderer_options: Optional[BaseRendererOptions]
    if renderer_kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**renderer_kwargs)
    elif renderer_kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs(via, **renderer_kwargs)
    else:
        final_renderer_options = renderer_options

    rendered = _transforms().render(original, renderer=via, options=final_renderer_options)
    payload = rendered.encode("utf-8") if isinstance(rendered, str) else rendered

    # The intermediate is machine-generated, so it is parsed with plain defaults:
    # reusing the source's parser options would be a category error (they belong
    # to a different format) and would let a parsing quirk mask a rendering loss.
    roundtripped = to_ast(payload, source_format=via)

    return build_report(original, roundtripped, source_format=actual_source_format, via=via)


def optimizable_formats() -> list[str]:
    """Return the formats :func:`optimize_options` knows how to tune."""
    from all2md.optimize import KNOBS

    return sorted(KNOBS)


def optimize_options(
    source: Union[str, Path, IO[bytes], bytes],
    *,
    source_format: DocumentFormat = "auto",
    parser_options: Optional[BaseParserOptions] = None,
    rounds: int = 1,
    include_presets: bool = True,
    sample_pages: Optional[int] = None,
    remote_input_options: Optional[RemoteInputOptions] = None,
) -> "OptimizationReport":
    """Search converter options for the settings that convert ``source`` best.

    Converts the document many times under different settings and ranks them by a
    reference-free fidelity objective (see :mod:`all2md.optimize`), so this works on
    the documents that need it most: the ones with no known-good output to compare
    against. Returns the winning options as a diff from the defaults, ready to drop
    into an ``.all2md.toml``.

    This is *not* cheap — it is tens of conversions. Use ``sample_pages`` to tune on
    a slice of a long document, and enable the conversion cache
    (:func:`all2md.conversion_cache.use_conversion_cache`) to skip re-converting
    option sets already tried.

    Parameters
    ----------
    source : str or Path or file-like or bytes
        The document to tune against.
    source_format : str, default "auto"
        Override format detection.
    parser_options : BaseParserOptions, optional
        Starting point for the search. Options outside the searched knobs are held
        fixed at whatever this specifies, so it doubles as a way to pin settings the
        optimizer must not touch.
    rounds : int, default 1
        Coordinate-descent passes over the knobs. More rounds can recover knobs that
        only pay off in combination, at proportionally more conversions.
    include_presets : bool, default True
        Score the named presets (``quality``, ``complete``, ...) before refining.
    sample_pages : int, optional
        Tune against only the first N pages, so a 400-page document does not have to
        be reconverted in full for every candidate. Paginated formats only. Use at
        least 2 (ideally 3+): running headers and footers are recognized by the fact
        that they *repeat*, so a single-page sample cannot see them at all.
    remote_input_options : RemoteInputOptions, optional
        Controls retrieval when ``source`` is a URL.

    Returns
    -------
    OptimizationReport
        The winning options, the fitness they scored, what the defaults scored, and
        every candidate evaluated.

    Raises
    ------
    FormatError
        If the detected format has no tunable knobs.

    Examples
    --------
        >>> from all2md import optimize_options
        >>> report = optimize_options("scanned.pdf")  # doctest: +SKIP
        >>> report.best_options  # doctest: +SKIP
        {'table_detection_mode': 'ruling', 'detect_columns': True}

    """
    from all2md.cli.presets import PRESETS
    from all2md.optimize import DocumentMetrics, extract_metrics, search, tunable_knobs

    resolved = _resolve_document_source(source, remote_input_options, None).payload

    # The search parses the same source dozens of times, so a stream -- which can
    # only be read once -- has to be materialized up front.
    if hasattr(resolved, "read"):
        resolved = resolved.read()

    if source_format != "auto":
        actual_format: str = source_format
    elif isinstance(resolved, (str, Path, bytes)):
        actual_format = registry.detect_format(resolved)
    else:
        raise FormatError("Cannot auto-detect format from this source. Please specify source_format.")

    knobs = tunable_knobs(actual_format)
    if not knobs:
        raise FormatError(
            f"No tunable options for format {actual_format!r}. "
            f"Optimizable formats: {', '.join(optimizable_formats())}"
        )

    options_class = _get_parser_options_class_for_format(cast(DocumentFormat, actual_format))
    if options_class is None:
        raise FormatError(f"No parser options class for format {actual_format!r}")

    base = parser_options if parser_options is not None else options_class()
    if sample_pages is not None:
        if not hasattr(base, "pages"):
            raise FormatError(f"Format {actual_format!r} is not paginated; sample_pages does not apply.")
        if sample_pages < 1:
            raise ValidationError("sample_pages must be >= 1", parameter_name="sample_pages")
        if sample_pages < 2:
            # Running headers and footers are identified by the fact that they
            # *repeat*. One page has nothing to repeat against, so the furniture
            # dimension goes blind and header/footer trimming looks free.
            logger.warning(
                "sample_pages=1 leaves no repetition signal, so running headers and footers "
                "cannot be detected. Sample at least 2 pages (3+ is better)."
            )
        # A 1-based list, not the "1-N" string form: string page ranges are
        # double-converted to 0-based and come back off by one (see #75).
        base = base.create_updated(pages=list(range(1, sample_pages + 1)))

    def evaluate(overrides: dict[str, Any]) -> DocumentMetrics:
        candidate_options = base.create_updated(**overrides) if overrides else base
        document = to_ast(
            cast(Union[str, Path, IO[bytes], bytes], resolved),
            parser_options=candidate_options,
            source_format=cast(DocumentFormat, actual_format),
        )
        return extract_metrics(document)

    presets: dict[str, dict[str, Any]] = {}
    if include_presets:
        for name, preset in PRESETS.items():
            # Presets are nested by format; only this format's section is relevant.
            section = preset.get("config", {}).get(actual_format, {})
            if section:
                presets[name] = section

    report = search(knobs, evaluate, presets=presets, rounds=rounds)
    report.source_format = actual_format

    # Coordinate descent accumulates whatever it walked through, so the winner can
    # carry knobs it set to the value they already had. Those are no-ops: drop them
    # so "recommended settings" means settings you actually have to change.
    report.best_options = {
        name: value for name, value in report.best_options.items() if getattr(base, name, object()) != value
    }
    return report


def _record_source_path(ast_doc: "Document", source: Any) -> None:
    """Stash the absolute path of a file-based source onto the AST.

    Populates ``ast_doc.metadata['source_path']`` only when the caller
    handed in a ``str`` or ``Path`` that resolves to an existing file.
    Streams, bytes, and content-strings (which look path-like but don't
    exist on disk) are left alone.
    """
    if not isinstance(source, (str, Path)):
        return
    try:
        candidate = Path(source)
    except (TypeError, ValueError):
        return
    try:
        if candidate.is_file():
            ast_doc.metadata["source_path"] = str(candidate.resolve())
    except OSError:
        # Path may be too long, contain illegal chars, or be unreachable;
        # treat it the same as a non-file input and skip.
        return


def _maybe_apply_preserve_formatting(
    preserve_formatting: bool,
    ast_doc: "Document",
    target_format: str,
    renderer_options: Optional[BaseRendererOptions],
    kwargs: dict,
) -> None:
    """When enabled, route a template-based round-trip through render kwargs.

    Sets ``template_path`` to the AST's stashed source path and
    ``clear_template_body=True`` so the AST replaces the template's body
    while inheriting page setup, theme, headers/footers, and style
    definitions. No-ops if the target isn't docx, the AST has no
    ``source_path``, or the caller already specified a ``template_path``
    via ``renderer_options`` or kwargs.
    """
    if not preserve_formatting or target_format != "docx":
        return
    source_path = ast_doc.metadata.get("source_path") if ast_doc.metadata else None
    if not source_path:
        return
    if "template_path" in kwargs:
        return
    if renderer_options is not None and getattr(renderer_options, "template_path", None):
        return
    kwargs["template_path"] = source_path
    kwargs.setdefault("clear_template_body", True)


def from_ast(
    ast_doc: Document,
    target_format: DocumentFormat,
    output: Union[str, Path, IO[bytes], IO[str], None] = None,
    *,
    renderer_options: Optional[BaseRendererOptions] = None,
    transforms: Optional[list] = None,
    hooks: Optional[dict] = None,
    progress_callback: Optional[ProgressCallback] = None,
    preserve_formatting: bool = False,
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
    preserve_formatting : bool, default False
        When True and ``target_format`` is ``"docx"``, use the AST's stashed
        ``source_path`` (populated by ``to_ast`` for file-based inputs) as the
        rendering template and clear its body before rendering. This preserves
        page setup, theme, headers/footers, and custom style definitions from
        the original document on a docx round-trip. Ignored if no source path
        is stashed or the caller already specified a ``template_path``.
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
    # Inject template_path / clear_template_body when preserve_formatting=True
    _maybe_apply_preserve_formatting(preserve_formatting, ast_doc, target_format, renderer_options, kwargs)

    # Prepare renderer options
    final_renderer_options: Optional[BaseRendererOptions]
    if kwargs and renderer_options:
        final_renderer_options = renderer_options.create_updated(**kwargs)
    elif kwargs:
        final_renderer_options = _create_renderer_options_from_kwargs(target_format, **kwargs)
    else:
        final_renderer_options = renderer_options

    # Use transform pipeline to render
    content = _transforms().render(
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
    preserve_formatting: bool = False,
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
    preserve_formatting : bool, default False
        When True and ``target_format`` is ``"docx"``, use the AST's stashed
        ``source_path`` as a rendering template and clear its body. Only useful
        when the markdown source was originally derived from a docx file whose
        path is still available; in that case pass ``template_path`` explicitly
        instead. See ``from_ast`` for details.
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
        preserve_formatting=preserve_formatting,
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
    preserve_formatting: bool = False,
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
    preserve_formatting : bool, default False
        When True and the target is ``"docx"`` and the source is a docx file,
        the rendered output uses the source as its template and the source's
        body is cleared before rendering. This makes a docx round-trip
        (e.g. ``convert("in.docx", "out.docx")``) preserve page setup, theme,
        headers/footers, and custom paragraph styles instead of regenerating
        a generic-looking document.
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

    # Inject template_path / clear_template_body when preserve_formatting=True
    _maybe_apply_preserve_formatting(
        preserve_formatting,
        ast_document,
        actual_target_format,
        renderer_options,
        renderer_kwargs,
    )

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

    rendered = _transforms().render(
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
