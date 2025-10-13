#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands.py
"""CLI command handlers and utilities for all2md.

This module provides command-line interface implementation for the all2md
document conversion library, including command handlers, version info,
and system diagnostics.
"""
import argparse
import fnmatch
import json
import logging
import os
import platform
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, Dict, List, Optional

from all2md.api import convert
from all2md.cli.builder import EXIT_SUCCESS, create_parser, get_exit_code_for_exception, EXIT_VALIDATION_ERROR, \
    EXIT_FILE_ERROR
from all2md.cli.processors import (
    _get_rich_markdown_kwargs,
    _should_use_rich_output,
    process_detect_only,
    process_dry_run, process_stdin, setup_and_validate_options, validate_arguments,
)
from all2md.converter_registry import registry
from all2md.converter_metadata import ConverterMetadata
from all2md.dependencies import check_version_requirement, get_package_version
from all2md.transforms import registry as transform_registry
from all2md.constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS

def _get_version() -> str:
    """Get the version of all2md package."""
    try:
        return version("all2md")
    except Exception:
        return "unknown"


def _get_about_info() -> str:
    """Get detailed information about all2md including system info and dependencies."""
    version_str = _get_version()

    # System information
    python_version = platform.python_version()
    python_path = sys.executable
    os_info = platform.platform()
    architecture = platform.machine()

    # Get dependency information
    registry.auto_discover()
    formats = registry.list_formats()

    # Count available formats
    available_formats = []
    unavailable_formats = []

    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if not metadata_list or len(metadata_list) == 0:
            continue

        # Use the highest priority (first) converter
        metadata = metadata_list[0]

        # Check if all dependencies are satisfied
        all_available = True
        if metadata.required_packages:
            for install_name, _import_name, version_spec in metadata.required_packages:
                if version_spec:
                    meets_req, _ = check_version_requirement(install_name, version_spec)
                    if not meets_req:
                        all_available = False
                        break
                else:
                    installed_version = get_package_version(install_name)
                    if not installed_version:
                        all_available = False
                        break

        if all_available:
            available_formats.append(format_name)
        else:
            unavailable_formats.append(format_name)

    # Get unique dependencies across all formats
    all_deps = {}
    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if metadata_list and len(metadata_list) > 0:
            # Use the highest priority (first) converter
            metadata = metadata_list[0]
            if metadata.required_packages:
                for install_name, _import_name, version_spec in metadata.required_packages:
                    if install_name not in all_deps:
                        installed_version = get_package_version(install_name)
                        if version_spec:
                            meets_req, _ = check_version_requirement(install_name, version_spec)
                            status = 'installed' if meets_req else 'version_mismatch'
                        else:
                            meets_req = installed_version is not None
                            status = 'installed' if meets_req else 'not_installed'

                        all_deps[install_name] = {
                            'version': installed_version,
                            'required': version_spec,
                            'status': status
                        }

    # Build dependency report
    dep_lines = []
    for pkg_name, dep_info in sorted(all_deps.items()):
        if dep_info['status'] == 'installed':
            check = "✓"
            version_info = f"{dep_info['version']}"
            if dep_info['required']:
                version_info += f" (required: {dep_info['required']})"
        elif dep_info['status'] == 'version_mismatch':
            check = "✗"
            version_info = f"{dep_info['version']} (required: {dep_info['required']})"
        else:
            check = "✗"
            version_info = "not installed"

        dep_lines.append(f"  {check} {pkg_name:20} {version_info}")

    dependencies_report = "\n".join(dep_lines) if dep_lines else "  (none)"

    # Build format availability report
    total_formats = len(available_formats) + len(unavailable_formats)
    available_count = len(available_formats)

    return f"""all2md {version_str}

A Python document conversion library for transformation
between various file formats and Markdown.

System Information:
  Python:        {python_version} ({python_path})
  Platform:      {os_info}
  Architecture:  {architecture}

Installed Dependencies ({len([d for d in all_deps.values() if d['status'] == 'installed'])}/{len(all_deps)}):
{dependencies_report}

Available Formats ({available_count}/{total_formats} ready):
  Ready:   {', '.join(sorted(available_formats))}
  Missing: {', '.join(sorted(unavailable_formats)) if unavailable_formats else '(none)'}

Features:
  • Advanced PDF parsing with table detection
  • AST-based transformation pipeline
  • Plugin system for custom transforms
  • Intelligent format detection from content
  • Configurable Markdown output options
  • Attachment handling (download, embed, skip)
  • Command-line interface with stdin support
  • Python API for programmatic use
  • Multi-file and directory processing
  • Rich terminal output and progress bars

Install all dependencies: pip install all2md[all]
Install specific format:   pip install all2md[pdf,docx,html]

Documentation: https://github.com/thomas.villani/all2md
License: MIT License
Author: Thomas Villani <thomas.villani@gmail.com>"""


