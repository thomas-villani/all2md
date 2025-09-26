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
from typing import Any, Dict, List, Optional, Tuple, cast

from . import to_markdown
from .cli_builder import DynamicCLIBuilder
from .exceptions import InputError, MarkdownConversionError


def get_env_var_value(key: str) -> Optional[str]:
    """Get environment variable with ALL2MD_ prefix.

    Parameters
    ----------
    key : str
        The parameter name (e.g., 'rich', 'output_dir')

    Returns
    -------
    Optional[str]
        Environment variable value or None if not set
    """
    env_key = f"ALL2MD_{key.upper().replace('-', '_')}"
    return os.environ.get(env_key)


def apply_env_vars_to_parser(parser: argparse.ArgumentParser) -> None:
    """Apply environment variables as defaults to parser arguments.

    This sets environment variable values as defaults for argparse arguments.
    CLI arguments will still take precedence over environment variables.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The argument parser to modify
    """
    for action in parser._actions:
        if action.dest and action.dest != 'help':
            # Convert argument dest to environment variable format
            env_value = get_env_var_value(action.dest)

            if env_value is not None:
                # Handle different argument types
                if action.type is int:
                    try:
                        action.default = int(env_value)
                    except ValueError:
                        logging.warning(f"Invalid integer value for ALL2MD_{action.dest.upper()}: {env_value}")
                elif action.type is float:
                    try:
                        action.default = float(env_value)
                    except ValueError:
                        logging.warning(f"Invalid float value for ALL2MD_{action.dest.upper()}: {env_value}")
                elif hasattr(action, 'choices') and action.choices:
                    # Handle choice arguments
                    if env_value in action.choices:
                        action.default = env_value
                    else:
                        logging.warning(f"Invalid choice for ALL2MD_{action.dest.upper()}: {env_value}. Choices: {list(action.choices)}")
                elif hasattr(action, '__class__') and action.__class__.__name__ == '_StoreTrueAction':
                    # Handle boolean flags
                    action.default = env_value.lower() in ('true', '1', 'yes', 'on')
                elif hasattr(action, '__class__') and action.__class__.__name__ == '_StoreFalseAction':
                    # Handle negative boolean flags
                    action.default = env_value.lower() not in ('true', '1', 'yes', 'on')
                else:
                    # Handle string arguments
                    action.default = env_value


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
    builder = DynamicCLIBuilder()
    parser = builder.build_parser()

    # Update version to show actual version
    for action in parser._actions:
        if action.dest == 'version':
            action.version = f"all2md {_get_version()}"
            break

    # Add new CLI options for enhanced features
    parser.add_argument(
        '--rich',
        action='store_true',
        help='Enable rich terminal output with formatting'
    )

    parser.add_argument(
        '--progress',
        action='store_true',
        help='Show progress bar for file conversions (automatically enabled for multiple files)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        help='Directory to save converted files (for multi-file processing)'
    )

    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Process directories recursively'
    )

    parser.add_argument(
        '--parallel', '-p',
        type=positive_int,
        nargs='?',
        const=None,
        default=1,
        help='Process files in parallel (optionally specify number of workers, must be positive)'
    )

    parser.add_argument(
        '--skip-errors',
        action='store_true',
        help='Continue processing remaining files if one fails'
    )

    parser.add_argument(
        '--preserve-structure',
        action='store_true',
        help='Preserve directory structure in output directory'
    )

    parser.add_argument(
        '--collate',
        action='store_true',
        help='Combine multiple files into a single output (stdout or file)'
    )

    parser.add_argument(
        '--no-summary',
        action='store_true',
        help='Disable summary output after processing multiple files'
    )

    # Apply environment variables as defaults
    apply_env_vars_to_parser(parser)

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
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value} is not a valid integer")


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


