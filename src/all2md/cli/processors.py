"""Specialized processing functions for all2md CLI.

This module contains focused processing functions extracted from the main()
function to improve maintainability and testability.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, TypedDict, cast

from all2md import convert, to_ast, to_markdown
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_INPUT_ERROR,
    EXIT_SUCCESS,
    DynamicCLIBuilder,
    get_exit_code_for_exception,
)
from all2md.constants import DocumentFormat
from all2md.converter_registry import registry
from all2md.exceptions import All2MdError, DependencyError


logger = logging.getLogger(__name__)

_OPTION_COMPAT_WARNINGS: set[str] = set()


class TransformSpec(TypedDict):
    """Serializable specification for reconstructing a transform instance."""

    name: str
    params: Dict[str, Any]


def _final_option_segment(remainder: str) -> str:
    """Return the terminal segment of a dot-delimited option path."""

    return remainder.split('.')[-1]


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
        if '.' not in key:
            filtered[key] = value
            continue

        prefix, remainder = key.split('.', 1)
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
    if parser_hint != 'auto':
        parser_format = parser_hint
    else:
        parser_format = _detect_format_for_path(input_path)

    renderer_format: str | None
    if renderer_hint and renderer_hint != 'auto':
        renderer_format = renderer_hint
    else:
        renderer_format = None

    return _filter_options_for_formats(options, parser_format, renderer_format)
def _process_items_with_progress(
        items: List[Any],
        process_fn: Any,
        args: argparse.Namespace,
        description: str,
        log_success_msg: Optional[Any] = None,
        log_error_msg: Optional[Any] = None
) -> Tuple[int, List[Any], List[Tuple[Any, str]]]:
    """Process items with unified progress tracking.

    This helper provides a consistent pattern for processing lists of items
    with progress tracking (rich/tqdm/plain) and error handling.

    Parameters
    ----------
    items : List[Any]
        List of items to process
    process_fn : Callable[[Any], int]
        Processing function that takes an item and returns exit code (0 = success)
        The function is responsible for its own error handling and should not raise.
    args : argparse.Namespace
        Command-line arguments containing rich, progress, skip_errors flags
    description : str
        Description for progress bar
    log_success_msg : Callable[[Any], str], optional
        Function to format success messages (takes item, returns message)
    log_error_msg : Callable[[Any, str], str], optional
        Function to format error messages (takes item and error, returns message)

    Returns
    -------
    Tuple[int, List[Any], List[Tuple[Any, str]]]
        Tuple of (max_exit_code, successful_items, failed_items_with_errors)

    Notes
    -----
    This function centralizes the pattern:
    1. Set up progress context (rich/tqdm/plain)
    2. Loop through items
    3. Process each item
    4. Update progress
    5. Handle errors (continue if skip_errors, otherwise break)
    6. Return results

    Examples
    --------
    >>> def process_file(file: Path) -> int:
    ...     # Process file, return 0 on success
    ...     return 0
    >>> max_code, successes, failures = _process_items_with_progress(
    ...     files,
    ...     process_file,
    ...     args,
    ...     "Converting files",
    ...     log_success_msg=lambda f: f"Processed {f}",
    ...     log_error_msg=lambda f, e: f"Failed {f}: {e}"
    ... )

    """
    from all2md.cli.progress import ProgressContext

    # Determine if progress should be shown
    show_progress = getattr(args, 'progress', False) or getattr(args, 'rich', False) or len(items) > 1

    successes: List[Any] = []
    failures: List[Tuple[Any, str]] = []
    max_exit_code = EXIT_SUCCESS

    # Use unified progress context
    use_rich = getattr(args, 'rich', False)
    with ProgressContext(use_rich, show_progress, len(items), description) as progress:
        for item in items:
            # Process item (should return exit code)
            exit_code = process_fn(item)

            if exit_code == EXIT_SUCCESS:
                successes.append(item)
                if log_success_msg:
                    msg = log_success_msg(item)
                    progress.log(msg, level='success')
            else:
                # Item failed - error message should have been set by process_fn
                # For now, we track it generically
                failures.append((item, "Processing failed"))
                max_exit_code = max(max_exit_code, exit_code)

                if log_error_msg:
                    msg = log_error_msg(item, "Processing failed")
                    progress.log(msg, level='error')

                # Check if we should continue or break
                if not getattr(args, 'skip_errors', False):
                    break

            progress.update()

    return max_exit_code, successes, failures


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
            converter_name='rich-output',
            missing_packages=[('rich', '')],
            message=(
                "Rich output requires the optional 'rich' dependency. "
                "Install with: pip install all2md[rich]"
            ),
        )

    # Force rich output regardless of TTY if explicitly requested
    if hasattr(args, 'force_rich') and args.force_rich:
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

    if hasattr(args, 'rich_code_theme') and args.rich_code_theme:
        kwargs['code_theme'] = args.rich_code_theme

    if hasattr(args, 'rich_inline_code_theme') and args.rich_inline_code_theme:
        kwargs['inline_code_theme'] = args.rich_inline_code_theme

    if hasattr(args, 'rich_hyperlinks'):
        kwargs['hyperlinks'] = args.rich_hyperlinks

    if hasattr(args, 'rich_justify') and args.rich_justify:
        kwargs['justify'] = args.rich_justify

    return kwargs


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
    import platform
    import pydoc

    # Check if using Rich formatting on Windows/WSL
    # Plain text paging works fine on Windows, but Rich ANSI codes don't display well
    if is_rich:
        system = platform.system()
        is_windows_or_wsl = False

        if system == 'Windows':
            is_windows_or_wsl = True
        elif system == 'Linux':
            # Check if running under WSL
            try:
                with open('/proc/version', 'r') as f:
                    if 'microsoft' in f.read().lower():
                        is_windows_or_wsl = True
            except Exception:
                pass

        if is_windows_or_wsl:
            print(
                "Warning: --pager with --rich is not well supported on Windows/WSL.",
                file=sys.stderr
            )
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
    if not hasattr(parsed_args, 'transform_specs'):
        parsed_args.transform_specs = []  # type: ignore[attr-defined]

    if not hasattr(parsed_args, 'transforms') or not parsed_args.transforms:
        parsed_args.transform_specs = []  # type: ignore[attr-defined]
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
            if param_spec.cli_flag:
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
                if param_spec.cli_flag:
                    print(f"Use {param_spec.cli_flag} to specify this parameter", file=sys.stderr)
                raise argparse.ArgumentTypeError(
                    f"Transform '{transform_name}' missing required parameter: {param_name}"
                )

        # Record serializable transform spec for reuse (e.g., across processes)
        transform_specs.append({'name': transform_name, 'params': dict(params)})

        # Create transform instance
        try:
            transform = metadata.create_instance(**params)
            transform_instances.append(transform)
        except Exception as e:
            print(f"Error creating transform '{transform_name}': {e}", file=sys.stderr)
            raise argparse.ArgumentTypeError(f"Failed to create transform: {transform_name}") from e

    parsed_args.transform_specs = transform_specs  # type: ignore[attr-defined]

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

    from all2md.transforms import registry as transform_registry

    instances: list[Any] = []
    for spec in transform_specs:
        name = spec['name']
        params = spec.get('params', {})
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
    import sys

    # Track which preset is being used (highest security wins)
    preset_used = None

    if parsed_args.strict_html_sanitize:
        preset_used = "strict-html-sanitize"
        # Strict HTML sanitization preset - use format-qualified keys
        # HTML options
        options['html.strip_dangerous_elements'] = True
        options['html.network.allow_remote_fetch'] = False
        options['html.local_files.allow_local_files'] = False
        options['html.local_files.allow_cwd_files'] = False
        # MHTML options (shares local file access settings)
        options['mhtml.local_files.allow_local_files'] = False
        options['mhtml.local_files.allow_cwd_files'] = False
        # EML options (for HTML content in emails)
        options['eml.html_network.allow_remote_fetch'] = False

    if parsed_args.safe_mode:
        preset_used = "safe-mode"
        # Balanced security for untrusted input
        # HTML options
        options['html.strip_dangerous_elements'] = True
        options['html.network.allow_remote_fetch'] = True
        options['html.network.require_https'] = True
        options['html.local_files.allow_local_files'] = False
        options['html.local_files.allow_cwd_files'] = False
        # MHTML options
        options['mhtml.local_files.allow_local_files'] = False
        options['mhtml.local_files.allow_cwd_files'] = False
        # EML options
        options['eml.html_network.allow_remote_fetch'] = True
        options['eml.html_network.require_https'] = True

    if parsed_args.paranoid_mode:
        preset_used = "paranoid-mode"
        # Maximum security - most restrictive settings
        # HTML options
        options['html.strip_dangerous_elements'] = True
        options['html.network.allow_remote_fetch'] = False  # Block all remote fetches
        options['html.max_asset_size_bytes'] = 5 * 1024 * 1024  # 5MB
        options['html.local_files.allow_local_files'] = False
        options['html.local_files.allow_cwd_files'] = False
        # MHTML options
        options['mhtml.local_files.allow_local_files'] = False
        options['mhtml.local_files.allow_cwd_files'] = False
        # EML options
        options['eml.html_network.allow_remote_fetch'] = False  # Block all remote fetches
        options['eml.max_asset_size_bytes'] = 5 * 1024 * 1024  # 5MB
        # Base options (no format prefix - applies to all formats)
        options['max_asset_size_bytes'] = 5 * 1024 * 1024  # 5MB (reduced from default 20MB)

    # Show warning if preset is used
    if preset_used:
        print(f"Security preset applied: {preset_used}", file=sys.stderr)
        print("Note: Individual security flags can override preset values if specified explicitly.", file=sys.stderr)

    return options


def setup_and_validate_options(parsed_args: argparse.Namespace) -> Tuple[Dict[str, Any], str, Optional[list]]:
    """Set up conversion options and build transforms.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    Tuple[Dict[str, Any], str, Optional[list]]
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
    env_config_path = os.environ.get('ALL2MD_CONFIG')

    # Priority order:
    # 1. Explicit --config flag
    # 2. ALL2MD_CONFIG environment variable
    # 3. Auto-discovered config (.all2md.toml or .all2md.json in cwd or home)
    explicit_config_path = getattr(parsed_args, 'config', None)

    try:
        config_from_file = load_config_with_priority(
            explicit_path=explicit_config_path,
            env_var_path=env_config_path
        )
    except argparse.ArgumentTypeError as e:
        print(f"Error loading configuration file: {e}", file=sys.stderr)
        raise

    # Apply preset if specified (preset is applied to config, then CLI args override)
    if hasattr(parsed_args, 'preset') and parsed_args.preset:
        try:
            config_from_file = apply_preset(parsed_args.preset, config_from_file)
        except ValueError as e:
            print(f"Error applying preset: {e}", file=sys.stderr)
            raise argparse.ArgumentTypeError(str(e)) from e

    # Map CLI arguments to options (CLI args take highest priority)
    builder = DynamicCLIBuilder()
    options = builder.map_args_to_options(parsed_args, config_from_file)
    format_arg = parsed_args.format if parsed_args.format != "auto" else "auto"

    # Apply security presets if specified
    options = apply_security_preset(parsed_args, options)

    # Build transform instances if --transform was used
    transforms = build_transform_instances(parsed_args)

    return options, format_arg, transforms


