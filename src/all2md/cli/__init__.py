"""Command-line interface for all2md document conversion library.

This module provides a simple CLI tool for converting documents to Markdown
format using the all2md library. It supports all formats handled by the
library and provides convenient options for common use cases.

Environment Variable Support
----------------------------
All CLI options support environment variable defaults using the pattern
ALL2MD_<OPTION_NAME> where option names are converted to uppercase with
hyphens and dots replaced by underscores. CLI arguments always override
environment variables.

Examples
--------
Basic conversion:
    $ all2md document.pdf

Specify output file:
    $ all2md document.docx --out output.md

Download attachments:
    $ all2md document.docx --attachment-mode download --attachment-output-dir ./attachments

Use underscore emphasis:
    $ all2md document.html --markdown-emphasis-symbol "_"

Convert multiple files:
    $ all2md *.pdf --output-dir ./converted

Use rich formatting:
    $ all2md document.pdf --rich

Process directory recursively:
    $ all2md ./documents --recursive --output-dir ./markdown

Collate multiple files into one output:
    $ all2md *.pdf --collate --out combined.md

Use environment variables for defaults:
    $ export ALL2MD_RICH=true
    $ export ALL2MD_OUTPUT_DIR=./converted
    $ export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"
    $ all2md *.pdf  # Uses environment defaults
"""

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from all2md import to_markdown
from all2md.cli.builder import DynamicCLIBuilder
from all2md.exceptions import All2MdError


def _get_version() -> str:
    """Get the version of all2md package."""
    try:
        from importlib.metadata import version
        return version("all2md")
    except Exception:
        return "unknown"


