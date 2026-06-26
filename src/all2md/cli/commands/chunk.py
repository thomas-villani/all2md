#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/cli/commands/chunk.py
"""Document chunking command.

``all2md chunk`` splits one or more documents into provenance-carrying chunks
suitable for RAG / LLM pipelines, emitting JSONL by default (one chunk per
line). Each chunk records its section context and, where the source format
tracks it, the originating page / line span — provenance most chunkers drop.

Examples
--------
    all2md chunk report.pdf --strategy semantic --max-tokens 512 --overlap 64
    all2md chunk notes.md --strategy paragraph --token-counter whitespace
    all2md chunk *.docx --format json --out chunks.json
    cat doc.html | all2md chunk - --strategy section

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import cast

from all2md.ast.nodes import Document
from all2md.chunking import STRATEGIES, ProvenanceChunk, chunk_ast
from all2md.cli.builder import (
    EXIT_DEPENDENCY_ERROR,
    EXIT_ERROR,
    EXIT_FILE_ERROR,
    EXIT_SUCCESS,
    EXIT_VALIDATION_ERROR,
)
from all2md.cli.config import apply_config_to_parser
from all2md.exceptions import All2MdError, DependencyError


def _positive_int(value: str) -> int:
    """Validate a strictly positive integer argument."""
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected an integer, got '{value}'") from e
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {ivalue}")
    return ivalue


def _non_negative_int(value: str) -> int:
    """Validate a non-negative integer argument."""
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected an integer, got '{value}'") from e
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {ivalue}")
    return ivalue


def _heading_level(value: str) -> int:
    """Validate a heading level (1-6)."""
    try:
        ivalue = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected an integer 1-6, got '{value}'") from e
    if not 1 <= ivalue <= 6:
        raise argparse.ArgumentTypeError(f"heading level must be between 1 and 6, got {ivalue}")
    return ivalue


def _create_chunk_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for ``all2md chunk``."""
    parser = argparse.ArgumentParser(
        prog="all2md chunk",
        description="Split documents into provenance-carrying chunks (JSONL) for RAG/LLM pipelines.",
        add_help=True,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more documents to chunk (any supported format; use '-' for stdin).",
    )

    parser.add_argument(
        "--strategy",
        choices=list(STRATEGIES),
        default="semantic",
        help="Chunking strategy. 'semantic' (default) windows each section by real tokens; "
        "'heading'/'section'/'auto' cut at semantic boundaries; "
        "'token'/'sentence'/'paragraph'/'word'/'line'/'char'/'code' are fine-grained.",
    )
    parser.add_argument(
        "--max-tokens",
        type=_positive_int,
        default=512,
        help="Maximum tokens per chunk (default: 512).",
    )
    parser.add_argument(
        "--overlap",
        type=_non_negative_int,
        default=0,
        help="Overlap between consecutive windows (coerced to 0 for coarse strategies; default: 0).",
    )
    parser.add_argument(
        "--min-tokens",
        type=_non_negative_int,
        default=0,
        help="Drop trailing chunks smaller than this many tokens (default: 0, keep all).",
    )
    parser.add_argument(
        "--max-heading-level",
        type=_heading_level,
        default=None,
        help="For fine strategies, only descend into sections at or above this heading level (1-6).",
    )
    parser.add_argument(
        "--include-preamble",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit content before the first heading as its own chunk(s) (default: enabled).",
    )
    parser.add_argument(
        "--heading-merge",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Prepend each section's heading line to its chunk text (default: enabled).",
    )
    parser.add_argument(
        "--token-counter",
        choices=["auto", "tiktoken", "whitespace"],
        default="auto",
        help="Token-counting backend. 'auto' prefers tiktoken, falling back to a whitespace "
        "approximation for count-only strategies (default: auto).",
    )

    parser.add_argument(
        "--avoid-table-split",
        action="store_true",
        help="Keep each table whole: emit it as its own chunk rather than splitting it mid-row "
        "(the table chunk may exceed --max-tokens). Applies to fine strategies.",
    )
    parser.add_argument(
        "--avoid-code-split",
        action="store_true",
        help="Keep each fenced code block whole: emit it as its own chunk rather than splitting it "
        "(the code chunk may exceed --max-tokens). Applies to fine strategies.",
    )
    parser.add_argument(
        "--elide-data-uris",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Replace long base64 'data:' URIs (e.g. embedded images) with a short placeholder so "
        "they don't inflate token counts or shred into noise (default: enabled).",
    )
    parser.add_argument(
        "--drop-elements",
        metavar="TYPES",
        help="Comma-separated AST node types to strip before chunking, e.g. 'image,table,code_block'. "
        "Aliases like 'images'/'tables'/'code' are accepted. Useful for removing noise (e.g. base64 images).",
    )

    parser.add_argument(
        "--attachment-mode",
        choices=["skip", "alt_text", "save", "base64"],
        default=None,
        help="How the converter handles images/attachments before chunking (overrides config; "
        "default: the converter default, 'alt_text'). Use 'skip'/'alt_text' to avoid huge base64 blobs.",
    )

    parser.add_argument(
        "--format",
        "-f",
        dest="output_format",
        choices=["jsonl", "json", "pretty"],
        default="jsonl",
        help="Output format: jsonl (default, one object per line), json (array), pretty (human-readable).",
    )
    parser.add_argument("--out", "-o", help="Write output to a file (default: stdout).")

    parser.add_argument(
        "--config",
        help="Path to a configuration file. Values in its [chunk] section provide defaults "
        "(CLI flags still override). If omitted, ALL2MD_CONFIG and auto-discovered configs apply.",
    )
    parser.add_argument(
        "--no-config",
        action="store_true",
        help="Disable configuration file loading for this command.",
    )

    return parser


