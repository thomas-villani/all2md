"""Specialized processing functions for all2md CLI.

This module contains focused processing functions extracted from the main()
function to improve maintainability and testability.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

from all2md import convert, to_markdown
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_SUCCESS,
    DynamicCLIBuilder,
    get_exit_code_for_exception,
)
from all2md.constants import DocumentFormat
from all2md.exceptions import All2MdError, DependencyError


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
        # Print helpful error message
        print("Error: Rich library not installed but --rich flag was used.", file=sys.stderr)
        print("Install with: pip install all2md[rich]", file=sys.stderr)
        sys.exit(EXIT_DEPENDENCY_ERROR)

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
    if not hasattr(parsed_args, 'transforms') or not parsed_args.transforms:
        return None

    try:
        from all2md.transforms import registry as transform_registry
    except ImportError:
        # Transform system not available
        return None

    transform_instances = []

    for transform_name in parsed_args.transforms:
        try:
            metadata = transform_registry.get_metadata(transform_name)
        except ValueError as e:
            print(f"Error: Unknown transform '{transform_name}'", file=sys.stderr)
            print("Use 'all2md list-transforms' to see available transforms", file=sys.stderr)
            raise argparse.ArgumentTypeError(f"Unknown transform: {transform_name}") from e

        # Extract parameters from CLI args
        params = {}
        for param_name, param_spec in metadata.parameters.items():
            if param_spec.cli_flag:
                # Convert CLI flag to arg name: --heading-offset → heading_offset
                arg_name = param_spec.cli_flag.lstrip('-').replace('-', '_')

                if hasattr(parsed_args, arg_name):
                    value = getattr(parsed_args, arg_name)
                    # Only include non-default values
                    if value is not None and value != param_spec.default:
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

        # Create transform instance
        try:
            transform = metadata.create_instance(**params)
            transform_instances.append(transform)
        except Exception as e:
            print(f"Error creating transform '{transform_name}': {e}", file=sys.stderr)
            raise argparse.ArgumentTypeError(f"Failed to create transform: {transform_name}") from e

    return transform_instances


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
        options['html.network.allow_remote_fetch'] = True
        options['html.network.require_https'] = True
        options['html.network.allowed_hosts'] = []  # Validate but allow all HTTPS hosts
        options['html.network.max_remote_asset_bytes'] = 5 * 1024 * 1024  # 5MB
        options['html.local_files.allow_local_files'] = False
        options['html.local_files.allow_cwd_files'] = False
        # MHTML options
        options['mhtml.local_files.allow_local_files'] = False
        options['mhtml.local_files.allow_cwd_files'] = False
        # EML options
        options['eml.html_network.allow_remote_fetch'] = True
        options['eml.html_network.require_https'] = True
        options['eml.html_network.allowed_hosts'] = []
        options['eml.html_network.max_remote_asset_bytes'] = 5 * 1024 * 1024  # 5MB
        # Base options (no format prefix - applies to all formats)
        options['max_attachment_size_bytes'] = 5 * 1024 * 1024  # 5MB (reduced from default 20MB)

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
        If options JSON file cannot be loaded or transform building fails

    """
    # Load options from JSON file if specified
    json_options = None
    if parsed_args.options_json:
        try:
            json_options = load_options_from_json(parsed_args.options_json)
        except argparse.ArgumentTypeError as e:
            print(f"Error loading options JSON: {e}", file=sys.stderr)
            raise

    # Map CLI arguments to options
    builder = DynamicCLIBuilder()
    options = builder.map_args_to_options(parsed_args, json_options)
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
        markdown_content = to_markdown(
            input_source,
            source_format=cast(DocumentFormat, format_arg),
            transforms=transforms,
            **options
        )

        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"Converted stdin -> {output_path}", file=sys.stderr)
        else:
            if parsed_args.pager:
                try:
                    if _should_use_rich_output(parsed_args):
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

    # Process single file (without rich/progress)
    # This includes cases where --rich is set but TTY check fails (piped output)
    if len(files) == 1 and not _should_use_rich_output(parsed_args) and not parsed_args.progress:
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
                # Convert the document
                markdown_content = to_markdown(
                    file,
                    source_format=cast(DocumentFormat, format_arg),
                    transforms=transforms,
                    **options
                )

                # Display with pager
                if _should_use_rich_output(parsed_args):
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

        exit_code, file_str, error = convert_single_file(
            file, output_path, options, format_arg, transforms, False, target_format
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
        return _create_output_package(parsed_args, files)

    # Otherwise, process files normally to disk
    if parsed_args.collate:
        exit_code = process_files_collated(files, parsed_args, options, format_arg, transforms)
    elif _should_use_rich_output(parsed_args):
        exit_code = process_with_rich_output(files, parsed_args, options, format_arg, transforms)
    elif parsed_args.progress or len(files) > 1:
        exit_code = process_with_progress_bar(files, parsed_args, options, format_arg, transforms)
    else:
        exit_code = process_files_simple(files, parsed_args, options, format_arg, transforms)

    return exit_code

def _create_output_package(parsed_args: argparse.Namespace, input_files: List[Path]) -> int:
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
        source_format = getattr(parsed_args, 'format', 'auto')

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

        # Collect conversion options from parsed_args
        # This will be passed to convert() for each file
        options: Dict[str, Any] = {}

        # Create the zip package directly from conversions
        created_zip = create_package_from_conversions(
            input_files=input_files,
            zip_path=zip_path,
            target_format=target_format,
            options=options,
            transforms=None,  # Transforms would need to be built from parsed_args if needed
            source_format=source_format
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
        # Convert the document
        markdown_content = to_markdown(input_path, source_format=format_arg, transforms=transforms, **options)  # type: ignore[arg-type]

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

    # Determine if we should show progress
    show_progress = args.progress or args.rich or len(files) > 1

    # Process with rich output if requested
    if show_progress and args.rich:
        try:
            from rich.console import Console
            from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

            console = Console()
            with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    console=console
            ) as progress:
                task_id = progress.add_task("[cyan]Converting and collating files...", total=len(files))

                for file in files:
                    exit_code = process_file(file)
                    if exit_code == EXIT_SUCCESS:
                        console.print(f"[green]OK[/green] Processed {file}")
                    else:
                        console.print(f"[red]ERROR[/red] {file}: {failed[-1][1]}")
                        if not args.skip_errors:
                            break
                    progress.update(task_id, advance=1)

        except ImportError:
            from all2md.constants import EXIT_DEPENDENCY_ERROR
            print("Error: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
            return EXIT_DEPENDENCY_ERROR

    # Process with tqdm progress bar if requested
    elif show_progress:
        try:
            from tqdm import tqdm
            with tqdm(files, desc="Converting and collating files", unit="file") as pbar:
                for file in pbar:
                    pbar.set_postfix_str(f"Processing {file.name}")
                    exit_code = process_file(file)
                    if exit_code != EXIT_SUCCESS:
                        print(f"Error: Failed to convert {file}: {failed[-1][1]}", file=sys.stderr)
                        if not args.skip_errors:
                            break
        except ImportError:
            # Fallback to simple processing
            print("Warning: tqdm not installed. Install with: pip install all2md[progress]", file=sys.stderr)
            for file in files:
                exit_code = process_file(file)
                if exit_code != EXIT_SUCCESS:
                    print(f"Error: Failed to convert {file}: {failed[-1][1]}", file=sys.stderr)
                    if not args.skip_errors:
                        break

    # Simple processing without progress indicators
    else:
        for file in files:
            exit_code = process_file(file)
            if exit_code != EXIT_SUCCESS:
                print(f"Error: Failed to convert {file}: {failed[-1][1]}", file=sys.stderr)
                if not args.skip_errors:
                    break

    # Output the collated result
    if collated_content:
        final_content = file_separator.join(collated_content)

        if output_path:
            output_path.write_text(final_content, encoding="utf-8")
            print(f"Collated {len(collated_content)} files -> {output_path}", file=sys.stderr)
        else:
            print(final_content)

    # Summary
    if not args.no_summary:
        if args.rich:
            try:
                from rich.console import Console
                from rich.table import Table
                console = Console()
                table = Table(title="Collation Summary")
                table.add_column("Status", style="cyan", no_wrap=True)
                table.add_column("Count", style="magenta")

                table.add_row("+ Successfully processed", str(len(collated_content)))
                table.add_row("- Failed", str(len(failed)))
                table.add_row("Total", str(len(files)))

                console.print(table)
            except ImportError:
                pass
        else:
            msg = f"\nCollation complete: {len(collated_content)}/{len(files)} files processed successfully"
            print(msg, file=sys.stderr)

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

    if target_format in ('auto', 'markdown'):
        extension = '.md'
    else:
        try:
            metadata_list = registry.get_format_info(target_format)
            if metadata_list and len(metadata_list) > 0:
                metadata = metadata_list[0]
                if metadata.extensions:
                    extension = metadata.extensions[0]
                else:
                    extension = f'.{target_format}'
            else:
                extension = f'.{target_format}'
        except Exception:
            extension = f'.{target_format}'

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
        target_format: str = 'markdown'
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

    Returns
    -------
    Tuple[int, str, Optional[str]]
        (exit_code, file_path_str, error_message)

    """
    try:
        # Convert the document using the convert() API for bidirectional conversion
        if output_path:
            # Write to file - convert() handles the target format correctly
            convert(
                input_path,
                output=output_path,
                source_format=cast(DocumentFormat, format_arg),
                target_format=cast(DocumentFormat, target_format),
                transforms=transforms,
                **options
            )
            return EXIT_SUCCESS, str(input_path), None
        else:
            # Output to stdout - only markdown is supported for stdout
            result = convert(
                input_path,
                output=None,
                source_format=cast(DocumentFormat, format_arg),
                target_format='markdown',
                transforms=transforms,
                **options
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
        from all2md.constants import EXIT_DEPENDENCY_ERROR
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
                markdown_content = to_markdown(file, source_format=cast(Any, format_arg), **options)
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
                        transforms,
                        False,
                        target_format
                    )
                    futures[future] = (file, output_path)

                for future in as_completed(futures):
                    file, output_path = futures[future]
                    exit_code, file_str, error = future.result()

                    if exit_code == EXIT_SUCCESS:
                        results.append((file, output_path))
                        if output_path:
                            console.print(f"[green]OK[/green] {file} -> {output_path}")
                        else:
                            console.print(f"[green]OK[/green] Converted {file}")
                    else:
                        failed.append((file, error))
                        console.print(f"[red]ERROR[/red] {file}: {error}")
                        max_exit_code = max(max_exit_code, exit_code)
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

                exit_code, file_str, error = convert_single_file(
                    file,
                    output_path,
                    options,
                    format_arg,
                    transforms,
                    False,
                    target_format
                )

                if exit_code == EXIT_SUCCESS:
                    results.append((file, output_path))
                    if output_path:
                        console.print(f"[green]OK[/green] {file} -> {output_path}")
                    else:
                        console.print(f"[green]OK[/green] Converted {file}")
                else:
                    failed.append((file, error))
                    console.print(f"[red]ERROR[/red] {file}: {error}")
                    max_exit_code = max(max_exit_code, exit_code)
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
                target_format
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
            target_format
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
