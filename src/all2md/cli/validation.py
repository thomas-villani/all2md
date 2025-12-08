"""Structured validation helpers for CLI argument checks."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional

from all2md.cli.input_items import CLIInputItem


class ValidationSeverity(str, Enum):
    """Severity levels for validation problems."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class ValidationProblem:
    """Represents a validation issue discovered during CLI processing."""

    message: str
    severity: ValidationSeverity

    def log(self, logger: logging.Logger) -> None:
        """Emit the problem using the appropriate log level."""
        if self.severity is ValidationSeverity.ERROR:
            logger.error(self.message)
        else:
            logger.warning(self.message)


def collect_argument_problems(
    parsed_args: argparse.Namespace,
    files: Optional[List[CLIInputItem]] = None,
) -> list[ValidationProblem]:
    """Collect validation problems for parsed CLI arguments."""
    problems: list[ValidationProblem] = []

    attachment_dir = getattr(parsed_args, "attachment_output_dir", None)
    attachment_mode = getattr(parsed_args, "attachment_mode", None)
    if attachment_dir and attachment_mode and attachment_mode != "save":
        problems.append(
            ValidationProblem(
                "--attachment-output-dir specified but attachment mode is " f"'{attachment_mode}' (expected 'save')",
                ValidationSeverity.WARNING,
            )
        )

    output_dir = getattr(parsed_args, "output_dir", None)
    if output_dir:
        output_dir_path = Path(output_dir)
        if output_dir_path.exists() and not output_dir_path.is_dir():
            problems.append(
                ValidationProblem(
                    f"--output-dir must be a directory, not a file: {output_dir}",
                    ValidationSeverity.ERROR,
                )
            )

    if files and len(files) > 1 and getattr(parsed_args, "out", None) and not output_dir:
        problems.append(
            ValidationProblem(
                "--out is ignored for multiple files. Use --output-dir instead.",
                ValidationSeverity.WARNING,
            )
        )

    # Check for conflicting batch/merge list options
    batch_from_list = getattr(parsed_args, "batch_from_list", None)
    merge_from_list = getattr(parsed_args, "merge_from_list", None)

    if batch_from_list and merge_from_list:
        problems.append(
            ValidationProblem(
                "--batch-from-list and --merge-from-list cannot be used together. "
                "Use --batch-from-list to process files individually or --merge-from-list to combine them.",
                ValidationSeverity.ERROR,
            )
        )

    # Check for stdin conflicts with batch-from-list
    input_list = getattr(parsed_args, "input", [])
    if batch_from_list and batch_from_list != "-" and "-" in input_list:
        problems.append(
            ValidationProblem(
                "--batch-from-list cannot be used with stdin input ('-'). "
                "Either read the file list from stdin using '--batch-from-list -' "
                "or provide file paths via stdin, not both.",
                ValidationSeverity.ERROR,
            )
        )

    # Check for conflicting outline and extract options
    outline = getattr(parsed_args, "outline", False)
    extract = getattr(parsed_args, "extract", None)

    if outline and extract:
        problems.append(
            ValidationProblem(
                "--outline and --extract cannot be used together. "
                "Use --outline to view document structure or --extract to extract specific sections.",
                ValidationSeverity.ERROR,
            )
        )

    # Check for document splitting conflicts
    split_by = getattr(parsed_args, "split_by", None)

    if split_by:
        # Require output location for splitting
        out = getattr(parsed_args, "out", None)
        output_dir = getattr(parsed_args, "output_dir", None)

        if not out and not output_dir:
            problems.append(
                ValidationProblem(
                    "--split-by requires either --out or --output-dir to specify output location for split files.",
                    ValidationSeverity.ERROR,
                )
            )

        # Check conflicts with other options
        collate = getattr(parsed_args, "collate", False)
        if collate:
            problems.append(
                ValidationProblem(
                    "--split-by and --collate cannot be used together. "
                    "Choose either splitting (one input to many outputs) or collating (many inputs to one output).",
                    ValidationSeverity.ERROR,
                )
            )

        if extract:
            problems.append(
                ValidationProblem(
                    "--split-by and --extract cannot be used together. "
                    "Choose either splitting the full document or extracting specific sections.",
                    ValidationSeverity.ERROR,
                )
            )

        if outline:
            problems.append(
                ValidationProblem(
                    "--split-by and --outline cannot be used together. "
                    "Use --outline to view document structure or --split-by to split the document.",
                    ValidationSeverity.ERROR,
                )
            )

    return problems


def report_validation_problems(
    problems: Iterable[ValidationProblem],
    *,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Report validation problems via logging.

    Returns True when any errors were encountered.
    """
    logger = logger or logging.getLogger(__name__)
    has_errors = False

    for problem in problems:
        problem.log(logger)
        if problem.severity is ValidationSeverity.ERROR:
            has_errors = True

    return has_errors


def validate_arguments(
    parsed_args: argparse.Namespace,
    files: Optional[List[CLIInputItem]] = None,
    *,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """Validate parsed arguments, logging any issues. Maintains legacy API."""
    problems = collect_argument_problems(parsed_args, files)
    return not report_validation_problems(problems, logger=logger)
