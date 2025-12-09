#  Copyright (c) 2025 Tom Villani, Ph.D.

# ${DIR_PATH}/${FILE_NAME}
"""Document search commands for all2md CLI.

This module provides search and grep commands for querying documents using
various retrieval modes including keyword (BM25), vector (semantic), hybrid,
and grep (pattern matching). Supports index persistence, rich output
formatting, and configurable chunking strategies.
"""
import argparse
import json
import os
import sys
import textwrap
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict, List, Mapping

from all2md.cli.builder import EXIT_DEPENDENCY_ERROR, EXIT_ERROR, EXIT_FILE_ERROR, EXIT_SUCCESS, EXIT_VALIDATION_ERROR
from all2md.cli.commands.shared import collect_input_files
from all2md.cli.config import load_config_with_priority
from all2md.cli.input_items import CLIInputItem
from all2md.exceptions import DependencyError
from all2md.options.search import SearchOptions
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.search.service import SearchDocumentInput, SearchMode, SearchResult, SearchService


def _make_search_progress_callback(enabled: bool) -> ProgressCallback | None:
    if not enabled:
        return None

    def callback(event: ProgressEvent) -> None:
        if getattr(event, "event_type", None) == "error":
            print(f"[ERROR] {event.message}", file=sys.stderr)
            return
        if getattr(event, "event_type", None) == "item_done" and event.metadata.get("item_type") not in {
            "document",
            "search",
        }:
            return
        print(f"[{event.event_type.upper()}] {event.message}", file=sys.stderr)

    return callback


def _rich_snippet(snippet: str) -> Any:
    if not snippet:
        return None
    from rich.text import Text

    text = Text()
    cursor = 0
    while cursor < len(snippet):
        start = snippet.find("<<", cursor)
        if start == -1:
            # Process remaining text for ellipses
            _append_with_dim_ellipses(text, snippet[cursor:])
            break
        # Process text before highlight marker for ellipses
        _append_with_dim_ellipses(text, snippet[cursor:start])
        end = snippet.find(">>", start)
        if end == -1:
            _append_with_dim_ellipses(text, snippet[start:])
            break
        text.append(snippet[start + 2 : end], style="bold yellow")
        cursor = end + 2
    return text


def _append_with_dim_ellipses(text: Any, content: str) -> None:
    """Append content to Text object, styling ellipses as dim.

    Parameters
    ----------
    text : rich.text.Text
        The Text object to append to
    content : str
        Content that may contain ellipses

    """
    if not content:
        return

    # Split on ellipses and append with appropriate styling
    parts = content.split("...")
    for i, part in enumerate(parts):
        if part:
            text.append(part)
        if i < len(parts) - 1:
            text.append("...", style="dim")


