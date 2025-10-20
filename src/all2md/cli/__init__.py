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
Basic conversion:
    $ all2md document.pdf

Specify output file:
    $ all2md document.docx --out output.md

Download attachments:
    $ all2md document.docx --attachment-mode download --attachment-output-dir ./attachments

Use underscore emphasis:
    $ all2md document.html --markdown-emphasis-symbol "_"

Convert multiple files:
    $ all2md *.pdf --output-dir ./converted

Use rich formatting:
    $ all2md document.pdf --rich

Process directory recursively:
    $ all2md ./documents --recursive --output-dir ./markdown

Collate multiple files into one output:
    $ all2md *.pdf --collate --out combined.md

Use environment variables for defaults:
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

from all2md.cli.builder import EXIT_FILE_ERROR, EXIT_VALIDATION_ERROR, DynamicCLIBuilder, create_parser
from all2md.cli.commands import (
    _configure_logging,
    _get_about_info,
    collect_input_files,
    handle_convert_command,
    handle_dependency_commands,
    handle_help_command,
    save_config_to_file,
)
from all2md.cli.processors import (
    convert_single_file,
    generate_output_path,
    merge_exclusion_patterns_from_json,
    process_detect_only,
    process_dry_run,
    process_multi_file,
    setup_and_validate_options,
)
from all2md.cli.validation import (
    collect_argument_problems,
    report_validation_problems,
    validate_arguments,
)

logger = logging.getLogger(__name__)

__all__ = [
    "main",
    "DynamicCLIBuilder",
    "create_parser",
    "convert_single_file",
    "generate_output_path",
    "process_detect_only",
    "process_dry_run",
    "process_multi_file",
    "collect_argument_problems",
    "report_validation_problems",
    "validate_arguments",
]


def main(args: list[str] | None = None) -> int:
    """Execute main CLI entry point with focused delegation to specialized processors."""
    convert_result = handle_convert_command(args)
    if convert_result is not None:
        return convert_result

    help_result = handle_help_command(args)
    if help_result is not None:
        return help_result

    # Check for dependency management commands first
    deps_result = handle_dependency_commands(args)
    if deps_result is not None:
        return deps_result

    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Check for ALL2MD_CONFIG environment variable if --config not provided
    if not parsed_args.config:
        env_config = os.environ.get("ALL2MD_CONFIG")
        if env_config:
            parsed_args.config = env_config

    # Handle --about flag
    if parsed_args.about:
        print(_get_about_info())
        return 0

    # Handle --save-config
    if parsed_args.save_config:
        try:
            save_config_to_file(parsed_args, parsed_args.save_config)
            return 0
        except Exception as e:
            print(f"Error saving configuration: {e}", file=sys.stderr)
            return 1

    # Ensure input is provided when not using special flags
    # Note: --batch-from-list and --merge-from-list provide input, so don't require parsed_args.input
    has_batch_list = hasattr(parsed_args, "batch_from_list") and parsed_args.batch_from_list
    has_merge_list = hasattr(parsed_args, "merge_from_list") and parsed_args.merge_from_list
    if not parsed_args.input and not has_batch_list and not has_merge_list:
        print("Error: Input file is required", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    # Set up logging level - configures root logger for all modules
    # Note: All modules use logging.getLogger(__name__) for consistent logger hierarchy
    # --trace takes highest precedence, then --verbose, then --log-level
    if parsed_args.trace:
        log_level = logging.DEBUG
    elif parsed_args.verbose and parsed_args.log_level == "WARNING":
        log_level = logging.DEBUG
    else:
        # --log-level takes precedence if explicitly set
        log_level = getattr(logging, parsed_args.log_level.upper())

    # Configure logging with file handler if --log-file is specified
    _configure_logging(log_level, log_file=parsed_args.log_file, trace_mode=parsed_args.trace)

    # Expand input list from --batch-from-list if specified
    if hasattr(parsed_args, "batch_from_list") and parsed_args.batch_from_list:
        try:
            from all2md.cli.commands import parse_batch_list

            batch_paths = parse_batch_list(parsed_args.batch_from_list)
            # Extend the input list with paths from the batch file
            parsed_args.input.extend(batch_paths)
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    # Multi-file/directory processing
    items = collect_input_files(parsed_args.input, parsed_args.recursive, exclude_patterns=parsed_args.exclude)

    # Allow empty items if using --merge-from-list (it has its own input handling)
    if not items and not has_merge_list:
        if parsed_args.exclude:
            print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
        else:
            print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Handle exclusion patterns from config file
    if parsed_args.config:
        try:
            from all2md.cli.config import load_config_file

            config_options = load_config_file(parsed_args.config)
            updated_patterns = merge_exclusion_patterns_from_json(parsed_args, config_options)

            if updated_patterns:
                parsed_args.exclude = updated_patterns
                # Re-collect files with updated exclusion patterns
                items = collect_input_files(
                    parsed_args.input, parsed_args.recursive, exclude_patterns=parsed_args.exclude
                )

                # Allow empty items if using --merge-from-list (it has its own input handling)
                if not items and not has_merge_list:
                    if parsed_args.exclude:
                        print("Error: No valid input files found (all files excluded by patterns)", file=sys.stderr)
                    else:
                        print("Error: No valid input files found", file=sys.stderr)
                    return EXIT_FILE_ERROR
        except argparse.ArgumentTypeError as e:
            print(f"Error: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

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
        # Watch mode requires --output-dir
        if not parsed_args.output_dir:
            print("Error: --watch requires --output-dir to be specified", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

        # Import and run watch mode
        from all2md.cli.watch import run_watch_mode

        # Convert input paths (which might be strings) to Path objects
        paths_to_watch = [Path(f) for f in parsed_args.input]

        return run_watch_mode(
            paths=paths_to_watch,
            output_dir=Path(parsed_args.output_dir),
            options=options,
            format_arg=format_arg,
            transforms=transforms,
            debounce=parsed_args.watch_debounce,
            preserve_structure=parsed_args.preserve_structure,
            recursive=parsed_args.recursive,
            exclude_patterns=parsed_args.exclude,
        )

    # Delegate to multi-file processor
    return process_multi_file(items, parsed_args, options, format_arg, transforms)


if __name__ == "__main__":
    sys.exit(main())
