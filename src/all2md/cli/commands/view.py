#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Document viewer command for all2md CLI.

This module provides the view command for converting documents to HTML and
displaying them in a web browser with optional themes. Supports temporary
or persistent output files and includes table of contents generation.
"""
import argparse
import os
import sys
import tempfile
import webbrowser
from pathlib import Path

from all2md import HtmlRendererOptions, from_ast, to_ast
from all2md.cli import EXIT_FILE_ERROR
from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS


def handle_view_command(args: list[str] | None = None) -> int:
    """Handle view command to display document in browser.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'view')

    Returns
    -------
    int
        Exit code (0 for success)

    """
    parser = argparse.ArgumentParser(
        prog="all2md view",
        description="Convert and view document in browser with HTML themes.",
    )
    parser.add_argument("input", help="File to view (use '-' for stdin)")
    parser.add_argument(
        "--keep",
        nargs="?",
        const=True,
        default=False,
        help="Keep HTML file. Optionally specify output path (default: keep temp file)",
    )
    parser.add_argument("--toc", action="store_true", help="Include table of contents")
    parser.add_argument("--dark", action="store_true", help="Use dark mode theme")
    parser.add_argument(
        "--theme",
        help="Custom theme template path or built-in theme name (minimal, dark, newspaper, docs, sidebar)",
    )
    parser.add_argument(
        "--extract",
        type=str,
        metavar="SPEC",
        help="Extract specific section(s) from document. "
        "Supports: name pattern ('Introduction', 'Chapter*'), "
        "single index ('#:1'), range ('#:1-3'), "
        "multiple ('#:1,3,5'), or open-ended ('#:3-'). "
        "Sections are 1-indexed.",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    # Handle stdin or validate input file exists
    is_stdin = parsed.input == "-"
    if is_stdin:
        # Read from stdin
        stdin_data = sys.stdin.buffer.read()
        if not stdin_data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source = stdin_data
        input_display_name = "stdin"
    else:
        # Validate file exists
        input_path = Path(parsed.input)
        if not input_path.exists():
            print(f"Error: Input file not found: {parsed.input}", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source = parsed.input
        input_display_name = input_path.name

    # Select theme template
    if parsed.theme:
        # Check if it's a built-in theme name or a custom path
        theme_path = Path(parsed.theme)
        # First check if it's a valid HTML file path
        if theme_path.exists() and theme_path.is_file() and theme_path.suffix == ".html":
            # Use the provided file path
            pass
        else:
            # Try as built-in theme name
            builtin_theme = Path(__file__).parent / "themes" / f"{parsed.theme}.html"
            if builtin_theme.exists():
                theme_path = builtin_theme
            else:
                print(f"Error: Theme not found: {parsed.theme}", file=sys.stderr)
                print("Available built-in themes: minimal, dark, newspaper, docs, sidebar", file=sys.stderr)
                return EXIT_FILE_ERROR
    elif parsed.dark:
        theme_path = Path(__file__).parent / "themes" / "dark.html"
    else:
        theme_path = Path(__file__).parent / "themes" / "minimal.html"

    # Verify theme template exists
    if not theme_path.exists():
        print(f"Error: Theme template not found: {theme_path}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Print status
    print(f"Converting {input_display_name}...")

    try:
        # Convert to AST
        doc = to_ast(input_source)

        # Apply section extraction if requested
        if parsed.extract:
            from all2md.cli.processors import extract_sections_from_document

            try:
                doc = extract_sections_from_document(doc, parsed.extract)
            except ValueError as e:
                print(f"Error: {e}", file=sys.stderr)
                return EXIT_ERROR

        # Set custom title for web preview
        doc.metadata["title"] = f"{input_display_name} - all2md Web Preview"

        # Render with replace mode
        html_opts = HtmlRendererOptions(
            template_mode="replace",
            template_file=str(theme_path),
            include_toc=parsed.toc,
        )
        html_result = from_ast(doc, "html", renderer_options=html_opts)

        # from_ast with string format returns str, not bytes or None
        if not isinstance(html_result, str):
            raise RuntimeError("Expected string result from HTML rendering")
        html_content = html_result

        # Determine output path
        if isinstance(parsed.keep, str):
            # User provided a specific output path
            output_path = Path(parsed.keep).resolve()  # Convert to absolute path
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Write directly to the specified file
            output_path.write_text(html_content, encoding="utf-8")
            print(f"Saved to: {output_path}")
            use_temp = False
        else:
            # Use temporary file
            fd, temp_path = tempfile.mkstemp(suffix=".html", prefix="all2md-view-")
            try:
                os.write(fd, html_content.encode("utf-8"))
            finally:
                os.close(fd)
            output_path = Path(temp_path).resolve()  # Convert to absolute path
            use_temp = True

        # Open in browser with absolute path (unless testing)
        if not os.environ.get("ALL2MD_TEST_NO_BROWSER"):
            print("Opening in browser...")
            webbrowser.open(f"file://{output_path}")
        else:
            print("Skipping browser launch (test mode)")

        # Wait for user (only if using temp file and not in test mode)
        if use_temp:
            print(f"\nTemporary file: {output_path}")

            # Skip interactive prompt in test mode
            if not os.environ.get("ALL2MD_TEST_NO_BROWSER"):
                try:
                    input("Press Enter to clean up and exit...")
                except (KeyboardInterrupt, EOFError):
                    print()  # New line after interrupt

            # Cleanup if not keeping temp file
            if not parsed.keep:
                try:
                    os.unlink(str(output_path))
                    print("Temporary file cleaned up.")
                except Exception as e:
                    print(f"Warning: Could not delete temporary file: {e}", file=sys.stderr)
            else:
                print(f"Kept temporary file: {output_path}")

        return EXIT_SUCCESS

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR
