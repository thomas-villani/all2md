#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/optimize.py
"""Conversion optimizer command.

``all2md optimize`` converts a document many times under different converter
settings and reports the ones that recover the most well-formed structure -- as a
``.all2md.toml`` snippet you can paste straight into a config file.

It is built for the documents that need it most: the gnarly PDF with no known-good
output to compare against. The objective is therefore reference-free (see
:mod:`all2md.optimize`) -- it does not need a ground truth, and it is deliberately
*not* the ``all2md report`` confidence score, which saturates at 100 on anything not
visibly broken and so has no gradient to search.

This costs tens of conversions. ``--sample-pages`` tunes on a slice of a long
document and ``--cache`` makes repeat runs nearly free.

Examples
--------
    all2md optimize scanned.pdf
    all2md optimize report.pdf --sample-pages 5 --cache
    all2md optimize page.html --json
    all2md optimize paper.pdf --rounds 2 --out .all2md.toml

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from all2md.cli.commands.shared import add_cache_arguments, conversion_cache_from_args, protect_stdout
from all2md.constants import DocumentFormat
from all2md.exceptions import All2MdError, DependencyError
from all2md.optimize import OptimizationReport

#: How many ranked candidates the pretty output lists by default.
_DEFAULT_TOP = 5


def _create_optimize_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``all2md optimize``."""
    from all2md.optimize import KNOBS

    parser = argparse.ArgumentParser(
        prog="all2md optimize",
        description="Search converter options for the settings that convert a document best.",
        add_help=True,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help=f"Documents to tune ({', '.join(sorted(KNOBS))}; use '-' for stdin).",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="auto",
        help="Override source format detection (required for stdin of an ambiguous type).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help=(
            "Coordinate-descent passes over the knobs (default: 1). More rounds can find knobs "
            "that only pay off together, at proportionally more conversions."
        ),
    )
    parser.add_argument(
        "--sample-pages",
        type=int,
        metavar="N",
        help=(
            "Tune against only the first N pages of a paginated document. Use at least 2: "
            "running headers/footers are found by their repetition, so one page cannot reveal them."
        ),
    )
    parser.add_argument(
        "--no-presets",
        action="store_true",
        help="Skip scoring the named presets; refine from the defaults only.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=_DEFAULT_TOP,
        metavar="N",
        help=f"How many ranked candidates to show (default: {_DEFAULT_TOP}; 0 for all).",
    )
    parser.add_argument("--json", action="store_true", help="Emit the full report as JSON.")
    parser.add_argument(
        "--out",
        "-o",
        metavar="FILE",
        help="Write the recommended settings to FILE as a TOML snippet instead of stdout.",
    )
    parser.add_argument("--config", help="Path to a configuration file.")
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    add_cache_arguments(parser)
    return parser