def collect_input_files(
    input_paths: List[str],
    recursive: bool = False,
    extensions: Optional[List[str]] = None
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

    Returns
    -------
    List[Path]
        List of file paths to process
    """
    from .constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, PLAINTEXT_EXTENSIONS

    ALL_ALLOWED_EXTENSIONS = PLAINTEXT_EXTENSIONS + DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS

    files = []

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
    return files


def generate_output_path(
    input_file: Path,
    output_dir: Optional[Path] = None,
    preserve_structure: bool = False,
    base_input_dir: Optional[Path] = None
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

        # Ensure output directory exists
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
        markdown_content = to_markdown(input_path, format=cast(str, format_arg), **options)

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
        markdown_content = to_markdown(input_path, format=cast(str, format_arg), **options)

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


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Handle --about flag
    if parsed_args.about:
        print(_get_about_info())
        return 0

    # Ensure input is provided when not using --about
    if not parsed_args.input:
        print("Error: Input file is required", file=sys.stderr)
        return 1

    # Set up logging level
    log_level = getattr(logging, parsed_args.log_level.upper())
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Handle stdin input
    if len(parsed_args.input) == 1 and parsed_args.input[0] == '-':
        # Read from stdin (single file mode)
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

        # Validate attachment options
        if parsed_args.attachment_output_dir and parsed_args.attachment_mode != "download":
            print("Warning: --attachment-output-dir specified but attachment mode is "
                  f"'{parsed_args.attachment_mode}' (not 'download')", file=sys.stderr)

        # Load options from JSON file if specified
        json_options = None
        if parsed_args.options_json:
            try:
                json_options = load_options_from_json(parsed_args.options_json)
            except argparse.ArgumentTypeError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 1

        # Map CLI arguments to options
        builder = DynamicCLIBuilder()
        options = builder.map_args_to_options(parsed_args, json_options)

        try:
            # Convert the document
            format_arg = parsed_args.format if parsed_args.format != "auto" else "auto"
            markdown_content = to_markdown(input_source, format=cast(str, format_arg), **options)

            # Output the result
            if parsed_args.out:
                output_path = Path(parsed_args.out)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown_content, encoding="utf-8")
                print(f"Converted stdin -> {output_path}")
            else:
                print(markdown_content)

            return 0

        except (MarkdownConversionError, InputError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except ImportError as e:
            print(f"Missing dependency: {e}", file=sys.stderr)
            print("Install required dependencies with: pip install all2md[full]", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)
            return 1

    # Multi-file/directory processing
    files = collect_input_files(parsed_args.input, parsed_args.recursive)

    if not files:
        print("Error: No valid input files found", file=sys.stderr)
        return 1

    # Validate output directory if specified
    if parsed_args.output_dir:
        output_dir_path = Path(parsed_args.output_dir)
        if output_dir_path.exists() and not output_dir_path.is_dir():
            print(f"Error: --output-dir must be a directory, not a file: {parsed_args.output_dir}", file=sys.stderr)
            return 1

    # Validate options
    if parsed_args.attachment_output_dir and parsed_args.attachment_mode != "download":
        print("Warning: --attachment-output-dir specified but attachment mode is "
              f"'{parsed_args.attachment_mode}' (not 'download')", file=sys.stderr)

    # For multi-file, --out becomes --output-dir
    if len(files) > 1 and parsed_args.out and not parsed_args.output_dir:
        print("Warning: --out is ignored for multiple files. Use --output-dir instead.", file=sys.stderr)

    # Load options
    json_options = None
    if parsed_args.options_json:
        try:
            json_options = load_options_from_json(parsed_args.options_json)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Map CLI arguments to options
    builder = DynamicCLIBuilder()
    options = builder.map_args_to_options(parsed_args, json_options)
    format_arg = parsed_args.format if parsed_args.format != "auto" else "auto"

    # Process single file
    if len(files) == 1 and not parsed_args.rich and not parsed_args.progress:
        file = files[0]

        # Determine output path
        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
        elif parsed_args.output_dir:
            output_path = generate_output_path(file, Path(parsed_args.output_dir), False, None)
        else:
            output_path = None

        success, file_str, error = convert_single_file(file, output_path, options, format_arg, False)

        if success:
            if output_path:
                print(f"Converted {file} -> {output_path}")
            return 0
        else:
            print(f"Error: {error}", file=sys.stderr)
            return 1

    # Process multiple files or with special output
    if parsed_args.collate:
        return process_files_collated(files, parsed_args, options, format_arg)
    elif parsed_args.rich:
        return process_with_rich_output(files, parsed_args, options, format_arg)
    elif parsed_args.progress or len(files) > 1:
        return process_with_progress_bar(files, parsed_args, options, format_arg)
    else:
        return process_files_simple(files, parsed_args, options, format_arg)


if __name__ == "__main__":
    sys.exit(main())
