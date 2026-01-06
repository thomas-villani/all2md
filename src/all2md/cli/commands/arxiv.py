#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/arxiv.py
"""ArXiv package generation command for all2md CLI.

This module provides the arxiv subcommand for generating ArXiv-ready
submission packages from document files.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from all2md.api import to_ast
from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.packagers.arxiv import ArxivPackageOptions, ArxivPackager

logger = logging.getLogger(__name__)


def handle_arxiv_command(args: list[str] | None = None) -> int:
    """Handle arxiv command for ArXiv package generation.

    Converts a document (DOCX, Markdown, etc.) to an ArXiv-ready
    LaTeX submission package with figures and bibliography.

    Parameters
    ----------
    args : list of str, optional
        Command line arguments (beyond 'arxiv')

    Returns
    -------
    int
        Exit code (0 for success)

    Examples
    --------
    Command line usage:

        all2md arxiv paper.docx -o submission/
        all2md arxiv paper.md --output-format tar.gz -o paper.tar.gz
        all2md arxiv paper.docx --document-class revtex4-2 -o sub/

    """
    parser = argparse.ArgumentParser(
        prog="all2md arxiv",
        description="Generate ArXiv submission package from document.",
    )
    parser.add_argument(
        "input",
        help="Input document (DOCX, Markdown, HTML, etc.)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output directory or .tar.gz file",
    )
    parser.add_argument(
        "--document-class",
        default="article",
        help="LaTeX document class (default: article)",
    )
    parser.add_argument(
        "--document-class-options",
        default="",
        help="Comma-separated document class options (e.g., '12pt,a4paper')",
    )
    parser.add_argument(
        "--bib-style",
        default="plain",
        help="Bibliography style (default: plain)",
    )
    parser.add_argument(
        "--figure-format",
        choices=["png", "pdf", "eps", "jpg"],
        default="png",
        help="Target format for figures (default: png)",
    )
    parser.add_argument(
        "--output-format",
        choices=["directory", "tar.gz"],
        default="directory",
        help="Output format (default: directory)",
    )
    parser.add_argument(
        "--no-convert-footnotes",
        action="store_true",
        help="Don't convert footnotes to citations",
    )
    parser.add_argument(
        "--no-natbib",
        action="store_true",
        help="Don't include natbib package",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    # Validate input
    input_path = Path(parsed.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    try:
        # Parse input document
        print(f"Parsing {input_path}...")
        document = to_ast(input_path)

        # Parse document class options
        doc_class_options = []
        if parsed.document_class_options:
            doc_class_options = [opt.strip() for opt in parsed.document_class_options.split(",") if opt.strip()]

        # Configure packager
        options = ArxivPackageOptions(
            document_class=parsed.document_class,
            document_class_options=doc_class_options,
            bibliography_style=parsed.bib_style,
            figure_format=parsed.figure_format,
            output_format=parsed.output_format,
            convert_footnotes=not parsed.no_convert_footnotes,
            include_natbib=not parsed.no_natbib,
        )

        # Generate package
        print("Generating ArXiv package...")
        packager = ArxivPackager(options)
        output_path = packager.package(
            document,
            parsed.output,
            source_dir=input_path.parent,
        )

        print(f"ArXiv package created at: {output_path}")
        return EXIT_SUCCESS

    except Exception as e:
        logger.exception(f"Package generation failed: {e}")
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
