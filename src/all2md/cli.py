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
import sys
from pathlib import Path
from typing import Optional

from . import to_markdown
from .exceptions import MdparseConversionError, MdparseInputError


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
        default=True,
        help="Enable multi-column layout detection (default: enabled)"
    )
    pdf_group.add_argument(
        "--pdf-no-detect-columns",
        action="store_false",
        dest="pdf_detect_columns",
        help="Disable multi-column layout detection"
    )

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

    return parser


def parse_pdf_pages(pages_str: str) -> list[int]:
    """Parse comma-separated page numbers."""
    try:
        return [int(p.strip()) for p in pages_str.split(",")]
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid page numbers: {pages_str}") from e


def main(args: Optional[list[str]] = None) -> int:
    """Main CLI entry point."""
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Check input file exists
    input_path = Path(parsed_args.input)
    if not input_path.exists():
        print(f"Error: Input file does not exist: {input_path}", file=sys.stderr)
        return 1

    # Build options dictionary from arguments
    options = {}

    # Attachment options
    if parsed_args.attachment_mode != "alt_text":
        options["attachment_mode"] = parsed_args.attachment_mode
    if parsed_args.attachment_output_dir:
        options["attachment_output_dir"] = parsed_args.attachment_output_dir
    if parsed_args.attachment_base_url:
        options["attachment_base_url"] = parsed_args.attachment_base_url

    # Markdown formatting options
    if parsed_args.markdown_emphasis_symbol != "*":
        options["markdown_emphasis_symbol"] = parsed_args.markdown_emphasis_symbol
    if parsed_args.markdown_bullet_symbols != "*-+":
        options["markdown_bullet_symbols"] = parsed_args.markdown_bullet_symbols
    if parsed_args.markdown_page_separator != "-----":
        options["markdown_page_separator"] = parsed_args.markdown_page_separator

    # PDF options
    if parsed_args.pdf_pages:
        options["pdf_pages"] = parse_pdf_pages(parsed_args.pdf_pages)
    if parsed_args.pdf_password:
        options["pdf_password"] = parsed_args.pdf_password
    if not parsed_args.pdf_detect_columns:
        options["pdf_detect_columns"] = False

    # HTML options
    if parsed_args.html_extract_title:
        options["html_extract_title"] = True
    if parsed_args.html_strip_dangerous_elements:
        options["html_strip_dangerous_elements"] = True

    # PowerPoint options
    if parsed_args.pptx_slide_numbers:
        options["pptx_slide_numbers"] = True
    if not parsed_args.pptx_include_notes:
        options["pptx_include_notes"] = False

    # Email options
    if not parsed_args.eml_include_headers:
        options["eml_include_headers"] = False
    if not parsed_args.eml_preserve_thread_structure:
        options["eml_preserve_thread_structure"] = False

    try:
        # Convert the document
        markdown_content = to_markdown(input_path, **options)

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