def validate_arguments(parsed_args: argparse.Namespace, files: Optional[List[Path]] = None) -> bool:
    """Validate command line arguments and file inputs.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    files : List[Path], optional
        List of input files to validate

    Returns
    -------
    bool
        True if arguments are valid, False otherwise

    Side Effects
    ------------
    Prints error messages to stderr for invalid arguments

    """
    # Validate attachment options
    if parsed_args.attachment_output_dir and parsed_args.attachment_mode != "download":
        print("Warning: --attachment-output-dir specified but attachment mode is "
              f"'{parsed_args.attachment_mode}' (not 'download')", file=sys.stderr)

    # Validate output directory if specified
    if parsed_args.output_dir:
        output_dir_path = Path(parsed_args.output_dir)
        if output_dir_path.exists() and not output_dir_path.is_dir():
            print(f"Error: --output-dir must be a directory, not a file: {parsed_args.output_dir}",
                  file=sys.stderr)
            return False

    # For multi-file, --out becomes --output-dir
    if files and len(files) > 1 and parsed_args.out and not parsed_args.output_dir:
        print("Warning: --out is ignored for multiple files. Use --output-dir instead.",
              file=sys.stderr)

    return True


def process_stdin(
        parsed_args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process input from stdin.

    Parameters
    ----------
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
        Exit code (0 for success, see constants.py for complete exit code list)

    """
    # Read from stdin
    try:
        stdin_data = sys.stdin.buffer.read()
        if not stdin_data:
            print("Error: No data received from stdin", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error reading from stdin: {e}", file=sys.stderr)
        return 1

    # Process stdin data
    input_source = stdin_data

    try:
        effective_options = prepare_options_for_execution(
            options,
            None,
            format_arg,
            'markdown',
        )

        markdown_content = to_markdown(
            input_source,
            source_format=cast(DocumentFormat, format_arg),
            transforms=transforms,
            **effective_options
        )

        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"Converted stdin -> {output_path}", file=sys.stderr)
        else:
            if parsed_args.pager:
                try:
                    try:
                        use_rich_output = _should_use_rich_output(parsed_args)
                        rich_error: str | None = None
                    except DependencyError as exc:
                        use_rich_output = False
                        rich_error = str(exc)

                    if use_rich_output:
                        from rich.console import Console
                        from rich.markdown import Markdown
                        console = Console()
                        # Get Rich markdown kwargs from CLI args
                        rich_kwargs = _get_rich_markdown_kwargs(parsed_args)
                        # Capture Rich output with ANSI codes
                        with console.capture() as capture:
                            console.print(Markdown(markdown_content, **rich_kwargs))
                        content_to_page = capture.get()
                        is_rich = True
                    else:
                        content_to_page = markdown_content
                        is_rich = False

                    if rich_error:
                        print(f"Warning: {rich_error}", file=sys.stderr)

                    # Try to page the content using available pager
                    if not _page_content(content_to_page, is_rich=is_rich):
                        # If paging fails, just print the content
                        print(content_to_page)
                except ImportError:
                    msg = "Warning: Rich library not installed. Install with: pip install all2md[rich]"
                    print(msg, file=sys.stderr)
                    print(markdown_content)
            else:
                print(markdown_content)

        return 0

    except Exception as e:

        exit_code = get_exit_code_for_exception(e)

        # Print appropriate error message
        if isinstance(e, (DependencyError, ImportError)):
            print(f"Missing dependency: {e}", file=sys.stderr)
            print("Install required dependencies with: pip install all2md[full]", file=sys.stderr)
        elif isinstance(e, All2MdError):
            print(f"Error: {e}", file=sys.stderr)
        else:
            print(f"Unexpected error: {e}", file=sys.stderr)

        return exit_code


def process_multi_file(
        files: List[Path],
        parsed_args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process multiple files with appropriate output handling.

    Parameters
    ----------
    files : List[Path]
        List of files to process
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
    # Import processing functions

    # Handle detect-only mode
    if parsed_args.detect_only:
        return process_detect_only(files, parsed_args, format_arg)

    # Handle dry run mode
    if parsed_args.dry_run:
        return process_dry_run(files, parsed_args, format_arg)

    try:
        should_use_rich = _should_use_rich_output(parsed_args)
        rich_dependency_error: Optional[str] = None
    except DependencyError as exc:
        should_use_rich = False
        rich_dependency_error = str(exc)

    if rich_dependency_error:
        print(f"Warning: {rich_dependency_error}", file=sys.stderr)

    # Process single file (without rich/progress)
    # This includes cases where --rich is set but TTY check fails (piped output)
    if len(files) == 1 and not should_use_rich and not parsed_args.progress:
        file = files[0]

        # Determine output path and target format
        output_path: Optional[Path] = None
        target_format = 'markdown'  # default

        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Auto-detect target format from output filename if --output-type not explicitly provided
            provided_args: set[str] = getattr(parsed_args, '_provided_args', set())
            if 'output_type' not in provided_args:
                from all2md.converter_registry import registry
                detected = registry.detect_format(output_path)
                target_format = detected if detected != 'txt' else 'markdown'
            else:
                target_format = parsed_args.output_type
        elif parsed_args.output_dir:
            target_format = getattr(parsed_args, 'output_type', 'markdown')
            output_path = generate_output_path(
                file, Path(parsed_args.output_dir), False, None, target_format=target_format
            )
        else:
            target_format = 'markdown'  # stdout, always markdown

        # Handle pager for stdout output
        if output_path is None and parsed_args.pager:
            try:
                effective_options = prepare_options_for_execution(
                    options,
                    file,
                    format_arg,
                    'markdown',
                )

                # Convert the document
                markdown_content = to_markdown(
                    file,
                    source_format=cast(DocumentFormat, format_arg),
                    transforms=transforms,
                    **effective_options
                )

                # Display with pager
                if should_use_rich:
                    from rich.console import Console
                    from rich.markdown import Markdown
                    console = Console()
                    # Get Rich markdown kwargs from CLI args
                    rich_kwargs = _get_rich_markdown_kwargs(parsed_args)
                    # Capture Rich output with ANSI codes
                    with console.capture() as capture:
                        console.print(Markdown(markdown_content, **rich_kwargs))
                    content_to_page = capture.get()
                    is_rich = True
                else:
                    content_to_page = markdown_content
                    is_rich = False

                # Try to page the content using available pager
                if not _page_content(content_to_page, is_rich=is_rich):
                    # If paging fails, just print the content
                    print(content_to_page)

                return 0
            except ImportError:
                print("Warning: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
                # Fall through to regular conversion
            except Exception as e:

                exit_code = get_exit_code_for_exception(e)
                if isinstance(e, (DependencyError, ImportError)):
                    print(f"Missing dependency: {e}", file=sys.stderr)
                else:
                    print(f"Error: {e}", file=sys.stderr)
                return exit_code

        transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(parsed_args, 'transform_specs', None))
        exit_code, file_str, error = convert_single_file(
            file,
            output_path,
            options,
            format_arg,
            transforms,
            False,
            target_format,
            transform_specs_for_workers,
        )

        if exit_code == 0:
            if output_path:
                print(f"Converted {file} -> {output_path}", file=sys.stderr)
            return 0
        else:
            print(f"Error: {error}", file=sys.stderr)
            return exit_code

    # If --zip is specified, skip disk writes and package directly to zip
    if parsed_args.zip:
        return _create_output_package(parsed_args, files, options, format_arg, transforms)

    # Check for merge-from-list mode (takes precedence over collate)
    if hasattr(parsed_args, 'merge_from_list') and parsed_args.merge_from_list:
        return process_merge_from_list(parsed_args, options, format_arg, transforms)

    # Otherwise, process files normally to disk
    if parsed_args.collate:
        exit_code = process_files_collated(files, parsed_args, options, format_arg, transforms)
    else:
        # Use unified processing function for all modes (rich/progress/simple)
        # This consolidates process_with_rich_output, process_with_progress_bar, and process_files_simple
        exit_code = process_files_unified(files, parsed_args, options, format_arg, transforms)

    return exit_code


def _create_output_package(
        parsed_args: argparse.Namespace,
        input_files: List[Path],
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Create output package (zip) after successful conversion.

    Converts files directly to zip archive using in-memory BytesIO buffers,
    eliminating intermediate disk I/O. Supports all output formats and processes
    files incrementally to minimize memory usage.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    input_files : List[Path]
        List of input files to convert and package
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
        target_format = getattr(parsed_args, 'output_type', 'markdown')

        # Determine zip path
        if parsed_args.zip == 'auto':
            # Use output_dir name if available, otherwise use generic name
            if hasattr(parsed_args, 'output_dir') and parsed_args.output_dir:
                output_dir_name = Path(parsed_args.output_dir).name
                zip_path = Path(f"{output_dir_name}.zip")
            else:
                zip_path = Path("output.zip")
        else:
            zip_path = Path(parsed_args.zip)

        # Create the zip package directly from conversions
        # Pass user-specified options and transforms
        created_zip = create_package_from_conversions(
            input_files=input_files,
            zip_path=zip_path,
            target_format=target_format,
            options=options,
            transforms=transforms,
            source_format=format_arg
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

        with open(json_path, 'r', encoding='utf-8') as f:
            options = json.load(f)

        if not isinstance(options, dict):
            raise argparse.ArgumentTypeError(
                f"Options JSON file must contain a JSON object, got {type(options).__name__}")

        return options

    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"Invalid JSON in options file {json_file_path}: {e}") from e
    except Exception as e:
        raise argparse.ArgumentTypeError(f"Error reading options file {json_file_path}: {e}") from e


# TODO: what is this for? Is it needed?
def merge_exclusion_patterns_from_json(
        parsed_args: argparse.Namespace,
        json_options: dict
) -> Optional[List[str]]:
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
    if 'exclude' in json_options and parsed_args.exclude is None:
        return json_options['exclude']
    return None


def parse_merge_list(list_path: Path | str, separator: str = '\t') -> List[Tuple[Path, Optional[str]]]:
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

        >>> echo "chapter1.pdf\\tIntro" | all2md --merge-from-list - --out book.md

    """
    try:
        # Check if reading from stdin
        if list_path == '-' or str(list_path) == '-':
            # Read from stdin
            lines = sys.stdin.readlines()
            # Resolve paths relative to current working directory
            list_dir = Path.cwd()
        else:
            # Read from file
            list_path = Path(list_path)
            if not list_path.exists():
                raise argparse.ArgumentTypeError(f"Merge list file does not exist: {list_path}")

            with open(list_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Resolve paths relative to list file directory
            list_dir = list_path.parent

        # Parse entries
        entries: List[Tuple[Path, Optional[str]]] = []

        for line_num, line in enumerate(lines, 1):
            # Strip whitespace
            line = line.strip()

            # Skip comments and blank lines
            if not line or line.startswith('#'):
                continue

            # Split by separator
            parts = line.split(separator, 1)
            file_path_str = parts[0].strip()

            # Get section title if provided
            section_title = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None

            # Skip if second part is a comment
            if section_title and section_title.startswith('#'):
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
                    f"File not found in merge list (line {line_num}): {file_path_str}\n"
                    f"Resolved path: {file_path}"
                )

            entries.append((file_path, section_title))

        if not entries:
            source_desc = "stdin" if (list_path == '-' or str(list_path) == '-') else str(list_path)
            raise argparse.ArgumentTypeError(f"Merge list is empty or contains no valid entries: {source_desc}")

        return entries

    except argparse.ArgumentTypeError:
        raise
    except Exception as e:
        source_desc = "stdin" if (list_path == '-' or str(list_path) == '-') else str(list_path)
        raise argparse.ArgumentTypeError(f"Error reading merge list from {source_desc}: {e}") from e


def process_merge_from_list(
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
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
        separator = args.list_separator if hasattr(args, 'list_separator') else '\t'

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
                section_heading = Heading(
                    level=1,
                    content=[Text(content=section_title)]
                )
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
                progress.log(f"[OK] Processed {file_path}", level='success')
            else:
                error_msg = failed[-1][1] if failed else "Unknown error"
                progress.log(f"[ERROR] {file_path}: {error_msg}", level='error')
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
            title=args.toc_title if hasattr(args, 'toc_title') else "Table of Contents",
            max_depth=args.toc_depth if hasattr(args, 'toc_depth') else 3,
            position=args.toc_position if hasattr(args, 'toc_position') else "top"
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
            with open(output_path, 'w', encoding='utf-8') as f:
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


def process_detect_only(
        files: List[Path],
        args: argparse.Namespace,
        format_arg: str
) -> int:
    """Process files in detect-only mode - show format detection without conversion plan.

    Parameters
    ----------
    files : List[Path]
        List of files to detect formats for
    args : argparse.Namespace
        Command-line arguments
    format_arg : str
        Format specification

    Returns
    -------
    int
        Exit code (0 for success, 1 if any detection issues)

    """
    from all2md.converter_registry import registry
    from all2md.dependencies import check_version_requirement

    # Auto-discover parsers
    registry.auto_discover()

    print("DETECT-ONLY MODE - Format Detection Results")
    print(f"Analyzing {len(files)} file(s)")
    print()

    # Gather detection info
    detection_results: list[dict[str, Any]] = []
    any_issues = False

    transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(args, 'transform_specs', None))

    for file in files:
        # Detect format
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(file)

            # Determine detection method
            metadata_list = registry.get_format_info(detected_format)
            metadata = metadata_list[0] if metadata_list else None
            if metadata and file.suffix.lower() in metadata.extensions:
                detection_method = "file extension"
            else:
                # Check MIME type
                import mimetypes
                mime_type, _ = mimetypes.guess_type(str(file))
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
                                (install_name, 'version mismatch', installed_version, version_spec)
                            )
                        else:
                            dependency_status.append((install_name, 'missing', None, version_spec))
                    else:
                        dependency_status.append((install_name, 'ok', installed_version, version_spec))
                else:
                    from all2md.dependencies import check_package_installed
                    # Use import_name for import checking
                    if not check_package_installed(import_name):
                        converter_available = False
                        any_issues = True
                        dependency_status.append((install_name, 'missing', None, None))
                    else:
                        dependency_status.append((install_name, 'ok', None, None))

        detection_results.append({
            'file': file,
            'format': detected_format,
            'method': detection_method,
            'available': converter_available,
            'deps': dependency_status,
            'metadata': converter_metadata,
        })

    # Display results
    if args.rich:
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()

            # Main detection table
            table = Table(title="Format Detection Results")
            table.add_column("File", style="cyan", no_wrap=False)
            table.add_column("Detected Format", style="yellow")
            table.add_column("Detection Method", style="magenta")
            table.add_column("Converter Status", style="white")

            for result in detection_results:
                if result['available']:
                    status = "[green][OK] Available[/green]"
                else:
                    status = "[red][X] Unavailable[/red]"

                table.add_row(
                    str(result['file']),
                    result['format'].upper(),
                    result['method'],
                    status
                )

            console.print(table)

            # Show dependency details if there are issues
            if any_issues:
                console.print("\n[bold yellow]Dependency Issues:[/bold yellow]")
                for result in detection_results:
                    if not result['available']:
                        console.print(f"\n[cyan]{result['file']}[/cyan] ({result['format'].upper()}):")
                        for pkg_name, status, installed, required in result['deps']:
                            if status == 'missing':
                                console.print(f"  [red][X] {pkg_name} - Not installed[/red]")
                            elif status == 'version mismatch':
                                msg = f"  [yellow][!] {pkg_name} - Version mismatch"
                                msg += f" (requires {required}, installed: {installed})[/yellow]"
                                console.print(msg)

                        if result['metadata']:
                            install_cmd = result['metadata'].get_install_command()
                            console.print(f"  [dim]Install: {install_cmd}[/dim]")

        except ImportError:
            # Fall back to plain text
            args.rich = False

    if not args.rich:
        # Plain text output
        for i, result in enumerate(detection_results, 1):
            status = "[OK]" if result['available'] else "[X]"
            print(f"{i:3d}. {status} {result['file']}")
            print(f"     Format: {result['format'].upper()}")
            print(f"     Detection: {result['method']}")

            if result['deps']:
                print("     Dependencies:")
                for pkg_name, status_str, installed, required in result['deps']:
                    if status_str == 'ok':
                        version_info = f" ({installed})" if installed else ""
                        print(f"       [OK] {pkg_name}{version_info}")
                    elif status_str == 'missing':
                        print(f"       [MISSING] {pkg_name}")
                    elif status_str == 'version mismatch':
                        print(f"       [MISMATCH] {pkg_name} (requires {required}, installed: {installed})")

                if not result['available'] and result['metadata']:
                    install_cmd = result['metadata'].get_install_command()
                    print(f"     Install: {install_cmd}")
            else:
                print("     Dependencies: None required")

            print()

    print(f"\nTotal files analyzed: {len(detection_results)}")
    if any_issues:
        unavailable_count = sum(1 for r in detection_results if not r['available'])
        print(f"Files with unavailable parsers: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected parsers are available")
        return 0


