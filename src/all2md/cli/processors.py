"""Specialized processing functions for all2md CLI.

This module contains focused processing functions extracted from the main()
function to improve maintainability and testability.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import json
import logging
import mimetypes
import os
import platform
import pydoc
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

from all2md.api import convert, from_ast, to_ast, to_markdown
from all2md.ast.nodes import Document, Heading, Node, Text, ThematicBreak
from all2md.ast.nodes import Document as ASTDocument
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_SUCCESS,
    DynamicCLIBuilder,
    get_exit_code_for_exception,
)
from all2md.cli.config import load_config_with_priority
from all2md.cli.input_items import CLIInputItem
from all2md.cli.output import should_use_rich_output
from all2md.cli.packaging import create_package_from_conversions
from all2md.cli.presets import apply_preset
from all2md.cli.progress import ProgressContext, SummaryRenderer, create_progress_context_callback
from all2md.constants import DocumentFormat
from all2md.converter_registry import check_package_installed, registry
from all2md.exceptions import All2MdError, DependencyError
from all2md.transforms import AddHeadingIdsTransform, GenerateTocTransform
from all2md.transforms import transform_registry as transform_registry
from all2md.utils.input_sources import RemoteInputOptions
from all2md.utils.packages import check_version_requirement

logger = logging.getLogger(__name__)


def extract_sections_from_document(doc: Document, extract_spec: str) -> Document:
    """Extract specific sections from a document based on extraction specification.

    This function is a thin wrapper around the extract_sections() utility from
    document_utils, maintained for backward compatibility.

    Parameters
    ----------
    doc : Document
        Source document to extract sections from
    extract_spec : str
        Extraction specification:
        - Name pattern: "Introduction", "Intro*", "*Results*" (uses fnmatch)
        - Single index: "#:1" (1-based)
        - Range: "#:1-3" (1-based, inclusive)
        - Multiple: "#:1,3,5" (1-based)
        - Open-ended: "#:3-" (from 3 to end)

    Returns
    -------
    Document
        New document containing only extracted sections, with ThematicBreak separators

    Raises
    ------
    ValueError
        If extraction spec is invalid or no matching sections found

    Examples
    --------
    >>> doc = Document(children=[...])
    >>> extracted = extract_sections_from_document(doc, "Introduction")
    >>> extracted = extract_sections_from_document(doc, "#:1-3")
    >>> extracted = extract_sections_from_document(doc, "Chapter*")

    """
    from all2md.ast.sections import extract_sections

    # Use the enhanced extract_sections utility
    return extract_sections(doc, extract_spec, case_sensitive=False, combine=True)


def generate_outline_from_document(doc: Document, max_level: int = 6) -> str:
    """Generate a markdown-formatted outline from document headings.

    Parameters
    ----------
    doc : Document
        Source document to extract outline from
    max_level : int
        Maximum heading level to include (1-6, default: 6)

    Returns
    -------
    str
        Markdown-formatted outline with nested list structure

    Examples
    --------
    >>> doc = Document(children=[...])
    >>> outline = generate_outline_from_document(doc, max_level=3)
    >>> print(outline)
    * Introduction
      * Background
        * Related Work
    * Methods
      * Data Collection

    """
    from all2md.ast.sections import get_all_sections

    # Get all sections from document
    sections = get_all_sections(doc, min_level=1, max_level=max_level)

    if not sections:
        return "No headings found in document"

    # Build markdown list with proper indentation
    lines = []
    for section in sections:
        # Calculate indentation: 2 spaces per level beyond first
        indent = "  " * (section.level - 1)

        # Get heading text
        heading_text = section.get_heading_text()

        # Format as markdown list item
        lines.append(f"{indent}* {heading_text}")

    return "\n".join(lines)


def _compute_base_input_dir(items: List[CLIInputItem], preserve_structure: bool) -> Optional[Path]:
    """Return the shared base directory for local inputs when preserving structure."""
    if not preserve_structure:
        return None

    local_dirs: List[str] = []
    for item in items:
        if not item.is_local_file():
            continue
        path = item.best_path()
        if not path:
            continue
        try:
            local_dirs.append(str(path.parent.resolve()))
        except OSError:
            local_dirs.append(str(path.parent))

    if not local_dirs:
        return None

    try:
        return Path(os.path.commonpath(local_dirs))
    except ValueError:
        return None


def _relative_parent(item: CLIInputItem, base_input_dir: Optional[Path]) -> Path:
    """Return the relative parent path for output generation."""
    if not base_input_dir or not item.is_local_file():
        return Path()

    path = item.best_path()
    if not path:
        return Path()

    try:
        return path.parent.resolve().relative_to(base_input_dir)
    except (ValueError, OSError):
        return Path()


def _generate_output_path_for_item(
    item: CLIInputItem,
    output_dir: Optional[Path],
    preserve_structure: bool,
    base_input_dir: Optional[Path],
    target_format: str,
    index: int,
    *,
    dry_run: bool = False,
) -> Optional[Path]:
    """Generate an output path for a CLI input item, handling remote sources."""
    if output_dir is None:
        return None

    extension = registry.get_default_extension_for_format(target_format)
    stem = item.derive_output_stem(index)
    relative_parent = _relative_parent(item, base_input_dir) if preserve_structure else Path()

    output_path = output_dir / relative_parent / f"{stem}{extension}"
    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


class TransformSpec(TypedDict):
    """Serializable specification for reconstructing a transform instance."""

    name: str
    params: Dict[str, Any]


def _final_option_segment(remainder: str) -> str:
    """Return the terminal segment of a dot-delimited option path."""
    return remainder.split(".")[-1]


def _filter_options_for_formats(
    options: Dict[str, Any],
    parser_format: str | None,
    renderer_format: str | None,
) -> Dict[str, Any]:
    """Project a namespaced options dict onto parser/renderer kwargs.

    Parameters
    ----------
    options : dict
        Fully-qualified options dictionary (e.g., {'pdf.pages': [1]})
    parser_format : str or None
        Detected parser format. When None, format-qualified options are applied as fallback.
    renderer_format : str or None
        Target renderer format. When None, format-qualified renderer options are applied as fallback.

    Returns
    -------
    dict
        Options dictionary suitable for passing to convert()/to_markdown().

    Notes
    -----
    When format is unknown (None), format-qualified options are still applied and will be
    used if applicable to the actual parser/renderer that handles the input. This commonly
    occurs with stdin input, collation rendering, or when format detection fails.

    """
    filtered: Dict[str, Any] = {}
    parser_fallback: Dict[str, Any] = {}
    renderer_fallback: Dict[str, Any] = {}

    for key, value in options.items():
        if "." not in key:
            filtered[key] = value
            continue

        prefix, remainder = key.split(".", 1)
        terminal = _final_option_segment(remainder)

        if parser_format and prefix == parser_format:
            filtered[terminal] = value
            continue

        if renderer_format and prefix == renderer_format:
            filtered[terminal] = value
            continue

        if not parser_format:
            parser_fallback[terminal] = value

        if not renderer_format:
            renderer_fallback[terminal] = value

    # Apply fallback options when format is unknown
    if not parser_format and parser_fallback:
        logger.debug(
            "Parser format unknown - applying %d format-qualified option(s) as fallback: %s",
            len(parser_fallback),
            ", ".join(parser_fallback.keys()),
        )
        for key, value in parser_fallback.items():
            if key not in filtered:
                filtered[key] = value

    if not renderer_format and renderer_fallback:
        logger.debug(
            "Renderer format unknown - applying %d format-qualified option(s) as fallback: %s",
            len(renderer_fallback),
            ", ".join(renderer_fallback.keys()),
        )
        for key, value in renderer_fallback.items():
            if key not in filtered:
                filtered[key] = value

    return filtered


def _extract_remote_input_options(options: Dict[str, Any]) -> tuple[RemoteInputOptions | None, Dict[str, Any]]:
    """Split remote input configuration from the general options dict."""
    remote_prefix = "remote_input."
    remote_kwargs: Dict[str, Any] = {}
    remaining: Dict[str, Any] = {}

    for key, value in options.items():
        if key.startswith(remote_prefix):
            field_name = key[len(remote_prefix) :]
            if field_name == "allowed_hosts" and isinstance(value, str):
                remote_kwargs[field_name] = [host.strip() for host in value.split(",") if host.strip()]
            else:
                remote_kwargs[field_name] = value
        else:
            remaining[key] = value

    remote_options = RemoteInputOptions(**remote_kwargs) if remote_kwargs else None
    return remote_options, remaining


def _detect_format_for_path(input_path: Path | None) -> str | None:
    """Best-effort format detection for an input path."""
    if input_path is None:
        return None

    try:
        detected = registry.detect_format(input_path)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Failed to detect format for %s: %s", input_path, exc)
        return None

    return cast(Optional[str], detected)


def prepare_options_for_execution(
    options: Dict[str, Any],
    input_path: Path | None,
    parser_hint: str,
    renderer_hint: str | None = None,
) -> Dict[str, Any]:
    """Prepare CLI options for API consumption based on detected formats."""
    parser_format: str | None
    if parser_hint != "auto":
        parser_format = parser_hint
    else:
        parser_format = _detect_format_for_path(input_path)

    renderer_format: str | None
    if renderer_hint and renderer_hint != "auto":
        renderer_format = renderer_hint
    else:
        renderer_format = None
    remote_options, remaining = _extract_remote_input_options(options)
    filtered = _filter_options_for_formats(remaining, parser_format, renderer_format)
    if remote_options:
        filtered["remote_input_options"] = remote_options
    return filtered


def _get_rich_markdown_kwargs(args: argparse.Namespace) -> dict:
    """Build kwargs for Rich Markdown from CLI args.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    dict
        Kwargs dictionary for Rich Markdown constructor

    Notes
    -----
    Supported Rich Markdown options:
    - code_theme: Pygments theme for code blocks
    - inline_code_theme: Pygments theme for inline code
    - hyperlinks: Enable/disable hyperlinks
    - justify: Text justification (left, center, right, full)

    Note: line_numbers and indent_guides are not directly supported by
    Rich's Markdown class. These would require custom rendering.

    """
    kwargs = {}

    if hasattr(args, "rich_code_theme") and args.rich_code_theme:
        kwargs["code_theme"] = args.rich_code_theme

    if hasattr(args, "rich_inline_code_theme") and args.rich_inline_code_theme:
        kwargs["inline_code_theme"] = args.rich_inline_code_theme

    if hasattr(args, "rich_hyperlinks"):
        kwargs["hyperlinks"] = args.rich_hyperlinks

    if hasattr(args, "rich_justify") and args.rich_justify:
        kwargs["justify"] = args.rich_justify

    return kwargs


def _apply_rich_formatting(markdown_content: str, args: argparse.Namespace) -> tuple[str, bool]:
    """Apply Rich formatting to markdown content if requested.

    Parameters
    ----------
    markdown_content : str
        Plain markdown content to format
    args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    tuple[str, bool]
        Tuple of (formatted_content, is_rich_formatted)
        Returns (plain_markdown, False) if rich is unavailable or not requested

    """
    try:
        from rich.console import Console
        from rich.markdown import Markdown

        console = Console()
        rich_kwargs = _get_rich_markdown_kwargs(args)
        no_wrap = getattr(args, "rich_no_word_wrap", False)
        with console.capture() as capture:
            console.print(Markdown(markdown_content, **rich_kwargs), no_wrap=no_wrap)
        return capture.get(), True
    except ImportError:
        print("Warning: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
        return markdown_content, False


def _determine_syntax_language(target_format: str) -> str:
    """Map output format name to Pygments lexer name for syntax highlighting.

    This function provides explicit mappings for formats where the format
    name differs from the Pygments lexer name, and falls back to using
    the format name directly for other formats.

    Parameters
    ----------
    target_format : str
        The output format name (e.g., "html", "markdown", "rst")

    Returns
    -------
    str
        The Pygments lexer name for syntax highlighting with Rich

    """
    # Explicit mappings where format name != lexer name
    lookup = {
        "txt": "text",
        "sourcecode": "text",
        "json": "json",
        "yaml": "yaml",
    }

    normalized = target_format.lower()
    return lookup.get(normalized, normalized)


def _render_rich_text_output(text: str, args: argparse.Namespace, target_format: str) -> bool:
    """Attempt to render non-markdown text with Rich Syntax."""
    try:
        from rich.console import Console
        from rich.syntax import Syntax
    except ImportError:
        print("Warning: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
        print(text)
        return False

    no_wrap = getattr(args, "rich_no_word_wrap", False)
    theme = getattr(args, "rich_code_theme", "monokai") or "monokai"
    language = _determine_syntax_language(target_format)

    try:
        syntax = Syntax(text, language, theme=theme, word_wrap=not no_wrap)
    except Exception:
        # Fallback to plain printing when Rich can't determine lexer
        print(text)
        return False

    console = Console()
    console.print(syntax, no_wrap=no_wrap)
    return True


def _page_content(content: str, is_rich: bool = False) -> bool:
    """Page content using pydoc.pager.

    Parameters
    ----------
    content : str
        Content to page
    is_rich : bool
        Whether the content contains Rich formatting (ANSI codes)

    Returns
    -------
    bool
        True if paging succeeded, False if should fall back to printing

    """
    # Check if using Rich formatting on Windows/WSL
    # Plain text paging works fine on Windows, but Rich ANSI codes don't display well
    if is_rich:
        system = platform.system()
        is_windows_or_wsl = False

        if system == "Windows":
            is_windows_or_wsl = True
        elif system == "Linux":
            # Check if running under WSL
            try:
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        is_windows_or_wsl = True
            except Exception:
                pass

        if is_windows_or_wsl:
            print("Warning: --pager with --rich is not well supported on Windows/WSL.", file=sys.stderr)
            print("The content will be displayed without paging.", file=sys.stderr)
            return False

    # Use pydoc.pager (works fine for plain text on all platforms)
    try:
        pydoc.pager(content)
        return True
    except Exception:
        return False


def build_transform_instances(parsed_args: argparse.Namespace) -> Optional[list]:
    """Build transform instances from CLI arguments.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed CLI arguments

    Returns
    -------
    Optional[list]
        List of transform instances (in order) or None if no transforms

    Raises
    ------
    argparse.ArgumentTypeError
        If transform is unknown or required parameters are missing

    """
    if not hasattr(parsed_args, "transform_specs"):
        parsed_args.transform_specs = []

    if not hasattr(parsed_args, "transforms") or not parsed_args.transforms:
        parsed_args.transform_specs = []
        return None

    transform_instances = []
    transform_specs: list[TransformSpec] = []

    for transform_name in parsed_args.transforms:
        try:
            metadata = transform_registry.get_metadata(transform_name)
        except ValueError as e:
            print(f"Error: Unknown transform '{transform_name}'", file=sys.stderr)
            print("Use 'all2md list-transforms' to see available transforms", file=sys.stderr)
            raise argparse.ArgumentTypeError(f"Unknown transform: {transform_name}") from e

        # Extract parameters from CLI args using centralized logic
        params = {}
        for param_name, param_spec in metadata.parameters.items():
            if param_spec.should_expose():
                # Get the dest name used in argparse namespace (consistent with builder)
                dest = param_spec.get_dest_name(param_name, transform_name)

                # Extract value using centralized extraction logic
                # This handles default filtering and _provided_args tracking
                value, was_provided = param_spec.extract_value(parsed_args, dest)

                if was_provided:
                    params[param_name] = value

        # Validate required parameters
        for param_name, param_spec in metadata.parameters.items():
            if param_spec.required and param_name not in params:
                print(f"Error: Transform '{transform_name}' requires parameter: {param_name}", file=sys.stderr)
                if param_spec.should_expose():
                    print(
                        f"Use {param_spec.get_cli_flag(param_name)} to specify this parameter",
                        file=sys.stderr,
                    )
                raise argparse.ArgumentTypeError(
                    f"Transform '{transform_name}' missing required parameter: {param_name}"
                )

        # Record serializable transform spec for reuse (e.g., across processes)
        transform_specs.append({"name": transform_name, "params": dict(params)})

        # Create transform instance
        try:
            transform = metadata.create_instance(**params)
            transform_instances.append(transform)
        except Exception as e:
            print(f"Error creating transform '{transform_name}': {e}", file=sys.stderr)
            raise argparse.ArgumentTypeError(f"Failed to create transform: {transform_name}") from e

    parsed_args.transform_specs = transform_specs

    return transform_instances


def _instantiate_transforms_from_specs(transform_specs: list[TransformSpec]) -> list[Any]:
    """Recreate transform instances from serialized specs.

    Parameters
    ----------
    transform_specs : list[TransformSpec]
        Serializable transform specifications containing names and parameters.

    Returns
    -------
    list[Any]
        List of transform instances instantiated from the registry.

    """
    if not transform_specs:
        return []

    instances: list[Any] = []
    for spec in transform_specs:
        name = spec["name"]
        params = spec.get("params", {})
        instances.append(transform_registry.get_transform(name, **params))

    return instances


def apply_security_preset(parsed_args: argparse.Namespace, options: Dict[str, Any]) -> Dict[str, Any]:
    """Apply security preset configurations to options.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    options : Dict[str, Any]
        Current options dictionary

    Returns
    -------
    Dict[str, Any]
        Updated options with security presets applied

    Notes
    -----
    Security presets set multiple options to secure defaults using format-qualified
    keys to prevent ambiguity and unintended side effects. Explicit CLI flags
    can still override preset values if specified.

    Format-qualified keys ensure precise targeting:
    - html.* -> HtmlOptions fields
    - html.network.* -> HtmlOptions.network (NetworkFetchOptions)
    - html.local_files.* -> HtmlOptions.local_files (LocalFileAccessOptions)
    - mhtml.local_files.* -> MhtmlOptions.local_files (LocalFileAccessOptions)
    - eml.html_network.* -> EmlOptions.html_network (NetworkFetchOptions)
    - max_attachment_size_bytes -> BaseParserOptions (top-level, no prefix)

    """
    # Track which preset is being used (highest security wins)
    preset_used = None

    if parsed_args.strict_html_sanitize:
        preset_used = "strict-html-sanitize"
        # Strict HTML sanitization preset - use format-qualified keys
        # HTML options
        options["html.strip_dangerous_elements"] = True
        options["html.network.allow_remote_fetch"] = False
        options["html.local_files.allow_local_files"] = False
        options["html.local_files.allow_cwd_files"] = False
        # MHTML options (shares local file access settings)
        options["mhtml.local_files.allow_local_files"] = False
        options["mhtml.local_files.allow_cwd_files"] = False
        # EML options (for HTML content in emails)
        options["eml.html_network.allow_remote_fetch"] = False

    if parsed_args.safe_mode:
        preset_used = "safe-mode"
        # Balanced security for untrusted input
        # HTML options
        options["html.strip_dangerous_elements"] = True
        options["html.network.allow_remote_fetch"] = True
        options["html.network.require_https"] = True
        options["html.local_files.allow_local_files"] = False
        options["html.local_files.allow_cwd_files"] = False
        # MHTML options
        options["mhtml.local_files.allow_local_files"] = False
        options["mhtml.local_files.allow_cwd_files"] = False
        # EML options
        options["eml.html_network.allow_remote_fetch"] = True
        options["eml.html_network.require_https"] = True

    if parsed_args.paranoid_mode:
        preset_used = "paranoid-mode"
        # Maximum security - most restrictive settings
        # HTML options
        options["html.strip_dangerous_elements"] = True
        options["html.network.allow_remote_fetch"] = False  # Block all remote fetches
        options["html.max_asset_size_bytes"] = 5 * 1024 * 1024  # 5MB
        options["html.local_files.allow_local_files"] = False
        options["html.local_files.allow_cwd_files"] = False
        # MHTML options
        options["mhtml.local_files.allow_local_files"] = False
        options["mhtml.local_files.allow_cwd_files"] = False
        # EML options
        options["eml.html_network.allow_remote_fetch"] = False  # Block all remote fetches
        options["eml.max_asset_size_bytes"] = 5 * 1024 * 1024  # 5MB
        # Base options (no format prefix - applies to all formats)
        options["max_asset_size_bytes"] = 5 * 1024 * 1024  # 5MB (reduced from default 20MB)

    # Show warning if preset is used
    if preset_used:
        print(f"Security preset applied: {preset_used}", file=sys.stderr)
        print("Note: Individual security flags can override preset values if specified explicitly.", file=sys.stderr)

    return options


def setup_and_validate_options(
    parsed_args: argparse.Namespace,
) -> Tuple[Dict[str, Any], DocumentFormat, Optional[list]]:
    """Set up conversion options and build transforms.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    Tuple[Dict[str, Any], DocumentFormat, Optional[list]]
        Tuple of (options_dict, format_arg, transforms)

    Raises
    ------
    argparse.ArgumentTypeError
        If config file cannot be loaded or transform building fails

    """
    # Load configuration from file (with auto-discovery if not explicitly specified)
    config_from_file = {}

    # Check if --no-config flag is set to disable all configuration file loading
    no_config = getattr(parsed_args, "no_config", False)

    if not no_config:
        env_config_path = os.environ.get("ALL2MD_CONFIG")

        # Priority order:
        # 1. Explicit --config flag
        # 2. ALL2MD_CONFIG environment variable
        # 3. Auto-discovered config (.all2md.toml or .all2md.json in cwd or home)
        explicit_config_path = getattr(parsed_args, "config", None)

        try:
            config_from_file = load_config_with_priority(
                explicit_path=explicit_config_path, env_var_path=env_config_path
            )
        except argparse.ArgumentTypeError as e:
            print(f"Error loading configuration file: {e}", file=sys.stderr)
            raise

    # Apply preset if specified (preset is applied to config, then CLI args override)
    if hasattr(parsed_args, "preset") and parsed_args.preset:
        try:
            config_from_file = apply_preset(parsed_args.preset, config_from_file)
        except ValueError as e:
            print(f"Error applying preset: {e}", file=sys.stderr)
            raise argparse.ArgumentTypeError(str(e)) from e

    # Map CLI arguments to options (CLI args take highest priority)
    builder = DynamicCLIBuilder()
    options = builder.map_args_to_options(parsed_args, config_from_file)
    format_arg = cast(DocumentFormat, parsed_args.format if parsed_args.format != "auto" else "auto")

    # Apply security presets if specified
    options = apply_security_preset(parsed_args, options)

    # Build transform instances if --transform was used
    transforms = build_transform_instances(parsed_args)

    return options, format_arg, transforms


def process_multi_file(
    items: List[CLIInputItem],
    parsed_args: argparse.Namespace,
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
) -> int:
    """Process multiple files with appropriate output handling.

    Parameters
    ----------
    items : List[CLIInputItem]
        List of CLI input items to process
    parsed_args : argparse.Namespace
        Parsed command line arguments
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform instances to apply

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise; see constants.py for complete list)

    """
    # Handle detect-only / dry-run at the top for clarity
    if parsed_args.detect_only:
        return process_detect_only(items, parsed_args, format_arg)

    if parsed_args.dry_run:
        return process_dry_run(items, parsed_args, format_arg)

    # If --zip is specified, skip disk writes and package directly to zip
    if parsed_args.zip:
        return _create_output_package(parsed_args, items, options, format_arg, transforms)

    # Check for merge-from-list mode (takes precedence over collate)
    if parsed_args.merge_from_list:
        return process_merge_from_list(parsed_args, options, format_arg, transforms)

    # Check for document splitting mode
    if getattr(parsed_args, "split_by", None):
        return process_files_with_splitting(items, parsed_args, options, format_arg, transforms)

    # Otherwise, process files normally to disk
    if parsed_args.collate:
        exit_code = process_files_collated(items, parsed_args, options, format_arg, transforms)
    else:
        # Use unified processing function for all modes (rich/progress/simple)
        # This consolidates process_with_rich_output, process_with_progress_bar, and process_files_simple
        exit_code = process_files_unified(items, parsed_args, options, format_arg, transforms)

    return exit_code


def _create_output_package(
    parsed_args: argparse.Namespace,
    input_items: List[CLIInputItem],
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
) -> int:
    """Create output package (zip) after successful conversion.

    Converts files directly to zip archive using in-memory BytesIO buffers,
    eliminating intermediate disk I/O. Supports all output formats and processes
    files incrementally to minimize memory usage.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    input_items : List[CLIInputItem]
        List of input items to convert and package
    options : Dict[str, Any]
        Conversion options to pass to convert()
    format_arg : str
        Source format specification
    transforms : list, optional
        List of transform instances to apply

    Returns
    -------
    int
        Exit code (0 for success)

    """
    try:
        # Determine target format
        target_format = getattr(parsed_args, "output_format", "markdown")

        # Determine zip path
        if parsed_args.zip == "auto":
            # Use output_dir name if available, otherwise use generic name
            if hasattr(parsed_args, "output_dir") and parsed_args.output_dir:
                output_dir_name = Path(parsed_args.output_dir).name
                zip_path = Path(f"{output_dir_name}.zip")
            else:
                zip_path = Path("output.zip")
        else:
            zip_path = Path(parsed_args.zip)

        # Create the zip package directly from conversions
        # Pass user-specified options and transforms
        created_zip = create_package_from_conversions(
            input_items=input_items,
            zip_path=zip_path,
            target_format=target_format,
            options=options,
            transforms=transforms,
            source_format=format_arg,
        )

        print(f"Created package: {created_zip}", file=sys.stderr)
        return 0

    except Exception as e:
        logger.error(f"Failed to create output package: {e}")
        return EXIT_ERROR


def load_options_from_json(json_file_path: str) -> dict:
    """Load options from a JSON file.

    Parameters
    ----------
    json_file_path : str
        Path to the JSON file containing options

    Returns
    -------
    dict
        Dictionary of options loaded from the JSON file

    Raises
    ------
    argparse.ArgumentTypeError
        If the JSON file cannot be read or parsed

    """
    try:
        json_path = Path(json_file_path)
        if not json_path.exists():
            raise argparse.ArgumentTypeError(f"Options JSON file does not exist: {json_file_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            options = json.load(f)

        if not isinstance(options, dict):
            raise argparse.ArgumentTypeError(
                f"Options JSON file must contain a JSON object, got {type(options).__name__}"
            )

        return options

    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid JSON in options file {json_file_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading options file {json_file_path}: {e}") from e


def merge_exclusion_patterns_from_json(parsed_args: argparse.Namespace, json_options: dict) -> Optional[List[str]]:
    """Merge exclusion patterns from JSON options if not specified via CLI.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    json_options : dict
        Options loaded from JSON file

    Returns
    -------
    Optional[List[str]]
        Updated exclusion patterns or None if no changes

    """
    if "exclude" in json_options and parsed_args.exclude is None:
        return json_options["exclude"]
    return None


def parse_merge_list(list_path: Path | str, separator: str = "\t") -> List[Tuple[Path, Optional[str]]]:
    r"""Parse merge list file and return file paths with optional section titles.

    Parameters
    ----------
    list_path : Path or str
        Path to the list file containing documents to merge, or '-' to read from stdin
    separator : str, default '\t'
        Separator character for the list file (default: tab for TSV)

    Returns
    -------
    List[Tuple[Path, Optional[str]]]
        List of (file_path, section_title) tuples where section_title is None
        if not specified in the list file

    Raises
    ------
    argparse.ArgumentTypeError
        If the list file cannot be read or contains invalid entries

    Notes
    -----
    List file format:
    - TSV format: path[<separator>section_title]
    - Lines starting with # are comments
    - Blank lines are ignored
    - File paths are resolved relative to the list file directory (or cwd if stdin)
    - If no section title is provided, None is used
    - Use '-' as the path to read the list from stdin

    Examples
    --------
    List file content::

        # This is a comment
        chapter1.pdf	Introduction
        chapter2.pdf	Background
        chapter3.pdf

    Results in::

        [
            (Path('chapter1.pdf'), 'Introduction'),
            (Path('chapter2.pdf'), 'Background'),
            (Path('chapter3.pdf'), None)
        ]

    Reading from stdin::

        $ echo "chapter1.pdf\\tIntro" | all2md --merge-from-list - --out book.md

    """
    try:
        # Check if reading from stdin
        if list_path == "-" or str(list_path) == "-":
            # Read from stdin
            lines = sys.stdin.readlines()
            # Resolve paths relative to current working directory
            list_dir = Path.cwd()
        else:
            # Read from file
            list_path = Path(list_path)
            if not list_path.exists():
                raise argparse.ArgumentTypeError(f"Merge list file does not exist: {list_path}")

            with open(list_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Resolve paths relative to list file directory
            list_dir = list_path.parent

        # Parse entries
        entries: List[Tuple[Path, Optional[str]]] = []

        for line_num, line in enumerate(lines, 1):
            # Strip whitespace
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith("#"):
                continue

            # Split by separator
            parts = line.split(separator, 1)
            file_path_str = parts[0].strip()

            # Get section title if provided
            section_title = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

            # Skip if second part is a comment
            if section_title and section_title.startswith("#"):
                section_title = None

            # Resolve file path (relative to list file directory)
            if not file_path_str:
                continue

            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = list_dir / file_path

            # Validate file exists
            if not file_path.exists():
                raise argparse.ArgumentTypeError(
                    f"File not found in merge list (line {line_num}): {file_path_str}\n" f"Resolved path: {file_path}"
                )

            entries.append((file_path, section_title))

        if not entries:
            source_desc = "stdin" if (list_path == "-" or str(list_path) == "-") else str(list_path)
            raise argparse.ArgumentTypeError(f"Merge list is empty or contains no valid entries: {source_desc}")

        return entries

    except argparse.ArgumentTypeError:
        raise
    except Exception as e:
        source_desc = "stdin" if (list_path == "-" or str(list_path) == "-") else str(list_path)
        raise argparse.ArgumentTypeError(f"Error reading merge list from {source_desc}: {e}") from e


def _merge_single_entry(
    file_path: Path,
    section_title: Optional[str],
    options: Dict[str, Any],
    format_arg: str,
    no_section_titles: bool,
    progress_cb: Optional[Any] = None,
) -> tuple[list, int, Optional[str]]:
    """Process a single file for merging.

    Parameters
    ----------
    file_path : Path
        Path to file to process
    section_title : Optional[str]
        Optional section title
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    no_section_titles : bool
        Whether to skip section titles
    progress_cb : ProgressCallback, optional
        Optional progress callback

    Returns
    -------
    tuple[list, int, Optional[str]]
        Tuple of (children nodes, exit code, error message)

    """
    try:
        # Convert file to AST
        effective_options = prepare_options_for_execution(
            options,
            file_path,
            format_arg,
        )

        doc = to_ast(
            file_path,
            source_format=cast(DocumentFormat, format_arg),
            progress_callback=progress_cb,
            **effective_options,
        )

        children: list[Node] = []
        # Add section title if provided and not disabled
        if section_title and not no_section_titles:
            section_heading = Heading(level=1, content=[Text(content=section_title)])
            children.append(section_heading)

        # Add all children from this document
        children.extend(doc.children)

        return children, EXIT_SUCCESS, None

    except Exception as e:
        exit_code = get_exit_code_for_exception(e)
        error_msg = str(e)
        if isinstance(e, ImportError):
            error_msg = f"Missing dependency: {e}"
        elif not isinstance(e, All2MdError):
            error_msg = f"Unexpected error: {e}"

        return [], exit_code, error_msg


def _apply_document_transforms(merged_doc: Document, args: argparse.Namespace, transforms: Optional[list]) -> Document:
    """Apply TOC generation and additional transforms to merged document.

    Parameters
    ----------
    merged_doc : Document
        Merged document to transform
    args : argparse.Namespace
        Command-line arguments
    transforms : list, optional
        List of transform instances

    Returns
    -------
    Document
        Transformed document

    """
    # Apply TOC generation if requested
    if args.generate_toc:
        # First, add heading IDs if they don't exist
        id_transform = AddHeadingIdsTransform()
        transformed = id_transform.transform(merged_doc)
        assert isinstance(transformed, Document), "Transform should return Document"
        merged_doc = transformed

        # Then generate TOC
        toc_transform = GenerateTocTransform(
            title=args.toc_title if hasattr(args, "toc_title") else "Table of Contents",
            max_depth=args.toc_depth if hasattr(args, "toc_depth") else 3,
            position=args.toc_position if hasattr(args, "toc_position") else "top",
        )
        transformed = toc_transform.transform(merged_doc)
        assert isinstance(transformed, Document), "Transform should return Document"
        merged_doc = transformed

    # Apply any additional transforms
    if transforms:
        for transform in transforms:
            transformed = transform.transform(merged_doc)
            assert isinstance(transformed, Document), "Transform should return Document"
            merged_doc = transformed

    return merged_doc


def _determine_output_format(args: argparse.Namespace, output_path: Optional[Path]) -> str:
    """Determine target output format from args and output path.

    Parameters
    ----------
    args : argparse.Namespace
        Command-line arguments
    output_path : Optional[Path]
        Output path if specified

    Returns
    -------
    str
        Target format string

    """
    # Check if output_format was explicitly provided by user
    provided_args: set[str] = getattr(args, "_provided_args", set())
    if "output_format" in provided_args:
        return args.output_format

    # Auto-detect from output path
    if output_path:
        try:
            detected_target = registry.detect_format(output_path)
            return detected_target if detected_target != "txt" else "markdown"
        except Exception:
            return "markdown"

    return "markdown"


def _write_merged_output(
    merged_doc: Document,
    target_format: str,
    output_path: Optional[Path],
    options: Dict[str, Any],
    format_arg: str,
) -> Optional[Any]:
    """Render and write merged document to output.

    Parameters
    ----------
    merged_doc : Document
        Merged document to render
    target_format : str
        Target format for rendering
    output_path : Optional[Path]
        Output path if specified
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification

    Returns
    -------
    Optional[Any]
        Rendered result if output to stdout, None if written to file

    """
    # Prepare renderer options
    render_options = prepare_options_for_execution(
        options,
        None,
        format_arg,
        target_format,
    )
    render_options.pop("remote_input_options", None)

    # Render the merged document
    result = from_ast(
        merged_doc,
        target_format=cast(DocumentFormat, target_format),
        output=output_path,
        transforms=None,
        **render_options,
    )

    # Handle output to stdout
    if result is not None and output_path is None:
        if isinstance(result, bytes):
            sys.stdout.buffer.write(result)
            sys.stdout.buffer.flush()
        else:
            print(result)
    elif output_path is None and result is None:
        print("", end="")

    return result


def process_merge_from_list(
    args: argparse.Namespace, options: Dict[str, Any], format_arg: str, transforms: Optional[list] = None
) -> int:
    """Process files from a list file and merge them into a single document.

    Parameters
    ----------
    args : argparse.Namespace
        Command-line arguments containing merge-from-list settings
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform instances to apply

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)

    """
    # Parse the list file
    try:
        list_path_arg = args.merge_from_list
        separator = args.list_separator if hasattr(args, "list_separator") else "\t"
        entries = parse_merge_list(list_path_arg, separator=separator)
    except Exception as e:
        print(f"Error parsing merge list: {e}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Process entries with progress tracking
    merged_children: list = []
    failed: list = []
    max_exit_code = EXIT_SUCCESS

    show_progress = args.progress or args.rich or len(entries) > 1
    use_rich = args.rich

    with ProgressContext(use_rich, show_progress, len(entries), "Merging files from list") as progress:
        progress_callback = create_progress_context_callback(progress) if show_progress else None

        for file_path, section_title in entries:
            progress.set_postfix(f"Processing {file_path.name}")

            children, exit_code, error_msg = _merge_single_entry(
                file_path, section_title, options, format_arg, args.no_section_titles, progress_callback
            )

            if exit_code == EXIT_SUCCESS:
                merged_children.extend(children)
                progress.log(f"[OK] Processed {file_path}", level="success")
            else:
                failed.append((file_path, error_msg))
                max_exit_code = max(max_exit_code, exit_code)
                progress.log(f"[ERROR] {file_path}: {error_msg}", level="error")
                if not args.skip_errors:
                    break

            progress.update()

    # Check if any files were successfully processed
    if not merged_children:
        print("Error: No files were successfully processed", file=sys.stderr)
        return max_exit_code or EXIT_INPUT_ERROR

    # Create and transform merged document
    merged_doc = Document(children=merged_children)
    merged_doc = _apply_document_transforms(merged_doc, args, transforms)

    # Determine output path and format
    output_path: Optional[Path] = None
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    target_format = _determine_output_format(args, output_path)

    # Render and write output
    try:
        _write_merged_output(merged_doc, target_format, output_path, options, format_arg)

        # Print success message
        quiet = getattr(args, "quiet", False)
        if output_path and not quiet:
            print(f"Successfully merged {len(entries)} files to {output_path}")

        # Print warnings for failed files
        if failed and not quiet:
            print(f"\nWarning: {len(failed)} file(s) failed to process:", file=sys.stderr)
            for file_path, error in failed:
                print(f"  {file_path}: {error}", file=sys.stderr)

        return max_exit_code

    except Exception as e:
        print(f"Error rendering merged document: {e}", file=sys.stderr)
        return get_exit_code_for_exception(e)


def _detect_format_for_item(item: CLIInputItem, format_arg: str) -> tuple[str, str]:
    """Detect format and detection method for a single item.

    Parameters
    ----------
    item : CLIInputItem
        Input item to detect format for
    format_arg : str
        Format argument from CLI

    Returns
    -------
    tuple[str, str]
        (detected_format, detection_method)

    """
    if format_arg != "auto":
        return format_arg, "explicit (--format)"

    detected_format = registry.detect_format(item.raw_input)

    # Determine detection method
    metadata_list = registry.get_format_info(detected_format)
    metadata = metadata_list[0] if metadata_list else None
    suffix = item.suffix.lower() if item.suffix else ""
    if metadata and suffix in metadata.extensions:
        return detected_format, "file extension"

    # Check MIME type
    guess_target = item.display_name
    if item.path_hint:
        guess_target = str(item.path_hint)
    mime_type, _ = mimetypes.guess_type(guess_target)
    if mime_type and metadata and mime_type in metadata.mime_types:
        return detected_format, "MIME type"

    return detected_format, "magic bytes/content"


def _check_converter_dependencies(
    converter_metadata: Any,
) -> tuple[bool, list[tuple[str, str, str | None, str | None]]]:
    """Check converter dependencies and return availability status.

    Parameters
    ----------
    converter_metadata : Any
        Converter metadata object

    Returns
    -------
    tuple[bool, list[tuple[str, str, str | None, str | None]]]
        (converter_available, dependency_status_list)

    """
    converter_available = True
    dependency_status: list[tuple[str, str, str | None, str | None]] = []

    if not converter_metadata or not converter_metadata.required_packages:
        return converter_available, dependency_status

    # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
    for install_name, import_name, version_spec in converter_metadata.required_packages:
        if version_spec:
            # Use install_name for version checking (pip/metadata lookup)
            meets_req, installed_version = check_version_requirement(install_name, version_spec)
            if not meets_req:
                converter_available = False
                if installed_version:
                    dependency_status.append((install_name, "version mismatch", installed_version, version_spec))
                else:
                    dependency_status.append((install_name, "missing", None, version_spec))
            else:
                dependency_status.append((install_name, "ok", installed_version, version_spec))
        else:
            # Use import_name for import checking
            if not check_package_installed(import_name):
                converter_available = False
                dependency_status.append((install_name, "missing", None, None))
            else:
                dependency_status.append((install_name, "ok", None, None))

    return converter_available, dependency_status


def _render_detection_results_rich(detection_results: list[dict[str, Any]], any_issues: bool) -> None:
    """Render detection results using rich formatting.

    Parameters
    ----------
    detection_results : list[dict[str, Any]]
        List of detection results
    any_issues : bool
        Whether there were any dependency issues

    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Main detection table
    table = Table(title="Format Detection Results")
    table.add_column("Input", style="cyan", no_wrap=False)
    table.add_column("Detected Format", style="yellow")
    table.add_column("Detection Method", style="magenta")
    table.add_column("Converter Status", style="white")

    for result in detection_results:
        if result["available"]:
            status = "[green][OK] Available[/green]"
        else:
            status = "[red][X] Unavailable[/red]"

        table.add_row(result["item"].display_name, result["format"].upper(), result["method"], status)

    console.print(table)

    # Show dependency details if there are issues
    if any_issues:
        console.print("\n[bold yellow]Dependency Issues:[/bold yellow]")
        for result in detection_results:
            if not result["available"]:
                console.print(f"\n[cyan]{result['item'].display_name}[/cyan] ({result['format'].upper()}):")
                for pkg_name, status, installed, required in result["deps"]:
                    if status == "missing":
                        console.print(f"  [red][X] {pkg_name} - Not installed[/red]")
                    elif status == "version mismatch":
                        msg = f"  [yellow][!] {pkg_name} - Version mismatch"
                        msg += f" (requires {required}, installed: {installed})[/yellow]"
                        console.print(msg)

                if result["metadata"]:
                    install_cmd = result["metadata"].get_install_command()
                    console.print(f"  [dim]Install: {install_cmd}[/dim]")


