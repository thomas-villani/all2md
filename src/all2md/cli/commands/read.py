#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands/read.py
"""Read a document in an interactive terminal viewer: ``all2md read`` (``rcat -i``).

The document is parsed once and shown in a scrolling viewer with an outline,
a list of the links on screen and a status bar. In-document links and footnote
references move the viewer; other links are shown with their target, never
opened, and are not clickable in the terminal unless ``--clickable-links``
says so. Given a folder, a glob pattern or several files (or nothing, on a
terminal), the viewer opens on a tree of the documents there instead. Needs the ``tui`` extra
(Wijjit, Python 3.11+); ``rcat`` without ``-i`` works without it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Union

from all2md.cli.builder import EXIT_DEPENDENCY_ERROR, EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS
from all2md.cli.commands.shared import add_cache_arguments, conversion_cache_from_args
from all2md.cli.config import apply_config_to_parser
from all2md.options.terminal import CLICKABLE_LINKS_HELP

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
        "links, or choose one from a tree of a folder's documents. Links inside the document move the viewer; "
        "other links are shown with their target, never opened (see --clickable-links for the terminal's own "
        "Ctrl+click).",
        epilog=_keys_epilog(),
        formatter_class=_KeysHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="*",
        help="File to read ('-' for stdin), or folders, glob patterns or several files to choose from in a "
        "file tree (default: the current folder)",
    )
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
        help="Input format, when detection needs help; applies to every file opened (default: auto)",
    )
    parser.add_argument("--code-theme", default=None, help="Pygments theme for code blocks (default: monokai)")
    parser.add_argument(
        "--clickable-links",
        choices=["none", "web", "all"],
        default="none",
        help=CLICKABLE_LINKS_HELP,
    )
    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [read] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument("--no-config", action="store_true", help="Disable configuration file loading for this command.")
    add_cache_arguments(parser)
    return parser


class _KeysHelpFormatter(argparse.HelpFormatter):
    """Wrap the description as usual, but print the key table in the epilog as written."""

    def _fill_text(self, text: str, width: int, indent: str) -> str:
        if text.startswith("keys:"):
            return text
        return super()._fill_text(text, width, indent)


def _keys_epilog() -> str:
    """Return the key table for ``--help``: the default keys, then what ``--keys vim`` adds."""
    from all2md.tui.keys import help_rows

    def table(rows: list[tuple[str, str]]) -> list[str]:
        width = max(len(keys) for keys, _ in rows)
        return [f"  {keys.ljust(width)}  {description}" for keys, description in rows]

    lines = ["keys:", *table(help_rows("default")), "", "--keys vim adds:", *table(help_rows("vim", only_new=True))]
    return chr(10).join(lines)


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

    from all2md.tui.app import Viewer

    sources: list[str] = list(parsed.input)
    if not sources and not sys.stdin.isatty():
        sources = ["-"]
    viewer_args: dict[str, Any] = {"preset": parsed.keys, "outline": not parsed.no_outline}

    if sources == ["-"]:
        data = sys.stdin.buffer.read()
        if not data:
            print("Error: No data received from stdin", file=sys.stderr)
            return EXIT_FILE_ERROR
        if not reattach_terminal_input():
            print(
                "Error: cannot read the keyboard after reading the document from stdin; "
                "save it to a file and run `all2md read FILE`",
                file=sys.stderr,
            )
            return EXIT_ERROR
        try:
            layout = _lay_out(data, parsed)
        except Exception as e:  # the converters raise their own All2MdError subclasses
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_ERROR
        Viewer(layout, "stdin", **viewer_args).run()
        return EXIT_SUCCESS

    if "-" in sources:
        print("Error: '-' (stdin) cannot be read together with other inputs", file=sys.stderr)
        return EXIT_ERROR

    if len(sources) == 1 and Path(sources[0]).is_file():
        try:
            layout = _lay_out(sources[0], parsed)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_ERROR
        Viewer(layout, Path(sources[0]).name, **viewer_args).run()
        return EXIT_SUCCESS

    from all2md.tui.files import collect

    try:
        files = collect(sources)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    if not files.files:
        print(f"Error: no documents all2md can read were found in {', '.join(sources) or '.'}", file=sys.stderr)
        return EXIT_FILE_ERROR
    title = files.root.name or str(files.root)
    Viewer(None, title, files=files, opener=lambda path: _lay_out(str(path), parsed), **viewer_args).run()
    return EXIT_SUCCESS


def _lay_out(source: Union[bytes, str], parsed: argparse.Namespace) -> Any:
    """Parse ``source`` (a path or stdin's bytes) and return its ``DocumentLayout``.

    Raises whatever the parser raises.
    """
    from all2md import to_ast
    from all2md.cli.processors import load_converter_config_options, prepare_options_for_execution
    from all2md.options.terminal import TerminalRendererOptions
    from all2md.tui.layout import DocumentLayout

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)
    opts_path = None if isinstance(source, bytes) else Path(source)
    to_ast_kwargs = prepare_options_for_execution(converter_options, opts_path, parsed.format)
    if parsed.format != "auto":
        to_ast_kwargs["source_format"] = parsed.format
    with conversion_cache_from_args(parsed):
        doc = to_ast(source, **to_ast_kwargs)
    options = TerminalRendererOptions(clickable_links=parsed.clickable_links)
    if parsed.code_theme:
        options = options.create_updated(code_theme=parsed.code_theme)
    return DocumentLayout(doc, options)


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

            # Descriptor 0 gets its own duplicate of the console handle, so the
            # file opened here can close; the standard handle then names fd 0's.
            with open("CONIN$", "r+b", buffering=0) as console:
                os.dup2(console.fileno(), 0)
            std_input_handle = -10
            if not ctypes.windll.kernel32.SetStdHandle(std_input_handle, msvcrt.get_osfhandle(0)):
                return False
        else:
            tty = os.open("/dev/tty", os.O_RDONLY)
            os.dup2(tty, 0)
            os.close(tty)
        sys.stdin = open(0, encoding="utf-8", closefd=False)  # noqa: SIM115
    except OSError:
        return False
    return sys.stdin.isatty()