# Friendly aliases for --drop-elements onto canonical AST node-type names.
_DROP_ALIASES = {
    "images": "image",
    "tables": "table",
    "code": "code_block",
    "code-block": "code_block",
    "code-blocks": "code_block",
    "codeblocks": "code_block",
    "figures": "image",
    "lists": "list",
    "links": "link",
    "headings": "heading",
}


def _parse_drop_elements(spec: str | None) -> list[str]:
    """Parse a ``--drop-elements`` spec into canonical node-type names."""
    if not spec:
        return []
    types: list[str] = []
    for raw in spec.split(","):
        name = raw.strip().lower()
        if not name:
            continue
        types.append(_DROP_ALIASES.get(name, name))
    return types


def _load_ast(source: str, converter_options: dict) -> tuple[Document, str, str | None]:
    """Load an input to an AST, returning ``(doc, document_id, document_path)``.

    ``converter_options`` is a dot-notation options dict (from config + CLI
    overrides); it is projected onto the detected format before conversion.
    """
    from all2md import to_ast
    from all2md.cli.processors import prepare_options_for_execution

    if source == "-":
        data = sys.stdin.buffer.read()
        if not data:
            raise All2MdError("No data received from stdin")
        kwargs = prepare_options_for_execution(converter_options, None, "auto")
        return cast(Document, to_ast(data, **kwargs)), "stdin", None

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {source}")
    kwargs = prepare_options_for_execution(converter_options, path, "auto")
    return cast(Document, to_ast(source, **kwargs)), path.stem, path.as_posix()


def _render_pretty(chunks: list[ProvenanceChunk]) -> str:
    """Render chunks as a compact human-readable listing."""
    lines: list[str] = []
    for chunk in chunks:
        loc = []
        if chunk.section_heading:
            loc.append(f"§ {chunk.section_heading}")
        if chunk.page is not None:
            loc.append(f"p.{chunk.page}" + (f"-{chunk.page_end}" if chunk.page_end != chunk.page else ""))
        location = "  ".join(loc) if loc else "(preamble)"
        preview = chunk.text.strip().replace("\n", " ")
        if len(preview) > 100:
            preview = preview[:97] + "..."
        lines.append(f"[{chunk.index}] {chunk.chunk_id}  ({chunk.token_count} tok)  {location}")
        lines.append(f"    {preview}")
    return "\n".join(lines)


