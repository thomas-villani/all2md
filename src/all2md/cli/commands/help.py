#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Tiered help documentation command for all2md CLI.

This module provides the help command for displaying various levels of
CLI documentation, including quick reference, full help, and format-specific
help sections. Supports both plain text and rich terminal output.
"""

import argparse
import sys
from typing import Optional

from all2md.cli.help_formatter import display_help


def _read_cheatsheet() -> str:
    """Read the bundled CLI cheatsheet Markdown shipped in the wheel."""
    import importlib.resources  # nosemgrep: python.lang.compatibility.python37.python37-compatibility-importlib2

    ref = importlib.resources.files("all2md.cli") / "cheatsheet.md"
    return ref.read_text(encoding="utf-8")


def _print_cheatsheet(use_rich: bool) -> None:
    """Print the CLI cheatsheet, optionally rendered with rich Markdown."""
    text = _read_cheatsheet()
    if use_rich:
        try:
            from rich.console import Console
            from rich.markdown import Markdown

            Console().print(Markdown(text))
            return
        except ImportError:
            print("Warning: rich not installed; printing plain text.", file=sys.stderr)
    print(text)


def handle_help_command(args: list[str] | None = None) -> int | None:
    """Handle the ``help`` subcommand for tiered CLI documentation."""
    if not args:
        args = sys.argv[1:]

    if not args or args[0] != "help":
        return None

    help_args = args[1:]

    parser = argparse.ArgumentParser(
        prog="all2md help",
        description="Show all2md CLI help sections (quick, full, cheatsheet, or format-specific).",
    )
    parser.add_argument(
        "section",
        nargs="?",
        default="quick",
        help="Help selector: quick (default), full, cheatsheet, or a format (pdf, docx, html, ...).",
    )
    parser.add_argument(
        "--rich",
        action="store_true",
        help="Render help with rich formatting when the rich package is installed.",
    )

    parsed = parser.parse_args(help_args)

    if parsed.section == "cheatsheet":
        _print_cheatsheet(use_rich=parsed.rich)
        return 0

    requested_rich: Optional[bool]
    if parsed.rich:
        requested_rich = True
    else:
        requested_rich = None

    display_help(parsed.section, use_rich=requested_rich)
    return 0