def _render_detection_results_plain(detection_results: list[dict[str, Any]]) -> None:
    """Render detection results using plain text formatting.

    Parameters
    ----------
    detection_results : list[dict[str, Any]]
        List of detection results

    """
    for i, result in enumerate(detection_results, 1):
        status = "[OK]" if result["available"] else "[X]"
        print(f"{i:3d}. {status} {result['item'].display_name}")
        print(f"     Format: {result['format'].upper()}")
        print(f"     Detection: {result['method']}")

        if result["deps"]:
            print("     Dependencies:")
            for pkg_name, status_str, installed, required in result["deps"]:
                if status_str == "ok":
                    version_info = f" ({installed})" if installed else ""
                    print(f"       [OK] {pkg_name}{version_info}")
                elif status_str == "missing":
                    print(f"       [MISSING] {pkg_name}")
                elif status_str == "version mismatch":
                    print(f"       [MISMATCH] {pkg_name} (requires {required}, installed: {installed})")

            if not result["available"] and result["metadata"]:
                install_cmd = result["metadata"].get_install_command()
                print(f"     Install: {install_cmd}")
        else:
            print("     Dependencies: None required")

        print()


def process_detect_only(items: List[CLIInputItem], args: argparse.Namespace, format_arg: str) -> int:
    """Process inputs in detect-only mode - show format detection without conversion plan."""
    # Auto-discover parsers
    registry.auto_discover()

    print("DETECT-ONLY MODE - Format Detection Results")
    print(f"Analyzing {len(items)} input(s)")
    print()

    # Gather detection info
    detection_results: list[dict[str, Any]] = []
    any_issues = False

    for item in items:
        # Detect format and method
        detected_format, detection_method = _detect_format_for_item(item, format_arg)

        # Get converter info
        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        # Check dependencies
        converter_available, dependency_status = _check_converter_dependencies(converter_metadata)

        # Track if there are any issues
        if not converter_available:
            any_issues = True

        detection_results.append(
            {
                "item": item,
                "format": detected_format,
                "method": detection_method,
                "available": converter_available,
                "deps": dependency_status,
                "metadata": converter_metadata,
            }
        )

    # Display results
    if args.rich:
        try:
            _render_detection_results_rich(detection_results, any_issues)
        except ImportError:
            # Fall back to plain text
            args.rich = False

    if not args.rich:
        _render_detection_results_plain(detection_results)

    # Print summary
    print(f"\nTotal inputs analyzed: {len(detection_results)}")
    if any_issues:
        unavailable_count = sum(1 for r in detection_results if not r["available"])
        print(f"Inputs with unavailable parsers: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected parsers are available")
        return 0


