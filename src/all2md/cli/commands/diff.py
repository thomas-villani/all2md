#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/diff.py
"""Document comparison and diff generation command.

This module provides the diff command for comparing two documents of any
supported format and generating unified, HTML, or JSON diff output. It
supports various comparison granularities (block, sentence, word) and
context options similar to traditional diff tools.
"""
import argparse
import sys
from pathlib import Path

from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR
from all2md.diff.renderers.html import HtmlDiffRenderer
from all2md.diff.renderers.json import JsonDiffRenderer
from all2md.diff.renderers.unified import UnifiedDiffRenderer


def _validate_context_lines(value: str) -> int:
    """Validate context lines is a positive integer.

    Parameters
    ----------
    value : str
        Context lines value as string

    Returns
    -------
    int
        Validated context lines value

    Raises
    ------
    argparse.ArgumentTypeError
        If value is not a positive integer

    """
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"context lines must be an integer, got '{value}'") from e

    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"context lines must be non-negative, got {ivalue}")

    return ivalue


def _create_diff_parser() -> argparse.ArgumentParser:
    """Create argparse parser for diff command.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser for diff command

    """
    parser = argparse.ArgumentParser(
        prog="all2md diff",
        description="Compare two documents and generate a unified diff (like diff but for any document format)",
        add_help=True,
    )

    # Positional arguments
    parser.add_argument("original", help="Original document (any supported format, use '-' for stdin)")
    parser.add_argument("modified", help="Modified document (any supported format, use '-' for stdin)")

    # Output options
    parser.add_argument(
        "--format",
        "-f",
        choices=["unified", "html", "json"],
        default="unified",
        help="Output format: unified (default, like diff -u), html (visual), json (structured)",
    )
    parser.add_argument("--output", "-o", help="Write diff to file (default: stdout)")
    parser.add_argument(
        "--color",
        dest="color",
        choices=["auto", "always", "never"],
        default="auto",
        help="Colorize output: auto (default, if terminal), always, never",
    )

    # Comparison options
    parser.add_argument(
        "--ignore-whitespace",
        "-w",
        action="store_true",
        help="Ignore whitespace changes (like diff -w)",
    )
    parser.add_argument(
        "--context",
        "-C",
        type=_validate_context_lines,
        default=3,
        help="Number of context lines (default: 3, like diff -C)",
    )
    parser.add_argument(
        "--granularity",
        choices=["block", "sentence", "word"],
        default="block",
        help="Diff granularity: block (default), sentence, or word",
    )

    # HTML-specific options
    parser.add_argument(
        "--no-context",
        dest="show_context",
        action="store_false",
        default=True,
        help="Hide context lines in HTML output",
    )

    return parser


def handle_diff_command(args: list[str] | None = None) -> int:
    """Handle diff command to compare two documents.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'diff')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    # Parse arguments
    parser = _create_diff_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    # Handle stdin or validate source files
    is_stdin1 = parsed.original == "-"
    is_stdin2 = parsed.modified == "-"

    # Cannot read both from stdin
    if is_stdin1 and is_stdin2:
        print("Error: Cannot read both original and modified from stdin", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Load "original"
    if is_stdin1:
        stdin_data = sys.stdin.buffer.read()
        if not stdin_data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        src_original_input = stdin_data
        src_original_label = "stdin"
    else:
        src_original_path = Path(parsed.original)
        if not src_original_path.exists():
            print(f"Error: Source file not found: {parsed.original}", file=sys.stderr)
            return EXIT_FILE_ERROR
        src_original_input = parsed.original
        src_original_label = str(src_original_path)

    # Load "modified"
    if is_stdin2:
        stdin_data = sys.stdin.buffer.read()
        if not stdin_data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        src_modified_input = stdin_data
        src_modified_label = "stdin"
    else:
        src_modified_path = Path(parsed.modified)
        if not src_modified_path.exists():
            print(f"Error: Source file not found: {parsed.modified}", file=sys.stderr)
            return EXIT_FILE_ERROR
        src_modified_input = parsed.modified
        src_modified_label = str(src_modified_path)

    try:
        from all2md import to_ast
        from all2md.diff.text_diff import compare_documents

        # Convert both documents to AST
        print(f"Comparing {src_original_label} and {src_modified_label}...", file=sys.stderr)
        doc1 = to_ast(src_original_input)
        doc2 = to_ast(src_modified_input)

        # Compare documents
        diff_result = compare_documents(
            doc1,
            doc2,
            old_label=src_original_label,
            new_label=src_modified_label,
            context_lines=parsed.context,
            ignore_whitespace=parsed.ignore_whitespace,
            granularity=parsed.granularity,
        )

        has_changes = any(op.tag != "equal" for op in diff_result.iter_operations())

        if not has_changes:
            print("No differences found.", file=sys.stderr)
            # Still output empty diff in requested format
            if parsed.output:
                output_path = Path(parsed.output)
                if parsed.format == "html":
                    output = HtmlDiffRenderer(show_context=parsed.show_context).render(diff_result)
                elif parsed.format == "json":
                    output = JsonDiffRenderer().render(diff_result)
                else:
                    output = "\n".join(diff_result.iter_unified_diff())
                output_path.write_text(output, encoding="utf-8")
            return 0

        # Render diff based on format
        if parsed.format == "html":
            html_renderer = HtmlDiffRenderer(show_context=parsed.show_context)
            output = html_renderer.render(diff_result)

            # Write HTML output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing HTML diff to {output_path}...", file=sys.stderr)
                output_path.write_text(output, encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                print(output)

        elif parsed.format == "json":
            json_renderer = JsonDiffRenderer()
            output = json_renderer.render(diff_result)

            # Write JSON output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing JSON diff to {output_path}...", file=sys.stderr)
                output_path.write_text(output, encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                print(output)

        else:  # unified format (default)
            # Determine if we should use colors
            use_colors = False
            if parsed.color == "always":
                use_colors = True
            elif parsed.color == "auto" and not parsed.output:
                # Auto-detect: use colors if stdout is a TTY
                use_colors = sys.stdout.isatty()

            # Render with optional colors
            unified_renderer = UnifiedDiffRenderer(use_color=use_colors)

            # Write output
            if parsed.output:
                output_path = Path(parsed.output)
                print(f"Writing unified diff to {output_path}...", file=sys.stderr)
                # Don't use colors when writing to file
                plain_lines = diff_result.iter_unified_diff()
                output_path.write_text("\n".join(plain_lines), encoding="utf-8")
                print(f"Diff written to: {output_path}", file=sys.stderr)
            else:
                for line in unified_renderer.render(diff_result.iter_unified_diff()):
                    print(line)

        return 0

    except Exception as e:
        print(f"Error comparing documents: {e}", file=sys.stderr)
        return EXIT_ERROR
