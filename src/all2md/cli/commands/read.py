#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/read.py
"""Read a document in an interactive terminal viewer: ``all2md read`` (``rcat -i``).

The document is parsed once and shown in a scrolling viewer with an outline,
a list of the links on screen and a status bar. In-document links and footnote
references move the viewer; other links are shown, never opened. Needs the
``tui`` extra (Wijjit, Python 3.11+); ``rcat`` without ``-i`` works without it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from all2md.cli.builder import EXIT_DEPENDENCY_ERROR, EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import add_cache_arguments, conversion_cache_from_args
from all2md.cli.config import apply_config_to_parser

INSTALL_HINT = "all2md read needs the tui extra: pip install 'all2md[tui]'"


def _create_read_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the ``read`` command.

    Exposed as a factory so ``config generate`` can introspect the command's
    options to emit a ``[read]`` config-template section.
    """
    from all2md.tui.keys import PRESETS

    parser = argparse.ArgumentParser(
        prog="all2md read",
        description="Read a document in an interactive terminal viewer, with an outline and a list of its "
        "links. Links inside the document move the viewer; other links are shown, never opened.",
    )
    parser.add_argument("input", nargs="?", help="File to read (use '-' for stdin)")
    parser.add_argument(
        "--keys",
        choices=sorted(PRESETS),
        default="default",
        help="Key preset: 'default' (arrows, PgUp/PgDn, Space, [ and ]) or 'vim', which adds the keys of "
        "less and vim (j/k, f/b, d/u, g/G) (default: default)",
    )
    parser.add_argument("--no-outline", action="store_true", help="Start with the outline panel hidden")
    parser.add_argument(
        "--format",
        "--input-type",
        dest="format",
        default="auto",
        help="Input format, when detection needs help (default: auto)",
    )
    parser.add_argument("--code-theme", default=None, help="Pygments theme for code blocks (default: monokai)")
    parser.add_argument(
        "--no-hyperlinks",
        action="store_true",
        help="Do not emit terminal hyperlinks (OSC 8); external links then cannot be Ctrl+clicked",
    )
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [read] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument("--no-config", action="store_true", help="Disable configuration file loading for this command.")
    add_cache_arguments(parser)
    return parser


def handle_read_command(args: list[str] | None = None) -> int:
    """Handle ``all2md read``.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'read').

    Returns
    -------
    int
        Exit code.

    """
    parser = _create_read_parser()
    try:
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "read", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else EXIT_ERROR

    from all2md.tui.app import wijjit_available

    if not wijjit_available():
        if sys.version_info < (3, 11):
            print(f"{INSTALL_HINT}, which needs Python 3.11 or later; `rcat FILE` works here.", file=sys.stderr)
        else:
            print(INSTALL_HINT, file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR

    source = parsed.input
    if source is None:
        if sys.stdin.isatty():
            print("Error: give a file to read (or '-' for stdin)", file=sys.stderr)
            return EXIT_ERROR
        source = "-"

    if source == "-":
        data = sys.stdin.buffer.read()
        if not data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source: bytes | str = data
        title = "stdin"
        if not reattach_terminal_input():
            print(
                "Error: cannot read the keyboard after reading the document from stdin; "
                "save it to a file and run `all2md read FILE`",
                file=sys.stderr,
            )
            return EXIT_ERROR
    else:
        path = Path(source)
        if not path.is_file():
            print(f"Error: Input file not found: {source}", file=sys.stderr)
            return EXIT_FILE_ERROR
        input_source = source
        title = path.name

    from all2md import to_ast
    from all2md.cli.processors import load_converter_config_options, prepare_options_for_execution
    from all2md.options.terminal import TerminalRendererOptions
    from all2md.tui.app import Viewer
    from all2md.tui.layout import DocumentLayout

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)
    try:
        opts_path = None if isinstance(input_source, bytes) else Path(input_source)
        to_ast_kwargs = prepare_options_for_execution(converter_options, opts_path, parsed.format)
        if parsed.format != "auto":
            to_ast_kwargs["source_format"] = parsed.format
        with conversion_cache_from_args(parsed):
            doc = to_ast(input_source, **to_ast_kwargs)
    except Exception as e:  # the converters raise their own All2MdError subclasses
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_ERROR

    options = TerminalRendererOptions(hyperlinks=not parsed.no_hyperlinks)
    if parsed.code_theme:
        options = options.create_updated(code_theme=parsed.code_theme)
    Viewer(DocumentLayout(doc, options), title, preset=parsed.keys, outline=not parsed.no_outline).run()
    return EXIT_SUCCESS


def reattach_terminal_input() -> bool:
    """Point standard input back at the terminal after a document was piped in.

    ``cat notes.md | all2md read`` uses up stdin on the document, and the viewer
    then needs the keyboard. POSIX reopens ``/dev/tty`` onto descriptor 0;
    Windows opens the console input buffer, ``CONIN$``, and makes it the
    standard input handle.

    Returns
    -------
    bool
        True when stdin is (again) a terminal.

    """
    if sys.stdin is not None and sys.stdin.isatty():
        return True
    try:
        if sys.platform == "win32":
            import ctypes
            import msvcrt

            console = open("CONIN$", "r+b", buffering=0)  # noqa: SIM115 - kept open for the session
            kernel32 = ctypes.windll.kernel32
            std_input_handle = -10
            if not kernel32.SetStdHandle(std_input_handle, msvcrt.get_osfhandle(console.fileno())):
                return False
            os.dup2(console.fileno(), 0)
        else:
            tty = os.open("/dev/tty", os.O_RDONLY)
            os.dup2(tty, 0)
            os.close(tty)
        sys.stdin = open(0, encoding="utf-8", closefd=False)  # noqa: SIM115
    except OSError:
        return False
    return sys.stdin.isatty()
