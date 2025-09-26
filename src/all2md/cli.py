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
"""

import argparse
import json
import logging
import sys
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Optional, cast

from . import to_markdown
from .cli_builder import DynamicCLIBuilder
from .exceptions import InputError, MarkdownConversionError
from .converter_registry import registry


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

    return parser


def parse_pdf_pages(pages_str: str) -> list[int]:
    """Parse comma-separated page numbers."""
    try:
        return [int(p.strip()) for p in pages_str.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid page numbers: {pages_str}") from e


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

    # Handle stdin input or check input file exists
    if parsed_args.input == '-':
        # Read from stdin
        try:
            stdin_data = sys.stdin.buffer.read()
            if not stdin_data:
                print("Error: No data received from stdin", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error reading from stdin: {e}", file=sys.stderr)
            return 1
        input_source = stdin_data
    else:
        # Regular file input
        input_path = Path(parsed_args.input)
        if not input_path.exists():
            print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
            return 1
        input_source = input_path

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

    # Map CLI arguments to options using dynamic mapping
    builder = DynamicCLIBuilder()
    options = builder.map_args_to_options(parsed_args, json_options)

    try:
        # Convert the document with format override if specified
        format_arg = parsed_args.format if parsed_args.format != "auto" else "auto"
        markdown_content = to_markdown(input_source, format=cast(str, format_arg), **options)

        # Output the result
        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            if parsed_args.input == '-':
                print(f"Converted stdin -> {output_path}")
            else:
                print(f"Converted {input_source} -> {output_path}")
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


if __name__ == "__main__":
    sys.exit(main())