def _collect_file_info_for_dry_run(items: List[CLIInputItem], format_arg: str) -> List[Dict[str, Any]]:
    """Collect file information for dry run display.

    Parameters
    ----------
    items : list of CLIInputItem
        Input items to analyze
    format_arg : str
        Format specification

    Returns
    -------
    list of dict
        List of file info dictionaries

    """
    file_info_list: List[Dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(item.raw_input)

            all_extensions: List[str] = []
            for fmt_name in registry.list_formats():
                fmt_info_list = registry.get_format_info(fmt_name)
                if fmt_info_list:
                    for fmt_info in fmt_info_list:
                        all_extensions.extend(fmt_info.extensions)

            suffix = item.suffix.lower() if item.suffix else ""
            detection_method = "extension" if suffix in all_extensions else "content analysis"

        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        converter_available = True
        dependency_issues: List[str] = []

        if converter_metadata:
            required_packages = converter_metadata.get_required_packages_for_content(
                content=None,
                input_data=item.display_name,
            )

            if required_packages:
                for pkg_name, _import_name, version_spec in required_packages:
                    if version_spec:
                        meets_req, installed_version = check_version_requirement(pkg_name, version_spec)
                        if not meets_req:
                            converter_available = False
                            if installed_version:
                                dependency_issues.append(f"{pkg_name} (version mismatch)")
                            else:
                                dependency_issues.append(f"{pkg_name} (missing)")
                    else:
                        if not check_package_installed(pkg_name):
                            converter_available = False
                            dependency_issues.append(f"{pkg_name} (missing)")

        file_info_list.append(
            {
                "item": item,
                "detected_format": detected_format,
                "detection_method": detection_method,
                "converter_available": converter_available,
                "dependency_issues": dependency_issues,
                "converter_metadata": converter_metadata,
                "index": index,
            }
        )

    return file_info_list


def _determine_output_destination(
    item: CLIInputItem,
    args: argparse.Namespace,
    file_info_list: List[Dict[str, Any]],
    base_input_dir: Optional[Path],
    index: int,
) -> str:
    """Determine output destination for an item in dry run.

    Parameters
    ----------
    item : CLIInputItem
        Input item
    args : argparse.Namespace
        Command line arguments
    file_info_list : list of dict
        All file info
    base_input_dir : Path or None
        Base input directory
    index : int
        Item index

    Returns
    -------
    str
        Output destination string

    """
    if args.collate:
        return str(Path(args.out)) if args.out else "stdout (collated)"

    if len(file_info_list) == 1 and args.out and not args.output_dir:
        return str(Path(args.out))

    if args.output_dir:
        target_format = getattr(args, "output_format", "markdown")
        computed = _generate_output_path_for_item(
            item,
            Path(args.output_dir),
            args.preserve_structure,
            base_input_dir,
            target_format,
            index,
            dry_run=True,
        )
        return str(computed)

    return "stdout"


def _render_dry_run_rich(
    file_info_list: List[Dict[str, Any]],
    args: argparse.Namespace,
    base_input_dir: Optional[Path],
) -> bool:
    """Render dry run output using rich formatting.

    Parameters
    ----------
    file_info_list : list of dict
        File information list
    args : argparse.Namespace
        Command line arguments
    base_input_dir : Path or None
        Base input directory

    Returns
    -------
    bool
        True if successfully rendered with rich, False otherwise

    """
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Dry Run - Planned Conversions")
        table.add_column("Input", style="cyan", no_wrap=False)
        table.add_column("Output", style="green", no_wrap=False)
        table.add_column("Format", style="yellow")
        table.add_column("Detection", style="magenta")
        table.add_column("Status", style="white")

        for info in file_info_list:
            item = info["item"]
            output_str = _determine_output_destination(item, args, file_info_list, base_input_dir, info["index"])

            if info["converter_available"]:
                status = "[green][OK] Ready[/green]"
            else:
                issues = ", ".join(info["dependency_issues"][:2])
                if len(info["dependency_issues"]) > 2:
                    issues += "..."
                status = f"[red][X] {issues}[/red]"

            table.add_row(
                item.display_name,
                output_str,
                info["detected_format"].upper(),
                info["detection_method"],
                status,
            )

        console.print(table)
        return True

    except ImportError:
        return False


def _render_dry_run_plain(
    file_info_list: List[Dict[str, Any]],
    args: argparse.Namespace,
    base_input_dir: Optional[Path],
) -> None:
    """Render dry run output using plain text.

    Parameters
    ----------
    file_info_list : list of dict
        File information list
    args : argparse.Namespace
        Command line arguments
    base_input_dir : Path or None
        Base input directory

    """
    for info in file_info_list:
        item = info["item"]
        print(f"{item.display_name}")
        print(f"  Format: {info['detected_format'].upper()} ({info['detection_method']})")

        if info["converter_available"]:
            print("  Status: ready")
        else:
            issues_str = ", ".join(info["dependency_issues"]) or "dependency issues"
            print(f"  Status: missing requirements ({issues_str})")

        destination = _determine_output_destination(item, args, file_info_list, base_input_dir, info["index"])
        print(f"  Output: {destination}")
        print()


def process_dry_run(items: List[CLIInputItem], args: argparse.Namespace, format_arg: str) -> int:
    """Show what would be processed without performing any conversions.

    Parameters
    ----------
    items : list of CLIInputItem
        Input items to process
    args : argparse.Namespace
        Command line arguments
    format_arg : str
        Format specification

    Returns
    -------
    int
        Exit code

    """
    base_input_dir = _compute_base_input_dir(items, args.preserve_structure)

    registry.auto_discover()

    print("DRY RUN MODE - Showing what would be processed")
    print(f"Found {len(items)} input(s) to convert")
    print()

    file_info_list = _collect_file_info_for_dry_run(items, format_arg)

    if args.rich:
        if not _render_dry_run_rich(file_info_list, args, base_input_dir):
            args.rich = False

    if not args.rich:
        _render_dry_run_plain(file_info_list, args, base_input_dir)

    print("Options that would be used:")
    if args.format != "auto":
        print(f"  Format: {args.format}")
    if args.recursive:
        print("  Recursive directory processing: enabled")
    parallel_provided = hasattr(args, "_provided_args") and "parallel" in args._provided_args
    if parallel_provided and args.parallel is None:
        worker_count = os.cpu_count() or "auto"
        print(f"  Parallel processing: {worker_count} workers (auto-detected)")
    elif isinstance(args.parallel, int) and args.parallel != 1:
        print(f"  Parallel processing: {args.parallel} workers")
    if args.preserve_structure:
        print("  Preserve directory structure: enabled")
    if args.collate:
        print("  Collate multiple inputs: enabled")
    if args.exclude:
        print(f"  Exclusion patterns: {', '.join(args.exclude)}")

    print()
    print("No inputs were converted (dry run mode).")
    return 0


def _convert_item_to_ast_for_collation(
    item: CLIInputItem,
    options: Dict[str, Any],
    format_arg: str,
    progress_callback: Optional[Any] = None,
) -> Tuple[int, Optional[ASTDocument], Optional[str]]:
    """Load an input item into an AST for collation.

    Parameters
    ----------
    item : CLIInputItem
        CLI input item to convert
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    progress_callback : ProgressCallback, optional
        Optional callback for progress updates

    Returns
    -------
    Tuple[int, Optional[ASTDocument], Optional[str]]
        Tuple of (exit_code, ast_document, error_message)

    """
    try:
        detection_hint = item.best_path()
        effective_options = prepare_options_for_execution(
            options,
            detection_hint,
            format_arg,
            renderer_hint=None,
        )

        ast_document = to_ast(
            item.raw_input,
            source_format=cast(DocumentFormat, format_arg),
            progress_callback=progress_callback,
            **effective_options,
        )

        return EXIT_SUCCESS, ast_document, None

    except Exception as exc:
        exit_code = get_exit_code_for_exception(exc)
        error_msg = str(exc)
        if isinstance(exc, ImportError):
            error_msg = f"Missing dependency: {exc}"
        elif not isinstance(exc, All2MdError):
            error_msg = f"Unexpected error: {exc}"
        return exit_code, None, error_msg


def process_files_collated(
    items: List[CLIInputItem],
    args: argparse.Namespace,
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
) -> int:
    """Collate multiple inputs into a single output using an AST pipeline."""
    collected_documents: List[ASTDocument] = []
    failures: List[Tuple[CLIInputItem, str, int]] = []

    use_rich = args.rich
    show_progress = args.progress or args.rich or len(items) > 1

    with ProgressContext(use_rich, show_progress, len(items), "Loading documents") as progress:
        # Create progress callback wrapper
        progress_callback = create_progress_context_callback(progress) if show_progress else None

        for _offset, item in enumerate(items, start=1):
            progress.set_postfix(f"Processing {item.name}")
            exit_code, document, error = _convert_item_to_ast_for_collation(
                item, options, format_arg, progress_callback
            )

            if exit_code == EXIT_SUCCESS and document:
                heading = Heading(level=1, content=[Text(f"File: {item.name}")])
                composed_children = [heading, *document.children]
                composed_doc = ASTDocument(children=composed_children, metadata=document.metadata)
                collected_documents.append(composed_doc)
                progress.log(f"[OK] {item.display_name}", level="success")
            else:
                message = error or "Unknown error"
                failures.append((item, message, exit_code))
                progress.log(f"[ERROR] {item.display_name}: {message}", level="error")
                if not args.skip_errors:
                    break

            progress.update()

    if not collected_documents:
        print("Error: No inputs were successfully processed", file=sys.stderr)
        return max((code for _, _, code in failures), default=EXIT_INPUT_ERROR)

    merged_children: List[Any] = []
    for index, document in enumerate(collected_documents):
        merged_children.extend(document.children)
        if index != len(collected_documents) - 1:
            merged_children.append(ThematicBreak())

    merged_document = ASTDocument(children=merged_children)

    if transforms:
        for transform in transforms:
            transformed = transform.transform(merged_document)
            assert isinstance(transformed, ASTDocument), "Transform should return Document"
            merged_document = transformed

    output_path: Optional[Path] = None
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    target_format = args.output_format
    if target_format == "auto":
        if output_path:
            try:
                detected_target = registry.detect_format(output_path)
                target_format = detected_target if detected_target != "txt" else "markdown"
            except Exception:
                target_format = "markdown"
        else:
            target_format = "markdown"

    render_options = prepare_options_for_execution(
        options,
        None,
        format_arg,
        target_format,
    )
    render_options.pop("remote_input_options", None)

    try:
        result = from_ast(
            merged_document,
            target_format=cast(DocumentFormat, target_format),
            output=output_path,
            transforms=None,
            **render_options,
        )

        if result is not None and output_path is None:
            if isinstance(result, bytes):
                print(result.decode("utf-8", errors="replace"))
            else:
                print(result)
        elif output_path is None and result is None:
            print("", end="")

        if output_path:
            print(
                f"Collated {len(collected_documents)} input(s) -> {output_path}",
                file=sys.stderr,
            )

    except Exception as exc:
        exit_code = get_exit_code_for_exception(exc)
        print(f"Error rendering collated document: {exc}", file=sys.stderr)
        return exit_code

    if not args.no_summary:
        renderer = SummaryRenderer(use_rich=args.rich)
        renderer.render_conversion_summary(
            successful=len(collected_documents),
            failed=len(failures),
            total=len(items),
            title="Collation Summary",
        )

    if failures:
        return max(code for _, _, code in failures)

    return EXIT_SUCCESS


def _determine_split_base_name(item: CLIInputItem, args: argparse.Namespace) -> str:
    """Determine base name for split files.

    Parameters
    ----------
    item : CLIInputItem
        Input item being processed
    args : argparse.Namespace
        CLI arguments

    Returns
    -------
    str
        Base name to use for split files

    """
    if args.out:
        return Path(args.out).stem
    else:
        if hasattr(item, "stem") and item.stem:
            return item.stem
        elif hasattr(item, "name") and item.name:
            return Path(item.name).stem
        else:
            return "output"


def _determine_split_output_dir(args: argparse.Namespace) -> Path:
    """Determine output directory for split files.

    Parameters
    ----------
    args : argparse.Namespace
        CLI arguments

    Returns
    -------
    Path
        Directory path for split files

    """
    if args.out:
        out_path = Path(args.out)
        return out_path.parent if out_path.parent != Path(".") else Path.cwd()
    elif args.output_dir:
        return Path(args.output_dir)
    else:
        return Path.cwd()


def _generate_split_filename(
    base_name: str,
    split_result: Any,
    target_format: str,
    naming_style: str = "numeric",
    digits: int = 3,
) -> str:
    """Generate filename for a split document.

    Parameters
    ----------
    base_name : str
        Base filename (without extension)
    split_result : SplitResult
        Split result containing index and title
    target_format : str
        Target output format (determines extension)
    naming_style : str
        Naming style: 'numeric' or 'title'
    digits : int
        Number of digits for padding

    Returns
    -------
    str
        Generated filename with extension

    """
    from all2md.converter_registry import registry

    extension = registry.get_default_extension_for_format(target_format)
    index_str = str(split_result.index).zfill(digits)

    if naming_style == "title" and split_result.title:
        slug = split_result.get_filename_slug()
        if slug:
            return f"{base_name}_{index_str}_{slug}{extension}"

    return f"{base_name}_{index_str}{extension}"


def process_files_with_splitting(
    items: List[CLIInputItem],
    args: argparse.Namespace,
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
) -> int:
    """Process files with document splitting into multiple output files.

    Parameters
    ----------
    items : List[CLIInputItem]
        Input items to process
    args : argparse.Namespace
        CLI arguments including split_by specification
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Source format specification
    transforms : list, optional
        AST transforms to apply

    Returns
    -------
    int
        Exit code (0 for success)

    """
    from all2md.ast.splitting import DocumentSplitter, parse_split_spec

    try:
        strategy, param = parse_split_spec(args.split_by)
    except ValueError as e:
        print(f"Error: Invalid split specification: {e}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    max_exit_code = EXIT_SUCCESS

    use_rich = args.rich
    show_progress = args.progress or args.rich or len(items) > 1

    for item in items:
        with ProgressContext(use_rich, show_progress, 1, f"Processing {item.name}") as progress:
            progress_callback = create_progress_context_callback(progress) if show_progress else None

            try:
                effective_options = prepare_options_for_execution(
                    options,
                    item.best_path(),
                    format_arg,
                )

                doc = to_ast(
                    item.raw_input,
                    source_format=cast(DocumentFormat, format_arg),
                    progress_callback=progress_callback,
                    **effective_options,
                )

                if transforms:
                    for transform in transforms:
                        transformed = transform.transform(doc)
                        assert isinstance(transformed, Document), "Transform should return Document"
                        doc = transformed

                if strategy == "heading":
                    splits = DocumentSplitter.split_by_heading_level(doc, level=param)
                elif strategy == "length":
                    splits = DocumentSplitter.split_by_word_count(doc, target_words=param)
                elif strategy == "parts":
                    splits = DocumentSplitter.split_by_parts(doc, num_parts=param)
                elif strategy == "break":
                    splits = DocumentSplitter.split_by_break(doc)
                elif strategy == "delimiter":
                    splits = DocumentSplitter.split_by_delimiter(doc, delimiter=param)
                elif strategy == "auto":
                    splits = DocumentSplitter.split_auto(doc)
                elif strategy in ("page", "chapter"):
                    print(
                        f"Warning: {strategy} splitting not yet implemented, using h1 fallback",
                        file=sys.stderr,
                    )
                    splits = DocumentSplitter.split_by_heading_level(doc, level=1)
                else:
                    print(f"Error: Unknown split strategy: {strategy}", file=sys.stderr)
                    return EXIT_INPUT_ERROR

                base_name = _determine_split_base_name(item, args)
                output_dir = _determine_split_output_dir(args)
                output_dir.mkdir(parents=True, exist_ok=True)

                target_format = getattr(args, "output_format", "markdown")
                if target_format == "auto":
                    target_format = "markdown"

                naming_style = getattr(args, "split_by_naming", "numeric")
                digits = getattr(args, "split_by_digits", 3)

                render_options = prepare_options_for_execution(
                    options,
                    None,
                    format_arg,
                    target_format,
                )
                render_options.pop("remote_input_options", None)

                for split_result in splits:
                    filename = _generate_split_filename(
                        base_name,
                        split_result,
                        target_format,
                        naming_style,
                        digits,
                    )
                    output_path = output_dir / filename

                    from_ast(
                        split_result.document,
                        target_format=cast(DocumentFormat, target_format),
                        output=output_path,
                        **render_options,
                    )

                    progress.log(
                        f"Created: {output_path} ({split_result.word_count} words)",
                        level="success",
                    )

                print(
                    f"Successfully split {item.display_name} into {len(splits)} file(s) in {output_dir}",
                    file=sys.stderr,
                )

            except Exception as e:
                exit_code = get_exit_code_for_exception(e)
                print(f"Error processing {item.display_name}: {e}", file=sys.stderr)
                max_exit_code = max(max_exit_code, exit_code)
                if not args.skip_errors:
                    return exit_code

            progress.update()

    return max_exit_code


def generate_output_path(
    input_file: Path,
    output_dir: Optional[Path] = None,
    preserve_structure: bool = False,
    base_input_dir: Optional[Path] = None,
    dry_run: bool = False,
    target_format: str = "markdown",
) -> Path:
    """Generate output path for a converted file.

    Parameters
    ----------
    input_file : Path
        Input file path
    output_dir : Path, optional
        Output directory
    preserve_structure : bool
        Whether to preserve directory structure
    base_input_dir : Path, optional
        Base input directory for preserving structure
    dry_run : bool, default=False
        If True, don't create directories
    target_format : str, default="markdown"
        Target output format to determine file extension

    Returns
    -------
    Path
        Output file path

    """
    # Determine output file extension based on target format
    extension = registry.get_default_extension_for_format(target_format)

    # Generate output filename
    output_name = input_file.stem + extension

    if output_dir:
        if preserve_structure and base_input_dir:
            # Preserve directory structure
            relative_path = input_file.relative_to(base_input_dir)
            output_path = output_dir / relative_path.parent / output_name
        else:
            # Flat output directory
            output_path = output_dir / output_name

        # Ensure output directory exists (unless dry run)
        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Output in same directory as input
        output_path = input_file.parent / output_name

    return output_path


def convert_single_file(
    input_item: CLIInputItem,
    output_path: Optional[Path],
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
    show_progress: bool = False,
    target_format: str = "markdown",
    transform_specs: Optional[list[TransformSpec]] = None,
    progress_callback: Optional[Any] = None,
    extract_spec: Optional[str] = None,
    outline: bool = False,
    outline_max_level: int = 6,
) -> Tuple[int, str, Optional[str]]:
    """Convert a single file to the specified target format.

    Parameters
    ----------
    input_item : CLIInputItem
        CLI input item describing the source
    output_path : Path, optional
        Output file path. If None, prints to stdout (markdown only)
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Source format specification
    transforms : list, optional
        List of transform instances to apply
    show_progress : bool, default False
        Whether to show progress (currently unused)
    target_format : str, default 'markdown'
        Target output format (e.g., 'markdown', 'docx', 'pdf', 'html')
    transform_specs : list[TransformSpec], optional
        Serializable transform specifications to rebuild in worker processes
    progress_callback : ProgressCallback, optional
        Optional callback for progress updates
    extract_spec : str, optional
        Section extraction specification (e.g., "Introduction", "#:1-3")
    outline : bool, default False
        Whether to output document outline instead of full content
    outline_max_level : int, default 6
        Maximum heading level to include in outline (1-6)

    Returns
    -------
    Tuple[int, str, Optional[str]]
        (exit_code, file_path_str, error_message)

    """
    try:
        local_transforms = transforms
        if local_transforms is None and transform_specs:
            local_transforms = _instantiate_transforms_from_specs(transform_specs)

        source_value: Any = input_item.raw_input
        if isinstance(source_value, str):
            if source_value.startswith("https:/") and not source_value.startswith("https://"):
                source_value = source_value.replace("https:/", "https://", 1)
            elif source_value.startswith("http:/") and not source_value.startswith("http://"):
                source_value = source_value.replace("http:/", "http://", 1)

        renderer_hint = target_format
        if renderer_hint == "auto" and output_path:
            try:
                detected_target = registry.detect_format(output_path)
                if detected_target and detected_target != "txt":
                    renderer_hint = detected_target
            except Exception:  # pragma: no cover - best effort
                renderer_hint = "auto"

        effective_options = prepare_options_for_execution(
            options,
            input_item.best_path(),
            format_arg,
            renderer_hint,
        )

        # If outline is requested, generate and output outline
        if outline:
            # Parse to AST
            doc = to_ast(
                source_value,
                source_format=cast(DocumentFormat, format_arg),
                progress_callback=progress_callback,
                **effective_options,
            )

            # Generate outline
            outline_text = generate_outline_from_document(doc, max_level=outline_max_level)

            # Output outline
            if output_path:
                output_path.write_text(outline_text, encoding="utf-8")
                return EXIT_SUCCESS, input_item.display_name, None

            # Print to stdout
            print(outline_text)
            return EXIT_SUCCESS, input_item.display_name, None

        # If extraction is requested, use AST pipeline
        if extract_spec:
            # Parse to AST
            doc = to_ast(
                source_value,
                source_format=cast(DocumentFormat, format_arg),
                progress_callback=progress_callback,
                **effective_options,
            )

            # Extract sections
            doc = extract_sections_from_document(doc, extract_spec)

            # Apply transforms
            if local_transforms:
                for transform in local_transforms:
                    doc = transform.transform(doc)

            # Render from AST
            render_target = target_format if target_format != "auto" else "markdown"
            result = from_ast(
                doc,
                target_format=cast(DocumentFormat, render_target),
                output=output_path,
                **effective_options,
            )

            if output_path:
                return EXIT_SUCCESS, input_item.display_name, None

            # Handle stdout output
            if isinstance(result, bytes):
                sys.stdout.buffer.write(result)
                sys.stdout.buffer.flush()
            elif isinstance(result, str):
                print(result)

            return EXIT_SUCCESS, input_item.display_name, None

        # Normal conversion path (no extraction)
        if output_path:
            convert(
                source_value,
                output=output_path,
                source_format=cast(DocumentFormat, format_arg),
                target_format=cast(DocumentFormat, target_format),
                transforms=local_transforms,
                progress_callback=progress_callback,
                **effective_options,
            )
            return EXIT_SUCCESS, input_item.display_name, None

        render_target = target_format if target_format != "auto" else "markdown"

        result = convert(
            source_value,
            output=None,
            source_format=cast(DocumentFormat, format_arg),
            target_format=cast(DocumentFormat, render_target),
            transforms=local_transforms,
            progress_callback=progress_callback,
            **effective_options,
        )

        if isinstance(result, bytes):
            sys.stdout.buffer.write(result)
            sys.stdout.buffer.flush()
        elif isinstance(result, str):
            print(result)
        # result can only be bytes, str, or None at this point

        return EXIT_SUCCESS, input_item.display_name, None

    except Exception as exc:
        exit_code = get_exit_code_for_exception(exc)
        error_msg = str(exc)
        if isinstance(exc, ImportError):
            error_msg = f"Missing dependency: {exc}"
        elif not isinstance(exc, All2MdError):
            error_msg = f"Unexpected error: {exc}"
        return exit_code, input_item.display_name, error_msg


def process_files_unified(
    items: List[CLIInputItem],
    args: argparse.Namespace,
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list] = None,
) -> int:
    """Process CLI inputs with unified progress handling."""
    base_input_dir = _compute_base_input_dir(items, args.preserve_structure)

    try:
        should_use_rich = should_use_rich_output(args, True)
        rich_dependency_error: Optional[str] = None
    except DependencyError as exc:
        should_use_rich = False
        rich_dependency_error = str(exc)

    if rich_dependency_error:
        print(f"Warning: {rich_dependency_error}", file=sys.stderr)

    # Check if output_format was explicitly provided by user
    # If not, use "auto" to enable format detection from output filename
    provided_args: set[str] = getattr(args, "_provided_args", set())
    if "output_format" in provided_args:
        target_format_default = args.output_format
    else:
        target_format_default = "auto"

    # Special case: single item to stdout
    if len(items) == 1 and not args.out and not args.output_dir:
        return _render_single_item_to_stdout(
            items[0],
            args,
            options,
            format_arg,
            transforms,
            should_use_rich,
            target_format_default,
        )

    transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(args, "transform_specs", None))

    planned_tasks: List[Tuple[CLIInputItem, Optional[Path], str, int]] = []

    output_dir = Path(args.output_dir) if args.output_dir else None

    for index, item in enumerate(items, start=1):
        target_format = target_format_default
        output_path: Optional[Path] = None

        if args.out and len(items) == 1:
            output_path = Path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        elif output_dir:
            output_path = _generate_output_path_for_item(
                item,
                output_dir,
                args.preserve_structure,
                base_input_dir,
                target_format,
                index,
            )

        planned_tasks.append((item, output_path, target_format, index))

    show_progress = args.progress or (should_use_rich and args.rich) or len(items) > 1
    use_rich = should_use_rich

    results: List[Tuple[CLIInputItem, Optional[Path]]] = []
    failures: List[Tuple[CLIInputItem, Optional[str], int]] = []
    max_exit_code = EXIT_SUCCESS

    # Get extract_spec from args if present
    extract_spec = getattr(args, "extract", None)

    # Get outline parameters from args if present
    outline = getattr(args, "outline", False)
    outline_max_level = getattr(args, "outline_max_level", 6)

    use_parallel = (
        hasattr(args, "_provided_args") and "parallel" in args._provided_args and args.parallel is None
    ) or (isinstance(args.parallel, int) and args.parallel != 1)

    if use_parallel:
        max_workers = args.parallel if args.parallel else os.cpu_count()

        with ProgressContext(use_rich, show_progress, len(planned_tasks), "Converting inputs") as progress:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(
                        convert_single_file,
                        item,
                        output_path,
                        options,
                        format_arg,
                        None,
                        False,
                        target_format,
                        transform_specs_for_workers,
                        None,  # progress_callback (not supported in parallel mode)
                        extract_spec,
                        outline,
                        outline_max_level,
                    ): (item, output_path)
                    for item, output_path, target_format, _ in planned_tasks
                }

                for future in as_completed(futures):
                    item, output_path = futures[future]
                    exit_code, _, error = future.result()

                    if exit_code == EXIT_SUCCESS:
                        results.append((item, output_path))
                        message = f"[OK] {item.display_name}"
                        if output_path:
                            message = f"[OK] {item.display_name} -> {output_path}"
                        progress.log(message, level="success")
                    else:
                        failures.append((item, error, exit_code))
                        progress.log(f"[ERROR] {item.display_name}: {error}", level="error")
                        max_exit_code = max(max_exit_code, exit_code)
                        if not args.skip_errors:
                            break

                    progress.update()
    else:
        with ProgressContext(use_rich, show_progress, len(planned_tasks), "Converting inputs") as progress:
            # Create progress callback wrapper for sequential processing
            progress_callback = create_progress_context_callback(progress) if show_progress else None

            for item, output_path, target_format, _index in planned_tasks:
                progress.set_postfix(f"Processing {item.name}")

                exit_code, _, error = convert_single_file(
                    item,
                    output_path,
                    options,
                    format_arg,
                    transforms,
                    False,
                    target_format,
                    transform_specs_for_workers,
                    progress_callback,
                    extract_spec,
                    outline,
                    outline_max_level,
                )

                if exit_code == EXIT_SUCCESS:
                    results.append((item, output_path))
                    message = f"[OK] {item.display_name}"
                    if output_path:
                        message = f"[OK] {item.display_name} -> {output_path}"
                    progress.log(message, level="success")
                else:
                    failures.append((item, error, exit_code))
                    progress.log(f"[ERROR] {item.display_name}: {error}", level="error")
                    max_exit_code = max(max_exit_code, exit_code)
                    if not args.skip_errors:
                        break

                progress.update()

    if not args.no_summary and len(items) > 1:
        renderer = SummaryRenderer(use_rich=use_rich)
        renderer.render_conversion_summary(
            successful=len(results),
            failed=len(failures),
            total=len(items),
        )

    if failures:
        return max_exit_code

    return EXIT_SUCCESS