def process_dry_run(
        files: List[Path],
        args: argparse.Namespace,
        format_arg: str
) -> int:
    """Process files in dry run mode - show what would be done without doing it.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
    format_arg : str
        Format specification

    Returns
    -------
    int
        Exit code (always 0 for dry run)

    """
    from all2md.converter_registry import registry
    from all2md.dependencies import check_version_requirement

    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    # Auto-discover parsers for format detection
    registry.auto_discover()

    print("DRY RUN MODE - Showing what would be processed")
    print(f"Found {len(files)} file(s) to convert")
    print()

    # Gather format detection information for each file
    file_info_list: list[dict[str, Any]] = []
    for file in files:
        # Detect format for this file
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(file)
            # Try to determine detection method
            all_extensions = []
            for fmt_name in registry.list_formats():
                fmt_info_list = registry.get_format_info(fmt_name)
                if fmt_info_list:
                    # Collect extensions from all converters for this format
                    for fmt_info in fmt_info_list:
                        all_extensions.extend(fmt_info.extensions)
            if file.suffix.lower() in all_extensions:
                detection_method = "extension"
            else:
                detection_method = "content analysis"

        # Get converter metadata
        converter_metadata_list = registry.get_format_info(detected_format)
        converter_metadata = converter_metadata_list[0] if converter_metadata_list else None

        # Check if converter is available using context-aware dependency checking
        converter_available = True
        dependency_issues = []
        if converter_metadata:
            # Use context-aware checking to get accurate dependency requirements for this file
            required_packages = converter_metadata.get_required_packages_for_content(
                content=None,
                input_data=str(file)
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

        file_info_list.append({
            'file': file,
            'detected_format': detected_format,
            'detection_method': detection_method,
            'converter_available': converter_available,
            'dependency_issues': dependency_issues,
            'converter_metadata': converter_metadata,
        })

    if args.rich:
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title="Dry Run - Planned Conversions")
            table.add_column("Input File", style="cyan", no_wrap=False)
            table.add_column("Output", style="green", no_wrap=False)
            table.add_column("Format", style="yellow")
            table.add_column("Detection", style="magenta")
            table.add_column("Status", style="white")

            for info in file_info_list:
                file = info['file']

                if args.collate:
                    # For collation, all files go to one output
                    if args.out:
                        output_str = str(Path(args.out))
                    else:
                        output_str = "stdout (collated)"
                else:
                    # Individual file processing
                    if len(file_info_list) == 1 and args.out and not args.output_dir:
                        output_path = Path(args.out)
                    else:
                        target_format = getattr(args, 'output_type', 'markdown')
                        output_path = generate_output_path(
                            file,
                            Path(args.output_dir) if args.output_dir else None,
                            args.preserve_structure,
                            base_input_dir,
                            dry_run=True,
                            target_format=target_format
                        )
                    output_str = str(output_path)

                # Format status with color coding
                if info['converter_available']:
                    status = "[green][OK] Ready[/green]"
                else:
                    issues = ", ".join(info['dependency_issues'][:2])
                    if len(info['dependency_issues']) > 2:
                        issues += "..."
                    status = f"[red][X] {issues}[/red]"

                table.add_row(
                    str(file),
                    output_str,
                    info['detected_format'].upper(),
                    info['detection_method'],
                    status
                )

            console.print(table)

        except ImportError:
            # Fallback to simple output
            args.rich = False

    if not args.rich:
        # Simple text output
        for i, info in enumerate(file_info_list, 1):
            file = info['file']

            if args.collate:
                if args.out:
                    output_str = f" -> {args.out} (collated)"
                else:
                    output_str = " -> stdout (collated)"
            else:
                if len(file_info_list) == 1 and args.out and not args.output_dir:
                    output_path = Path(args.out)
                else:
                    target_format = getattr(args, 'output_type', 'markdown')
                    output_path = generate_output_path(
                        file,
                        Path(args.output_dir) if args.output_dir else None,
                        args.preserve_structure,
                        base_input_dir,
                        dry_run=True,
                        target_format=target_format
                    )
                output_str = f" -> {output_path}"

            # Format detection and status
            status = "[OK]" if info['converter_available'] else "[X]"
            format_str = f"[{info['detected_format'].upper()}, {info['detection_method']}]"

            print(f"{i:3d}. {status} {file}{output_str}")
            print(f"     Format: {format_str}")

            if not info['converter_available']:
                issues_str = ", ".join(info['dependency_issues'])
                print(f"     Issues: {issues_str}")

            print()  # Blank line between files

    print()
    print("Options that would be used:")
    if args.format != "auto":
        print(f"  Format: {args.format}")
    if args.recursive:
        print("  Recursive directory processing: enabled")
    # Check if parallel was explicitly provided
    parallel_provided = hasattr(args, '_provided_args') and 'parallel' in args._provided_args
    if parallel_provided and args.parallel is None:
        worker_count = os.cpu_count() or 'auto'
        print(f"  Parallel processing: {worker_count} workers (auto-detected)")
    elif isinstance(args.parallel, int) and args.parallel != 1:
        print(f"  Parallel processing: {args.parallel} workers")
    if args.preserve_structure:
        print("  Preserve directory structure: enabled")
    if args.collate:
        print("  Collate multiple files: enabled")
    if args.exclude:
        print(f"  Exclusion patterns: {', '.join(args.exclude)}")

    print()
    print("No files were actually converted (dry run mode).")
    return 0