def _format_plain_snippet(snippet: str, width: int = 100, indent: str = "      ") -> list[str]:
    formatted: list[str] = []
    for raw_line in snippet.splitlines():
        if not raw_line:
            formatted.append(indent)
            continue
        wrapped = textwrap.wrap(
            raw_line,
            width=width,
            initial_indent=indent,
            subsequent_indent=indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        if wrapped:
            formatted.extend(wrapped)
        else:
            formatted.append(indent + raw_line)
    return formatted


def _group_results_by_doc_and_section(results: List[SearchResult]) -> dict[str, dict[str, list[SearchResult]]]:
    """Group search results by document path and section.

    Parameters
    ----------
    results : List[SearchResult]
        Search results to group

    Returns
    -------
    dict[str, dict[str, list[SearchResult]]]
        Nested dictionary with structure: {doc_label: {section: [results]}}

    """
    grouped: dict[str, dict[str, list[SearchResult]]] = {}
    for result in results:
        metadata = result.chunk.metadata
        doc_label = (
            metadata.get("document_path") or metadata.get("path_hint") or metadata.get("document_id") or "unknown"
        )
        section = metadata.get("section_heading") or "(preamble)"

        if doc_label not in grouped:
            grouped[doc_label] = {}
        if section not in grouped[doc_label]:
            grouped[doc_label][section] = []
        grouped[doc_label][section].append(result)
    return grouped


def _parse_line_number_if_present(line: str, show_line_numbers: bool) -> tuple[str | None, str]:
    """Parse line number from grep output if present.

    Parameters
    ----------
    line : str
        Line that may contain line number in format "123: content"
    show_line_numbers : bool
        Whether line numbers are expected in output

    Returns
    -------
    tuple[str | None, str]
        Tuple of (line_number, content). line_number is None if not found.

    """
    if not show_line_numbers or ": " not in line:
        return None, line

    parts = line.split(": ", 1)
    if parts[0].isdigit():
        return parts[0], parts[1]
    return None, line


def _render_compact_rich(
    grouped: dict[str, dict[str, list[SearchResult]]], console: Any, show_line_numbers: bool
) -> None:
    """Render grep results in compact format using rich.

    Parameters
    ----------
    grouped : dict[str, dict[str, list[SearchResult]]]
        Results grouped by document and section
    console : rich.console.Console
        Rich console for output
    show_line_numbers : bool
        Whether to show line numbers

    """
    from rich.text import Text

    for doc_path, sections in grouped.items():
        # File header
        header = Text(str(doc_path), style="bold magenta")
        console.print(header)

        # Print each match in compact format
        for section_name, section_results in sections.items():
            for result in section_results:
                snippet = result.chunk.text
                if snippet:
                    for line in snippet.splitlines():
                        line_number, content = _parse_line_number_if_present(line, show_line_numbers)

                        # Build the output line with 2-space indent
                        output = Text("  ")
                        output.append(section_name, style="bold cyan")
                        output.append(":")
                        if line_number:
                            output.append(line_number, style="green")
                            output.append(":")
                        snippet_text = _rich_snippet(content)
                        if snippet_text:
                            output.append(snippet_text)
                        else:
                            output.append(content)
                        console.print(output)


def _render_compact_plain(grouped: dict[str, dict[str, list[SearchResult]]], show_line_numbers: bool) -> None:
    """Render grep results in compact format using plain text.

    Parameters
    ----------
    grouped : dict[str, dict[str, list[SearchResult]]]
        Results grouped by document and section
    show_line_numbers : bool
        Whether to show line numbers

    """
    for doc_path, sections in grouped.items():
        # File header
        print(str(doc_path))

        # Print each match in compact format
        for section_name, section_results in sections.items():
            for result in section_results:
                snippet = result.chunk.text
                if snippet:
                    for line in snippet.splitlines():
                        line_number, content = _parse_line_number_if_present(line, show_line_numbers)

                        # Strip highlighting markers in plain mode
                        plain_content = content.replace("<<", "").replace(">>", "")

                        # Build the output line with 2-space indent
                        if line_number:
                            print(f"  {section_name}:{line_number}:{plain_content}")
                        else:
                            print(f"  {section_name}:{plain_content}")


def _render_grouped_rich(grouped: dict[str, dict[str, list[SearchResult]]], console: Any) -> None:
    """Render grep results in grouped format using rich.

    Parameters
    ----------
    grouped : dict[str, dict[str, list[SearchResult]]]
        Results grouped by document and section
    console : rich.console.Console
        Rich console for output

    """
    from rich.text import Text

    for doc_path, sections in grouped.items():
        # File header
        header = Text(str(doc_path), style="bold magenta")
        console.print(header)
        console.print()

        # Print each section
        for section_name, section_results in sections.items():
            # Section heading
            console.print(Text(section_name, style="bold cyan"))

            # Print matches for this section
            for result in section_results:
                snippet = result.chunk.text
                if snippet:
                    # Indent each line
                    for line in snippet.splitlines():
                        snippet_text = _rich_snippet(line)
                        if snippet_text:
                            console.print(Text("  ") + snippet_text)
                        else:
                            console.print(f"  {line}")

            console.print()


def _render_grouped_plain(grouped: dict[str, dict[str, list[SearchResult]]]) -> None:
    """Render grep results in grouped format using plain text.

    Parameters
    ----------
    grouped : dict[str, dict[str, list[SearchResult]]]
        Results grouped by document and section

    """
    for doc_path, sections in grouped.items():
        # File header
        print(str(doc_path))
        print()

        # Print each section
        for section_name, section_results in sections.items():
            # Section heading
            print(section_name)

            # Print matches for this section
            for result in section_results:
                snippet = result.chunk.text
                if snippet:
                    # Indent each line of the snippet
                    for line in snippet.splitlines():
                        # Strip highlighting markers in plain mode
                        plain_line = line.replace("<<", "").replace(">>", "")
                        print(f"  {plain_line}")

            print()


def _render_grep_results(
    results: List[SearchResult],
    *,
    use_rich: bool,
    context_before: int = 0,
    context_after: int = 0,
    show_line_numbers: bool = False,
) -> None:
    """Render grep results in ripgrep-style format.

    Groups matches by file, showing file path as a header followed by
    matching lines with line numbers.

    Parameters
    ----------
    results : List[SearchResult]
        Search results from grep mode
    use_rich : bool
        Whether to use rich formatting
    context_before : int, default = 0
        Number of lines of context before matches
    context_after : int, default = 0
        Number of lines of context after matches
    show_line_numbers : bool, default = False
        Whether line numbers are shown in the output

    """
    console = None
    if use_rich:
        try:
            from rich.console import Console

            console = Console()
        except ImportError:
            use_rich = False

    # Determine if we should use compact format (no context lines)
    use_compact_format = context_before == 0 and context_after == 0

    # Group results by document path and section
    grouped = _group_results_by_doc_and_section(results)

    # Render in compact format when no context lines
    if use_compact_format:
        if use_rich and console is not None:
            _render_compact_rich(grouped, console, show_line_numbers)
        else:
            _render_compact_plain(grouped, show_line_numbers)
        return

    # Render in grouped format when context lines are present
    if use_rich and console is not None:
        _render_grouped_rich(grouped, console)
    else:
        _render_grouped_plain(grouped)


def _render_search_results(
    results: List[SearchResult],
    *,
    use_rich: bool,
    grep_context_before: int = 0,
    grep_context_after: int = 0,
    grep_show_line_numbers: bool = False,
) -> None:
    if not results:
        print("No results found.")
        return

    # Check if this is grep mode
    is_grep = False
    if results:
        first_backend = results[0].metadata.get("backend", "") if isinstance(results[0].metadata, Mapping) else ""
        is_grep = first_backend == "grep"

    if is_grep:
        _render_grep_results(
            results,
            use_rich=use_rich,
            context_before=grep_context_before,
            context_after=grep_context_after,
            show_line_numbers=grep_show_line_numbers,
        )
        return

    console = None
    if use_rich:
        try:
            from rich.console import Console

            console = Console()
        except ImportError:
            print("Rich output requested but `rich` is not installed. Falling back to plain output.")
            use_rich = False

    for rank, result in enumerate(results, start=1):
        metadata = result.chunk.metadata
        doc_label = metadata.get("document_path") or metadata.get("path_hint") or metadata.get("document_id")
        heading = metadata.get("section_heading") or ""
        backend = str(result.metadata.get("backend", "")) if isinstance(result.metadata, Mapping) else ""
        occurrences = result.metadata.get("occurrences") if isinstance(result.metadata, Mapping) else None
        lines = result.metadata.get("lines") if isinstance(result.metadata, Mapping) else None
        show_score = backend != "grep"

        if use_rich and console is not None:
            from rich.text import Text

            header = Text(f"{rank:>2}. ", style="bold cyan")
            if show_score:
                header.append(f"score={result.score:.4f} ", style="green")
            if backend:
                header.append(f"[{backend}] ")
            if doc_label:
                header.append(str(doc_label))
            console.print(header)

            if heading:
                console.print(Text(f"  Heading: {heading}", style="bold"))
            if lines:
                console.print(Text(f"  Lines: {', '.join(str(line) for line in lines)}", style="dim"))
            if occurrences and backend == "grep":
                console.print(Text(f"  Matches: {occurrences}", style="dim"))

            snippet_text = _rich_snippet(result.chunk.text)
            if snippet_text:
                snippet_lines = snippet_text.wrap(console, width=console.width - 15)
                for line in snippet_lines:
                    line.pad_left(4)
                console.print(snippet_lines)

            console.print()
            continue

        line = f"{rank:>2}."
        if show_score:
            line += f" score={result.score:.4f}"
        if backend:
            line += f" [{backend}]"
        if doc_label:
            line += f" {doc_label}"
        print(line)
        if heading:
            print(f"    Heading: {heading}")
        if lines:
            print(f"    Lines: {', '.join(str(line) for line in lines)}")
        if occurrences and backend == "grep":
            print(f"    Matches: {occurrences}")
        snippet = result.chunk.text
        if snippet:
            for line in _format_plain_snippet(snippet):
                print(line)


def handle_search_command(args: list[str] | None = None) -> int:
    """Handle ``all2md search`` for keyword/vector/hybrid queries."""
    parser = argparse.ArgumentParser(
        prog="all2md search",
        description="Search documents using keyword, vector, or hybrid retrieval.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", help="Search query text")
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Files, directories, or globs to index. Omit when reusing persisted index.",
    )
    parser.add_argument("--config", help="Optional configuration file overriding defaults")
    parser.add_argument("--index-dir", help="Directory containing or storing persisted index data")
    parser.add_argument("--persist", action="store_true", help="Persist index state to --index-dir")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild even if cached index exists")
    parser.add_argument("--top-k", type=int, default=10, help="Maximum number of results to return")
    parser.add_argument("--json", action="store_true", help="Emit search results as JSON")
    parser.add_argument("--progress", action="store_true", help="Print progress updates during indexing/search")
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories when indexing inputs")
    parser.add_argument("--exclude", action="append", help="Glob pattern to exclude (repeatable)")
    parser.add_argument("--rich", action="store_true", help="Enable rich-style output formatting when printing")
    parser.add_argument(
        "-A",
        "--after-context",
        dest="grep_context_after",
        type=int,
        help="Print NUM lines of trailing context (grep mode)",
    )
    parser.add_argument(
        "-B",
        "--before-context",
        dest="grep_context_before",
        type=int,
        help="Print NUM lines of leading context (grep mode)",
    )
    parser.add_argument(
        "-C",
        "--context",
        dest="grep_context",
        type=int,
        help="Print NUM lines of leading and trailing context (equivalent to -A NUM -B NUM)",
    )
    parser.add_argument(
        "-e",
        "--regex",
        dest="grep_regex",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Interpret query as a regular expression when using grep mode",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--mode",
        dest="mode",
        choices=["grep", "keyword", "vector", "hybrid"],
        help="Explicit search mode to execute",
    )
    mode_group.add_argument("--grep", dest="mode", action="store_const", const="grep", help="Shortcut for --mode grep")
    mode_group.add_argument(
        "--keyword", dest="mode", action="store_const", const="keyword", help="Shortcut for --mode keyword"
    )
    mode_group.add_argument(
        "--vector", dest="mode", action="store_const", const="vector", help="Shortcut for --mode vector"
    )
    mode_group.add_argument(
        "--hybrid", dest="mode", action="store_const", const="hybrid", help="Shortcut for --mode hybrid"
    )

    parser.add_argument("--chunk-size", dest="chunk_size_tokens", type=int, help="Maximum tokens per chunk")
    parser.add_argument("--chunk-overlap", dest="chunk_overlap_tokens", type=int, help="Token overlap per chunk")
    parser.add_argument("--min-chunk-tokens", dest="min_chunk_tokens", type=int, help="Minimum chunk size")
    parser.add_argument(
        "--include-preamble",
        dest="include_preamble",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include content that appears before the first heading",
    )
    parser.add_argument(
        "--max-heading-level",
        dest="max_heading_level",
        type=int,
        help="Limit chunking to headings at or below this level",
    )
    parser.add_argument("--bm25-k1", dest="bm25_k1", type=float, help="BM25 k1 parameter")
    parser.add_argument("--bm25-b", dest="bm25_b", type=float, help="BM25 b parameter")
    parser.add_argument(
        "--vector-model",
        dest="vector_model_name",
        help="Sentence-transformers model used for embedding generation",
    )
    parser.add_argument(
        "--vector-batch-size",
        dest="vector_batch_size",
        type=int,
        help="Batch size for embedding generation",
    )
    parser.add_argument("--vector-device", dest="vector_device", help="Torch device string for embeddings")
    parser.add_argument(
        "--vector-normalize",
        dest="vector_normalize_embeddings",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Normalize embeddings before FAISS indexing",
    )
    parser.add_argument(
        "--hybrid-keyword-weight",
        dest="hybrid_keyword_weight",
        type=float,
        help="Keyword contribution in hybrid mode",
    )
    parser.add_argument(
        "--hybrid-vector-weight",
        dest="hybrid_vector_weight",
        type=float,
        help="Vector contribution in hybrid mode",
    )
    parser.add_argument(
        "--default-mode",
        dest="default_mode",
        choices=["grep", "keyword", "vector", "hybrid"],
        help="Update the default mode recorded with persisted indexes",
    )

    try:
        parsed = parser.parse_args(args or [])
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0

    if parsed.persist and not parsed.index_dir:
        parser.error("--persist requires --index-dir")

    if getattr(parsed, "grep_context", None) is not None:
        if parsed.grep_context_before is None:
            parsed.grep_context_before = parsed.grep_context
        if parsed.grep_context_after is None:
            parsed.grep_context_after = parsed.grep_context

    if parsed.grep_context_before is not None and parsed.grep_context_before < 0:
        parser.error("--before-context must be non-negative")
    if parsed.grep_context_after is not None and parsed.grep_context_after < 0:
        parser.error("--after-context must be non-negative")

    if parsed.top_k <= 0:
        parser.error("--top-k must be a positive integer")

    env_config_path = os.environ.get("ALL2MD_CONFIG")
    try:
        config_data = load_config_with_priority(explicit_path=parsed.config, env_var_path=env_config_path)
    except argparse.ArgumentTypeError as exc:
        print(f"Error loading configuration: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    search_section: dict[str, Any] = {}
    if config_data and isinstance(config_data, dict):
        search_section = config_data.get("search", {}) or {}

    options = _apply_search_config(SearchOptions(), search_section)
    overrides = _collect_search_overrides(parsed)
    if overrides:
        try:
            options = options.create_updated(**overrides)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    try:
        resolved_mode = _parse_search_mode(parsed.mode, options)
    except argparse.ArgumentTypeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_ERROR

    index_path = Path(parsed.index_dir).expanduser() if parsed.index_dir else None

    service: SearchService | None = None
    using_existing = False
    # Skip index persistence for grep mode (grep doesn't need indexing)
    if index_path and index_path.exists() and not parsed.rebuild and resolved_mode != "grep":
        try:
            service = SearchService.load(index_path, options=options)
            using_existing = True
        except FileNotFoundError:
            using_existing = False

    if using_existing and parsed.inputs:
        print(
            "Error: Cannot specify inputs when reusing an existing index. Use --rebuild to regenerate it.",
            file=sys.stderr,
        )
        return EXIT_VALIDATION_ERROR

    items: List[CLIInputItem] = []
    if parsed.inputs:
        items = collect_input_files(parsed.inputs, recursive=parsed.recursive, exclude_patterns=parsed.exclude)
        if not items and not using_existing:
            print("Error: No valid input files found", file=sys.stderr)
            return EXIT_FILE_ERROR

    # Enable progress by default for vector search (which is typically slow)
    enable_progress = parsed.progress or resolved_mode == "vector"
    progress_callback = _make_search_progress_callback(enable_progress)
    service = service or SearchService(options=options)

    if not using_existing:
        documents = _create_search_documents(items)
        if not documents:
            print("Error: No input documents available for indexing", file=sys.stderr)
            return EXIT_FILE_ERROR
        try:
            service.build_indexes(documents, modes={resolved_mode}, progress_callback=progress_callback)
        except DependencyError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_DEPENDENCY_ERROR
        except Exception as exc:
            print(f"Error building index: {exc}", file=sys.stderr)
            return EXIT_ERROR

        # Skip saving index for grep mode (grep doesn't need indexing)
        if index_path and parsed.persist and resolved_mode != "grep":
            try:
                service.save(index_path)
            except Exception as exc:
                print(f"Error saving index: {exc}", file=sys.stderr)
                return EXIT_ERROR

    try:
        results = service.search(
            parsed.query, mode=resolved_mode, top_k=parsed.top_k, progress_callback=progress_callback
        )
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error executing search: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if parsed.json:
        print(json.dumps([_result_to_dict(result) for result in results], indent=2, ensure_ascii=False))
    else:
        _render_search_results(
            results,
            use_rich=parsed.rich,
            grep_context_before=options.grep_context_before,
            grep_context_after=options.grep_context_after,
            grep_show_line_numbers=options.grep_show_line_numbers,
        )

    return EXIT_SUCCESS


def handle_grep_command(args: list[str] | None = None) -> int:
    """Handle ``all2md grep`` for simple text search in documents.

    This is a simplified interface to the search system that only uses grep mode,
    making it work like traditional grep but for binary document formats.
    """
    parser = argparse.ArgumentParser(
        prog="all2md grep",
        description="Search for text patterns in documents (works on binary formats too).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("query", help="Search query text or pattern")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Files, directories, or globs to search (use '-' for stdin)",
    )
    parser.add_argument(
        "-e",
        "--regex",
        dest="grep_regex",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Interpret query as a regular expression",
    )
    parser.add_argument(
        "-A",
        "--after-context",
        dest="grep_context_after",
        type=int,
        help="Print NUM lines of trailing context",
    )
    parser.add_argument(
        "-B",
        "--before-context",
        dest="grep_context_before",
        type=int,
        help="Print NUM lines of leading context",
    )
    parser.add_argument(
        "-C",
        "--context",
        dest="grep_context",
        type=int,
        help="Print NUM lines of leading and trailing context (equivalent to -A NUM -B NUM)",
    )
    parser.add_argument(
        "-n",
        "--line-number",
        dest="grep_show_line_numbers",
        action="store_true",
        help="Show line numbers for matching lines",
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        dest="grep_ignore_case",
        action="store_true",
        help="Perform case-insensitive matching",
    )
    parser.add_argument(
        "-M",
        "--max-columns",
        dest="grep_max_columns",
        type=int,
        help="Maximum display width for long lines (default: 150, 0 = unlimited)",
    )
    parser.add_argument("--recursive", action="store_true", help="Recurse into directories when searching")
    parser.add_argument("--exclude", action="append", help="Glob pattern to exclude (repeatable)")
    parser.add_argument("--rich", action="store_true", help="Enable rich-style output formatting")

    parsed = parser.parse_args(args)

    # Apply context shortcuts
    if parsed.grep_context is not None:
        if parsed.grep_context_before is None:
            parsed.grep_context_before = parsed.grep_context
        if parsed.grep_context_after is None:
            parsed.grep_context_after = parsed.grep_context

    # Create search options with grep-specific settings
    options = SearchOptions()
    overrides = {}
    if parsed.grep_context_before is not None:
        overrides["grep_context_before"] = parsed.grep_context_before
    if parsed.grep_context_after is not None:
        overrides["grep_context_after"] = parsed.grep_context_after
    if parsed.grep_regex is not None:
        overrides["grep_regex"] = parsed.grep_regex
    if parsed.grep_show_line_numbers:
        overrides["grep_show_line_numbers"] = parsed.grep_show_line_numbers
    if parsed.grep_ignore_case:
        overrides["grep_ignore_case"] = parsed.grep_ignore_case
    if parsed.grep_max_columns is not None:
        overrides["grep_max_columns"] = parsed.grep_max_columns

    if overrides:
        try:
            options = options.create_updated(**overrides)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return EXIT_VALIDATION_ERROR

    # Collect input files
    items = collect_input_files(parsed.inputs, recursive=parsed.recursive, exclude_patterns=parsed.exclude)
    if not items:
        print("Error: No valid input files found", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Create documents
    documents = _create_search_documents(items)
    if not documents:
        print("Error: No input documents available for searching", file=sys.stderr)
        return EXIT_FILE_ERROR

    # Build index and search (grep mode, no persistence)
    service = SearchService(options=options)
    try:
        service.build_indexes(documents, modes={SearchMode.GREP})
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error building index: {exc}", file=sys.stderr)
        return EXIT_ERROR

    try:
        # Grep mode returns all results (no top_k limit)
        results = service.search(parsed.query, mode="grep", top_k=999999)
    except DependencyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DEPENDENCY_ERROR
    except Exception as exc:
        print(f"Error during search: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Render results
    _render_search_results(
        results,
        use_rich=parsed.rich,
        grep_context_before=options.grep_context_before,
        grep_context_after=options.grep_context_after,
        grep_show_line_numbers=options.grep_show_line_numbers,
    )
    return EXIT_SUCCESS


def _apply_search_config(options: SearchOptions, config_section: Mapping[str, object]) -> SearchOptions:
    if not config_section:
        return options
    valid_fields = {field.name for field in fields(SearchOptions)}
    filtered = {key: value for key, value in config_section.items() if key in valid_fields}
    if not filtered:
        return options
    return options.create_updated(**filtered)


def _collect_search_overrides(parsed: argparse.Namespace) -> Dict[str, object]:
    overrides: Dict[str, object] = {}
    for field_name in (
        "chunk_size_tokens",
        "chunk_overlap_tokens",
        "min_chunk_tokens",
        "include_preamble",
        "max_heading_level",
        "bm25_k1",
        "bm25_b",
        "vector_model_name",
        "vector_batch_size",
        "vector_device",
        "vector_normalize_embeddings",
        "hybrid_keyword_weight",
        "hybrid_vector_weight",
        "default_mode",
        "grep_context_before",
        "grep_context_after",
        "grep_regex",
    ):
        if hasattr(parsed, field_name):
            value = getattr(parsed, field_name)
            if value is not None:
                overrides[field_name] = value
    return overrides


def _parse_search_mode(mode_value: str | None, options: SearchOptions) -> SearchMode:
    mapping = {
        "grep": SearchMode.GREP,
        "keyword": SearchMode.KEYWORD,
        "bm25": SearchMode.KEYWORD,
        "vector": SearchMode.VECTOR,
        "hybrid": SearchMode.HYBRID,
    }
    selected = mode_value or options.default_mode
    normalized = selected.strip().lower()
    if normalized not in mapping:
        raise argparse.ArgumentTypeError(f"Unknown search mode: {selected}")
    return mapping[normalized]


def _create_search_documents(items: List[CLIInputItem]) -> list[SearchDocumentInput]:
    documents: list[SearchDocumentInput] = []
    for index, item in enumerate(items, start=1):
        metadata = {
            "display_name": item.display_name,
            "input_index": index,
        }
        metadata.update(item.metadata)
        if item.path_hint:
            metadata["path_hint"] = item.path_hint.as_posix()

        # SearchDocumentInput expects str | Path | bytes
        source_input: str | Path | bytes
        if isinstance(item.raw_input, bytes):
            # Use bytes directly for stdin input
            source_input = item.raw_input
        else:
            source_input = item.raw_input

        documents.append(
            SearchDocumentInput(
                source=source_input,
                document_id=item.stem,
                source_format="auto",
                metadata=metadata,
            )
        )
    return documents


def _result_to_dict(result: SearchResult) -> Dict[str, object]:
    return {
        "score": result.score,
        "chunk_id": result.chunk.chunk_id,
        "text": result.chunk.text,
        "chunk_metadata": dict(result.chunk.metadata),
        "result_metadata": dict(result.metadata),
    }
