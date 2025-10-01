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
from all2md.exceptions import InputError, MarkdownConversionError


def _get_version() -> str:
    """Get the version of all2md package."""
    try:
        from importlib.metadata import version
        return version("all2md")
    except Exception:
        return "unknown"


def _get_about_info() -> str:
    """Get detailed information about all2md."""
    version_str = _get_version()
    return f"""all2md {version_str}

A Python document conversion library for transformation
between various file formats to Markdown.

Supported formats:
  • PDF documents
  • Word documents (DOCX)
  • PowerPoint presentations (PPTX)
  • HTML documents
  • Email messages (EML)
  • EPUB e-books
  • Jupyter Notebooks (IPYNB)
  • OpenDocument Text/Presentation (ODT/ODP)
  • Rich Text Format (RTF)
  • Excel spreadsheets (XLSX)
  • CSV/TSV files
  • 200+ text file formats

Features:
  • Advanced PDF parsing with table detection
  • Intelligent format detection from content
  • Configurable Markdown output options
  • Attachment handling (download, embed, skip)
  • Command-line interface with stdin support
  • Python API for programmatic use
  • Multi-file and directory processing
  • Rich terminal output and progress bars

Documentation: https://github.com/thomas.villani/all2md
License: MIT License
Author: Thomas Villani <thomas.villani@gmail.com>"""


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
        show_progress: bool = False
) -> Tuple[int, str, Optional[str]]:
    """Convert a single file to markdown.

    Parameters
    ----------
    input_path : Path
        Input file path
    output_path : Path, optional
        Output file path (None for stdout)
    options : Dict[str, Any]
        Conversion options
    format_arg : str
        Format specification
    show_progress : bool
        Whether to show progress

    Returns
    -------
    Tuple[int, str, Optional[str]]
        Exit code (0 for success), file path string, and error message if failed
    """
    from all2md.constants import EXIT_SUCCESS, get_exit_code_for_exception

    try:
        # Convert the document
        markdown_content = to_markdown(input_path, format=format_arg, **options)

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
        elif not isinstance(e, (MarkdownConversionError, InputError)):
            error_msg = f"Unexpected error: {e}"
        return exit_code, str(input_path), error_msg