def convert_single_file_for_collation(
        input_path: Path,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None,
        file_separator: str = "\n\n---\n\n"
) -> Tuple[int, str, Optional[str]]:
    """Convert a single file to markdown for collation.

    Parameters
    ----------
    input_path : Path
        Input file path
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform instances to apply
    file_separator : str
        Separator to add between files

    Returns
    -------
    Tuple[int, str, Optional[str]]
        Exit code (0 for success), markdown content, and error message if failed

    """
    try:
        effective_options = prepare_options_for_execution(
            options,
            input_path,
            format_arg,
            'markdown',
        )

        # Convert the document
        markdown_content = to_markdown(
            input_path,
            source_format=cast(DocumentFormat, format_arg),
            transforms=transforms,
            **effective_options
        )

        # Add file header and separator
        header = f"# File: {input_path.name}\n\n"
        content_with_header = header + markdown_content

        return EXIT_SUCCESS, content_with_header, None

    except Exception as e:
        exit_code = get_exit_code_for_exception(e)
        error_msg = str(e)
        if isinstance(e, ImportError):
            error_msg = f"Missing dependency: {e}"
        elif not isinstance(e, All2MdError):
            error_msg = f"Unexpected error: {e}"
        return exit_code, "", error_msg


def process_files_collated(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process files and collate them into a single output.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform functions to apply

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)

    """
    collated_content = []
    failed = []
    file_separator = "\n\n---\n\n"
    max_exit_code = EXIT_SUCCESS

    # Determine output path
    output_path = None
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Helper function to process files
    def process_file(file: Path) -> int:
        """Process a single file for collation.

        Returns
        -------
        int
            Exit code (0 for success)

        """
        nonlocal max_exit_code
        exit_code, content, error = convert_single_file_for_collation(
            file, options, format_arg, transforms, file_separator
        )
        if exit_code == EXIT_SUCCESS:
            collated_content.append(content)
        else:
            failed.append((file, error))
            max_exit_code = max(max_exit_code, exit_code)
        return exit_code

    # Use unified progress tracking with ProgressContext
    from all2md.cli.progress import ProgressContext

    show_progress = args.progress or args.rich or len(files) > 1
    use_rich = args.rich

    with ProgressContext(use_rich, show_progress, len(files), "Converting and collating files") as progress:
        for file in files:
            progress.set_postfix(f"Processing {file.name}")
            exit_code = process_file(file)

            if exit_code == EXIT_SUCCESS:
                progress.log(f"[OK] Processed {file}", level='success')
            else:
                error_msg = failed[-1][1] if failed else "Unknown error"
                progress.log(f"[ERROR] {file}: {error_msg}", level='error')
                if not args.skip_errors:
                    break

            progress.update()

    # Output the collated result
    if collated_content:
        final_content = file_separator.join(collated_content)

        if output_path:
            output_path.write_text(final_content, encoding="utf-8")
            print(f"Collated {len(collated_content)} files -> {output_path}", file=sys.stderr)
        else:
            print(final_content)

    # Summary using unified renderer
    if not args.no_summary:
        from all2md.cli.progress import SummaryRenderer
        renderer = SummaryRenderer(use_rich=args.rich)
        renderer.render_conversion_summary(
            successful=len(collated_content),
            failed=len(failed),
            total=len(files),
            title="Collation Summary"
        )

    return max_exit_code


def generate_output_path(
        input_file: Path,
        output_dir: Optional[Path] = None,
        preserve_structure: bool = False,
        base_input_dir: Optional[Path] = None,
        dry_run: bool = False,
        target_format: str = "markdown"
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
        input_path: Path,
        output_path: Optional[Path],
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None,
        show_progress: bool = False,
        target_format: str = 'markdown',
        transform_specs: Optional[list[TransformSpec]] = None
) -> Tuple[int, str, Optional[str]]:
    """Convert a single file to the specified target format.

    Parameters
    ----------
    input_path : Path
        Input file path
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

        renderer_hint = target_format
        if renderer_hint == 'auto' and output_path:
            try:
                detected_target = registry.detect_format(output_path)
                if detected_target and detected_target != 'txt':
                    renderer_hint = detected_target
            except Exception:  # pragma: no cover - best effort
                renderer_hint = 'auto'

        effective_options = prepare_options_for_execution(
            options,
            input_path,
            format_arg,
            renderer_hint,
        )

        # Convert the document using the convert() API for bidirectional conversion
        if output_path:
            # Write to file - convert() handles the target format correctly
            convert(
                input_path,
                output=output_path,
                source_format=cast(DocumentFormat, format_arg),
                target_format=cast(DocumentFormat, target_format),
                transforms=local_transforms,
                **effective_options
            )
            return EXIT_SUCCESS, str(input_path), None
        else:
            # Output to stdout - only markdown is supported for stdout
            result = convert(
                input_path,
                output=None,
                source_format=cast(DocumentFormat, format_arg),
                target_format='markdown',
                transforms=local_transforms,
                **effective_options
            )
            # convert() returns str for markdown, bytes for binary formats
            if isinstance(result, bytes):
                # This shouldn't happen for markdown, but handle it just in case
                print(result.decode('utf-8', errors='replace'))
            else:
                print(result)
            return EXIT_SUCCESS, str(input_path), None

    except Exception as e:
        exit_code = get_exit_code_for_exception(e)
        error_msg = str(e)
        if isinstance(e, ImportError):
            error_msg = f"Missing dependency: {e}"
        elif not isinstance(e, All2MdError):
            error_msg = f"Unexpected error: {e}"
        return exit_code, str(input_path), error_msg


