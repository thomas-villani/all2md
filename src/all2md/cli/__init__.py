"""Command-line interface for all2md document conversion library.

This module provides a simple CLI tool for converting documents to Markdown
format using the all2md library. It supports all formats handled by the
library and provides convenient options for common use cases.

Environment Variable Support
----------------------------
All CLI options support environment variable defaults using the pattern
ALL2MD_<OPTION_NAME> where option names are converted to uppercase with
hyphens and dots replaced by underscores. CLI arguments always override
environment variables.

Examples
--------
Basic conversion::

    $ all2md document.pdf

Specify output file::

    $ all2md document.docx --out output.md

Save attachments::

    $ all2md document.docx --attachment-mode save --attachment-output-dir ./attachments

Use underscore emphasis::

    $ all2md document.html --markdown-emphasis-symbol "_"

Convert multiple files::

    $ all2md *.pdf --output-dir ./converted

Use rich formatting::

    $ all2md document.pdf --rich

Process directory recursively::

    $ all2md ./documents --recursive --output-dir ./markdown

Collate multiple files into one output::

    $ all2md *.pdf --collate --out combined.md

Use environment variables for defaults::

    $ export ALL2MD_RICH=true
    $ export ALL2MD_OUTPUT_DIR=./converted
    $ export ALL2MD_MARKDOWN_EMPHASIS_SYMBOL="_"
    $ all2md *.pdf  # Uses environment defaults

"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import cast

from all2md.cli.builder import EXIT_FILE_ERROR, EXIT_VALIDATION_ERROR, DynamicCLIBuilder, create_parser
from all2md.cli.commands import (
    dispatch_command,
)
from all2md.cli.commands.config import save_config_to_file
from all2md.cli.commands.help import handle_help_command
from all2md.cli.commands.shared import collect_input_files, get_about_info, parse_batch_list

# Note: processors imports are lazy-loaded to avoid loading AST and transforms
# for simple commands like --help
from all2md.cli.validation import (
    collect_argument_problems,
    report_validation_problems,
    validate_arguments,
)
from all2md.constants import DocumentFormat
from all2md.logging_utils import configure_logging

logger = logging.getLogger(__name__)

__all__ = [
    "main",
    "DynamicCLIBuilder",
    "create_parser",
    "collect_argument_problems",
    "report_validation_problems",
    "validate_arguments",
]


def _setup_logging_level(parsed_args: argparse.Namespace) -> None:
    """Set up logging level based on command-line arguments.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command-line arguments

    """
    # --trace takes highest precedence, then --verbose, then --log-level
    if parsed_args.trace:
        log_level = logging.DEBUG
    elif parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, parsed_args.log_level.upper())

    configure_logging(log_level, log_file=parsed_args.log_file, trace_mode=parsed_args.trace)


def _handle_batch_list_expansion(parsed_args: argparse.Namespace) -> int | None:
    """Expand input list from batch file if specified.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command-line arguments

    Returns
    -------
    int or None
        Exit code if error, None if successful

    """
    if hasattr(parsed_args, "batch_from_list") and parsed_args.batch_from_list:
        try:

            batch_paths = parse_batch_list(parsed_args.batch_from_list)
            parsed_args.input.extend(batch_paths)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR
    return None


def _collect_and_filter_inputs(parsed_args: argparse.Namespace, has_merge_list: bool) -> tuple[list, int | None]:
    """Collect and filter input files with config-based exclusions.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command-line arguments
    has_merge_list : bool
        Whether --merge-from-list is being used

    Returns
    -------
    tuple[list, int | None]
        Tuple of (items, exit_code). Exit code is None if successful.

    """
    # Initial file collection
    items = collect_input_files(parsed_args.input, parsed_args.recursive, exclude_patterns=parsed_args.exclude)

    if not items and not has_merge_list:
        if parsed_args.exclude:
            print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
        else:
            print("Error: No valid input files found", file=sys.stderr)
        return items, EXIT_FILE_ERROR

    # Handle config-based exclusion patterns
    if parsed_args.config:
        try:
            from all2md.cli.config import load_config_file
            from all2md.cli.processors import merge_exclusion_patterns_from_json

            config_options = load_config_file(parsed_args.config)
            updated_patterns = merge_exclusion_patterns_from_json(parsed_args, config_options)

            if updated_patterns:
                parsed_args.exclude = updated_patterns
                items = collect_input_files(
                    parsed_args.input, parsed_args.recursive, exclude_patterns=parsed_args.exclude
                )

                if not items and not has_merge_list:
                    if parsed_args.exclude:
                        print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
                    else:
                        print("Error: No valid input files found", file=sys.stderr)
                    return items, EXIT_FILE_ERROR
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return items, EXIT_VALIDATION_ERROR

    return items, None


def _handle_watch_mode(
    parsed_args: argparse.Namespace, options: dict, format_arg: DocumentFormat, transforms: list | None
) -> int:
    """Handle watch mode execution.

    Parameters
    ----------
    parsed_args : argparse.Namespace
        Parsed command-line arguments
    options : dict
        Conversion options
    format_arg : DocumentFormat
        Format specification
    transforms : list | None
        List of transforms

    Returns
    -------
    int
        Exit code from watch mode

    """
    if not parsed_args.output_dir:
        print("Error: --watch requires --output-dir to be specified", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    from all2md.cli.watch import run_watch_mode

    paths_to_watch = [Path(f) for f in parsed_args.input]
    target_format = cast(DocumentFormat, getattr(parsed_args, "output_format", "markdown"))
    output_extension = getattr(parsed_args, "output_extension", None)

    return run_watch_mode(
        paths=paths_to_watch,
        output_dir=Path(parsed_args.output_dir),
        options=options,
        format_arg=format_arg,
        target_format=target_format,
        output_extension=output_extension,
        transforms=transforms,
        debounce=parsed_args.watch_debounce,
        preserve_structure=parsed_args.preserve_structure,
        recursive=parsed_args.recursive,
        exclude_patterns=parsed_args.exclude,
    )


def main(args: list[str] | None = None) -> int:
    """Execute main CLI entry point with focused delegation to specialized processors."""
    # Handle special commands
    help_result = handle_help_command(args)
    if help_result is not None:
        return help_result

    deps_result = dispatch_command(args)
    if deps_result is not None:
        return deps_result

    # Parse arguments
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Lazy import processors to avoid loading AST/transforms for --help
    from all2md.cli.processors import (
        process_multi_file,
        setup_and_validate_options,
    )

    # Check for config from environment (skip if --no-config is set)
    if not getattr(parsed_args, "no_config", False) and not parsed_args.config:
        env_config = os.environ.get("ALL2MD_CONFIG")
        if env_config:
            parsed_args.config = env_config

    # Handle special flags
    if parsed_args.about:
        print(get_about_info())
        return 0

    if parsed_args.save_config:
        try:
            save_config_to_file(parsed_args, parsed_args.save_config)
            return 0
        except Exception as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)
            return 1

    # Ensure input is provided
    has_batch_list = hasattr(parsed_args, "batch_from_list") and parsed_args.batch_from_list
    has_merge_list = hasattr(parsed_args, "merge_from_list") and parsed_args.merge_from_list
    if not parsed_args.input and not has_batch_list and not has_merge_list:
        print("Error: Input file is required", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Set up logging
    _setup_logging_level(parsed_args)

    # Expand batch list if provided
    batch_error = _handle_batch_list_expansion(parsed_args)
    if batch_error is not None:
        return batch_error

    # Collect and filter inputs
    items, collect_error = _collect_and_filter_inputs(parsed_args, has_merge_list)
    if collect_error is not None:
        return collect_error

    # Validate arguments
    if not validate_arguments(parsed_args, items, logger=logger):
        return EXIT_VALIDATION_ERROR

    # Set up options
    try:
        options, format_arg, transforms = setup_and_validate_options(parsed_args)
    except argparse.ArgumentTypeError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Handle watch mode if requested
    if parsed_args.watch:
        return _handle_watch_mode(parsed_args, options, format_arg, transforms)

    # Delegate to multi-file processor
    return process_multi_file(items, parsed_args, options, format_arg, transforms)


if __name__ == "__main__":
    sys.exit(main())
