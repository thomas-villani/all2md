#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/report.py
"""Conversion confidence report command.

``all2md report`` converts one or more documents and prints a "quality card"
for each: a reference-free ``0-100`` confidence score, the signals behind it
(text density, OCR reliance, rejected tables, dropped embedded objects), and
the discrete degraded-content incidents the converter recorded. It answers
"how much should I trust this conversion?" without needing the original to
compare against.

Examples
--------
    all2md report scan.pdf
    all2md report report.pdf --json
    all2md report *.docx --fail-under 60
    cat doc.pdf | all2md report -

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast

from all2md.ast.nodes import Document
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from all2md.cli.commands.shared import add_cache_arguments, conversion_cache_from_args
from all2md.confidence import ConfidenceReport
from all2md.exceptions import All2MdError, DependencyError

# Signal keys that are purely informative context, not evidence of a problem —
# rendered without a warning marker regardless of value.
_INFO_SIGNALS = {
    "page_count",
    "meaningful_chars",
    "tables_detected",
    "tables_emitted",
    "table_count",
    "image_count",
    "running_headings_demoted",
}


def _create_report_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``all2md report``."""
    parser = argparse.ArgumentParser(
        prog="all2md report",
        description="Print a conversion confidence report ('quality card') for each document.",
        add_help=True,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more documents to inspect (any supported format; use '-' for stdin).",
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
    parser.add_argument("--out", "-o", help="Write output to a file (default: stdout).")
    parser.add_argument(
        "--attachment-mode",
        choices=["skip", "alt_text", "save", "base64"],
        default=None,
        help="How the converter handles images/attachments (overrides config). Report is unaffected "
        "by the choice; use 'skip'/'alt_text' to avoid decoding large embedded images.",
    )
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


def _load_ast(source: str, converter_options: dict) -> tuple[Document, str]:
    """Load an input to an AST, returning ``(doc, label)``.

    ``converter_options`` is a dot-notation options dict (config + CLI overrides)
    projected onto the detected format before conversion.
    """
    from all2md import to_ast
    from all2md.cli.processors import prepare_options_for_execution

    if source == "-":
        data = sys.stdin.buffer.read()
        if not data:
            raise All2MdError("No data received from stdin")
        kwargs = prepare_options_for_execution(converter_options, None, "auto")
        return cast(Document, to_ast(data, **kwargs)), "stdin"

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    kwargs = prepare_options_for_execution(converter_options, path, "auto")
    return cast(Document, to_ast(source, **kwargs)), path.as_posix()


def _band_upper(band: str) -> str:
    return band.upper()


def _format_signal_value(value: Any) -> str:
    """Render a signal value compactly (thousands-separated ints, trimmed floats)."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _render_pretty(label: str, report: ConfidenceReport) -> str:
    """Render a single report as a compact, human-readable quality card."""
    lines: list[str] = [label]
    lines.append(f"  confidence: {report.score}/100  ({_band_upper(report.band)})")
    if report.producer:
        lines.append(f"  producer:   {report.producer}")

    if report.signals:
        lines.append("")
        lines.append("  signals")
        width = max(len(key.replace("_", " ")) for key in report.signals)
        for key, value in report.signals.items():
            friendly = key.replace("_", " ")
            marker = "" if key in _INFO_SIGNALS else _signal_marker(key, value)
            suffix = f"   {marker}" if marker else ""
            lines.append(f"    {friendly.ljust(width)}  {_format_signal_value(value)}{suffix}")

    if report.degraded_events:
        lines.append("")
        lines.append("  degraded events")
        for event in report.degraded_events:
            detail = f"  ({event.detail})" if event.detail else ""
            times = f" x{event.count}" if event.count > 1 else ""
            lines.append(f"    {event.severity:<5} {event.kind}{times}{detail}")

    return "\n".join(lines)


def _signal_marker(key: str, value: Any) -> str:
    """Return a short 'warn'/'info' marker for a signal worth flagging.

    Healthy signals return an empty marker so the card stays calm and problems
    stand out.
    """
    if key == "chars_per_page":
        try:
            return "warn" if float(value) < 200 else ""
        except (TypeError, ValueError):
            return ""
    if key == "ocr_page_fraction":
        try:
            fraction = float(value)
        except (TypeError, ValueError):
            return ""
        if fraction > 0.5:
            return "warn"
        return "info" if fraction > 0 else ""
    # Any other non-info signal that surfaced (tables_rejected, *_dropped) is a
    # count of lost/rejected content; flag it when non-zero.
    try:
        return "warn" if float(value) > 0 else ""
    except (TypeError, ValueError):
        return ""


def handle_report_command(args: list[str] | None = None) -> int:
    """Handle the ``report`` command.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'report').

    Returns
    -------
    int
        Exit code. ``0`` on success; non-zero on load errors or when
        ``--fail-under`` is tripped.

    """
    from all2md.cli.config import apply_config_to_parser

    parser = _create_report_parser()
    try:
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "report", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    if parsed.fail_under is not None and not 0 <= parsed.fail_under <= 100:
        print("Error: --fail-under must be between 0 and 100.", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    stdin_count = sum(1 for src in parsed.inputs if src == "-")
    if stdin_count > 1:
        print("Error: stdin ('-') may only be used once.", file=sys.stderr)
        return EXIT_FILE_ERROR

    from all2md import confidence_report
    from all2md.cli.processors import load_converter_config_options

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)
    if parsed.attachment_mode:
        converter_options["attachment_mode"] = parsed.attachment_mode

    results: list[tuple[str, ConfidenceReport]] = []
    try:
        with conversion_cache_from_args(parsed):
            for source in parsed.inputs:
                doc, label = _load_ast(source, converter_options)
                results.append((label, confidence_report(doc)))
    except DependencyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except All2MdError as e:
        print(f"Error building report: {e}", file=sys.stderr)
        return EXIT_ERROR

    if parsed.json:
        payload = [{"input": label, **report.to_dict()} for label, report in results]
        output = json.dumps(payload if len(payload) != 1 else payload[0], ensure_ascii=False, indent=2)
    else:
        output = "\n\n".join(_render_pretty(label, report) for label, report in results)

    if parsed.out:
        out_path = Path(parsed.out)
        out_path.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote {len(results)} report(s) to {out_path}", file=sys.stderr)
    elif output:
        print(output)

    if parsed.fail_under is not None:
        worst = min((report.score for _, report in results), default=100)
        if worst < parsed.fail_under:
            print(
                f"Confidence {worst} is below --fail-under {parsed.fail_under}.",
                file=sys.stderr,
            )
            return EXIT_ERROR

    return EXIT_SUCCESS