def _format_output(chunks: list[ProvenanceChunk], output_format: str) -> str:
    """Serialize chunks to the requested output format."""
    if output_format == "jsonl":
        return "\n".join(json.dumps(c.to_dict(), ensure_ascii=False) for c in chunks)
    if output_format == "json":
        return json.dumps([c.to_dict() for c in chunks], ensure_ascii=False, indent=2)
    return _render_pretty(chunks)


def handle_chunk_command(args: list[str] | None = None) -> int:
    """Handle the ``chunk`` command.

    Parameters
    ----------
    args : list[str], optional
        Command line arguments (beyond 'chunk').

    Returns
    -------
    int
        Exit code (0 for success).

    """
    parser = _create_chunk_parser()
    try:
        pre_args, _ = parser.parse_known_args(args or [])
        apply_config_to_parser(parser, "chunk", explicit_path=pre_args.config, no_config=pre_args.no_config)
        parsed = parser.parse_args(args or [])
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0

    stdin_count = sum(1 for src in parsed.inputs if src == "-")
    if stdin_count > 1:
        print("Error: stdin ('-') may only be used once.", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Converter options from the config file (e.g. [pdf], [html], top-level keys),
    # mirroring `view`/`serve`, with an explicit --attachment-mode override.
    from all2md.cli.processors import load_converter_config_options

    converter_options = load_converter_config_options(explicit_path=parsed.config, no_config=parsed.no_config)
    if parsed.attachment_mode:
        converter_options["attachment_mode"] = parsed.attachment_mode

    drop_types = _parse_drop_elements(parsed.drop_elements)
    drop_transform = None
    if drop_types:
        from all2md.transforms.builtin import RemoveNodesTransform

        try:
            drop_transform = RemoveNodesTransform(node_types=drop_types)
        except ValueError as e:
            print(f"Error: invalid --drop-elements: {e}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    all_chunks: list[ProvenanceChunk] = []
    try:
        for source in parsed.inputs:
            doc, document_id, document_path = _load_ast(source, converter_options)
            if drop_transform is not None:
                doc = cast(Document, drop_transform.transform(doc))
            label = document_path or document_id
            print(f"Chunking {label} (strategy={parsed.strategy}, max_tokens={parsed.max_tokens})...", file=sys.stderr)
            chunks = chunk_ast(
                doc,
                strategy=parsed.strategy,
                max_tokens=parsed.max_tokens,
                overlap=parsed.overlap,
                document_id=document_id,
                document_path=document_path,
                include_preamble=parsed.include_preamble,
                heading_merge=parsed.heading_merge,
                max_heading_level=parsed.max_heading_level,
                avoid_table_split=parsed.avoid_table_split,
                avoid_code_split=parsed.avoid_code_split,
                elide_data_uris=parsed.elide_data_uris,
                min_tokens=parsed.min_tokens,
                token_counter=parsed.token_counter,
            )
            all_chunks.extend(chunks)
    except DependencyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_FILE_ERROR
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR
    except All2MdError as e:
        print(f"Error chunking document: {e}", file=sys.stderr)
        return EXIT_ERROR

    output = _format_output(all_chunks, parsed.output_format)

    if parsed.out:
        out_path = Path(parsed.out)
        out_path.write_text(output + ("\n" if output and not output.endswith("\n") else ""), encoding="utf-8")
        print(f"Wrote {len(all_chunks)} chunk(s) to {out_path}", file=sys.stderr)
    else:
        if output:
            print(output)
    print(f"Done: {len(all_chunks)} chunk(s) from {len(parsed.inputs)} input(s).", file=sys.stderr)
    return EXIT_SUCCESS