def process_files_unified(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process files with unified progress tracking (rich/tqdm/plain).

    This function consolidates the functionality of process_with_rich_output,
    process_with_progress_bar, and process_files_simple into a single
    implementation using the unified ProgressContext and SummaryRenderer.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
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
    from all2md.cli.progress import ProgressContext, SummaryRenderer

    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    try:
        should_use_rich = _should_use_rich_output(args)
        rich_dependency_error: Optional[str] = None
    except DependencyError as exc:
        should_use_rich = False
        rich_dependency_error = str(exc)

    if rich_dependency_error:
        print(f"Warning: {rich_dependency_error}", file=sys.stderr)

    # Special case: single file to stdout with rich formatting
    if len(files) == 1 and not args.out and not args.output_dir:
        file = files[0]

        # Check if we should use rich output for this
        if should_use_rich:
            # Import rich components
            from rich.markdown import Markdown
            try:
                from rich.console import Console
                console = Console()

                # Show progress during conversion
                with ProgressContext(True, True, 1, f"Converting {file.name}") as progress:
                    try:
                        # Convert the document
                        effective_options = prepare_options_for_execution(
                            options,
                            file,
                            format_arg,
                            'markdown',
                        )
                        markdown_content = to_markdown(
                            file,
                            source_format=cast(Any, format_arg),
                            transforms=transforms,
                            **effective_options
                        )
                        progress.update()
                    except Exception as e:
                        exit_code = get_exit_code_for_exception(e)
                        error = str(e)
                        if isinstance(e, ImportError):
                            error = f"Missing dependency: {e}"
                        elif not isinstance(e, All2MdError):
                            error = f"Unexpected error: {e}"
                        progress.log(f"[ERROR] {file}: {error}", level='error')
                        return exit_code

                # After progress completes, print the rich-formatted output
                rich_kwargs = _get_rich_markdown_kwargs(args)
                console.print(Markdown(markdown_content, **rich_kwargs))
                return EXIT_SUCCESS

            except ImportError:
                # Fall back to plain output
                pass

        # Plain output (no rich)
        try:
            effective_options = prepare_options_for_execution(
                options,
                file,
                format_arg,
                'markdown',
            )
            markdown_content = to_markdown(
                file,
                source_format=cast(Any, format_arg),
                transforms=transforms,
                **effective_options
            )
            print(markdown_content)
            return EXIT_SUCCESS
        except Exception as e:
            exit_code = get_exit_code_for_exception(e)
            print(f"Error: {e}", file=sys.stderr)
            return exit_code

    # Multi-file processing
    results: list[tuple[Path, Path | None]] = []
    failed: list[tuple[Path, str | None]] = []
    max_exit_code = EXIT_SUCCESS

    # Determine if progress should be shown
    show_progress = args.progress or (should_use_rich and args.rich) or len(files) > 1
    use_rich = should_use_rich

    transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(args, 'transform_specs', None))

    # Check if parallel processing is enabled
    use_parallel = (
        (hasattr(args, '_provided_args') and 'parallel' in args._provided_args and args.parallel is None) or
        (isinstance(args.parallel, int) and args.parallel != 1)
    )

    if use_parallel:
        # Parallel processing with progress
        max_workers = args.parallel if args.parallel else os.cpu_count()

        with ProgressContext(use_rich, show_progress, len(files), "Converting files") as progress:
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {}

                # Submit files to executor
                for file in files:
                    target_format = getattr(args, 'output_type', 'markdown')
                    output_path = generate_output_path(
                        file,
                        Path(args.output_dir) if args.output_dir else None,
                        args.preserve_structure,
                        base_input_dir,
                        target_format=target_format
                    )
                    future = executor.submit(
                        convert_single_file,
                        file,
                        output_path,
                        options,
                        format_arg,
                        None,
                        False,
                        target_format,
                        transform_specs_for_workers,
                    )
                    futures[future] = (file, output_path)

                # Process results as they complete
                for future in as_completed(futures):
                    file, output_path = futures[future]
                    result_exit_code, result_file_str, result_error = future.result()

                    if result_exit_code == EXIT_SUCCESS:
                        results.append((file, output_path))
                        if output_path:
                            progress.log(f"[OK] {file} -> {output_path}", level='success')
                        else:
                            progress.log(f"[OK] Converted {file}", level='success')
                    else:
                        failed.append((file, result_error))
                        progress.log(f"[ERROR] {file}: {result_error}", level='error')
                        max_exit_code = max(max_exit_code, result_exit_code)
                        if not args.skip_errors:
                            break

                    progress.update()
    else:
        # Sequential processing with progress
        with ProgressContext(use_rich, show_progress, len(files), "Converting files") as progress:
            for file in files:
                progress.set_postfix(f"Processing {file.name}")

                target_format = getattr(args, 'output_type', 'markdown')
                output_path = generate_output_path(
                    file,
                    Path(args.output_dir) if args.output_dir else None,
                    args.preserve_structure,
                    base_input_dir,
                    target_format=target_format
                )

                result_exit_code, result_file_str, result_error = convert_single_file(
                    file,
                    output_path,
                    options,
                    format_arg,
                    transforms,
                    False,
                    target_format,
                    transform_specs_for_workers,
                )

                if result_exit_code == EXIT_SUCCESS:
                    results.append((file, output_path))
                    if output_path:
                        progress.log(f"[OK] {file} -> {output_path}", level='success')
                    else:
                        progress.log(f"[OK] Converted {file}", level='success')
                else:
                    failed.append((file, result_error))
                    progress.log(f"[ERROR] {file}: {result_error}", level='error')
                    max_exit_code = max(max_exit_code, result_exit_code)
                    if not args.skip_errors:
                        break

                progress.update()

    # Show summary for multi-file processing
    if not args.no_summary and len(files) > 1:
        renderer = SummaryRenderer(use_rich=use_rich)
        renderer.render_conversion_summary(
            successful=len(results),
            failed=len(failed),
            total=len(files)
        )

    return max_exit_code


