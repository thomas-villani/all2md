"""Structured validation helpers for CLI argument checks."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional


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
        files: Optional[List[Path]] = None,
) -> list[ValidationProblem]:
    """Collect validation problems for parsed CLI arguments."""
    problems: list[ValidationProblem] = []

    attachment_dir = getattr(parsed_args, "attachment_output_dir", None)
    attachment_mode = getattr(parsed_args, "attachment_mode", None)
    if attachment_dir and attachment_mode and attachment_mode != "download":
        problems.append(
            ValidationProblem(
                "--attachment-output-dir specified but attachment mode is "
                f"'{attachment_mode}' (expected 'download')",
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
        files: Optional[List[Path]] = None,
        *,
        logger: Optional[logging.Logger] = None,
) -> bool:
    """Validate parsed arguments, logging any issues. Maintains legacy API."""
    problems = collect_argument_problems(parsed_args, files)
    return not report_validation_problems(problems, logger=logger)
