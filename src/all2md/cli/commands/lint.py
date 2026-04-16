"""Handler for the ``all2md lint`` subcommand."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from all2md.cli.builder import EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.cli.commands.shared import collect_input_files
from all2md.cli.config import load_config_with_priority
from all2md.linter import LintConfig, LintRunner, Severity
from all2md.linter.reporters import get_reporter
from all2md.linter.runner import LintResult

logger = logging.getLogger(__name__)


def handle_lint_command(args: list[str] | None = None) -> int:
    """Entry point for ``all2md lint``.

    Parameters
    ----------
    args : list[str], optional
        Arguments past ``lint`` (already stripped of the subcommand name).

    Returns
    -------
    int
        A process exit code from :mod:`all2md.cli.builder`.

    """
    parser = _build_parser()
    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_ERROR

    try:
        config = _build_lint_config(parsed)
    except (ValueError, argparse.ArgumentTypeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    items = collect_input_files(parsed.inputs, recursive=parsed.recursive)
    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    runner = LintRunner(config=config)
    results: list[LintResult] = []
    had_runtime_error = False

    for item in items:
        path = item.best_path()
        if path is None:
            if item.is_stdin():
                print("Error: lint does not yet support stdin input", file=sys.stderr)
                return EXIT_FILE_ERROR
            if item.is_remote():
                print(f"Error: lint does not yet support remote input ({item.display_name})", file=sys.stderr)
                return EXIT_FILE_ERROR
            continue

        try:
            results.append(runner.lint_file(path))
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_FILE_ERROR
        except Exception as exc:
            logger.exception("Lint run failed for %s", path)
            print(f"Error linting {path}: {exc}", file=sys.stderr)
            had_runtime_error = True

    try:
        reporter = get_reporter(parsed.format)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    rendered = reporter.render(results)
    if parsed.output:
        try:
            Path(parsed.output).write_text(rendered + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            return EXIT_FILE_ERROR
    else:
        print(rendered)

    if had_runtime_error:
        return EXIT_ERROR

    total_remaining = sum(r.total for r in results)
    if total_remaining > 0:
        return EXIT_VALIDATION_ERROR
    return EXIT_SUCCESS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="all2md lint",
        description=(
            "Lint converted documents for structural, heading, link, and typography issues. "
            "Runs 20 built-in rules across four categories and reports violations."
        ),
    )
    parser.add_argument("inputs", nargs="+", help="Files, directories, or globs to lint")
    parser.add_argument(
        "-R",
        "--recursive",
        action="store_true",
        help="Recurse into directories",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=("text", "json"),
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        help="Write report to this file instead of stdout",
    )
    parser.add_argument(
        "--config",
        help="Path to an explicit config file (.all2md.toml, pyproject.toml, etc.)",
    )
    parser.add_argument(
        "--rule",
        action="append",
        default=[],
        metavar="CODE",
        help="Only run this rule. May be repeated. Example: --rule STR001 --rule STR002",
    )
    parser.add_argument(
        "--disable",
        action="append",
        default=[],
        metavar="CODE",
        help="Skip this rule. May be repeated.",
    )
    parser.add_argument(
        "--severity",
        choices=("info", "warning", "error"),
        help=(
            "Minimum severity to report. Filters both output AND exit code: "
            "with --severity warning, INFO violations are dropped and do not affect the exit code."
        ),
    )
    return parser


def _build_lint_config(parsed: argparse.Namespace) -> LintConfig:
    """Merge the config file and CLI flags into a single :class:`LintConfig`."""
    config_dict: dict[str, Any] = {}
    raw = load_config_with_priority(explicit_path=parsed.config)
    if isinstance(raw, dict) and isinstance(raw.get("lint"), dict):
        config_dict = dict(raw["lint"])

    config = LintConfig.from_dict(config_dict)

    overrides: dict[str, Any] = {}
    if parsed.rule:
        overrides["enabled_rules"] = frozenset(parsed.rule)
    if parsed.disable:
        merged = set(config.disabled_rules)
        merged.update(parsed.disable)
        overrides["disabled_rules"] = frozenset(merged)
    if parsed.severity:
        overrides["severity_threshold"] = Severity.from_name(parsed.severity)

    if overrides:
        config = config.create_updated(**overrides)
    return config
