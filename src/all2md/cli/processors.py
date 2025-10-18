"""Specialized processing functions for all2md CLI.

This module contains focused processing functions extracted from the main()
function to improve maintainability and testability.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import json
import logging
import os
import platform
import pydoc
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

from all2md import convert, from_ast, to_ast, to_markdown
from all2md.ast.nodes import Document as ASTDocument
from all2md.ast.nodes import Heading, Text, ThematicBreak
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_SUCCESS,
    DynamicCLIBuilder,
    get_exit_code_for_exception,
)
from all2md.cli.input_items import CLIInputItem
from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, DependencyError
from all2md.transforms import registry as transform_registry
from all2md.utils.input_sources import RemoteInputOptions

logger = logging.getLogger(__name__)

_OPTION_COMPAT_WARNINGS: set[str] = set()


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
        Detected parser format. When None, fall back to legacy behaviour with warnings.
    renderer_format : str or None
        Target renderer format. When None, fall back with warnings for renderer-prefixed keys.

    Returns
    -------
    dict
        Options dictionary suitable for passing to convert()/to_markdown().

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

    if not parser_format and parser_fallback:
        for legacy_key, legacy_value in parser_fallback.items():
            if legacy_key not in filtered:
                filtered[legacy_key] = legacy_value
            if legacy_key not in _OPTION_COMPAT_WARNINGS:
                logger.warning(
                    "Using legacy parser option '%s'. Specify --format to avoid relying on implicit mapping.",
                    legacy_key,
                )
                _OPTION_COMPAT_WARNINGS.add(legacy_key)

    if not renderer_format and renderer_fallback:
        for legacy_key, legacy_value in renderer_fallback.items():
            if legacy_key not in filtered:
                filtered[legacy_key] = legacy_value
            if legacy_key not in _OPTION_COMPAT_WARNINGS:
                logger.warning(
                    "Using legacy renderer option '%s'. Specify --output-type to avoid implicit mapping.",
                    legacy_key,
                )
                _OPTION_COMPAT_WARNINGS.add(legacy_key)

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


def _check_rich_available() -> bool:
    """Check if Rich library is available.

    Returns
    -------
    bool
        True if Rich is available, False otherwise

    """
    try:
        import rich  # noqa: F401

        return True
    except ImportError:
        return False


def _should_use_rich_output(args: argparse.Namespace) -> bool:
    """Determine if Rich output should be used based on TTY and args.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    bool
        True if Rich output should be used

    Notes
    -----
    Rich output is used when:
    - The --rich flag is set
    - AND either --force-rich is set OR stdout is a TTY
    - AND Rich library is available

    """
    if not args.rich:
        return False

    # Check if Rich is available
    if not _check_rich_available():
        raise DependencyError(
            converter_name="rich-output",
            missing_packages=[("rich", "")],
            message=("Rich output requires the optional 'rich' dependency. " "Install with: pip install all2md[rich]"),
        )

    # Force rich output regardless of TTY if explicitly requested
    if hasattr(args, "force_rich") and args.force_rich:
        return True

    # Only use rich output if stdout is a TTY (not piped/redirected)
    return sys.stdout.isatty()


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


# TODO: we can do better than this, I think we have better utils in another module
def _determine_syntax_language(target_format: str) -> str:
    """Return the Rich/Pygments lexer name for a given renderer target."""
    lookup = {
        "html": "html",
        "asciidoc": "asciidoc",
        "markdown": "markdown",
        "rst": "rst",
        "org": "org",
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

    try:
        from all2md.transforms import registry as transform_registry
    except ImportError:
        # Transform system not available
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
    from all2md.cli.config import load_config_with_priority
    from all2md.cli.presets import apply_preset

    # Load configuration from file (with auto-discovery if not explicitly specified)
    config_from_file = {}
    env_config_path = os.environ.get("ALL2MD_CONFIG")

    # Priority order:
    # 1. Explicit --config flag
    # 2. ALL2MD_CONFIG environment variable
    # 3. Auto-discovered config (.all2md.toml or .all2md.json in cwd or home)
    explicit_config_path = getattr(parsed_args, "config", None)

    try:
        config_from_file = load_config_with_priority(explicit_path=explicit_config_path, env_var_path=env_config_path)
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
    import logging
    from pathlib import Path

    from all2md.cli.packaging import create_package_from_conversions

    logger = logging.getLogger(__name__)

    try:
        # Determine target format
        target_format = getattr(parsed_args, "output_type", "markdown")

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


# TODO: what is this for? Is it needed?
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
    List file content:

        # This is a comment
        chapter1.pdf	Introduction
        chapter2.pdf	Background
        chapter3.pdf

    Results in:
        [
            (Path('chapter1.pdf'), 'Introduction'),
            (Path('chapter2.pdf'), 'Background'),
            (Path('chapter3.pdf'), None)
        ]

    Reading from stdin:

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
    from all2md.ast.nodes import Document, Heading, Text
    from all2md.renderers.markdown import MarkdownRenderer
    from all2md.transforms.builtin import AddHeadingIdsTransform, GenerateTocTransform

    # Parse the list file (or stdin if '-')
    try:
        list_path_arg = args.merge_from_list
        separator = args.list_separator if hasattr(args, "list_separator") else "\t"

        # Pass as string to preserve '-' for stdin detection
        entries = parse_merge_list(list_path_arg, separator=separator)
    except Exception as e:
        print(f"Error parsing merge list: {e}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Prepare for merging
    merged_children: list = []
    failed: list = []
    max_exit_code = EXIT_SUCCESS

    # Determine if we should show progress
    show_progress = args.progress or args.rich or len(entries) > 1

    # Helper function to process a single file
    def process_entry(file_path: Path, section_title: Optional[str]) -> int:
        """Process a single file for merging.

        Returns
        -------
        int
            Exit code (0 for success)

        """
        nonlocal max_exit_code

        try:
            # Convert file to AST
            effective_options = prepare_options_for_execution(
                options,
                file_path,
                format_arg,
            )

            doc = to_ast(file_path, source_format=cast(DocumentFormat, format_arg), **effective_options)

            # Add section title if provided and not disabled
            if section_title and not args.no_section_titles:
                # Insert section heading at the beginning
                section_heading = Heading(level=1, content=[Text(content=section_title)])
                merged_children.append(section_heading)

            # Add all children from this document
            merged_children.extend(doc.children)

            return EXIT_SUCCESS

        except Exception as e:
            exit_code = get_exit_code_for_exception(e)
            error_msg = str(e)
            if isinstance(e, ImportError):
                error_msg = f"Missing dependency: {e}"
            elif not isinstance(e, All2MdError):
                error_msg = f"Unexpected error: {e}"

            failed.append((file_path, error_msg))
            max_exit_code = max(max_exit_code, exit_code)
            return exit_code

    # Use unified progress tracking with ProgressContext
    from all2md.cli.progress import ProgressContext

    use_rich = args.rich
    with ProgressContext(use_rich, show_progress, len(entries), "Merging files from list") as progress:
        for file_path, section_title in entries:
            progress.set_postfix(f"Processing {file_path.name}")
            exit_code = process_entry(file_path, section_title)

            if exit_code == EXIT_SUCCESS:
                progress.log(f"[OK] Processed {file_path}", level="success")
            else:
                error_msg = failed[-1][1] if failed else "Unknown error"
                progress.log(f"[ERROR] {file_path}: {error_msg}", level="error")
                if not args.skip_errors:
                    break

            progress.update()

    # If all files failed, return error
    if not merged_children:
        print("Error: No files were successfully processed", file=sys.stderr)
        return max_exit_code or EXIT_INPUT_ERROR

    # Create merged document
    merged_doc = Document(children=merged_children)

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

    # Render the merged document to markdown
    try:
        renderer = MarkdownRenderer()
        markdown_content = renderer.render_to_string(merged_doc)

        # Determine output path
        output_path = None
        if args.out:
            output_path = Path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write output
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            if not args.quiet:
                print(f"Successfully merged {len(entries)} files to {output_path}")
        else:
            # Print to stdout
            print(markdown_content)

        # Print warnings for failed files if any
        if failed and not args.quiet:
            print(f"\nWarning: {len(failed)} file(s) failed to process:", file=sys.stderr)
            for file_path, error in failed:
                print(f"  {file_path}: {error}", file=sys.stderr)

        return max_exit_code

    except Exception as e:
        print(f"Error rendering merged document: {e}", file=sys.stderr)
        return get_exit_code_for_exception(e)


def process_detect_only(items: List[CLIInputItem], args: argparse.Namespace, format_arg: str) -> int:
    """Process inputs in detect-only mode - show format detection without conversion plan."""
    from all2md.converter_registry import registry
    from all2md.dependencies import check_version_requirement

    # Auto-discover parsers
    registry.auto_discover()

    print("DETECT-ONLY MODE - Format Detection Results")
    print(f"Analyzing {len(items)} input(s)")
    print()

    # Gather detection info
    detection_results: list[dict[str, Any]] = []
    any_issues = False

    for item in items:
        # Detect format
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(item.raw_input)

            # Determine detection method
            metadata_list = registry.get_format_info(detected_format)
            metadata = metadata_list[0] if metadata_list else None
            suffix = item.suffix.lower() if item.suffix else ""
            if metadata and suffix in metadata.extensions:
                detection_method = "file extension"
            else:
                # Check MIME type
                import mimetypes

                guess_target = item.display_name
                if item.path_hint:
                    guess_target = str(item.path_hint)
                mime_type, _ = mimetypes.guess_type(guess_target)
                if mime_type and metadata and mime_type in metadata.mime_types:
                    detection_method = "MIME type"
                else:
                    detection_method = "magic bytes/content"

        # Get converter info
        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        # Check dependencies
        converter_available = True
        dependency_status: list[tuple[str, str, str | None, str | None]] = []

        if converter_metadata and converter_metadata.required_packages:
            # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
            for install_name, import_name, version_spec in converter_metadata.required_packages:
                if version_spec:
                    # Use install_name for version checking (pip/metadata lookup)
                    meets_req, installed_version = check_version_requirement(install_name, version_spec)
                    if not meets_req:
                        converter_available = False
                        any_issues = True
                        if installed_version:
                            dependency_status.append(
                                (install_name, "version mismatch", installed_version, version_spec)
                            )
                        else:
                            dependency_status.append((install_name, "missing", None, version_spec))
                    else:
                        dependency_status.append((install_name, "ok", installed_version, version_spec))
                else:
                    from all2md.dependencies import check_package_installed

                    # Use import_name for import checking
                    if not check_package_installed(import_name):
                        converter_available = False
                        any_issues = True
                        dependency_status.append((install_name, "missing", None, None))
                    else:
                        dependency_status.append((install_name, "ok", None, None))

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

        except ImportError:
            # Fall back to plain text
            args.rich = False

    if not args.rich:
        # Plain text output
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

    print(f"\nTotal inputs analyzed: {len(detection_results)}")
    if any_issues:
        unavailable_count = sum(1 for r in detection_results if not r["available"])
        print(f"Inputs with unavailable parsers: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected parsers are available")
        return 0


def process_dry_run(items: List[CLIInputItem], args: argparse.Namespace, format_arg: str) -> int:
    """Show what would be processed without performing any conversions."""
    from all2md.converter_registry import registry
    from all2md.dependencies import check_version_requirement

    base_input_dir = _compute_base_input_dir(items, args.preserve_structure)

    registry.auto_discover()

    print("DRY RUN MODE - Showing what would be processed")
    print(f"Found {len(items)} input(s) to convert")
    print()

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
                        from all2md.dependencies import check_package_installed

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

    if args.rich:
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

                if args.collate:
                    output_str = str(Path(args.out)) if args.out else "stdout (collated)"
                else:
                    if len(file_info_list) == 1 and args.out and not args.output_dir:
                        output_str = str(Path(args.out))
                    elif args.output_dir:
                        target_format = getattr(args, "output_type", "markdown")
                        computed = _generate_output_path_for_item(
                            item,
                            Path(args.output_dir),
                            args.preserve_structure,
                            base_input_dir,
                            target_format,
                            info["index"],
                            dry_run=True,
                        )
                        output_str = str(computed)
                    else:
                        output_str = "stdout"

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

        except ImportError:
            args.rich = False

    if not args.rich:
        for info in file_info_list:
            item = info["item"]
            print(f"{item.display_name}")
            print(f"  Format: {info['detected_format'].upper()} ({info['detection_method']})")

            if info["converter_available"]:
                print("  Status: ready")
            else:
                issues_str = ", ".join(info["dependency_issues"]) or "dependency issues"
                print(f"  Status: missing requirements ({issues_str})")

            if args.collate:
                destination = str(Path(args.out)) if args.out else "stdout (collated)"
            else:
                if len(file_info_list) == 1 and args.out and not args.output_dir:
                    destination = str(Path(args.out))
                elif args.output_dir:
                    target_format = getattr(args, "output_type", "markdown")
                    generated = _generate_output_path_for_item(
                        item,
                        Path(args.output_dir),
                        args.preserve_structure,
                        base_input_dir,
                        target_format,
                        info["index"],
                        dry_run=True,
                    )
                    destination = str(generated)
                else:
                    destination = "stdout"

            print(f"  Output: {destination}")
            print()

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
) -> Tuple[int, Optional[ASTDocument], Optional[str]]:
    """Load an input item into an AST for collation."""
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
    from all2md.cli.progress import ProgressContext, SummaryRenderer

    collected_documents: List[ASTDocument] = []
    failures: List[Tuple[CLIInputItem, str, int]] = []

    use_rich = args.rich
    show_progress = args.progress or args.rich or len(items) > 1

    with ProgressContext(use_rich, show_progress, len(items), "Loading documents") as progress:
        for _offset, item in enumerate(items, start=1):
            progress.set_postfix(f"Processing {item.name}")
            exit_code, document, error = _convert_item_to_ast_for_collation(item, options, format_arg)

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

    target_format = args.output_type
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
    from all2md.converter_registry import registry

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
        Serializable transform specifications to rebuild in worker processes.

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

        if output_path:
            convert(
                source_value,
                output=output_path,
                source_format=cast(DocumentFormat, format_arg),
                target_format=cast(DocumentFormat, target_format),
                transforms=local_transforms,
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
    from all2md.cli.progress import ProgressContext, SummaryRenderer

    base_input_dir = _compute_base_input_dir(items, args.preserve_structure)

    try:
        should_use_rich = _should_use_rich_output(args)
        rich_dependency_error: Optional[str] = None
    except DependencyError as exc:
        should_use_rich = False
        rich_dependency_error = str(exc)

    if rich_dependency_error:
        print(f"Warning: {rich_dependency_error}", file=sys.stderr)

    target_format_default = getattr(args, "output_type", "markdown")

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

        if render_target == "markdown":
            markdown_content = to_markdown(
                item.raw_input,
                source_format=cast(DocumentFormat, format_arg),
                transforms=transforms,
                **effective_options,
            )

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