def _toml_value(value: Any) -> str:
    """Render a Python option value as a TOML literal."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    return json.dumps(str(value))


def _toml_snippet(report: OptimizationReport) -> str:
    """Render the winning options as a pasteable ``.all2md.toml`` section."""
    if not report.best_options:
        return ""
    lines = [f"[{report.source_format}]"]
    for name, value in sorted(report.best_options.items()):
        lines.append(f"{name} = {_toml_value(value)}")
    return "\n".join(lines)


def _cli_command(label: str, report: OptimizationReport) -> str:
    """Render the winning options as a runnable ``all2md`` command line.

    Flag names are read from the CLI builder's own ``dest -> flag`` map rather than
    re-derived from the field names here. The naming rules are not mechanical -- a
    boolean that defaults to *True* is exposed as its negation
    (``detect_columns`` -> ``--pdf-no-detect-columns``) -- and a second hand-written
    copy of those rules would be free to drift out of sync with the real parser.

    Because the boolean flags *flip* the default, a value that already equals the
    default needs no flag at all; ``optimize_options`` has already pruned those.
    """
    import dataclasses

    from all2md.cli.builder import DynamicCLIBuilder
    from all2md.converter_registry import registry

    if not report.best_options:
        return ""

    builder = DynamicCLIBuilder()
    builder.build_parser()
    flag_for_dest = builder.dest_to_cli_flag

    options_class = registry.get_parser_options_class(report.source_format)
    defaults: dict[str, Any] = {}
    if options_class is not None:
        defaults = {
            f.name: f.default for f in dataclasses.fields(options_class) if f.default is not dataclasses.MISSING
        }

    parts: list[str] = []
    unmapped: list[str] = []
    for name, value in sorted(report.best_options.items()):
        flag = flag_for_dest.get(f"{report.source_format}.{name}")
        if flag is None:
            unmapped.append(name)
            continue
        if isinstance(value, bool):
            # The flag inverts the default, so its mere presence sets this value.
            if value == defaults.get(name):
                continue
            parts.append(flag)
        else:
            parts.append(f"{flag} {value}")

    if not parts:
        return ""

    quoted = f'"{label}"' if " " in label else label
    command = f"all2md {quoted} " + " ".join(parts)
    if unmapped:
        command += f"\n# no CLI flag for: {', '.join(unmapped)} (use the TOML snippet)"
    return command


def _optimize_one(
    source: str,
    source_format: str,
    rounds: int,
    sample_pages: int | None,
    include_presets: bool,
) -> tuple[str, OptimizationReport]:
    """Tune one input, returning ``(label, report)``."""
    from all2md import optimize_options

    src_format = cast(DocumentFormat, source_format)

    if source == "-":
        data = sys.stdin.buffer.read()
        if not data:
            raise All2MdError("No data received from stdin")
        return "stdin", optimize_options(
            data,
            source_format=src_format,
            rounds=rounds,
            sample_pages=sample_pages,
            include_presets=include_presets,
        )

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    return path.as_posix(), optimize_options(
        source,
        source_format=src_format,
        rounds=rounds,
        sample_pages=sample_pages,
        include_presets=include_presets,
    )


def _render_pretty(label: str, report: OptimizationReport, top: int) -> str:
    """Render one optimization result as a human-readable card."""
    lines: list[str] = [label]
    lines.append(f"  format:     {report.source_format}")
    lines.append(f"  evaluated:  {report.evaluated} candidates")

    if report.improved:
        lines.append(
            f"  fitness:    {report.best_fitness:.2f}  "
            f"(defaults scored {report.baseline_fitness:.2f}, {report.gain:+.2f})"
        )
        command = _cli_command(label, report)
        if command:
            lines.append("")
            lines.append("  command")
            for line in command.splitlines():
                lines.append(f"    {line}")
        lines.append("")
        lines.append("  .all2md.toml")
        for line in _toml_snippet(report).splitlines():
            lines.append(f"    {line}")
    else:
        lines.append(f"  fitness:    {report.baseline_fitness:.2f}")
        lines.append("")
        lines.append("  The defaults are already the best settings found. Nothing to change.")

    ranked = report.candidates if top <= 0 else report.candidates[:top]
    if ranked:
        lines.append("")
        lines.append("  ranked candidates")
        for candidate in ranked:
            options = (
                ", ".join(f"{k}={v}" for k, v in sorted(candidate.options.items()))
                if candidate.options
                else "(defaults)"
            )
            lines.append(f"    {candidate.fitness:6.2f}  {options}")

    # The fitness is pool-relative, so an absolute number would be misleading.
    lines.append("")
    lines.append("  Fitness ranks candidates against each other; it is not an absolute quality score.")
    lines.append("  For that, use `all2md report` (trust) or `all2md roundtrip` (fidelity).")
    return "\n".join(lines)


def handle_optimize_command(args: list[str] | None = None) -> int:
    """Handle the ``optimize`` command.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'optimize').

    Returns
    -------
    int
        Exit code. ``0`` on success; non-zero on load or validation errors.

    """
    from all2md.cli.config import apply_config_to_parser

    parser = _create_optimize_parser()
    try:
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "optimize", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    if parsed.rounds < 1:
        print("Error: --rounds must be at least 1.", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if parsed.sample_pages is not None and parsed.sample_pages < 1:
        print("Error: --sample-pages must be at least 1.", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if sum(1 for src in parsed.inputs if src == "-") > 1:
        print("Error: stdin ('-') may only be used once.", file=sys.stderr)
        return EXIT_FILE_ERROR

    results: list[tuple[str, OptimizationReport]] = []
    try:
        # Guard fd 1 so PyMuPDF advisories during the (many) parses cannot corrupt
        # the report -- especially the machine-readable --json stream.
        with protect_stdout(), conversion_cache_from_args(parsed):
            for source in parsed.inputs:
                results.append(
                    _optimize_one(
                        source,
                        parsed.format,
                        parsed.rounds,
                        parsed.sample_pages,
                        not parsed.no_presets,
                    )
                )
    except DependencyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except All2MdError as e:
        print(f"Error during optimization: {e}", file=sys.stderr)
        return EXIT_ERROR

    if parsed.json:
        payload: list[dict[str, Any]] = [
            {
                "input": label,
                **report.to_dict(),
                "command": _cli_command(label, report),
                "toml": _toml_snippet(report),
            }
            for label, report in results
        ]
        output = json.dumps(payload if len(payload) != 1 else payload[0], ensure_ascii=False, indent=2)
    elif parsed.out:
        snippets = [snippet for _, report in results if (snippet := _toml_snippet(report))]
        if not snippets:
            print("The defaults are already the best settings found; nothing to write.", file=sys.stderr)
            return EXIT_SUCCESS
        output = "\n\n".join(snippets)
    else:
        output = "\n\n".join(_render_pretty(label, report, parsed.top) for label, report in results)

    if parsed.out:
        Path(parsed.out).write_text(output + "\n", encoding="utf-8")
        print(f"Wrote recommended settings to {parsed.out}", file=sys.stderr)
    else:
        print(output)

    return EXIT_SUCCESS
