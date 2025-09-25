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
import logging
import sys
from dataclasses import fields
from pathlib import Path
from typing import Optional

from . import to_markdown
from .exceptions import MdparseConversionError, MdparseInputError
from .options import DocxOptions, EmlOptions, HtmlOptions, MarkdownOptions, PdfOptions, PptxOptions


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="all2md",
        description="Convert documents to Markdown format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported formats:
  PDF, Word (DOCX), PowerPoint (PPTX), HTML, Email (EML),
  Excel (XLSX), images (PNG, JPEG, GIF), and 200+ text formats

Examples:
  all2md document.pdf
  all2md document.docx --out output.md
  all2md document.html --attachment-mode download --attachment-output-dir ./images
  all2md presentation.pptx --markdown-emphasis-symbol "_"
        """,
    )

    # Input file (required)
    parser.add_argument("input", help="Input file to convert")

    # Output options
    parser.add_argument(
        "--out", "-o",
        help="Output file path (default: print to stdout)"
    )

    # Common attachment options
    parser.add_argument(
        "--attachment-mode",
        choices=["skip", "alt_text", "download", "base64"],
        default="alt_text",
        help="How to handle attachments/images (default: alt_text)"
    )
    parser.add_argument(
        "--attachment-output-dir",
        help="Directory to save attachments when using download mode"
    )
    parser.add_argument(
        "--attachment-base-url",
        help="Base URL for resolving attachment references"
    )

    # Common Markdown formatting options
    parser.add_argument(
        "--markdown-emphasis-symbol",
        choices=["*", "_"],
        default="*",
        help="Symbol to use for emphasis/italic text (default: *)"
    )
    parser.add_argument(
        "--markdown-bullet-symbols",
        default="*-+",
        help="Characters to cycle through for bullet lists (default: *-+)"
    )
    parser.add_argument(
        "--markdown-page-separator",
        default="-----",
        help="Text used to separate pages (default: -----)"
    )

    # PDF-specific options
    pdf_group = parser.add_argument_group("PDF options")
    pdf_group.add_argument(
        "--pdf-pages",
        help="Specific pages to convert (comma-separated, 0-based indexing)"
    )
    pdf_group.add_argument(
        "--pdf-password",
        help="Password for encrypted PDF documents"
    )
    pdf_group.add_argument(
        "--pdf-detect-columns",
        action="store_true",
        dest="pdf_detect_columns",
        help="Enable multi-column layout detection (default: enabled)"
    )
    pdf_group.add_argument(
        "--pdf-no-detect-columns",
        action="store_false",
        dest="pdf_detect_columns",
        help="Disable multi-column layout detection"
    )
    parser.set_defaults(pdf_detect_columns=True)

    # HTML-specific options
    html_group = parser.add_argument_group("HTML options")
    html_group.add_argument(
        "--html-extract-title",
        action="store_true",
        help="Extract and use HTML <title> element as main heading"
    )
    html_group.add_argument(
        "--html-strip-dangerous-elements",
        action="store_true",
        help="Remove potentially dangerous HTML elements (script, style, etc.)"
    )

    # PowerPoint-specific options
    pptx_group = parser.add_argument_group("PowerPoint options")
    pptx_group.add_argument(
        "--pptx-slide-numbers",
        action="store_true",
        help="Include slide numbers in output"
    )
    pptx_group.add_argument(
        "--pptx-no-include-notes",
        action="store_false",
        dest="pptx_include_notes",
        default=True,
        help="Exclude speaker notes from conversion"
    )

    # Email-specific options
    eml_group = parser.add_argument_group("Email options")
    eml_group.add_argument(
        "--eml-no-include-headers",
        action="store_false",
        dest="eml_include_headers",
        default=True,
        help="Exclude email headers from output"
    )
    eml_group.add_argument(
        "--eml-no-preserve-thread-structure",
        action="store_false",
        dest="eml_preserve_thread_structure",
        default=True,
        help="Don't maintain email thread/reply chain structure"
    )

    # Format override option
    parser.add_argument(
        "--format",
        choices=["auto", "pdf", "docx", "pptx", "html", "eml", "rtf", "ipynb", "csv", "tsv", "xlsx", "image", "txt"],
        default="auto",
        help="Force specific file format instead of auto-detection (default: auto)"
    )

    # Logging level option
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set logging level for debugging (default: WARNING)"
    )

    return parser


def parse_pdf_pages(pages_str: str) -> list[int]:
    """Parse comma-separated page numbers."""
    try:
        return [int(p.strip()) for p in pages_str.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid page numbers: {pages_str}") from e


def _map_cli_args_to_options(parsed_args: argparse.Namespace) -> dict:
    """Map CLI argument names to dataclass field names.

    This function handles the mapping between CLI argument names (like 'pdf_pages')
    and the actual dataclass field names (like 'pages' in PdfOptions).

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command line arguments

    Returns
    -------
    dict
        Mapped options dictionary ready for to_markdown()
    """
    options = {}
    args_dict = vars(parsed_args)

    # Get field names for each options class
    markdown_fields = {field.name for field in fields(MarkdownOptions)}
    pdf_fields = {field.name for field in fields(PdfOptions)}
    html_fields = {field.name for field in fields(HtmlOptions)}
    pptx_fields = {field.name for field in fields(PptxOptions)}
    eml_fields = {field.name for field in fields(EmlOptions)}
    docx_fields = {field.name for field in fields(DocxOptions)}

    # Define format prefix mappings
    format_mappings = {
        'pdf_': pdf_fields,
        'html_': html_fields,
        'pptx_': pptx_fields,
        'eml_': eml_fields,
        'docx_': docx_fields,
    }

    # Process each argument
    for arg_name, arg_value in args_dict.items():
        # Skip None values and special arguments
        if arg_value is None or arg_name in ['input', 'out', 'format', 'log_level']:
            continue

        # Handle attachment options (no prefix mapping needed)
        if arg_name.startswith('attachment_'):
            # Only include non-default values
            if (arg_name == 'attachment_mode' and arg_value != 'alt_text') or \
               (arg_name != 'attachment_mode' and arg_value is not None):
                options[arg_name] = arg_value
            continue

        # Handle markdown options (remove markdown_ prefix)
        if arg_name.startswith('markdown_'):
            field_name = arg_name[9:]  # Remove 'markdown_' prefix
            if field_name in markdown_fields:
                # Only include if different from default
                defaults = {'emphasis_symbol': '*', 'bullet_symbols': '*-+', 'page_separator': '-----'}
                if arg_value != defaults.get(field_name, arg_value):
                    options[field_name] = arg_value
            continue

        # Handle format-specific options
        mapped = False
        for prefix, field_set in format_mappings.items():
            if arg_name.startswith(prefix):
                field_name = arg_name[len(prefix):]  # Remove prefix
                if field_name in field_set:
                    # Handle special cases
                    if arg_name == 'pdf_pages' and arg_value:
                        options['pages'] = parse_pdf_pages(arg_value)
                    elif arg_name == 'pdf_detect_columns':
                        # Only set if False (True is default)
                        if not arg_value:
                            options['detect_columns'] = False
                    elif arg_name in ['pptx_include_notes', 'eml_include_headers', 'eml_preserve_thread_structure']:
                        # Only set if False (True is default for these)
                        if not arg_value:
                            options[field_name] = False
                    elif arg_name in ['html_extract_title', 'html_strip_dangerous_elements', 'pptx_slide_numbers']:
                        # Only set if True (False is default for these)
                        if arg_value:
                            options[field_name] = True
                    else:
                        # Set value if it's not default/falsy
                        if arg_value:
                            options[field_name] = arg_value
                mapped = True
                break

        # Handle unmapped arguments
        if not mapped and arg_value:
            # Direct mapping for any remaining arguments
            options[arg_name] = arg_value

    return options


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Set up logging level
    log_level = getattr(logging, parsed_args.log_level.upper())
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    # Check input file exists
    input_path = Path(parsed_args.input)
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
        return 1

    # Validate attachment options
    if parsed_args.attachment_output_dir and parsed_args.attachment_mode != "download":
        print("Warning: --attachment-output-dir specified but attachment mode is "
              f"'{parsed_args.attachment_mode}' (not 'download')", file=sys.stderr)

    # Map CLI arguments to options using dynamic mapping
    options = _map_cli_args_to_options(parsed_args)

    try:
        # Convert the document with format override if specified
        format_arg = parsed_args.format if parsed_args.format != "auto" else "auto"
        markdown_content = to_markdown(input_path, format=format_arg, **options)

        # Output the result
        if parsed_args.out:
            output_path = Path(parsed_args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown_content, encoding="utf-8")
            print(f"Converted {input_path} -> {output_path}")
        else:
            print(markdown_content)

        return 0

    except (MdparseConversionError, MdparseInputError) as e:
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
