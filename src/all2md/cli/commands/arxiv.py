#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/arxiv.py
"""ArXiv submission package command for all2md CLI.

This module provides the arxiv command for generating ArXiv-ready
LaTeX submission archives from any supported document format.
"""

import argparse
import sys
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.config import apply_config_to_parser


def _create_arxiv_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``arxiv`` command.

    Exposed as a factory so ``config generate`` can introspect the command's
    options to emit an ``[arxiv]`` config-template section.
    """
    parser = argparse.ArgumentParser(
        prog="all2md arxiv",
        description="Generate an ArXiv-ready LaTeX submission package from a document.",
    )
    parser.add_argument("input", help="Input file to convert")
    parser.add_argument("-o", "--output", required=True, help="Output path for archive or directory")
    parser.add_argument("--bib", default=None, help="Path to .bib bibliography file")
    parser.add_argument("--document-class", default="article", help="LaTeX document class (default: article)")
    parser.add_argument(
        "--figure-format", default="png", choices=["png", "jpg", "pdf"], help="Figure format (default: png)"
    )
    parser.add_argument("--figure-dir", default="figures", help="Figure subdirectory name (default: figures)")
    parser.add_argument(
        "--output-format",
        default="tar.gz",
        choices=["tar.gz", "directory"],
        help="Output format (default: tar.gz)",
    )
    parser.add_argument("--bib-style", default="plain", help="Bibliography style (default: plain)")
    parser.add_argument("--main-tex", default="main.tex", help="Main .tex filename (default: main.tex)")
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [arxiv] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    return parser


def handle_arxiv_command(args: list[str] | None = None) -> int:
    """Handle arxiv command to generate ArXiv submission packages.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'arxiv')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    parser = _create_arxiv_parser()

    try:
        # Pre-parse to discover config flags, fold the [arxiv] config section in as
        # defaults, then parse for real so explicit CLI flags win over config.
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "arxiv", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Validate input
    input_path = Path(parsed.input)
    if not input_path.is_file():
        print(f"Error: Input file not found: {parsed.input}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Validate bib file if specified
    bib_path = None
    if parsed.bib:
        bib_path = Path(parsed.bib)
        if not bib_path.is_file():
            print(f"Error: Bibliography file not found: {parsed.bib}", file=sys.stderr)
            return EXIT_FILE_ERROR

    try:
        from all2md import to_ast
        from all2md.options.arxiv import ArxivPackagerOptions
        from all2md.packagers.arxiv import ArxivPackager

        # Build options
        options = ArxivPackagerOptions(
            document_class=parsed.document_class,
            figure_format=parsed.figure_format,
            figure_dir=parsed.figure_dir,
            output_format=parsed.output_format,
            bibliography_style=parsed.bib_style,
            main_tex_filename=parsed.main_tex,
        )

        # Convert to AST and package
        doc = to_ast(str(input_path))
        packager = ArxivPackager(options=options)
        result = packager.package(doc, parsed.output, bib_file=bib_path)

        print(f"ArXiv package created: {result}")
        return EXIT_SUCCESS

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
