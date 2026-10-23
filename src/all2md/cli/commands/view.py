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
import time
import webbrowser
from pathlib import Path

from all2md import HtmlRendererOptions, from_ast, to_ast
from all2md.api import library_injected_options
from all2md.cli import EXIT_FILE_ERROR, window
from all2md.cli.builder import EXIT_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import add_cache_arguments, conversion_cache_from_args
from all2md.cli.commands.web_assets import ThemeError, inject_web_assets, inline_local_images, resolve_theme
from all2md.cli.config import apply_config_to_parser, load_config_with_priority
from all2md.cli.files_from import add_files_from_arguments, resolve_files_from


def _create_view_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``view`` command.

    Exposed as a factory so ``config generate`` can introspect the command's
    options to emit a ``[view]`` config-template section.
    """
    parser = argparse.ArgumentParser(
        prog="all2md view",
        description="Convert and view document in browser with HTML themes.",
    )
    parser.add_argument("input", nargs="?", help="File to view (use '-' for stdin)")
    add_files_from_arguments(parser)
    parser.add_argument(
        "--keep",
        nargs="?",
        const=True,
        default=False,
        help="Keep HTML file. Optionally specify output path (default: keep temp file)",
    )
    parser.add_argument("--toc", action="store_true", help="Include table of contents")
    parser.add_argument("-d", "--dark", action="store_true", help="Use dark mode theme")
    parser.add_argument(
        "-w",
        "--window",
        action="store_true",
        help="Open in a standalone native window (no browser chrome) instead of a browser tab. "
        "Requires the optional 'pywebview' dependency (pip install all2md[window]); falls back to "
        "a browser tab if it is not installed.",
    )
    parser.add_argument(
        "-t",
        "--theme",
        help="Theme to use: a built-in name (minimal, dark, newspaper, docs, sidebar), "
        "a custom .html template or plain .css file path, or a name registered in the "
        "config [themes] table",
    )
    parser.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Disable client-side rendering of ```mermaid code blocks as diagrams",
    )
    parser.add_argument(
        "--no-syntax-highlight",
        action="store_true",
        help="Disable client-side syntax highlighting of code blocks (highlight.js)",
    )
    parser.add_argument(
        "-x",
        "--extract",
        type=str,
        metavar="SPEC",
        help="Extract specific section(s) from document. "
        "Supports: name pattern ('Introduction', 'Chapter*'), "
        "single index ('#:1'), range ('#:1-3'), "
        "multiple ('#:1,3,5'), or open-ended ('#:3-'). "
        "Sections are 1-indexed.",
    )
    parser.add_argument(
        "-N",
        "--no-wait",
        action="store_true",
        help="Skip waiting for confirmation before cleaning up (useful for scripts)",
    )
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [view] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    add_cache_arguments(parser)
    return parser


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
    parser = _create_view_parser()

    try:
        # Pre-parse to discover config flags, fold the [view] config section in as
        # defaults, then parse for real so explicit CLI flags win over config.
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "view", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    files_from_error = resolve_files_from(parsed, "input", single=True)
    if files_from_error is not None:
        return files_from_error

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

    # Select theme template (built-in name, .html/.css path, or [themes] config name).
    theme_config = {} if parsed.no_config else load_config_with_priority(explicit_path=parsed.config)
    try:
        theme_path = resolve_theme(parsed.theme, dark=parsed.dark, config=theme_config)
    except ThemeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    if not theme_path.exists():
        print(f"Error: Theme template not found: {theme_path}", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Print status
    print(f"Converting {input_display_name}...")

    # Converter options from the config file (e.g. [pdf], [html], top-level keys)
    # so a single config drives `all2md`, `view`, and `serve` identically.
    from all2md.cli.processors import load_converter_config_options, prepare_options_for_execution

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)

    try:
        # Convert to AST, applying any config-supplied converter options for the
        # detected format (None path for stdin falls back to format-qualified keys).
        opts_path = None if is_stdin else Path(parsed.input)
        to_ast_kwargs = prepare_options_for_execution(converter_options, opts_path, "auto")
        # Embed attachments so a DOCX's or PDF's images show in the page, unless the
        # config chose otherwise. A format without attachments drops the option, and
        # since we added it, not the user, that must not warn.
        injected: tuple[str, ...] = ()
        if "attachment_mode" not in to_ast_kwargs:
            to_ast_kwargs["attachment_mode"] = "base64"
            injected = ("attachment_mode",)
        with conversion_cache_from_args(parsed), library_injected_options(*injected):
            doc = to_ast(input_source, **to_ast_kwargs)

        # Images the source names by path would not resolve from the page's own
        # location (a temp file, or --keep's), so they are embedded too.
        inline_local_images(doc, Path.cwd() if is_stdin else Path(parsed.input).resolve().parent)

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
            external_links_new_tab=True,
            render_mermaid=not parsed.no_mermaid,
        )
        html_result = from_ast(doc, "html", renderer_options=html_opts)

        # from_ast with string format returns str, not bytes or None
        if not isinstance(html_result, str):
            raise RuntimeError("Expected string result from HTML rendering")

        # Splice in the mermaid / highlight.js CDN includes (graceful offline degrade).
        is_dark = parsed.dark or parsed.theme == "dark"
        html_content = inject_web_assets(
            html_result,
            mermaid=not parsed.no_mermaid,
            highlight=not parsed.no_syntax_highlight,
            dark=is_dark,
        )

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

        # Standalone-window mode needs pywebview; fall back to a browser tab
        # (with a hint) if the optional dependency is missing.
        use_window = parsed.window
        if use_window and not window.is_available():
            print(f"Note: {window.INSTALL_HINT}", file=sys.stderr)
            print("Falling back to a browser tab.", file=sys.stderr)
            use_window = False

        # Open the rendered HTML. In window mode the call blocks until the user
        # closes the window, which doubles as the "done viewing" signal; in
        # browser mode we open a tab and (for temp files) wait separately below.
        if os.environ.get("ALL2MD_TEST_NO_BROWSER"):
            print("Skipping browser launch (test mode)")
        elif use_window:
            print("Opening in window...")
            window.open_window(output_path.as_uri(), title=f"{input_display_name} - all2md")
        else:
            print("Opening in browser...")
            webbrowser.open(output_path.as_uri())

        # Wait for user (only if using temp file and not in test mode)
        if use_temp:
            print(f"\nTemporary file: {output_path}")

            # In window mode the blocking window already served as the wait, so
            # we go straight to cleanup. Otherwise prompt (or sleep with --no-wait).
            if use_window or os.environ.get("ALL2MD_TEST_NO_BROWSER"):
                pass
            elif not parsed.no_wait:
                try:
                    input("Press Enter to clean up and exit...")
                except (KeyboardInterrupt, EOFError):
                    print()  # New line after interrupt
            else:
                # Give the browser time to load the file before deleting
                time.sleep(3)

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
