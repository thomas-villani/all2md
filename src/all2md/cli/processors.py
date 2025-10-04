"""Specialized processing functions for all2md CLI.

This module contains focused processing functions extracted from the main()
function to improve maintainability and testability.
"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from all2md import to_markdown
from all2md.cli.builder import DynamicCLIBuilder
from all2md.exceptions import InputError, MarkdownConversionError


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

    # Ensure discovery has happened
    transform_registry.discover_plugins()

    transform_instances = []

    for transform_name in parsed_args.transforms:
        try:
            metadata = transform_registry.get_metadata(transform_name)
        except ValueError as e:
            print(f"Error: Unknown transform '{transform_name}'", file=sys.stderr)
            print(f"Use 'all2md list-transforms' to see available transforms", file=sys.stderr)
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
    Security presets set multiple options to secure defaults. Explicit CLI flags
    can still override preset values if specified after the preset flag.

    The flat keys set by this function are automatically mapped to nested
    dataclass fields by _create_options_from_kwargs in __init__.py:

    - allow_remote_fetch, require_https, allowed_hosts, network_timeout,
      max_remote_asset_bytes -> HtmlOptions.network (NetworkFetchOptions)
    - allow_local_files, allow_cwd_files -> HtmlOptions.local_files,
      MhtmlOptions.local_files (LocalFileAccessOptions)
    - allow_remote_fetch, require_https, etc. -> EmlOptions.html_network
      (NetworkFetchOptions)
    """
    import sys

    # Track which preset is being used (highest security wins)
    preset_used = None

    if parsed_args.strict_html_sanitize:
        preset_used = "strict-html-sanitize"
        # Strict HTML sanitization preset
        options['strip_dangerous_elements'] = True
        options['allow_remote_fetch'] = False
        options['allow_local_files'] = False
        options['allow_cwd_files'] = False

    if parsed_args.safe_mode:
        preset_used = "safe-mode"
        # Balanced security for untrusted input
        options['strip_dangerous_elements'] = True
        options['allow_remote_fetch'] = True
        options['require_https'] = True
        options['allow_local_files'] = False
        options['allow_cwd_files'] = False

    if parsed_args.paranoid_mode:
        preset_used = "paranoid-mode"
        # Maximum security
        options['strip_dangerous_elements'] = True
        options['allow_remote_fetch'] = True
        options['require_https'] = True
        options['allowed_hosts'] = []  # Validate but allow all HTTPS hosts
        options['allow_local_files'] = False
        options['allow_cwd_files'] = False
        options['max_attachment_size_bytes'] = 5 * 1024 * 1024  # 5MB (reduced from default 20MB)
        options['max_remote_asset_bytes'] = 5 * 1024 * 1024  # 5MB

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
        json_options = load_options_from_json(parsed_args.options_json)

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
        Exit code (0 for success, 1 for general errors, 2 for dependency errors, 3 for input errors)
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
        markdown_content = to_markdown(input_source, format=format_arg, transforms=transforms, **options)

        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"Converted stdin -> {output_path}")
        else:
            if parsed_args.pager:
                try:
                    from rich.console import Console
                    console = Console()
                    with console.pager(styles=True):
                        console.print(markdown_content)
                except ImportError:
                    msg = "Warning: Rich library not installed. Install with: pip install all2md[rich]"
                    print(msg, file=sys.stderr)
                    print(markdown_content)
            else:
                print(markdown_content)

        return 0

    except Exception as e:
        from all2md.constants import get_exit_code_for_exception
        from all2md.exceptions import DependencyError

        exit_code = get_exit_code_for_exception(e)

        # Print appropriate error message
        if isinstance(e, (DependencyError, ImportError)):
            print(f"Missing dependency: {e}", file=sys.stderr)
            print("Install required dependencies with: pip install all2md[full]", file=sys.stderr)
        elif isinstance(e, (MarkdownConversionError, InputError)):
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
        Exit code (0 for success, highest error code otherwise: 1 for general errors,
        2 for dependency errors, 3 for input errors)
    """
    # Import processing functions
    from all2md.cli import (
        convert_single_file,
        generate_output_path,
        process_detect_only,
        process_dry_run,
        process_files_collated,
        process_files_simple,
        process_with_progress_bar,
        process_with_rich_output,
    )

    # Handle detect-only mode
    if parsed_args.detect_only:
        return process_detect_only(files, parsed_args, format_arg)

    # Handle dry run mode
    if parsed_args.dry_run:
        return process_dry_run(files, parsed_args, format_arg)

    # Process single file (without rich/progress)
    if len(files) == 1 and not parsed_args.rich and not parsed_args.progress:
        file = files[0]

        # Determine output path
        output_path: Optional[Path] = None
        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        elif parsed_args.output_dir:
            output_path = generate_output_path(file, Path(parsed_args.output_dir), False, None)

        # Handle pager for stdout output
        if output_path is None and parsed_args.pager:
            try:
                from rich.console import Console

                from all2md import to_markdown

                # Convert the document
                markdown_content = to_markdown(file, format=format_arg, transforms=transforms, **options)

                # Display with pager
                console = Console()
                with console.pager(styles=True):
                    console.print(markdown_content)

                return 0
            except ImportError:
                print("Warning: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
                # Fall through to regular conversion
            except Exception as e:
                from all2md.constants import get_exit_code_for_exception
                from all2md.exceptions import DependencyError

                exit_code = get_exit_code_for_exception(e)
                if isinstance(e, (DependencyError, ImportError)):
                    print(f"Missing dependency: {e}", file=sys.stderr)
                else:
                    print(f"Error: {e}", file=sys.stderr)
                return exit_code

        exit_code, file_str, error = convert_single_file(file, output_path, options, format_arg, transforms, False)

        if exit_code == 0:
            if output_path:
                print(f"Converted {file} -> {output_path}")
            return 0
        else:
            print(f"Error: {error}", file=sys.stderr)
            return exit_code

    # Process multiple files or with special output
    if parsed_args.collate:
        exit_code = process_files_collated(files, parsed_args, options, format_arg, transforms)
    elif parsed_args.rich:
        exit_code = process_with_rich_output(files, parsed_args, options, format_arg, transforms)
    elif parsed_args.progress or len(files) > 1:
        exit_code = process_with_progress_bar(files, parsed_args, options, format_arg, transforms)
    else:
        exit_code = process_files_simple(files, parsed_args, options, format_arg, transforms)

    # Handle output packaging if --zip was specified
    if exit_code == 0 and parsed_args.zip and parsed_args.output_dir:
        exit_code = _create_output_package(parsed_args, files)

    return exit_code


def _create_output_package(parsed_args: argparse.Namespace, input_files: List[Path]) -> int:
    """Create output package (zip) after successful conversion.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments
    input_files : List[Path]
        List of input files that were processed

    Returns
    -------
    int
        Exit code (0 for success)
    """
    import logging
    from pathlib import Path

    from all2md.cli.packaging import create_output_zip, organize_assets, update_markdown_asset_links
    from all2md.constants import EXIT_ERROR

    logger = logging.getLogger(__name__)

    try:
        output_dir = Path(parsed_args.output_dir)

        if not output_dir.exists():
            logger.error(f"Output directory does not exist: {output_dir}")
            return EXIT_ERROR

        # Collect generated markdown files
        markdown_files = list(output_dir.rglob("*.md"))

        if not markdown_files:
            logger.warning("No markdown files found in output directory for packaging")
            return 0

        # Organize assets according to layout if specified
        if hasattr(parsed_args, 'assets_layout') and parsed_args.assets_layout != 'flat':
            logger.debug(f"Organizing assets with layout: {parsed_args.assets_layout}")
            asset_mapping = organize_assets(
                markdown_files,
                output_dir,
                layout=parsed_args.assets_layout,
                attachment_dir=Path(parsed_args.attachment_output_dir) if hasattr(
                    parsed_args, 'attachment_output_dir') and parsed_args.attachment_output_dir else None
            )

            # Move assets to new locations
            for old_path, new_path in asset_mapping.items():
                if old_path != new_path:
                    new_path.parent.mkdir(parents=True, exist_ok=True)
                    if old_path.exists():
                        import shutil
                        shutil.move(str(old_path), str(new_path))

            # Update markdown file links
            for md_file in markdown_files:
                update_markdown_asset_links(md_file, asset_mapping, output_dir)

        # Determine zip path
        if parsed_args.zip == 'auto':
            zip_path = None  # Will use default: output_dir.zip
        else:
            zip_path = Path(parsed_args.zip)

        # Create the zip file
        created_zip = create_output_zip(
            output_dir,
            zip_path=zip_path,
            markdown_files=markdown_files
        )

        print(f"Created package: {created_zip}")
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
