"""Command-line interface for all2md document conversion library.

This module provides a simple CLI tool for converting documents to Markdown
format using the all2md library. It supports all formats handled by the
library and provides convenient options for common use cases.

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
    $ all2md *.pdf  # Will use rich output and save to ./converted/
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
    from all2md.cli.actions import (
        EnvironmentAwareAction,
        EnvironmentAwareAppendAction,
        EnvironmentAwareBooleanAction,
        PositiveIntAction,
    )

    builder = DynamicCLIBuilder()
    parser = builder.build_parser()

    # Add new CLI options for enhanced features
    parser.add_argument(
        '--rich',
        action=EnvironmentAwareBooleanAction,
        help='Enable rich terminal output with formatting'
    )

    parser.add_argument(
        '--progress',
        action=EnvironmentAwareBooleanAction,
        help='Show progress bar for file conversions (automatically enabled for multiple files)'
    )

    parser.add_argument(
        '--output-dir',
        action=EnvironmentAwareAction,
        type=str,
        help='Directory to save converted files (for multi-file processing)'
    )

    parser.add_argument(
        '--recursive', '-r',
        action=EnvironmentAwareBooleanAction,
        help='Process directories recursively'
    )

    parser.add_argument(
        '--parallel', '-p',
        action=PositiveIntAction,
        nargs='?',
        const=None,
        default=1,
        help='Process files in parallel (optionally specify number of workers, must be positive)'
    )

    parser.add_argument(
        '--skip-errors',
        action=EnvironmentAwareBooleanAction,
        help='Continue processing remaining files if one fails'
    )

    parser.add_argument(
        '--preserve-structure',
        action=EnvironmentAwareBooleanAction,
        help='Preserve directory structure in output directory'
    )

    parser.add_argument(
        '--collate',
        action=EnvironmentAwareBooleanAction,
        help='Combine multiple files into a single output (stdout or file)'
    )

    parser.add_argument(
        '--no-summary',
        action=EnvironmentAwareBooleanAction,
        help='Disable summary output after processing multiple files'
    )

    parser.add_argument(
        '--save-config',
        type=str,
        help='Save current CLI arguments to a JSON configuration file'
    )

    parser.add_argument(
        '--dry-run',
        action=EnvironmentAwareBooleanAction,
        help='Show what would be converted without actually processing files'
    )

    parser.add_argument(
        '--exclude',
        action=EnvironmentAwareAppendAction,
        metavar='PATTERN',
        help='Exclude files matching this glob pattern (can be specified multiple times)'
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
        'input', 'out', 'save_config', 'about', 'version', 'dry_run', 'format', '_env_checked'
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
            # Skip argparse sentinel values that aren't JSON serializable
            if hasattr(value, '__class__') and value.__class__.__name__ == '_MISSING_TYPE':
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
) -> Tuple[bool, str, Optional[str]]:
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
    Tuple[bool, str, Optional[str]]
        Success status, file path string, and error message if failed
    """
    try:
        # Convert the document
        markdown_content = to_markdown(input_path, format=format_arg, **options)

        # Output the result
        if output_path:
            output_path.write_text(markdown_content, encoding="utf-8")
            return True, str(input_path), None
        else:
            print(markdown_content)
            return True, str(input_path), None

    except (MarkdownConversionError, InputError) as e:
        return False, str(input_path), str(e)
    except ImportError as e:
        return False, str(input_path), f"Missing dependency: {e}"
    except Exception as e:
        return False, str(input_path), f"Unexpected error: {e}"


