#  Copyright (c) 2025 Tom Villani, Ph.D.

# src/all2md/cli/commands.py
"""CLI command handlers and utilities for all2md.

This module provides command-line interface implementation for the all2md
document conversion library, including command handlers, version info,
and system diagnostics.
"""

import logging
import sys

# Note: Command handlers are imported lazily in dispatch_command to avoid
# loading heavy modules (AST, transforms) during CLI startup for --help

logger = logging.getLogger(__name__)


def dispatch_command(args: list[str] | None = None) -> int | None:
    """Handle dependency management commands.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments

    Returns
    -------
    int or None
        Exit code if dependency command was handled, None otherwise

    """
    if not args:
        args = sys.argv[1:]

    if not args:
        return None

    # Check for completion command
    if args[0] == "completion":
        from all2md.cli.commands.completion import handle_completion_command

        return handle_completion_command(args)

    # Check for config command
    if args[0] == "config":
        from all2md.cli.commands.config import handle_config_command

        return handle_config_command(args)

    # Check for view command
    if args[0] == "view":
        from all2md.cli.commands.view import handle_view_command

        return handle_view_command(args[1:])

    # Check for serve command
    if args[0] == "serve":
        from all2md.cli.commands.server import handle_serve_command

        return handle_serve_command(args[1:])

    # Check for generate-site command
    if args[0] == "generate-site":
        from all2md.cli.commands.generate_site import handle_generate_site_command

        return handle_generate_site_command(args[1:])

    if args[0] == "search":
        from all2md.cli.commands.search import handle_search_command

        return handle_search_command(args[1:])

    # Check for grep command
    if args[0] == "grep":
        from all2md.cli.commands.search import handle_grep_command

        return handle_grep_command(args[1:])

    # Check for diff command
    if args[0] == "diff":
        from all2md.cli.commands.diff import handle_diff_command

        return handle_diff_command(args[1:])

    # Check for list-formats command
    if args[0] in ("list-formats", "formats"):
        from all2md.cli.commands.formats import handle_list_formats_command

        return handle_list_formats_command(args[1:])

    # Check for list-transforms command
    if args[0] in ("list-transforms", "transforms"):
        from all2md.cli.commands.transforms import handle_list_transforms_command

        return handle_list_transforms_command(args[1:])

    # Check for dependency management commands
    if args[0] == "check-deps":
        from all2md.dependencies import main as deps_main

        # Convert to standard deps CLI format
        deps_args = ["check"]

        # Parse remaining arguments
        remaining_args = args[1:]
        format_arg = None
        has_json = False
        has_rich = False
        has_help = False

        for arg in remaining_args:
            if arg in ("--help", "-h"):
                has_help = True
            elif arg == "--json":
                has_json = True
            elif arg == "--rich":
                has_rich = True
            elif not arg.startswith("-"):
                # This is the format argument
                format_arg = arg

        # Add arguments in the correct order
        if has_help:
            deps_args.append("--help")
        elif format_arg:
            deps_args.extend(["--format", format_arg])
            if has_json:
                deps_args.append("--json")
            if has_rich:
                deps_args.append("--rich")
        else:
            if has_json:
                deps_args.append("--json")
            if has_rich:
                deps_args.append("--rich")

        return deps_main(deps_args)

    return None