def convert_single_file_for_collation(
        input_path: Path,
        options: Dict[str, Any],
        format_arg: str,
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
        markdown_content = to_markdown(input_path, format=format_arg, **options)

        # Add file header and separator
        header = f"# File: {input_path.name}\n\n"
        content_with_header = header + markdown_content

        return EXIT_SUCCESS, content_with_header, None

    except Exception as e:
        exit_code = get_exit_code_for_exception(e)
        error_msg = str(e)
        if isinstance(e, ImportError):
            error_msg = f"Missing dependency: {e}"
        elif not isinstance(e, (MarkdownConversionError, InputError)):
            error_msg = f"Unexpected error: {e}"
        return exit_code, "", error_msg


def process_with_rich_output(
        files: List[Path],
        args: argparse.Namespace,
        options: Dict[str, Any],
        format_arg: str
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

        if args.parallel and args.parallel != 1:
            # Parallel processing
            task_id = progress.add_task("[cyan]Converting files...", total=len(files))

            max_workers = args.parallel if args.parallel else None
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
                        elif not isinstance(e, (MarkdownConversionError, InputError)):
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
                        elif not isinstance(e, (MarkdownConversionError, InputError)):
                            error = f"Unexpected error: {e}"
                else:
                    exit_code, file_str, error = convert_single_file(
                        file,
                        output_path,
                        options,
                        format_arg,
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
        format_arg: str
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
        format_arg: str
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
        format_arg: str
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
            file, options, format_arg, file_separator
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

    # Auto-discover converters for format detection
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

        # Check if converter is available
        converter_available = True
        dependency_issues = []
        if converter_metadata and converter_metadata.required_packages:
            for pkg_name, version_spec in converter_metadata.required_packages:
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
    if args.parallel and args.parallel != 1:
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

    # Auto-discover converters
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
            for pkg_name, version_spec in converter_metadata.required_packages:
                if version_spec:
                    meets_req, installed_version = check_version_requirement(pkg_name, version_spec)
                    if not meets_req:
                        converter_available = False
                        any_issues = True
                        if installed_version:
                            dependency_status.append((pkg_name, 'version mismatch', installed_version, version_spec))
                        else:
                            dependency_status.append((pkg_name, 'missing', None, version_spec))
                    else:
                        dependency_status.append((pkg_name, 'ok', installed_version, version_spec))
                else:
                    from all2md.dependencies import check_package_installed
                    if not check_package_installed(pkg_name):
                        converter_available = False
                        any_issues = True
                        dependency_status.append((pkg_name, 'missing', None, None))
                    else:
                        dependency_status.append((pkg_name, 'ok', None, None))

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
        print(f"Files with unavailable converters: {unavailable_count}")
        return EXIT_DEPENDENCY_ERROR
    else:
        print("All detected converters are available")
        return 0


def handle_list_formats_command(args: Optional[list[str]] = None) -> int:
    """Handle list-formats command to show available converters.

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

Show information about available document converters.

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

    # Auto-discover converters
    registry.auto_discover()

    # Get all formats
    formats = registry.list_formats()
    if specific_format:
        if specific_format not in formats:
            from all2md.constants import EXIT_INPUT_ERROR
            print(f"Error: Format '{specific_format}' not found", file=sys.stderr)
            print(f"Available formats: {', '.join(formats)}", file=sys.stderr)
            return EXIT_INPUT_ERROR
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

        for pkg_name, version_spec in metadata.required_packages:
            if version_spec:
                meets_req, installed_version = check_version_requirement(pkg_name, version_spec)
                if not meets_req:
                    all_available = False
                    if installed_version:
                        dep_status.append((pkg_name, version_spec, 'mismatch', installed_version))
                    else:
                        dep_status.append((pkg_name, version_spec, 'missing', None))
                else:
                    dep_status.append((pkg_name, version_spec, 'ok', installed_version))
            else:
                installed_version = get_package_version(pkg_name)
                if installed_version:
                    dep_status.append((pkg_name, version_spec, 'ok', installed_version))
                else:
                    all_available = False
                    dep_status.append((pkg_name, version_spec, 'missing', None))

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
                    content.append(f"[bold]Converter Module:[/bold] {metadata.converter_module}")
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
                print(f"Converter: {metadata.converter_module}")
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

                print(f"{status} {info['name'].upper():12} {ext_str}")

            print(f"\nTotal: {len(format_info_list)} formats")
            print("Use 'all2md list-formats <format>' for detailed information")

    return 0


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
        from all2md.constants import EXIT_INPUT_ERROR
        print("Error: Input file is required", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Set up logging level
    # If --verbose is specified and --log-level is at default, use DEBUG
    if parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        # --log-level takes precedence if explicitly set
        log_level = getattr(logging, parsed_args.log_level.upper())

    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Handle stdin input
    if len(parsed_args.input) == 1 and parsed_args.input[0] == '-':
        from all2md.constants import EXIT_INPUT_ERROR
        # Set up options and validate
        try:
            options, format_arg = setup_and_validate_options(parsed_args)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_INPUT_ERROR

        # Validate arguments
        if not validate_arguments(parsed_args):
            return EXIT_INPUT_ERROR

        return process_stdin(parsed_args, options, format_arg)

    # Multi-file/directory processing
    files = collect_input_files(
        parsed_args.input,
        parsed_args.recursive,
        exclude_patterns=parsed_args.exclude
    )

    if not files:
        from all2md.constants import EXIT_INPUT_ERROR
        if parsed_args.exclude:
            print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
        else:
            print("Error: No valid input files found", file=sys.stderr)
        return EXIT_INPUT_ERROR

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
                    from all2md.constants import EXIT_INPUT_ERROR
                    if parsed_args.exclude:
                        print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
                    else:
                        print("Error: No valid input files found", file=sys.stderr)
                    return EXIT_INPUT_ERROR
        except argparse.ArgumentTypeError as e:
            from all2md.constants import EXIT_INPUT_ERROR
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_INPUT_ERROR

    # Validate arguments
    if not validate_arguments(parsed_args, files):
        from all2md.constants import EXIT_INPUT_ERROR
        return EXIT_INPUT_ERROR

    # Set up options
    try:
        options, format_arg = setup_and_validate_options(parsed_args)
    except argparse.ArgumentTypeError as e:
        from all2md.constants import EXIT_INPUT_ERROR
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_INPUT_ERROR

    # Delegate to multi-file processor
    return process_multi_file(files, parsed_args, options, format_arg)


if __name__ == "__main__":
    sys.exit(main())