def _configure_logging(
        log_level: int,
        log_file: Optional[str] = None,
        trace_mode: bool = False
) -> None:
    """Configure logging with console and optional file output.

    Parameters
    ----------
    log_level : int
        Logging level (DEBUG, INFO, WARNING, ERROR)
    log_file : str, optional
        Path to log file for writing logs
    trace_mode : bool, default False
        Enable trace mode with timestamps and detailed formatting

    """
    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Format string depends on trace mode
    if trace_mode:
        # Trace mode: detailed format with timestamps
        format_str = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'
    else:
        # Normal mode: simple format
        format_str = '%(levelname)s: %(message)s'
        date_format = None

    formatter = logging.Formatter(format_str, datefmt=date_format)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if log_file is specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # Log to stderr so user knows where logs are going
            print(f"Logging to file: {log_file}", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not create log file {log_file}: {e}", file=sys.stderr)


def save_config_to_file(args: argparse.Namespace, config_path: str) -> None:
    """Save CLI arguments to a JSON configuration file.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed command line arguments
    config_path : str
        Path to save the configuration file

    Raises
    ------
    Exception
        If the configuration file cannot be written

    """
    # Exclude special arguments that shouldn't be saved
    exclude_args = {
        'input', 'out', 'save_config', 'about', 'version', 'dry_run', 'format', '_env_checked', '_provided_args'
    }
    # Note: 'exclude' is intentionally NOT excluded so it can be saved in config

    # Convert namespace to dict and filter
    args_dict = vars(args)
    config = {}

    for key, value in args_dict.items():
        if key not in exclude_args and value is not None:
            # Skip empty lists
            if isinstance(value, list) and not value:
                continue
            # Skip sentinel values that aren't JSON serializable
            # Check for dataclasses._MISSING_TYPE
            if hasattr(value, '__class__') and value.__class__.__name__ == '_MISSING_TYPE':
                continue
            # Check for plain object() sentinels (used for UNSET in MarkdownOptions)
            if type(value) is object:
                continue
            # Skip non-serializable types
            if isinstance(value, (set, frozenset)):
                continue
            # For boolean values, only include if they are explicitly False (user set a no- flag)
            # or True and not a default True value
            if isinstance(value, bool):
                # We need to check if this was explicitly set vs a default
                # For now, include False values (from --no- flags) and True values
                config[key] = value
            else:
                config[key] = value

    # Write to file
    config_path_obj = Path(config_path)
    config_path_obj.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path_obj, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"Configuration saved to {config_path}")


def collect_input_files(
        input_paths: List[str],
        recursive: bool = False,
        extensions: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None
) -> List[Path]:
    """Collect all input files from provided paths.

    Parameters
    ----------
    input_paths : List[str]
        List of file paths, directory paths, or glob patterns
    recursive : bool
        Whether to process directories recursively
    extensions : List[str], optional
        File extensions to filter (e.g., ['.pdf', '.docx'])
    exclude_patterns : List[str], optional
        Glob patterns to exclude from processing

    Returns
    -------
    List[Path]
        List of file paths to process

    """

    files: List[Path] = []

    # Default to all allowed extensions if not specified
    if extensions is None:
        extensions = ALL_ALLOWED_EXTENSIONS.copy()

    for input_path_str in input_paths:
        input_path = Path(input_path_str)

        # Handle glob patterns
        if '*' in input_path_str:
            files.extend(Path.cwd().glob(input_path_str))
        elif input_path.is_file():
            # Single file
            if not extensions or input_path.suffix.lower() in extensions:
                files.append(input_path)
        elif input_path.is_dir():
            # Directory - collect files
            if recursive:
                for ext in extensions:
                    files.extend(input_path.rglob(f'*{ext}'))
            else:
                for ext in extensions:
                    files.extend(input_path.glob(f'*{ext}'))
        else:
            logging.warning(f"Path does not exist: {input_path}")

    # Remove duplicates and sort
    files = sorted(set(files))

    # Apply exclusion patterns
    if exclude_patterns:
        filtered_files = []
        for file in files:
            exclude_file = False
            for pattern in exclude_patterns:
                # Check against filename and absolute path
                if (fnmatch.fnmatch(str(file), pattern) or
                        fnmatch.fnmatch(file.name, pattern)):
                    exclude_file = True
                    break

                # Try relative path if file is in current working directory
                try:
                    relative_path = file.relative_to(Path.cwd())
                    if fnmatch.fnmatch(str(relative_path), pattern):
                        exclude_file = True
                        break
                except ValueError:
                    # File is not in current working directory, skip relative path check
                    pass
            if not exclude_file:
                filtered_files.append(file)
        files = filtered_files

    return files