def _get_about_info() -> str:
    """Get detailed information about all2md including system info and dependencies."""
    import platform
    from all2md.converter_registry import registry
    from all2md.dependencies import get_package_version, check_version_requirement

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
        metadata = registry.get_format_info(format_name)
        if not metadata:
            continue

        # Check if all dependencies are satisfied
        all_available = True
        if metadata.required_packages:
            for install_name, import_name, version_spec in metadata.required_packages:
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
        metadata = registry.get_format_info(format_name)
        if metadata and metadata.required_packages:
            for install_name, import_name, version_spec in metadata.required_packages:
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


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser using dynamic generation."""
    from all2md.cli.custom_actions import (
        TrackingAppendAction,
        TrackingPositiveIntAction,
        TrackingStoreAction,
        TrackingStoreTrueAction,
    )

    builder = DynamicCLIBuilder()
    parser = builder.build_parser()

    # Add new CLI options for enhanced features
    parser.add_argument(
        '--rich',
        action=TrackingStoreTrueAction,
        help='Enable rich terminal output with formatting'
    )

    parser.add_argument(
        '--pager',
        action=TrackingStoreTrueAction,
        help='Display output using system pager for long documents (stdout only)'
    )

    parser.add_argument(
        '--progress',
        action=TrackingStoreTrueAction,
        help='Show progress bar for file conversions (automatically enabled for multiple files)'
    )

    parser.add_argument(
        '--output-dir',
        action=TrackingStoreAction,
        type=str,
        help='Directory to save converted files (for multi-file processing)'
    )

    parser.add_argument(
        '--recursive', '-r',
        action=TrackingStoreTrueAction,
        help='Process directories recursively'
    )

    parser.add_argument(
        '--parallel', '-p',
        action=TrackingPositiveIntAction,
        nargs='?',
        const=None,
        default=1,
        help='Process files in parallel (optionally specify number of workers, must be positive)'
    )

    parser.add_argument(
        '--skip-errors',
        action=TrackingStoreTrueAction,
        help='Continue processing remaining files if one fails'
    )

    parser.add_argument(
        '--preserve-structure',
        action=TrackingStoreTrueAction,
        help='Preserve directory structure in output directory'
    )

    parser.add_argument(
        '--zip',
        action=TrackingStoreAction,
        nargs='?',
        const='auto',
        metavar='PATH',
        help='Create zip archive of output (optionally specify custom path, default: output_dir.zip)'
    )

    parser.add_argument(
        '--assets-layout',
        action=TrackingStoreAction,
        choices=['flat', 'by-stem', 'structured'],
        default='flat',
        help='Asset organization: flat (single assets/ dir), by-stem (assets/{doc}/), structured (preserve structure)'
    )

    parser.add_argument(
        '--watch',
        action=TrackingStoreTrueAction,
        help='Watch mode: monitor files/directories and convert on change (requires --output-dir)'
    )

    parser.add_argument(
        '--watch-debounce',
        action=TrackingStoreAction,
        type=float,
        default=1.0,
        metavar='SECONDS',
        help='Debounce delay for watch mode in seconds (default: 1.0)'
    )

    parser.add_argument(
        '--collate',
        action=TrackingStoreTrueAction,
        help='Combine multiple files into a single output (stdout or file)'
    )

    parser.add_argument(
        '--no-summary',
        action=TrackingStoreTrueAction,
        help='Disable summary output after processing multiple files'
    )

    parser.add_argument(
        '--save-config',
        type=str,
        help='Save current CLI arguments to a JSON configuration file'
    )

    parser.add_argument(
        '--dry-run',
        action=TrackingStoreTrueAction,
        help='Show what would be converted without actually processing files'
    )

    parser.add_argument(
        '--detect-only',
        action=TrackingStoreTrueAction,
        help='Show format detection results without conversion (useful for debugging batch inputs)'
    )

    parser.add_argument(
        '--exclude',
        action=TrackingAppendAction,
        metavar='PATTERN',
        help='Exclude files matching this glob pattern (can be specified multiple times)'
    )

    # Security preset flags
    security_group = parser.add_argument_group('Security preset options')
    security_group.add_argument(
        '--strict-html-sanitize',
        action=TrackingStoreTrueAction,
        help='Enable strict HTML sanitization (disables remote fetch, local files, strips dangerous elements)'
    )
    security_group.add_argument(
        '--safe-mode',
        action=TrackingStoreTrueAction,
        help='Balanced security for untrusted input (allows HTTPS remote fetch, strips dangerous elements)'
    )
    security_group.add_argument(
        '--paranoid-mode',
        action=TrackingStoreTrueAction,
        help='Maximum security settings (strict restrictions, reduced size limits)'
    )


    return parser




def parse_pdf_pages(pages_str: str) -> list[int]:
    """Parse comma-separated page numbers."""
    try:
        return [int(p.strip()) for p in pages_str.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid page numbers: {pages_str}") from e


def positive_int(value: str) -> int:
    """Validate positive integer for argparse."""
    try:
        ivalue = int(value)
        if ivalue <= 0:
            raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
        return ivalue
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer") from e


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
            # Check for plain object() sentinels (used for _UNSET in MarkdownOptions)
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
    from all2md.constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

    ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS

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
        import fnmatch
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


def generate_output_path(
        input_file: Path,
        output_dir: Optional[Path] = None,
        preserve_structure: bool = False,
        base_input_dir: Optional[Path] = None,
        dry_run: bool = False
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

    Returns
    -------
    Path
        Output file path
    """
    # Generate output filename
    output_name = input_file.stem + '.md'

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
        show_progress: bool = False
) -> Tuple[int, str, Optional[str]]:
    """Convert a single file to markdown."""

    from all2md.constants import EXIT_SUCCESS, get_exit_code_for_exception

    try:
        # Convert the document
        markdown_content = to_markdown(input_path, format=format_arg, transforms=transforms, **options)

        # Output the result
        if output_path:
            output_path.write_text(markdown_content, encoding="utf-8")
            return EXIT_SUCCESS, str(input_path), None
        else:
            print(markdown_content)
            return EXIT_SUCCESS, str(input_path), None

    except Exception as e:
        exit_code = get_exit_code_for_exception(e)
        error_msg = str(e)
        if isinstance(e, ImportError):
            error_msg = f"Missing dependency: {e}"
        elif not isinstance(e, All2MdError):
            error_msg = f"Unexpected error: {e}"
        return exit_code, str(input_path), error_msg


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
    from all2md.constants import EXIT_SUCCESS, get_exit_code_for_exception

    try:
        # Convert the document
        markdown_content = to_markdown(input_path, format=format_arg, transforms=transforms, **options)

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
    from all2md.constants import EXIT_SUCCESS, get_exit_code_for_exception

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

    # Show header
    console.print(Panel.fit(
        Text("all2md Document Converter", style="bold cyan"),
        subtitle=f"Processing {len(files)} file(s)"
    ))

    results = []
    failed = []
    max_exit_code = EXIT_SUCCESS

    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
    ) as progress:

        # Check if parallel processing is enabled
        # parallel can be: 1 (default, sequential), None (--parallel without value, auto CPU count), or N (explicit worker count)
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

                # Special case: single file to stdout with rich formatting
                # Process directly on main thread to avoid wasteful worker spawn
                if len(files) == 1 and not args.out and not args.output_dir:
                    file = files[0]
                    try:
                        # Convert the document
                        markdown_content = to_markdown(file, format=format_arg, **options)

                        # Render with Rich Markdown
                        from rich.markdown import Markdown
                        console.print(Markdown(markdown_content))

                        exit_code = EXIT_SUCCESS
                        error = None
                    except Exception as e:
                        exit_code = get_exit_code_for_exception(e)
                        error = str(e)
                        if isinstance(e, ImportError):
                            error = f"Missing dependency: {e}"
                        elif not isinstance(e, All2MdError):
                            error = f"Unexpected error: {e}"

                    if exit_code == EXIT_SUCCESS:
                        results.append((file, None))
                        console.print(f"[green]OK[/green] Converted {file}")
                    else:
                        failed.append((file, error))
                        console.print(f"[red]ERROR[/red] {file}: {error}")
                        max_exit_code = max(max_exit_code, exit_code)

                    progress.update(task_id, advance=1)
                else:
                    # Submit files to executor for parallel processing
                    for file in files:
                        output_path = generate_output_path(
                            file,
                            Path(args.output_dir) if args.output_dir else None,
                            args.preserve_structure,
                            base_input_dir
                        )
                        future = executor.submit(
                            convert_single_file,
                            file,
                            output_path,
                            options,
                            format_arg,
                            transforms,
                            False
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
                # For single files without explicit output, use stdout with rich formatting
                if len(files) == 1 and not args.out and not args.output_dir:
                    output_path = None
                else:
                    output_path = generate_output_path(
                        file,
                        Path(args.output_dir) if args.output_dir else None,
                        args.preserve_structure,
                        base_input_dir
                    )

                # Special handling for single file rich output to stdout
                if len(files) == 1 and not args.out and not args.output_dir:
                    try:
                        # Convert the document
                        markdown_content = to_markdown(file, format=format_arg, **options)

                        # Render with Rich Markdown
                        from rich.markdown import Markdown
                        console.print(Markdown(markdown_content))

                        exit_code = EXIT_SUCCESS
                        error = None
                    except Exception as e:
                        exit_code = get_exit_code_for_exception(e)
                        error = str(e)
                        if isinstance(e, ImportError):
                            error = f"Missing dependency: {e}"
                        elif not isinstance(e, All2MdError):
                            error = f"Unexpected error: {e}"
                else:
                    exit_code, file_str, error = convert_single_file(
                        file,
                        output_path,
                        options,
                        format_arg,
                        transforms,
                        False
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

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)
    """
    from all2md.constants import EXIT_SUCCESS

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

            output_path = generate_output_path(
                file,
                Path(args.output_dir) if args.output_dir else None,
                args.preserve_structure,
                base_input_dir
            )

            exit_code, file_str, error = convert_single_file(
                file,
                output_path,
                options,
                format_arg,
                transforms,
                False
            )

            if exit_code == EXIT_SUCCESS:
                print(f"Converted {file} -> {output_path}")
            else:
                print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
                failed.append((file, error))
                max_exit_code = max(max_exit_code, exit_code)
                if not args.skip_errors:
                    break

    # Summary
    if not args.no_summary:
        print(f"\nConversion complete: {len(files) - len(failed)}/{len(files)} files successful")

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

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)
    """
    from all2md.constants import EXIT_SUCCESS

    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    failed = []
    max_exit_code = EXIT_SUCCESS

    for file in files:
        output_path = generate_output_path(
            file,
            Path(args.output_dir) if args.output_dir else None,
            args.preserve_structure,
            base_input_dir
        )

        exit_code, file_str, error = convert_single_file(
            file,
            output_path,
            options,
            format_arg,
            transforms,
            False
        )

        if exit_code == EXIT_SUCCESS:
            print(f"Converted {file} -> {output_path}")
        else:
            print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
            failed.append((file, error))
            max_exit_code = max(max_exit_code, exit_code)
            if not args.skip_errors:
                break

    return max_exit_code


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

    Returns
    -------
    int
        Exit code (0 for success, highest error code otherwise)
    """
    from all2md.constants import EXIT_SUCCESS

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
            print(f"Collated {len(collated_content)} files -> {output_path}")
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
            print(f"\nCollation complete: {len(collated_content)}/{len(files)} files processed successfully")

    return max_exit_code


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
    file_info_list = []
    for file in files:
        # Detect format for this file
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(file)
            # Try to determine detection method
            if file.suffix.lower() in [ext for fmt_name in registry.list_formats()
                                       for ext in registry.get_format_info(fmt_name).extensions
                                       if registry.get_format_info(fmt_name)]:
                detection_method = "extension"
            else:
                detection_method = "content analysis"

        # Get converter metadata
        converter_metadata = registry.get_format_info(detected_format)

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
                        output_path = generate_output_path(
                            file,
                            Path(args.output_dir) if args.output_dir else None,
                            args.preserve_structure,
                            base_input_dir,
                            dry_run=True
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
                    output_path = generate_output_path(
                        file,
                        Path(args.output_dir) if args.output_dir else None,
                        args.preserve_structure,
                        base_input_dir,
                        dry_run=True
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
    detection_results = []
    any_issues = False

    for file in files:
        # Detect format
        if format_arg != "auto":
            detected_format = format_arg
            detection_method = "explicit (--format)"
        else:
            detected_format = registry.detect_format(file)

            # Determine detection method
            metadata = registry.get_format_info(detected_format)
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
        converter_metadata = registry.get_format_info(detected_format)

        # Check dependencies
        converter_available = True
        dependency_status = []

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
                            dependency_status.append((install_name, 'version mismatch', installed_version, version_spec))
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
        from all2md.constants import EXIT_DEPENDENCY_ERROR
        unavailable_count = sum(1 for r in detection_results if not r['available'])
        print(f"Files with unavailable parsers: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected parsers are available")
        return 0


def handle_list_formats_command(args: Optional[list[str]] = None) -> int:
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
    from all2md.converter_registry import registry
    from all2md.dependencies import check_version_requirement, get_package_version

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
            from all2md.constants import EXIT_VALIDATION_ERROR
            print(f"Error: Format '{specific_format}' not found", file=sys.stderr)
            print(f"Available formats: {', '.join(formats)}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
        formats = [specific_format]

    # Gather format information
    format_info_list = []
    for format_name in formats:
        metadata = registry.get_format_info(format_name)
        if not metadata:
            continue

        # Check dependency status
        all_available = True
        dep_status = []

        # required_packages is now a list of 3-tuples: (install_name, import_name, version_spec)
        for install_name, import_name, version_spec in metadata.required_packages:
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
                    metadata = info['metadata']

                    # Create main panel
                    content = []
                    content.append(f"[bold]Format:[/bold] {info['name'].upper()}")
                    content.append(f"[bold]Description:[/bold] {metadata.description or 'N/A'}")
                    content.append(f"[bold]Extensions:[/bold] {', '.join(metadata.extensions) or 'N/A'}")
                    content.append(f"[bold]MIME Types:[/bold] {', '.join(metadata.mime_types) or 'N/A'}")
                    content.append(f"[bold]Converter:[/bold] {metadata.get_converter_display_string()}")
                    content.append(f"[bold]Priority:[/bold] {metadata.priority}")

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
                            install_cmd = metadata.get_install_command()
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
                metadata = info['metadata']
                print(f"\n{info['name'].upper()} Format")
                print("=" * 60)
                print(f"Description: {metadata.description or 'N/A'}")
                print(f"Extensions: {', '.join(metadata.extensions) or 'N/A'}")
                print(f"MIME Types: {', '.join(metadata.mime_types) or 'N/A'}")
                print(f"Converter: {metadata.get_converter_display_string()}")
                print(f"Priority: {metadata.priority}")

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
                        install_cmd = metadata.get_install_command()
                        print(f"\nInstall with: {install_cmd}")
                else:
                    print("\nNo dependencies required")
        else:
            print("\nAll2MD Supported Formats")
            print("=" * 60)
            for info in format_info_list:
                metadata = info['metadata']
                status = "[OK]" if info['all_available'] else "[X]"
                ext_str = ", ".join(metadata.extensions[:4])
                if len(metadata.extensions) > 4:
                    ext_str += f" +{len(metadata.extensions) - 4}"

                # Capabilities
                has_parser = metadata.parser_class is not None
                has_renderer = metadata.renderer_class is not None
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


def handle_list_transforms_command(args: Optional[list[str]] = None) -> int:
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
    try:
        from all2md.transforms import registry as transform_registry
    except ImportError:
        print("Error: Transform system not available", file=sys.stderr)
        return 1

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

    # Discover transforms
    transform_registry.discover_plugins()
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


def handle_convert_command(args: Optional[list[str]] = None) -> Optional[int]:
    """Handle the `convert` subcommand for bidirectional conversions."""
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != 'convert':
        return None

    convert_args = args[1:]
    parser = create_parser()
    parsed_args = parser.parse_args(convert_args)

    provided_args = getattr(parsed_args, '_provided_args', set())

    if 'output_type' not in provided_args:
        parsed_args.output_type = 'auto'

    if not parsed_args.out and not parsed_args.output_dir and len(parsed_args.input) == 2:
        parsed_args.out = parsed_args.input[-1]
        parsed_args.input = parsed_args.input[:1]

    if not parsed_args.options_json:
        env_config = os.environ.get('ALL2MD_CONFIG_JSON')
        if env_config:
            parsed_args.options_json = env_config

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
    from all2md.converter_registry import registry
    if target_format in ('auto', 'markdown'):
        return '.md'

    try:
        metadata = registry.get_format_info(target_format)
        if metadata and metadata.extensions:
            return metadata.extensions[0]
    except Exception:
        pass

    return f'.{target_format}'


def _run_convert_command(parsed_args: argparse.Namespace) -> int:
    from all2md.constants import EXIT_SUCCESS, EXIT_VALIDATION_ERROR, EXIT_FILE_ERROR, get_exit_code_for_exception
    from all2md.cli.processors import (
        process_stdin,
        setup_and_validate_options,
        validate_arguments,
    )

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

    try:
        from all2md import convert
    except ImportError:
        print("Error: Unable to import conversion API", file=sys.stderr)
        return 1

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
                    source_format=format_arg,
                    target_format=target_format,
                    transforms=transforms,
                    **options,
                )

                if isinstance(rendered, bytes):
                    rendered_text = rendered.decode('utf-8', errors='replace')
                else:
                    rendered_text = rendered or ""

                if parsed_args.pager:
                    try:
                        from rich.console import Console
                        console = Console()
                        with console.pager(styles=True):
                            console.print(rendered_text)
                    except ImportError:
                        print(rendered_text)
                else:
                    print(rendered_text)
                successes.append((file, None))
                continue

            convert(
                file,
                output=output_path,
                source_format=format_arg,
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


def handle_dependency_commands(args: Optional[list[str]] = None) -> Optional[int]:
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


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point with focused delegation to specialized processors."""
    from all2md.cli.processors import (
        load_options_from_json,
        merge_exclusion_patterns_from_json,
        process_multi_file,
        process_stdin,
        setup_and_validate_options,
        validate_arguments,
    )

    convert_result = handle_convert_command(args)
    if convert_result is not None:
        return convert_result

    # Check for dependency management commands first
    deps_result = handle_dependency_commands(args)
    if deps_result is not None:
        return deps_result

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Check for ALL2MD_CONFIG_JSON environment variable if --options-json not provided
    if not parsed_args.options_json:
        env_config = os.environ.get('ALL2MD_CONFIG_JSON')
        if env_config:
            parsed_args.options_json = env_config

    # Handle --about flag
    if parsed_args.about:
        print(_get_about_info())
        return 0

    # Handle --save-config
    if parsed_args.save_config:
        try:
            save_config_to_file(parsed_args, parsed_args.save_config)
            return 0
        except Exception as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)
            return 1

    # Ensure input is provided when not using special flags
    if not parsed_args.input:
        from all2md.constants import EXIT_VALIDATION_ERROR
        print("Error: Input file is required", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Set up logging level - configures root logger for all modules
    # Note: All modules use logging.getLogger(__name__) for consistent logger hierarchy
    # --trace takes highest precedence, then --verbose, then --log-level
    if parsed_args.trace:
        log_level = logging.DEBUG
    elif parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        # --log-level takes precedence if explicitly set
        log_level = getattr(logging, parsed_args.log_level.upper())

    # Configure logging with file handler if --log-file is specified
    _configure_logging(
        log_level,
        log_file=parsed_args.log_file,
        trace_mode=parsed_args.trace
    )

    # Handle stdin input
    if len(parsed_args.input) == 1 and parsed_args.input[0] == '-':
        from all2md.constants import EXIT_VALIDATION_ERROR
        # Set up options and validate
        try:
            options, format_arg, transforms = setup_and_validate_options(parsed_args)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        # Validate arguments
        if not validate_arguments(parsed_args):
            return EXIT_VALIDATION_ERROR

        return process_stdin(parsed_args, options, format_arg, transforms)

    # Multi-file/directory processing
    files = collect_input_files(
        parsed_args.input,
        parsed_args.recursive,
        exclude_patterns=parsed_args.exclude
    )

    if not files:
        from all2md.constants import EXIT_FILE_ERROR
        if parsed_args.exclude:
            print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
        else:
            print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Handle exclusion patterns from JSON
    if parsed_args.options_json:
        try:
            json_options = load_options_from_json(parsed_args.options_json)
            updated_patterns = merge_exclusion_patterns_from_json(parsed_args, json_options)

            if updated_patterns:
                parsed_args.exclude = updated_patterns
                # Re-collect files with updated exclusion patterns
                files = collect_input_files(
                    parsed_args.input,
                    parsed_args.recursive,
                    exclude_patterns=parsed_args.exclude
                )

                if not files:
                    from all2md.constants import EXIT_FILE_ERROR
                    if parsed_args.exclude:
                        print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
                    else:
                        print("Error: No valid input files found", file=sys.stderr)
                    return EXIT_FILE_ERROR
        except argparse.ArgumentTypeError as e:
            from all2md.constants import EXIT_VALIDATION_ERROR
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    # Validate arguments
    if not validate_arguments(parsed_args, files):
        from all2md.constants import EXIT_VALIDATION_ERROR
        return EXIT_VALIDATION_ERROR

    # Set up options
    try:
        options, format_arg, transforms = setup_and_validate_options(parsed_args)
    except argparse.ArgumentTypeError as e:
        from all2md.constants import EXIT_VALIDATION_ERROR
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Handle watch mode if requested
    if parsed_args.watch:
        from all2md.constants import EXIT_VALIDATION_ERROR

        # Watch mode requires --output-dir
        if not parsed_args.output_dir:
            print("Error: --watch requires --output-dir to be specified", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        # Import and run watch mode
        from all2md.cli.watch import run_watch_mode

        # Convert input paths (which might be strings) to Path objects
        paths_to_watch = [Path(f) for f in parsed_args.input]

        return run_watch_mode(
            paths=paths_to_watch,
            output_dir=Path(parsed_args.output_dir),
            options=options,
            format_arg=format_arg,
            transforms=transforms,
            debounce=parsed_args.watch_debounce,
            preserve_structure=parsed_args.preserve_structure,
            recursive=parsed_args.recursive,
            exclude_patterns=parsed_args.exclude
        )

    # Delegate to multi-file processor
    return process_multi_file(files, parsed_args, options, format_arg, transforms)


if __name__ == "__main__":
    sys.exit(main())