# TODO: remove - replaced by process_files_unified()
# This function is deprecated and no longer called. It has been replaced by
# process_files_unified() which consolidates rich/tqdm/plain progress handling.
def process_with_rich_output(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process files with rich terminal output.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
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
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        print("Error: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR

    console = Console()

    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        # Find common parent directory
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    # Special case: single file to stdout with rich formatting
    # Show progress bar during conversion, then print content after
    if len(files) == 1 and not args.out and not args.output_dir:
        file = files[0]

        # Store the converted content
        markdown_content = None
        conversion_error = None

        # Show progress bar during conversion
        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
        ) as progress:
            task_id = progress.add_task(f"[cyan]Converting {file.name}...", total=1)

            try:
                # Convert the document
                effective_options = prepare_options_for_execution(
                    options,
                    file,
                    format_arg,
                    'markdown',
                )
                markdown_content = to_markdown(
                    file,
                    source_format=cast(Any, format_arg),
                    **effective_options
                )
                progress.update(task_id, advance=1)
            except Exception as e:
                exit_code = get_exit_code_for_exception(e)
                error = str(e)
                if isinstance(e, ImportError):
                    error = f"Missing dependency: {e}"
                elif not isinstance(e, All2MdError):
                    error = f"Unexpected error: {e}"
                conversion_error = (exit_code, error)
                progress.update(task_id, advance=1)

        # After Progress context exits, the progress bar is finalized at the top
        # Now print the content below
        if conversion_error:
            exit_code, error = conversion_error
            console.print(f"[red]ERROR[/red] {file}: {error}")
            return exit_code

        if markdown_content:
            from rich.markdown import Markdown
            rich_kwargs = _get_rich_markdown_kwargs(args)
            console.print(Markdown(markdown_content, **rich_kwargs))
            return EXIT_SUCCESS

    # Show header for multi-file processing
    console.print(Panel.fit(
        Text("all2md Document Converter", style="bold cyan"),
        subtitle=f"Processing {len(files)} file(s)"
    ))

    results: list[tuple[Path, Path | None]] = []
    failed: list[tuple[Path, str | None]] = []
    max_exit_code = EXIT_SUCCESS

    transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(args, 'transform_specs', None))

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
    ) as progress:

        # Check if parallel processing is enabled
        # parallel can be: 1 (default, sequential), None (--parallel without value,
        # auto CPU count), or N (explicit worker count)
        use_parallel = (
                (hasattr(args, '_provided_args') and 'parallel' in args._provided_args and args.parallel is None) or
                (isinstance(args.parallel, int) and args.parallel != 1)
        )

        if use_parallel:
            # Parallel processing
            task_id = progress.add_task("[cyan]Converting files...", total=len(files))

            # Auto-detect CPU count if --parallel was provided without a value (None)
            # Otherwise use the explicit worker count
            max_workers = args.parallel if args.parallel else os.cpu_count()
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {}

                # Submit files to executor for parallel processing
                for file in files:
                    target_format = getattr(args, 'output_type', 'markdown')
                    output_path = generate_output_path(
                        file,
                        Path(args.output_dir) if args.output_dir else None,
                        args.preserve_structure,
                        base_input_dir,
                        target_format=target_format
                    )
                    future = executor.submit(
                        convert_single_file,
                        file,
                        output_path,
                        options,
                        format_arg,
                        None,
                        False,
                        target_format,
                        transform_specs_for_workers,
                    )
                    futures[future] = (file, output_path)

                for future in as_completed(futures):
                    file, output_path = futures[future]
                    result_exit_code, result_file_str, result_error = future.result()

                    if result_exit_code == EXIT_SUCCESS:
                        results.append((file, output_path))
                        if output_path:
                            console.print(f"[green]OK[/green] {file} -> {output_path}")
                        else:
                            console.print(f"[green]OK[/green] Converted {file}")
                    else:
                        failed.append((file, result_error))
                        console.print(f"[red]ERROR[/red] {file}: {result_error}")
                        max_exit_code = max(max_exit_code, result_exit_code)
                        if not args.skip_errors:
                            break

                    progress.update(task_id, advance=1)
        else:
            # Sequential processing
            task_id = progress.add_task("[cyan]Converting files...", total=len(files))

            for file in files:
                target_format = getattr(args, 'output_type', 'markdown')
                output_path = generate_output_path(
                    file,
                    Path(args.output_dir) if args.output_dir else None,
                    args.preserve_structure,
                    base_input_dir,
                    target_format=target_format
                )

                result_exit_code, result_file_str, result_error = convert_single_file(
                    file,
                    output_path,
                    options,
                    format_arg,
                    transforms,
                    False,
                    target_format,
                    transform_specs_for_workers,
                )

                if result_exit_code == EXIT_SUCCESS:
                    results.append((file, output_path))
                    if output_path:
                        console.print(f"[green]OK[/green] {file} -> {output_path}")
                    else:
                        console.print(f"[green]OK[/green] Converted {file}")
                else:
                    failed.append((file, result_error))
                    console.print(f"[red]ERROR[/red] {file}: {result_error}")
                    max_exit_code = max(max_exit_code, result_exit_code)
                    if not args.skip_errors:
                        break

                progress.update(task_id, advance=1)

    # Show summary table only for multiple files
    if not args.no_summary and len(files) > 1:
        console.print()
        table = Table(title="Conversion Summary")
        table.add_column("Status", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")

        table.add_row("+ Successful", str(len(results)))
        table.add_row("- Failed", str(len(failed)))
        table.add_row("Total", str(len(files)))

        console.print(table)

    return max_exit_code


# TODO: remove - replaced by process_files_unified()
# This function is deprecated and no longer called. It has been replaced by
# process_files_unified() which consolidates rich/tqdm/plain progress handling.
def process_with_progress_bar(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process files with tqdm progress bar.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform functions to apply

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)

    """
    try:
        from tqdm import tqdm
    except ImportError:
        print("Warning: tqdm not installed. Install with: pip install all2md[progress]", file=sys.stderr)
        # Fall back to simple processing
        return process_files_simple(files, args, options, format_arg)

    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    failed = []
    max_exit_code = EXIT_SUCCESS

    # Process files with progress bar
    transform_specs_for_workers = cast(Optional[list[TransformSpec]], getattr(args, 'transform_specs', None))

    with tqdm(files, desc="Converting files", unit="file") as pbar:
        for file in pbar:
            pbar.set_postfix_str(f"Processing {file.name}")

            target_format = getattr(args, 'output_type', 'markdown')
            output_path = generate_output_path(
                file,
                Path(args.output_dir) if args.output_dir else None,
                args.preserve_structure,
                base_input_dir,
                target_format=target_format
            )

            exit_code, file_str, error = convert_single_file(
                file,
                output_path,
                options,
                format_arg,
                transforms,
                False,
                target_format,
                transform_specs_for_workers,
            )

            if exit_code == EXIT_SUCCESS:
                print(f"Converted {file} -> {output_path}", file=sys.stderr)
            else:
                print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
                failed.append((file, error))
                max_exit_code = max(max_exit_code, exit_code)
                if not args.skip_errors:
                    break

    # Summary
    if not args.no_summary:
        print(f"\nConversion complete: {len(files) - len(failed)}/{len(files)} files successful", file=sys.stderr)

    return max_exit_code


# TODO: remove - replaced by process_files_unified()
# This function is deprecated and no longer called. It has been replaced by
# process_files_unified() which consolidates rich/tqdm/plain progress handling.
def process_files_simple(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str,
        transforms: Optional[list] = None
) -> int:
    """Process files without progress indicators.

    Parameters
    ----------
    files : List[Path]
        List of files to process
    args : argparse.Namespace
        Command-line arguments
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    transforms : list, optional
        List of transform functions to apply

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)

    """
    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    failed = []
    max_exit_code = EXIT_SUCCESS

    for file in files:
        target_format = getattr(args, 'output_type', 'markdown')
        output_path = generate_output_path(
            file,
            Path(args.output_dir) if args.output_dir else None,
            args.preserve_structure,
            base_input_dir,
            target_format=target_format
        )

        exit_code, file_str, error = convert_single_file(
            file,
            output_path,
            options,
            format_arg,
            transforms,
            False,
            target_format,
            transform_specs_for_workers,
        )

        if exit_code == EXIT_SUCCESS:
            print(f"Converted {file} -> {output_path}", file=sys.stderr)
        else:
            print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
            failed.append((file, error))
            max_exit_code = max(max_exit_code, exit_code)
            if not args.skip_errors:
                break

    return max_exit_code
