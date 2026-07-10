#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/roundtrip.py
"""Round-trip fidelity command.

``all2md roundtrip`` converts a document to another format, converts it straight
back, and scores what survived: a ``0-100`` structural fidelity score, the
per-dimension metrics behind it (structure, text, inline formatting, tables,
references), and the concrete differences it found. Unlike ``all2md report``,
this comparison has a ground truth -- the source document itself -- so a lossless
round trip scores exactly ``100`` and anything less is a real defect.

Examples
--------
    all2md roundtrip report.docx
    all2md roundtrip notes.md --via rst
    all2md roundtrip *.docx --fail-under 90
    all2md roundtrip paper.pdf --json
    cat notes.md | all2md roundtrip - --format markdown

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
from all2md.roundtrip import RoundTripReport

#: How many deltas the pretty card lists before summarizing the rest. Deltas are
#: coalesced and severity-ranked, so the first few are the ones worth reading.
_DEFAULT_MAX_DELTAS = 10

#: Human-readable gloss for each metric, shown beside its score.
_METRIC_HELP = {
    "structure": "headings, lists, tables, code blocks",
    "text": "the document's word stream",
    "inline": "bold, italic, code, links",
    "tables": "table dimensions and cell text",
    "references": "link and image targets",
}


def _create_roundtrip_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``all2md roundtrip``."""
    parser = argparse.ArgumentParser(
        prog="all2md roundtrip",
        description="Convert a document through another format and back, scoring what survived.",
        add_help=True,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more documents to round-trip (any supported format; use '-' for stdin).",
    )
    parser.add_argument(
        "--via",
        default="markdown",
        metavar="FORMAT",
        help="Intermediate format to round-trip through (default: markdown). "
        "Must have both a renderer and a parser; see 'all2md list-formats'.",
    )
    parser.add_argument(
        "--format",
        "-f",
        default="auto",
        metavar="FORMAT",
        help="Source format, overriding auto-detection. Worth setting for stdin, whose content "
        "cannot always be told apart (Markdown piped in sniffs as plaintext).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the report(s) as JSON (an array when multiple inputs are given).",
    )
    parser.add_argument(
        "--fail-under",
        type=int,
        default=None,
        metavar="SCORE",
        help="Exit non-zero if any document scores below SCORE (0-100). Useful as a CI gate.",
    )
    parser.add_argument(
        "--max-deltas",
        type=int,
        default=_DEFAULT_MAX_DELTAS,
        metavar="N",
        help=f"Show at most N differences per document (default: {_DEFAULT_MAX_DELTAS}; 0 for all).",
    )
    parser.add_argument("--out", "-o", help="Write output to a file (default: stdout).")
    parser.add_argument(
        "--config",
        help="Path to a configuration file whose converter sections provide parsing defaults.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )
    add_cache_arguments(parser)
    return parser


def _load_report(source: str, via: str, source_format: str, converter_options: dict) -> tuple[str, RoundTripReport]:
    """Round-trip one input, returning ``(label, report)``."""
    from all2md import roundtrip_report
    from all2md.cli.processors import prepare_options_for_execution

    # argparse hands us plain strings; ``--via`` was validated against
    # roundtrippable_formats() and ``--format`` is checked by the parser registry.
    via_format = cast(DocumentFormat, via)
    src_format = cast(DocumentFormat, source_format)

    if source == "-":
        data = sys.stdin.buffer.read()
        if not data:
            raise All2MdError("No data received from stdin")
        kwargs = prepare_options_for_execution(converter_options, None, source_format)
        return "stdin", roundtrip_report(data, via=via_format, source_format=src_format, **kwargs)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    kwargs = prepare_options_for_execution(converter_options, path, source_format)
    return path.as_posix(), roundtrip_report(source, via=via_format, source_format=src_format, **kwargs)


def _render_pretty(label: str, report: RoundTripReport, max_deltas: int) -> str:
    """Render a single report as a compact, human-readable fidelity card."""
    lines: list[str] = [label]
    lines.append(f"  fidelity:  {report.score}/100  ({report.band.upper()})")
    lines.append(f"  pipeline:  parse {report.source_format} -> render {report.via} -> parse {report.via}")

    if report.metrics:
        lines.append("")
        lines.append("  metrics")
        width = max(len(name) for name in report.metrics)
        for name, value in report.metrics.items():
            gloss = _METRIC_HELP.get(name, "")
            suffix = f"   {gloss}" if gloss else ""
            lines.append(f"    {name.ljust(width)}  {value:>3}/100{suffix}")

    if report.deltas:
        shown = report.deltas if max_deltas <= 0 else report.deltas[:max_deltas]
        lines.append("")
        lines.append("  differences")
        for delta in shown:
            detail = f"  ({delta.detail})" if delta.detail else ""
            times = f" x{delta.count}" if delta.count > 1 else ""
            lines.append(f"    {delta.severity:<5} {delta.kind}{times}{detail}")
        remaining = len(report.deltas) - len(shown)
        if remaining > 0:
            lines.append(f"    ... and {remaining} more (use --max-deltas 0 to show all)")

    return "\n".join(lines)


def handle_roundtrip_command(args: list[str] | None = None) -> int:
    """Handle the ``roundtrip`` command.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'roundtrip').

    Returns
    -------
    int
        Exit code. ``0`` on success; non-zero on load errors or when
        ``--fail-under`` is tripped.

    """
    from all2md.cli.config import apply_config_to_parser

    parser = _create_roundtrip_parser()
    try:
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "roundtrip", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    if parsed.fail_under is not None and not 0 <= parsed.fail_under <= 100:
        print("Error: --fail-under must be between 0 and 100.", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    if sum(1 for src in parsed.inputs if src == "-") > 1:
        print("Error: stdin ('-') may only be used once.", file=sys.stderr)
        return EXIT_FILE_ERROR

    from all2md import roundtrippable_formats

    available = roundtrippable_formats()
    if parsed.via not in available:
        print(
            f"Error: cannot round-trip through '{parsed.via}': it needs both a renderer and a parser.\n"
            f"Available: {', '.join(available)}",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR

    from all2md.cli.processors import load_converter_config_options

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)

    results: list[tuple[str, RoundTripReport]] = []
    try:
        # Guard fd 1 so PyMuPDF (and friends) advisory prints during parsing
        # cannot corrupt the report — especially the machine-readable --json stream.
        with protect_stdout(), conversion_cache_from_args(parsed):
            for source in parsed.inputs:
                results.append(_load_report(source, parsed.via, parsed.format, converter_options))
    except DependencyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except All2MdError as e:
        print(f"Error during round trip: {e}", file=sys.stderr)
        return EXIT_ERROR

    if parsed.json:
        payload: list[dict[str, Any]] = [{"input": label, **report.to_dict()} for label, report in results]
        output = json.dumps(payload if len(payload) != 1 else payload[0], ensure_ascii=False, indent=2)
    else:
        output = "\n\n".join(_render_pretty(label, report, parsed.max_deltas) for label, report in results)

    if parsed.out:
        out_path = Path(parsed.out)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {len(results)} report(s) to {out_path}", file=sys.stderr)
    elif output:
        print(output)

    if parsed.fail_under is not None:
        worst = min((report.score for _, report in results), default=100)
        if worst < parsed.fail_under:
            print(f"Fidelity {worst} is below --fail-under {parsed.fail_under}.", file=sys.stderr)
            return EXIT_ERROR

    return EXIT_SUCCESS