def convert_single_file_for_collation(
        input_path: Path,
        options: Dict[str, Any],
        format_arg: str,
        file_separator: str = "\n\n---\n\n"
) -> Tuple[bool, str, Optional[str]]:
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
    Tuple[bool, str, Optional[str]]
        Success status, markdown content, and error message if failed
    """
    try:
        # Convert the document
        markdown_content = to_markdown(input_path, format=format_arg, **options)

        # Add file header and separator
        header = f"# File: {input_path.name}\n\n"
        content_with_header = header + markdown_content

        return True, content_with_header, None

    except (MarkdownConversionError, InputError) as e:
        return False, "", str(e)
    except ImportError as e:
        return False, "", f"Missing dependency: {e}"
    except Exception as e:
        return False, "", f"Unexpected error: {e}"


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
        Exit code (0 for success, 1 for failure)
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        print("Error: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
        return 1

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
                    success, file_str, error = future.result()

                    if success:
                        results.append((file, output_path))
                        console.print(f"[green]✓[/green] {file} → {output_path}")
                    else:
                        failed.append((file, error))
                        console.print(f"[red]✗[/red] {file}: {error}")
                        if not args.skip_errors:
                            break

                    progress.update(task_id, advance=1)
        else:
            # Sequential processing
            task_id = progress.add_task("[cyan]Converting files...", total=len(files))

            for file in files:
                output_path = generate_output_path(
                    file,
                    Path(args.output_dir) if args.output_dir else None,
                    args.preserve_structure,
                    base_input_dir
                )

                success, file_str, error = convert_single_file(
                    file,
                    output_path,
                    options,
                    format_arg,
                    False
                )

                if success:
                    results.append((file, output_path))
                    console.print(f"[green]✓[/green] {file} → {output_path}")
                else:
                    failed.append((file, error))
                    console.print(f"[red]✗[/red] {file}: {error}")
                    if not args.skip_errors:
                        break

                progress.update(task_id, advance=1)

    # Show summary
    if not args.no_summary:
        console.print()
        table = Table(title="Conversion Summary")
        table.add_column("Status", style="cyan", no_wrap=True)
        table.add_column("Count", style="magenta")

        table.add_row("✓ Successful", str(len(results)))
        table.add_row("✗ Failed", str(len(failed)))
        table.add_row("Total", str(len(files)))

        console.print(table)

    return 0 if len(failed) == 0 else 1


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
        Exit code (0 for success, 1 for failure)
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

            success, file_str, error = convert_single_file(
                file,
                output_path,
                options,
                format_arg,
                False
            )

            if success:
                print(f"Converted {file} -> {output_path}")
            else:
                print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
                failed.append((file, error))
                if not args.skip_errors:
                    break

    # Summary
    if not args.no_summary:
        print(f"\nConversion complete: {len(files) - len(failed)}/{len(files)} files successful")

    return 0 if len(failed) == 0 else 1


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
        Exit code (0 for success, 1 for failure)
    """
    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    failed = []

    for file in files:
        output_path = generate_output_path(
            file,
            Path(args.output_dir) if args.output_dir else None,
            args.preserve_structure,
            base_input_dir
        )

        success, file_str, error = convert_single_file(
            file,
            output_path,
            options,
            format_arg,
            False
        )

        if success:
            print(f"Converted {file} -> {output_path}")
        else:
            print(f"Error: Failed to convert {file}: {error}", file=sys.stderr)
            failed.append((file, error))
            if not args.skip_errors:
                break

    return 0 if len(failed) == 0 else 1


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
        Exit code (0 for success, 1 for failure)
    """
    collated_content = []
    failed = []
    file_separator = "\n\n---\n\n"

    # Determine output path
    output_path = None
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # Helper function to process files
    def process_file(file: Path) -> bool:
        """Process a single file for collation."""
        success, content, error = convert_single_file_for_collation(
            file, options, format_arg, file_separator
        )
        if success:
            collated_content.append(content)
            return True
        else:
            failed.append((file, error))
            return False

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
                    if process_file(file):
                        console.print(f"[green]✓[/green] Processed {file}")
                    else:
                        console.print(f"[red]✗[/red] {file}: {failed[-1][1]}")
                        if not args.skip_errors:
                            break
                    progress.update(task_id, advance=1)

        except ImportError:
            print("Error: Rich library not installed. Install with: pip install all2md[rich]", file=sys.stderr)
            return 1

    # Process with tqdm progress bar if requested
    elif show_progress:
        try:
            from tqdm import tqdm
            with tqdm(files, desc="Converting and collating files", unit="file") as pbar:
                for file in pbar:
                    pbar.set_postfix_str(f"Processing {file.name}")
                    if not process_file(file):
                        print(f"Error: Failed to convert {file}: {failed[-1][1]}", file=sys.stderr)
                        if not args.skip_errors:
                            break
        except ImportError:
            # Fallback to simple processing
            print("Warning: tqdm not installed. Install with: pip install all2md[progress]", file=sys.stderr)
            for file in files:
                if not process_file(file):
                    print(f"Error: Failed to convert {file}: {failed[-1][1]}", file=sys.stderr)
                    if not args.skip_errors:
                        break

    # Simple processing without progress indicators
    else:
        for file in files:
            if not process_file(file):
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

                table.add_row("✓ Successfully processed", str(len(collated_content)))
                table.add_row("✗ Failed", str(len(failed)))
                table.add_row("Total", str(len(files)))

                console.print(table)
            except ImportError:
                pass
        else:
            print(f"\nCollation complete: {len(collated_content)}/{len(files)} files processed successfully")

    return 0 if len(failed) == 0 else 1


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
    # Determine base input directory for structure preservation
    base_input_dir = None
    if args.preserve_structure and len(files) > 0:
        base_input_dir = Path(os.path.commonpath([f.parent for f in files]))

    print("DRY RUN MODE - Showing what would be processed")
    print(f"Found {len(files)} file(s) to convert")
    print()

    if args.rich:
        try:
            from rich.console import Console
            from rich.table import Table

            console = Console()
            table = Table(title="Dry Run - Planned Conversions")
            table.add_column("Input File", style="cyan", no_wrap=False)
            table.add_column("Output", style="green", no_wrap=False)
            table.add_column("Format", style="yellow")

            for file in files:
                if args.collate:
                    # For collation, all files go to one output
                    if args.out:
                        output_str = str(Path(args.out))
                    else:
                        output_str = "stdout (collated)"
                else:
                    # Individual file processing
                    if len(files) == 1 and args.out and not args.output_dir:
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

                table.add_row(
                    str(file),
                    output_str,
                    format_arg if format_arg != "auto" else "auto-detect"
                )

            console.print(table)

        except ImportError:
            # Fallback to simple output
            args.rich = False

    if not args.rich:
        # Simple text output
        for i, file in enumerate(files, 1):
            if args.collate:
                if args.out:
                    output_str = f" -> {args.out} (collated)"
                else:
                    output_str = " -> stdout (collated)"
            else:
                if len(files) == 1 and args.out and not args.output_dir:
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

            print(f"{i:3d}. {file}{output_str}")

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
        print("Error: Input file is required", file=sys.stderr)
        return 1

    # Set up logging level
    log_level = getattr(logging, parsed_args.log_level.upper())
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Handle stdin input
    if len(parsed_args.input) == 1 and parsed_args.input[0] == '-':
        # Set up options and validate
        try:
            options, format_arg = setup_and_validate_options(parsed_args)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        # Validate arguments
        if not validate_arguments(parsed_args):
            return 1

        return process_stdin(parsed_args, options, format_arg)

    # Multi-file/directory processing
    files = collect_input_files(
        parsed_args.input,
        parsed_args.recursive,
        exclude_patterns=parsed_args.exclude
    )

    if not files:
        if parsed_args.exclude:
            print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
        else:
            print("Error: No valid input files found", file=sys.stderr)
        return 1

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
                    if parsed_args.exclude:
                        print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
                    else:
                        print("Error: No valid input files found", file=sys.stderr)
                    return 1
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Validate arguments
    if not validate_arguments(parsed_args, files):
        return 1

    # Set up options
    try:
        options, format_arg = setup_and_validate_options(parsed_args)
    except argparse.ArgumentTypeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Delegate to multi-file processor
    return process_multi_file(files, parsed_args, options, format_arg)


if __name__ == "__main__":
    sys.exit(main())