def handle_list_formats_command(args: list[str] | None = None) -> int:
    """Handle list-formats command to show available parsers.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'list-formats')

    Returns
    -------
    int
        Exit code (0 for success)

    """

    # Parse command line arguments for list-formats
    specific_format = None
    available_only = False
    use_rich = False

    if args:
        for arg in args:
            if arg in ('--help', '-h'):
                print("""Usage: all2md list-formats [OPTIONS] [FORMAT]

Show information about available document parsers.

Arguments:
  FORMAT              Show details for specific format only

Options:
  --available-only    Show only formats with satisfied dependencies
  --rich              Use rich terminal output with formatting
  -h, --help         Show this help message

Examples:
  all2md list-formats                    # List all formats
  all2md list-formats pdf                # Show details for PDF
  all2md list-formats --available-only   # Only show usable formats
""")
                return 0
            elif arg == '--available-only':
                available_only = True
            elif arg == '--rich':
                use_rich = True
            elif not arg.startswith('-'):
                specific_format = arg

    # Auto-discover parsers
    registry.auto_discover()

    # Get all formats
    formats = registry.list_formats()
    if specific_format:
        if specific_format not in formats:
            print(f"Error: Format '{specific_format}' not found", file=sys.stderr)
            print(f"Available formats: {', '.join(formats)}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
        formats = [specific_format]

    # Gather format information
    format_info_list: list[dict[str, Any]] = []
    for format_name in formats:
        metadata_list = registry.get_format_info(format_name)
        if not metadata_list or len(metadata_list) == 0:
            continue

        # Use the highest priority (first) converter
        metadata = metadata_list[0]

        # Check dependency status
        all_available = True
        dep_status: list[tuple[str, str | None, str, str | None]] = []

        # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
        for install_name, _import_name, version_spec in metadata.required_packages:
            if version_spec:
                # Use install_name for version checking (pip/metadata lookup)
                meets_req, installed_version = check_version_requirement(install_name, version_spec)
                if not meets_req:
                    all_available = False
                    if installed_version:
                        dep_status.append((install_name, version_spec, 'mismatch', installed_version))
                    else:
                        dep_status.append((install_name, version_spec, 'missing', None))
                else:
                    dep_status.append((install_name, version_spec, 'ok', installed_version))
            else:
                # Use install_name for version lookup (consistent with version checking)
                installed_version = get_package_version(install_name)
                if installed_version:
                    dep_status.append((install_name, version_spec, 'ok', installed_version))
                else:
                    all_available = False
                    dep_status.append((install_name, version_spec, 'missing', None))

        # Skip if filtering for available only
        if available_only and not all_available:
            continue

        format_info_list.append({
            'name': format_name,
            'metadata': metadata,
            'all_available': all_available,
            'dep_status': dep_status,
        })

    # Display results
    if use_rich:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if specific_format:
                # Detailed view for specific format
                info = format_info_list[0] if format_info_list else None
                if info:
                    fmt_metadata: ConverterMetadata | None = info['metadata']
                    assert fmt_metadata is not None  # Already filtered in list construction

                    # Create main panel
                    content = []
                    content.append(f"[bold]Format:[/bold] {info['name'].upper()}")
                    content.append(f"[bold]Description:[/bold] {fmt_metadata.description or 'N/A'}")
                    content.append(f"[bold]Extensions:[/bold] {', '.join(fmt_metadata.extensions) or 'N/A'}")
                    content.append(f"[bold]MIME Types:[/bold] {', '.join(fmt_metadata.mime_types) or 'N/A'}")
                    content.append(f"[bold]Converter:[/bold] {fmt_metadata.get_converter_display_string()}")
                    content.append(f"[bold]Priority:[/bold] {fmt_metadata.priority}")

                    console.print(Panel("\n".join(content), title=f"{info['name'].upper()} Format Details"))

                    # Dependencies table
                    if info['dep_status']:
                        dep_table = Table(title="Dependencies")
                        dep_table.add_column("Package", style="cyan")
                        dep_table.add_column("Required", style="yellow")
                        dep_table.add_column("Status", style="magenta")
                        dep_table.add_column("Installed", style="green")

                        for pkg_name, version_spec, status, installed_version in info['dep_status']:
                            status_icon = {
                                'ok': '[green][OK] Available[/green]',
                                'missing': '[red][X] Missing[/red]',
                                'mismatch': '[yellow][!] Version Mismatch[/yellow]'
                            }[status]

                            dep_table.add_row(
                                pkg_name,
                                version_spec or 'any',
                                status_icon,
                                installed_version or 'N/A'
                            )

                        console.print(dep_table)

                        # Show install command if needed
                        if not info['all_available']:
                            install_cmd = fmt_metadata.get_install_command()
                            console.print(f"\n[yellow]Install with:[/yellow] {install_cmd}")
                    else:
                        console.print("[green]No dependencies required[/green]")

            else:
                # Summary table for all formats
                table = Table(title=f"All2MD Supported Formats ({len(format_info_list)} formats)")
                table.add_column("Format", style="cyan", no_wrap=True)
                table.add_column("Extensions", style="yellow")
                table.add_column("Capabilities", style="blue")
                table.add_column("Status", style="magenta")
                table.add_column("Dependencies", style="white")

                for info in format_info_list:
                    metadata = info['metadata']

                    # Status indicator
                    if info['all_available']:
                        status = "[green][OK] Available[/green]"
                    else:
                        status = "[red][X] Unavailable[/red]"

                    # Extensions
                    ext_str = ", ".join(metadata.extensions[:4])
                    if len(metadata.extensions) > 4:
                        ext_str += f" +{len(metadata.extensions) - 4}"

                    # Capabilities
                    has_parser = metadata.parser_class is not None
                    has_renderer = metadata.renderer_class is not None
                    if has_parser and has_renderer:
                        capabilities = "Parse+Render"
                    elif has_parser:
                        capabilities = "Parse"
                    elif has_renderer:
                        capabilities = "Render"
                    else:
                        capabilities = "None"

                    # Dependencies summary
                    if info['dep_status']:
                        ok_count = sum(1 for _, _, s, _ in info['dep_status'] if s == 'ok')
                        total_count = len(info['dep_status'])
                        dep_str = f"{ok_count}/{total_count}"
                    else:
                        dep_str = "none"

                    table.add_row(
                        info['name'].upper(),
                        ext_str,
                        capabilities,
                        status,
                        dep_str
                    )

                console.print(table)
                console.print("\n[dim]Use 'all2md list-formats <format>' for detailed information[/dim]")

        except ImportError:
            # Fall back to plain text
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_format:
            info = format_info_list[0] if format_info_list else None
            if info:
                metadata_obj: ConverterMetadata | None = info['metadata']
                assert metadata_obj is not None  # Already filtered in list construction
                print(f"\n{info['name'].upper()} Format")
                print("=" * 60)
                print(f"Description: {metadata_obj.description or 'N/A'}")
                print(f"Extensions: {', '.join(metadata_obj.extensions) or 'N/A'}")
                print(f"MIME Types: {', '.join(metadata_obj.mime_types) or 'N/A'}")
                print(f"Converter: {metadata_obj.get_converter_display_string()}")
                print(f"Priority: {metadata_obj.priority}")

                if info['dep_status']:
                    print("\nDependencies:")
                    for pkg_name, version_spec, status, installed_version in info['dep_status']:
                        status_str = {
                            'ok': '[OK]',
                            'missing': '[MISSING]',
                            'mismatch': '[VERSION MISMATCH]'
                        }[status]

                        version_str = f" {version_spec}" if version_spec else ""
                        installed_str = f" (installed: {installed_version})" if installed_version else ""

                        print(f"  {status_str} {pkg_name}{version_str}{installed_str}")

                    if not info['all_available']:
                        install_cmd = metadata_obj.get_install_command()
                        print(f"\nInstall with: {install_cmd}")
                else:
                    print("\nNo dependencies required")
        else:
            print("\nAll2MD Supported Formats")
            print("=" * 60)
            for info in format_info_list:
                format_meta: ConverterMetadata | None = info['metadata']
                assert format_meta is not None  # Already filtered in list construction
                status = "[OK]" if info['all_available'] else "[X]"
                ext_str = ", ".join(format_meta.extensions[:4])
                if len(format_meta.extensions) > 4:
                    ext_str += f" +{len(format_meta.extensions) - 4}"

                # Capabilities
                has_parser = format_meta.parser_class is not None
                has_renderer = format_meta.renderer_class is not None
                if has_parser and has_renderer:
                    capabilities = "[R+W]"
                elif has_parser:
                    capabilities = "[R]  "
                elif has_renderer:
                    capabilities = "[W]  "
                else:
                    capabilities = "     "

                print(f"{status} {info['name'].upper():12} {capabilities} {ext_str}")

            print(f"\nTotal: {len(format_info_list)} formats")
            print("Use 'all2md list-formats <format>' for detailed information")

    return 0


def handle_list_transforms_command(args: list[str] | None = None) -> int:
    """Handle list-transforms command.

    Parameters
    ----------
    args : list[str], optional
        Additional arguments

    Returns
    -------
    int
        Exit code (0 for success)

    """

    # Parse options
    specific_transform = None
    use_rich = False

    if args:
        for arg in args:
            if arg in ('--help', '-h'):
                print("""Usage: all2md list-transforms [OPTIONS] [TRANSFORM]

Show available AST transforms.

Arguments:
  TRANSFORM          Show details for specific transform

Options:
  --rich            Use rich terminal output
  -h, --help        Show this help message

Examples:
  all2md list-transforms                    # List all transforms
  all2md list-transforms heading-offset     # Show details for specific transform
  all2md list-transforms --rich             # Use rich output
""")
                return 0
            elif arg == '--rich':
                use_rich = True
            elif not arg.startswith('-'):
                specific_transform = arg

    # List transforms (auto-discovers on first access)
    transforms = transform_registry.list_transforms()

    if specific_transform:
        if specific_transform not in transforms:
            print(f"Error: Transform '{specific_transform}' not found", file=sys.stderr)
            print(f"Available: {', '.join(transforms)}", file=sys.stderr)
            return 1
        transforms = [specific_transform]

    # Display transforms
    if use_rich:
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.table import Table

            console = Console()

            if specific_transform:
                # Detailed view
                metadata = transform_registry.get_metadata(specific_transform)

                content = []
                content.append(f"[bold]Name:[/bold] {metadata.name}")
                content.append(f"[bold]Description:[/bold] {metadata.description}")
                content.append(f"[bold]Priority:[/bold] {metadata.priority}")
                if metadata.dependencies:
                    content.append(f"[bold]Dependencies:[/bold] {', '.join(metadata.dependencies)}")
                if metadata.tags:
                    content.append(f"[bold]Tags:[/bold] {', '.join(metadata.tags)}")

                console.print(Panel("\n".join(content), title=f"Transform: {metadata.name}"))

                # Parameters table
                if metadata.parameters:
                    table = Table(title="Parameters")
                    table.add_column("Name", style="cyan")
                    table.add_column("Type", style="yellow")
                    table.add_column("Default", style="green")
                    table.add_column("CLI Flag", style="magenta")
                    table.add_column("Description", style="white")

                    for name, spec in metadata.parameters.items():
                        type_str = spec.type.__name__ if hasattr(spec.type, '__name__') else str(spec.type)
                        table.add_row(
                            name,
                            type_str,
                            str(spec.default) if spec.default is not None else 'None',
                            spec.cli_flag or 'N/A',
                            spec.help or ''
                        )

                    console.print(table)
            else:
                # Summary table
                table = Table(title=f"Available Transforms ({len(transforms)})")
                table.add_column("Name", style="cyan")
                table.add_column("Description", style="white")
                table.add_column("Tags", style="yellow")

                for name in transforms:
                    metadata = transform_registry.get_metadata(name)
                    table.add_row(
                        metadata.name,
                        metadata.description,
                        ', '.join(metadata.tags) if metadata.tags else ''
                    )

                console.print(table)
        except ImportError:
            use_rich = False

    if not use_rich:
        # Plain text output
        if specific_transform:
            metadata = transform_registry.get_metadata(specific_transform)
            print(f"\n{metadata.name}")
            print("=" * 60)
            print(f"Description: {metadata.description}")
            print(f"Priority: {metadata.priority}")
            if metadata.dependencies:
                print(f"Dependencies: {', '.join(metadata.dependencies)}")
            if metadata.tags:
                print(f"Tags: {', '.join(metadata.tags)}")

            if metadata.parameters:
                print("\nParameters:")
                for name, spec in metadata.parameters.items():
                    type_str = spec.type.__name__ if hasattr(spec.type, '__name__') else str(spec.type)
                    default_str = f"(default: {spec.default})" if spec.default is not None else ""
                    cli_str = f"  CLI: {spec.cli_flag}" if spec.cli_flag else ""
                    print(f"  {name} ({type_str}) {default_str}")
                    if spec.help:
                        print(f"    {spec.help}")
                    if cli_str:
                        print(cli_str)
        else:
            print("\nAvailable Transforms")
            print("=" * 60)
            for name in transforms:
                metadata = transform_registry.get_metadata(name)
                tags_str = f" [{', '.join(metadata.tags)}]" if metadata.tags else ""
                print(f"  {metadata.name:20} {metadata.description}{tags_str}")
            print(f"\nTotal: {len(transforms)} transforms")
            print("Use 'all2md list-transforms <transform>' for details")

    return 0


def handle_convert_command(args: list[str] | None = None) -> int | None:
    """Handle the `convert` subcommand for bidirectional conversions."""
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != 'convert':
        return None

    convert_args = args[1:]
    parser = create_parser()
    parsed_args = parser.parse_args(convert_args)

    provided_args: set[str] = getattr(parsed_args, '_provided_args', set())

    if 'output_type' not in provided_args:
        parsed_args.output_type = 'auto'

    if not parsed_args.out and not parsed_args.output_dir and len(parsed_args.input) == 2:
        parsed_args.out = parsed_args.input[-1]
        parsed_args.input = parsed_args.input[:1]

    if not parsed_args.config:
        env_config = os.environ.get('ALL2MD_CONFIG')
        if env_config:
            parsed_args.config = env_config

    if parsed_args.about:
        print(_get_about_info())
        return 0

    if parsed_args.save_config:
        try:
            save_config_to_file(parsed_args, parsed_args.save_config)
            return 0
        except Exception as exc:
            print(f"Error saving configuration: {exc}", file=sys.stderr)
            return 1

    return _run_convert_command(parsed_args)


def _default_extension_for_format(target_format: str) -> str:
    if target_format in ('auto', 'markdown'):
        return '.md'

    try:
        metadata_list = registry.get_format_info(target_format)
        if metadata_list and len(metadata_list) > 0:
            # Use the highest priority (first) converter
            metadata = metadata_list[0]
            if metadata.extensions:
                return metadata.extensions[0]
    except Exception:
        pass

    return f'.{target_format}'


def _run_convert_command(parsed_args: argparse.Namespace) -> int:


    options, format_arg, transforms = setup_and_validate_options(parsed_args)

    # Set up logging level
    if parsed_args.trace:
        log_level = logging.DEBUG
    elif parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, parsed_args.log_level.upper())

    # Configure logging with file handler if --log-file is specified
    _configure_logging(
        log_level,
        log_file=parsed_args.log_file,
        trace_mode=parsed_args.trace
    )

    if not validate_arguments(parsed_args):
        return EXIT_VALIDATION_ERROR

    if len(parsed_args.input) == 1 and parsed_args.input[0] == '-':
        return process_stdin(parsed_args, options, format_arg, transforms)

    files = collect_input_files(
        parsed_args.input,
        parsed_args.recursive,
        exclude_patterns=parsed_args.exclude
    )

    if not files:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Handle detection-only / dry-run using existing processors
    if parsed_args.detect_only:
        return process_detect_only(files, parsed_args, format_arg)

    if parsed_args.dry_run:
        return process_dry_run(files, parsed_args, format_arg)

    if parsed_args.collate:
        print("Error: --collate is only supported for markdown output", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if not parsed_args.out and not parsed_args.output_dir and len(files) > 1:
        print("Error: Multiple inputs require --output-dir or --out", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if parsed_args.out and len(files) > 1:
        print("Error: --out can only be used with a single input file", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if parsed_args.output_dir and parsed_args.output_type == 'auto':
        print("Error: --output-dir requires --output-type to determine file extensions", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    base_input_dir: Optional[Path] = None
    if parsed_args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    use_progress = parsed_args.progress or len(files) > 1
    progress_iterator = files
    progress_context = None

    if use_progress:
        try:
            from tqdm import tqdm
            progress_iterator = tqdm(files, desc="Converting files", unit="file")
            progress_context = progress_iterator
        except ImportError:
            print("Warning: tqdm not installed. Install with: pip install all2md[progress]", file=sys.stderr)
            use_progress = False

    successes: list[tuple[Path, Optional[Path]]] = []
    failures: list[tuple[Path, str, int]] = []

    def determine_output_path(input_file: Path) -> Optional[Path]:
        if parsed_args.out:
            return Path(parsed_args.out)
        if parsed_args.output_dir:
            ext = _default_extension_for_format(parsed_args.output_type)
            stem = input_file.stem
            relative_parent = Path()
            if parsed_args.preserve_structure and base_input_dir:
                try:
                    relative_parent = input_file.parent.relative_to(base_input_dir)
                except ValueError:
                    relative_parent = Path()
            target_dir = Path(parsed_args.output_dir) / relative_parent
            target_dir.mkdir(parents=True, exist_ok=True)
            return target_dir / f"{stem}{ext}"
        return None

    iterator = progress_iterator if use_progress else files

    for file in iterator:
        output_path = determine_output_path(file)

        if output_path and parsed_args.out:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            target_format = parsed_args.output_type

            if output_path is None:
                target_format = 'markdown'
                rendered = convert(
                    file,
                    output=None,
                    source_format=format_arg,  # type: ignore[arg-type]
                    target_format=target_format,  # type: ignore[arg-type]
                    transforms=transforms,
                    **options,
                )

                if isinstance(rendered, bytes):
                    rendered_text = rendered.decode('utf-8', errors='replace')
                else:
                    rendered_text = rendered or ""

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
                                console.print(Markdown(rendered_text, **rich_kwargs))
                            content_to_page = capture.get()
                            is_rich = True
                        else:
                            content_to_page = rendered_text
                            is_rich = False

                        # Import the helper function
                        from all2md.cli.processors import _page_content
                        # Try to page the content using available pager
                        if not _page_content(content_to_page, is_rich=is_rich):
                            # If paging fails, just print the content
                            print(content_to_page)
                    except ImportError:
                        print(rendered_text)
                else:
                    print(rendered_text)
                successes.append((file, None))
                continue

            convert(
                file,
                output=output_path,
                source_format=format_arg,  # type: ignore[arg-type]
                target_format=target_format,
                transforms=transforms,
                **options,
            )

            successes.append((file, output_path))

            if not parsed_args.rich:
                print(f"Converted {file} -> {output_path}")

        except Exception as exc:
            exit_code = get_exit_code_for_exception(exc)
            failures.append((file, str(exc), exit_code))
            print(f"Error converting {file}: {exc}", file=sys.stderr)
            if not parsed_args.skip_errors:
                break

    if progress_context is not None:
        progress_context.close()

    if parsed_args.rich and successes and not parsed_args.no_summary:
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title="Conversion Summary")
            table.add_column("File", style="cyan")
            table.add_column("Output", style="green")

            for src, dest in successes:
                table.add_row(str(src), str(dest) if dest else "stdout")

            if failures:
                table_fail = Table(title="Failures", style="red")
                table_fail.add_column("File")
                table_fail.add_column("Error")
                for src, message, _ in failures:
                    table_fail.add_row(str(src), message)
                console.print(table)
                console.print(table_fail)
            else:
                console.print(table)

        except ImportError:
            pass

    if failures:
        return max(exit_code for _, _, exit_code in failures)

    return EXIT_SUCCESS


def handle_config_generate_command(args: list[str] | None = None) -> int:
    """Handle config generate command to create default configuration files.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'config generate')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    # Parse arguments
    output_format = 'toml'
    output_path = None

    if args:
        i = 0
        while i < len(args):
            arg = args[i]
            if arg in ('--help', '-h'):
                print("""Usage: all2md config generate [OPTIONS]

Generate a default configuration file with all available options.

Options:
  --format FORMAT    Output format: 'toml' (default) or 'json'
  --out PATH         Output file path (default: prints to stdout)
  -h, --help        Show this help message

Examples:
  all2md config generate                           # Print TOML to stdout
  all2md config generate --format json             # Print JSON to stdout
  all2md config generate --out .all2md.toml        # Save TOML to file
  all2md config generate --format json --out config.json
""")
                return 0
            elif arg == '--format':
                if i + 1 < len(args):
                    output_format = args[i + 1]
                    i += 2
                else:
                    print("Error: --format requires an argument", file=sys.stderr)
                    return 1
            elif arg == '--out':
                if i + 1 < len(args):
                    output_path = args[i + 1]
                    i += 2
                else:
                    print("Error: --out requires an argument", file=sys.stderr)
                    return 1
            else:
                print(f"Error: Unknown argument '{arg}'", file=sys.stderr)
                return 1

    # Validate format
    if output_format not in ('toml', 'json'):
        print(f"Error: Invalid format '{output_format}'. Use 'toml' or 'json'", file=sys.stderr)
        return 1

    # Generate default configuration with comments
    default_config: Dict[str, Any] = {
        'attachment_mode': 'skip',
        'pdf': {
            'detect_columns': False,
            'skip_image_extraction': False,
            'enable_table_fallback_detection': True,
            'merge_hyphenated_words': False,
        },
        'html': {
            'strip_dangerous_elements': True,
            'extract_title': False,
        },
        'markdown': {
            'emphasis_symbol': '*',
        },
        'pptx': {
            'include_notes': False,
            'slide_numbers': False,
        },
        'epub': {
            'merge_chapters': False,
            'include_toc': False,
        },
        'ipynb': {
            'truncate_long_outputs': None,
        },
        'eml': {
            'include_headers': False,
            'preserve_thread_structure': False,
        },
    }

    # Generate output
    if output_format == 'toml':
        # Generate TOML with helpful comments
        output_lines = [
            '# all2md configuration file',
            '# Automatically generated default configuration',
            '#',
            '# Priority order for configuration:',
            '# 1. CLI arguments (highest priority)',
            '# 2. --config file specified on command line',
            '# 3. ALL2MD_CONFIG environment variable',
            '# 4. .all2md.toml or .all2md.json in current directory',
            '# 5. .all2md.toml or .all2md.json in home directory',
            '',
            '# Attachment handling mode: "skip", "download", or "base64"',
            f'attachment_mode = "{default_config["attachment_mode"]}"',
            '',
            '# PDF conversion options',
            '[pdf]',
            '# Detect multi-column layouts',
            f'detect_columns = {str(default_config["pdf"]["detect_columns"]).lower()}',
            '# Skip extracting images from PDFs',
            f'skip_image_extraction = {str(default_config["pdf"]["skip_image_extraction"]).lower()}',
            '# Enable fallback table detection',
            (f'enable_table_fallback_detection = '
             f'{str(default_config["pdf"]["enable_table_fallback_detection"]).lower()}'),
            '# Merge hyphenated words at line breaks',
            f'merge_hyphenated_words = {str(default_config["pdf"]["merge_hyphenated_words"]).lower()}',
            '',
            '# HTML conversion options',
            '[html]',
            '# Strip potentially dangerous HTML elements',
            f'strip_dangerous_elements = {str(default_config["html"]["strip_dangerous_elements"]).lower()}',
            '# Extract title from HTML',
            f'extract_title = {str(default_config["html"]["extract_title"]).lower()}',
            '',
            '# Markdown output options',
            '[markdown]',
            '# Symbol to use for emphasis: "*" or "_"',
            f'emphasis_symbol = "{default_config["markdown"]["emphasis_symbol"]}"',
            '',
            '# PowerPoint conversion options',
            '[pptx]',
            '# Include speaker notes',
            f'include_notes = {str(default_config["pptx"]["include_notes"]).lower()}',
            '# Include slide numbers in output',
            f'slide_numbers = {str(default_config["pptx"]["slide_numbers"]).lower()}',
            '',
            '# EPUB conversion options',
            '[epub]',
            '# Merge all chapters into single output',
            f'merge_chapters = {str(default_config["epub"]["merge_chapters"]).lower()}',
            '# Include table of contents',
            f'include_toc = {str(default_config["epub"]["include_toc"]).lower()}',
            '',
            '# Jupyter Notebook conversion options',
            '[ipynb]',
            '# Truncate long outputs (null for no truncation, or line count)',
            'truncate_long_outputs = null',
            '',
            '# Email conversion options',
            '[eml]',
            '# Include email headers',
            f'include_headers = {str(default_config["eml"]["include_headers"]).lower()}',
            '# Preserve email thread structure',
            f'preserve_thread_structure = {str(default_config["eml"]["preserve_thread_structure"]).lower()}',
        ]
        output_text = '\n'.join(output_lines)
    else:
        # JSON output
        output_text = json.dumps(default_config, indent=2, ensure_ascii=False)

    # Write output
    if output_path:
        try:
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path_obj, 'w', encoding='utf-8') as f:
                f.write(output_text)

            print(f"Configuration written to {output_path}")
            return 0
        except Exception as e:
            print(f"Error writing configuration file: {e}", file=sys.stderr)
            return 1
    else:
        print(output_text)
        return 0


def handle_config_show_command(args: list[str] | None = None) -> int:
    """Handle config show command to display effective configuration.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'config show')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    from all2md.cli.config import get_config_search_paths, load_config_with_priority

    # Parse arguments
    output_format = 'toml'
    show_source = True

    if args:
        for arg in args:
            if arg in ('--help', '-h'):
                print("""Usage: all2md config show [OPTIONS]

Display the effective configuration that would be used by all2md.

This shows the merged configuration from all sources in priority order:
1. ALL2MD_CONFIG environment variable
2. .all2md.toml or .all2md.json in current directory
3. .all2md.toml or .all2md.json in home directory

Options:
  --format FORMAT    Output format: 'toml' (default) or 'json'
  --no-source       Don't show configuration source information
  -h, --help        Show this help message

Examples:
  all2md config show                    # Show effective config
  all2md config show --format json      # Show as JSON
  all2md config show --no-source        # Hide source info
""")
                return 0
            elif arg == '--format':
                # Get next arg
                idx = args.index(arg)
                if idx + 1 < len(args):
                    output_format = args[idx + 1]
            elif arg == '--no-source':
                show_source = False
            elif not arg.startswith('-') and args[args.index(arg) - 1] != '--format':
                print(f"Error: Unknown argument '{arg}'", file=sys.stderr)
                return 1

    # Validate format
    if output_format not in ('toml', 'json'):
        print(f"Error: Invalid format '{output_format}'. Use 'toml' or 'json'", file=sys.stderr)
        return 1

    # Load configuration with priority
    env_config_path = os.environ.get('ALL2MD_CONFIG')
    config = load_config_with_priority(
        explicit_path=None,
        env_var_path=env_config_path
    )

    # Show source information
    if show_source:
        print("Configuration Sources (in priority order):")
        print("-" * 60)

        if env_config_path:
            exists = Path(env_config_path).exists()
            status = "FOUND" if exists else "NOT FOUND"
            print(f"1. ALL2MD_CONFIG env var: {env_config_path} [{status}]")
        else:
            print("1. ALL2MD_CONFIG env var: (not set)")

        search_paths = get_config_search_paths()
        for i, path in enumerate(search_paths, start=2):
            exists = path.exists()
            status = "FOUND" if exists else "-"
            print(f"{i}. {path} [{status}]")

        print()

    # Display configuration
    if not config:
        print("No configuration found. Using defaults.")
        print("\nTo create a config file, run: all2md config generate --out .all2md.toml")
        return 0

    print("Effective Configuration:")
    print("=" * 60)

    if output_format == 'toml':
        import tomli_w
        output_text = tomli_w.dumps(config)
    else:
        output_text = json.dumps(config, indent=2, ensure_ascii=False)

    print(output_text)
    return 0


def handle_config_validate_command(args: list[str] | None = None) -> int:
    """Handle config validate command to check configuration file syntax.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'config validate')

    Returns
    -------
    int
        Exit code (0 for success, 1 for invalid config)

    """
    from all2md.cli.config import load_config_file

    # Parse arguments
    config_file = None

    if args:
        for arg in args:
            if arg in ('--help', '-h'):
                print("""Usage: all2md config validate <config-file>

Validate a configuration file for syntax errors.

Arguments:
  config-file        Path to configuration file (.toml or .json)

Options:
  -h, --help        Show this help message

Examples:
  all2md config validate .all2md.toml
  all2md config validate ~/.all2md.json
""")
                return 0
            elif not arg.startswith('-'):
                config_file = arg
                break

    if not config_file:
        print("Error: Config file path required", file=sys.stderr)
        print("Usage: all2md config validate <config-file>", file=sys.stderr)
        return 1

    # Attempt to load and validate
    try:
        config = load_config_file(config_file)
        print(f"Configuration file is valid: {config_file}")
        print(f"Format: {Path(config_file).suffix}")
        print(f"Keys found: {', '.join(config.keys()) if config else '(empty)'}")
        return 0
    except argparse.ArgumentTypeError as e:
        print(f"Invalid configuration file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error validating configuration: {e}", file=sys.stderr)
        return 1


def handle_config_command(args: list[str] | None = None) -> int | None:
    """Handle config subcommands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if config command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != 'config':
        return None

    # Get subcommand
    if len(args) < 2:
        print("""Usage: all2md config <subcommand> [OPTIONS]

Configuration management commands.

Subcommands:
  generate           Generate a default configuration file
  show              Display effective configuration from all sources
  validate          Validate a configuration file

Use 'all2md config <subcommand> --help' for more information.

Examples:
  all2md config generate --out .all2md.toml
  all2md config show
  all2md config validate .all2md.toml
""", file=sys.stderr)
        return 1

    subcommand = args[1]
    subcommand_args = args[2:]

    if subcommand == 'generate':
        return handle_config_generate_command(subcommand_args)
    elif subcommand == 'show':
        return handle_config_show_command(subcommand_args)
    elif subcommand == 'validate':
        return handle_config_validate_command(subcommand_args)
    else:
        print(f"Error: Unknown config subcommand '{subcommand}'", file=sys.stderr)
        print("Valid subcommands: generate, show, validate", file=sys.stderr)
        return 1


def handle_dependency_commands(args: list[str] | None = None) -> int | None:
    """Handle dependency management commands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if dependency command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args:
        return None

    # Check for config command
    if args[0] == 'config':
        return handle_config_command(args)

    # Check for list-formats command
    if args[0] in ('list-formats', 'formats'):
        return handle_list_formats_command(args[1:])

    # Check for list-transforms command
    if args[0] in ('list-transforms', 'transforms'):
        return handle_list_transforms_command(args[1:])

    # Check for dependency management commands
    if args[0] == 'check-deps':
        from all2md.dependencies import main as deps_main
        # Convert to standard deps CLI format
        deps_args = ['check']

        # Check for help flags first
        if len(args) > 1 and args[1] in ('--help', '-h'):
            deps_args.append('--help')
        elif len(args) > 1 and args[1] not in ('--help', '-h'):
            # Only add format if it's not a help flag
            deps_args.extend(['--format', args[1]])
            # Check for help flags after format
            if len(args) > 2 and args[2] in ('--help', '-h'):
                deps_args.append('--help')

        return deps_main(deps_args)

    elif args[0] == 'install-deps':
        from all2md.dependencies import main as deps_main
        # Convert to standard deps CLI format
        deps_args = ['install']

        # Check for help flags first
        if len(args) > 1 and args[1] in ('--help', '-h'):
            deps_args.append('--help')
        elif len(args) > 1 and args[1] not in ('--help', '-h'):
            # Only add format if it's not a help flag
            deps_args.append(args[1])  # format argument
            # Check for additional flags
            for arg in args[2:]:
                if arg == '--upgrade':
                    deps_args.append('--upgrade')
                elif arg in ('--help', '-h'):
                    deps_args.append('--help')

        return deps_main(deps_args)

    return None