def _render_single_item_to_stdout(
    item: CLIInputItem,
    args: argparse.Namespace,
    options: Dict[str, Any],
    format_arg: str,
    transforms: Optional[list],
    should_use_rich: bool,
    target_format: str,
) -> int:
    """Render a single item to stdout, respecting pager and rich flags."""
    try:
        render_target = target_format if target_format != "auto" else "markdown"
        effective_options = prepare_options_for_execution(
            options,
            item.best_path(),
            format_arg,
            render_target,
        )

        # Check if extraction is requested
        extract_spec = getattr(args, "extract", None)

        # Check if outline is requested
        outline = getattr(args, "outline", False)
        outline_max_level = getattr(args, "outline_max_level", 6)

        # Handle outline mode
        if outline:
            # Parse to AST
            doc = to_ast(
                item.raw_input,
                source_format=cast(DocumentFormat, format_arg),
                **effective_options,
            )

            # Generate outline
            outline_text = generate_outline_from_document(doc, max_level=outline_max_level)

            # Apply rich formatting if requested
            if should_use_rich:
                content_to_output, is_rich = _apply_rich_formatting(outline_text, args)
            else:
                content_to_output, is_rich = outline_text, False

            # Apply paging if requested
            if args.pager:
                if not _page_content(content_to_output, is_rich=is_rich):
                    print(content_to_output)
            else:
                print(content_to_output)

            return EXIT_SUCCESS

        if render_target == "markdown":
            # Handle extraction using AST pipeline
            if extract_spec:
                # Parse to AST
                doc = to_ast(
                    item.raw_input,
                    source_format=cast(DocumentFormat, format_arg),
                    **effective_options,
                )

                # Extract sections
                doc = extract_sections_from_document(doc, extract_spec)

                # Apply transforms
                if transforms:
                    for transform in transforms:
                        doc = transform.transform(doc)

                # Render to markdown
                markdown_content = from_ast(doc, "markdown", **effective_options)
            else:
                # Normal markdown conversion
                markdown_content = to_markdown(
                    item.raw_input,
                    source_format=cast(DocumentFormat, format_arg),
                    transforms=transforms,
                    **effective_options,
                )

            # Ensure markdown_content is a string (markdown renderer always returns str when output=None)
            assert isinstance(markdown_content, str), "Markdown renderer should return str"

            # Apply rich formatting if requested
            if should_use_rich:
                content_to_output, is_rich = _apply_rich_formatting(markdown_content, args)
            else:
                content_to_output, is_rich = markdown_content, False

            # Apply paging if requested
            if args.pager:
                if not _page_content(content_to_output, is_rich=is_rich):
                    print(content_to_output)
            else:
                print(content_to_output)

            return EXIT_SUCCESS
        else:
            # Handle extraction for non-markdown formats
            if extract_spec:
                # Parse to AST
                doc = to_ast(
                    item.raw_input,
                    source_format=cast(DocumentFormat, format_arg),
                    **effective_options,
                )

                # Extract sections
                doc = extract_sections_from_document(doc, extract_spec)

                # Apply transforms
                if transforms:
                    for transform in transforms:
                        doc = transform.transform(doc)

                # Render to target format
                result = from_ast(doc, cast(DocumentFormat, render_target), **effective_options)
            else:
                # Normal conversion
                result = convert(
                    item.raw_input,
                    output=None,
                    source_format=cast(DocumentFormat, format_arg),
                    target_format=cast(DocumentFormat, render_target),
                    transforms=transforms,
                    **effective_options,
                )

            if isinstance(result, bytes):
                sys.stdout.buffer.write(result)
                sys.stdout.buffer.flush()
                return EXIT_SUCCESS

            text_output: str
            if isinstance(result, str):
                text_output = result
            else:
                # result can only be None at this point (already handled bytes)
                text_output = ""

            rendered = False
            if should_use_rich and args.rich and text_output is not None:
                rendered = _render_rich_text_output(text_output, args, render_target)

            if not rendered:
                if args.pager and text_output is not None:
                    if not _page_content(text_output, is_rich=False):
                        print(text_output)
                else:
                    print(text_output)

            return EXIT_SUCCESS
    except Exception as exc:
        exit_code = get_exit_code_for_exception(exc)
        print(f"Error: {exc}", file=sys.stderr)
        return exit_code
