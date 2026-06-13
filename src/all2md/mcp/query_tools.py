"""Read-only query tool implementations for the MCP server.

This module implements the search, diff, and outline tools. They are read-only
companions to the conversion tools in :mod:`all2md.mcp.tools` and reuse the
existing search, diff, and section subsystems rather than reimplementing them.

Functions
---------
- search_documents_impl: Implementation of search_documents tool
- diff_documents_impl: Implementation of diff_documents tool
- get_document_outline_impl: Implementation of get_document_outline tool

"""

#  Copyright (c) 2025 Tom Villani, Ph.D.

import logging
from pathlib import Path
from typing import cast

from all2md.api import to_ast
from all2md.ast.nodes import Document
from all2md.ast.sections import get_all_sections
from all2md.cli.commands.shared import collect_input_files
from all2md.constants import DocumentFormat
from all2md.diff.renderers import JsonDiffRenderer
from all2md.diff.text_diff import compare_documents
from all2md.exceptions import All2MdError, DependencyError
from all2md.mcp.config import MCPConfig
from all2md.mcp.schemas import (
    DiffDocumentsInput,
    DiffDocumentsOutput,
    GetDocumentOutlineInput,
    GetDocumentOutlineOutput,
    SearchDocumentsInput,
    SearchDocumentsOutput,
    SearchResultItem,
)
from all2md.mcp.security import MCPSecurityError, validate_read_path
from all2md.mcp.tools import _detect_source_type
from all2md.options.search import SearchOptions
from all2md.search.service import SearchDocumentInput, SearchService
from all2md.search.types import SearchMode as ServiceSearchMode

logger = logging.getLogger(__name__)

# Map the (restricted) MCP mode strings to the internal search enum.
_MODE_MAP: dict[str, ServiceSearchMode] = {
    "keyword": ServiceSearchMode.KEYWORD,
    "grep": ServiceSearchMode.GREP,
}


def _validate_index_dir(index_dir: str | Path, write_allowlist: list[str | Path] | None) -> Path:
    """Validate that a search index directory is within the write allowlist.

    Unlike :func:`validate_write_path`, the directory need not exist yet (it is
    created on first save), so existence is not required — only containment
    within an allowed write directory.

    Parameters
    ----------
    index_dir : str | Path
        Requested index directory.
    write_allowlist : list[str | Path] | None
        Allowed write directories (resolved Paths), or None to allow all.

    Returns
    -------
    Path
        The validated (absolute) index directory.

    Raises
    ------
    MCPSecurityError
        If the directory escapes the allowlist or uses parent traversal.

    """
    target = Path(index_dir)
    if ".." in target.parts:
        raise MCPSecurityError(f"Index directory contains parent references (..): {index_dir}", path=str(index_dir))

    # Resolve as much of the path as exists; fall back to absolute for new dirs.
    try:
        resolved = target.resolve()
    except (OSError, RuntimeError):
        resolved = target.absolute()

    if write_allowlist is None:
        return resolved

    for allowed_item in write_allowlist:
        try:
            allowed = Path(allowed_item).resolve() if isinstance(allowed_item, str) else allowed_item
            resolved.relative_to(allowed)
            return resolved
        except ValueError:
            continue
        except (OSError, RuntimeError):
            logger.warning(f"Invalid write allowlist directory: {allowed_item}")
            continue

    raise MCPSecurityError(f"Index directory not in write allowlist: {index_dir}", path=str(index_dir))


def _collect_search_documents(input_data: SearchDocumentsInput, config: MCPConfig) -> list[SearchDocumentInput]:
    """Resolve input paths to a validated list of documents to search."""
    paths = input_data.paths
    if not paths:
        if config.read_allowlist:
            paths = [str(p) for p in config.read_allowlist]
        else:
            raise ValueError("No search paths provided and no read allowlist is configured.")

    items = collect_input_files(paths, recursive=input_data.recursive)

    documents: list[SearchDocumentInput] = []
    for item in items:
        best = item.best_path()
        if best is None:
            # search operates on local files only (no stdin/remote in this slice)
            continue
        validated = validate_read_path(best, config.read_allowlist)
        documents.append(SearchDocumentInput(source=validated))

    if not documents:
        raise ValueError("No readable documents found for the given paths.")
    return documents


def search_documents_impl(input_data: SearchDocumentsInput, config: MCPConfig) -> SearchDocumentsOutput:
    """Implement the search_documents tool (grep + keyword modes).

    Parameters
    ----------
    input_data : SearchDocumentsInput
        Tool input parameters.
    config : MCPConfig
        Server configuration (allowlists, optional persistent index dir).

    Returns
    -------
    SearchDocumentsOutput
        Ranked search results.

    Raises
    ------
    MCPSecurityError
        If a path fails allowlist validation.
    All2MdError
        If the search backend is unavailable or fails.

    """
    mode = input_data.mode
    if mode not in _MODE_MAP:
        raise ValueError(f"Unsupported search mode: {mode!r}. Supported modes: keyword, grep.")
    service_mode = _MODE_MAP[mode]

    documents = _collect_search_documents(input_data, config)

    options = SearchOptions(
        default_mode=mode,
        grep_regex=input_data.regex,
        grep_ignore_case=input_data.ignore_case,
    )

    # Keyword mode can reuse a persisted index; grep needs the in-memory parsed
    # documents (AST), so it always builds fresh and is never persisted.
    persist_dir: Path | None = None
    if config.search_index_dir and service_mode is ServiceSearchMode.KEYWORD:
        persist_dir = _validate_index_dir(config.search_index_dir, config.write_allowlist)

    try:
        if persist_dir is not None and (persist_dir / "keyword").exists():
            logger.info(f"Loading persisted keyword index from: {persist_dir}")
            service = SearchService.load(persist_dir, options=options)
        else:
            service = SearchService(options=options)
            service.build_indexes(documents, modes={service_mode})
            if persist_dir is not None:
                logger.info(f"Persisting keyword index to: {persist_dir}")
                service.save(persist_dir)

        results = service.search(input_data.query, mode=service_mode, top_k=input_data.top_k)
    except DependencyError as e:
        # Surface the optional-dependency requirement (e.g. rank-bm25) cleanly.
        raise All2MdError(
            f"Search mode '{mode}' is unavailable: {e}. Install with: pip install 'all2md[search]'."
        ) from e
    except All2MdError:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise All2MdError(f"Search failed: {e}") from e

    # Rank by score and trim (grep returns section matches in document order).
    results = sorted(results, key=lambda r: r.score, reverse=True)[: input_data.top_k]

    items = [
        SearchResultItem(
            snippet=r.chunk.text,
            score=r.score,
            document_path=_as_str(r.chunk.metadata.get("document_path")),
            section_heading=_as_str(r.chunk.metadata.get("section_heading")),
            chunk_id=r.chunk.chunk_id,
        )
        for r in results
    ]

    logger.info(f"Search ({mode}) returned {len(items)} results")
    return SearchDocumentsOutput(results=items, mode=mode, total=len(items))


def diff_documents_impl(input_data: DiffDocumentsInput, config: MCPConfig) -> DiffDocumentsOutput:
    """Implement the diff_documents tool (unified + json output).

    Parameters
    ----------
    input_data : DiffDocumentsInput
        Tool input parameters.
    config : MCPConfig
        Server configuration (allowlists).

    Returns
    -------
    DiffDocumentsOutput
        Rendered diff and a change flag.

    Raises
    ------
    MCPSecurityError
        If a path source fails allowlist validation.
    All2MdError
        If conversion or diffing fails.

    """
    try:
        old_source, old_kind = _detect_source_type(input_data.old, config)
        new_source, new_kind = _detect_source_type(input_data.new, config)

        old_label = input_data.old if old_kind == "path" else "old"
        new_label = input_data.new if new_kind == "path" else "new"

        old_doc = to_ast(old_source)
        new_doc = to_ast(new_source)
        if not isinstance(old_doc, Document) or not isinstance(new_doc, Document):
            raise TypeError("Expected Document from to_ast for diff inputs")

        diff_result = compare_documents(
            old_doc,
            new_doc,
            old_label=old_label,
            new_label=new_label,
            context_lines=input_data.context_lines,
            ignore_whitespace=input_data.ignore_whitespace,
            granularity=input_data.granularity,
        )

        has_changes = any(op.tag != "equal" for op in diff_result.iter_operations())

        if input_data.format == "json":
            rendered = JsonDiffRenderer().render(diff_result)
        else:
            rendered = "\n".join(diff_result.iter_unified_diff())

        logger.info(f"Diff complete (changes={has_changes}, format={input_data.format})")
        return DiffDocumentsOutput(diff=rendered, has_changes=has_changes)

    except All2MdError:
        raise
    except Exception as e:
        logger.error(f"Diff failed: {e}")
        raise All2MdError(f"Diff failed: {e}") from e


def get_document_outline_impl(input_data: GetDocumentOutlineInput, config: MCPConfig) -> GetDocumentOutlineOutput:
    """Implement the get_document_outline tool.

    Parameters
    ----------
    input_data : GetDocumentOutlineInput
        Tool input parameters.
    config : MCPConfig
        Server configuration (allowlists).

    Returns
    -------
    GetDocumentOutlineOutput
        Ordered heading list (index/level/heading).

    Raises
    ------
    MCPSecurityError
        If a path source fails allowlist validation.
    All2MdError
        If conversion fails.

    """
    if not (1 <= input_data.max_level <= 6):
        raise ValueError(f"max_level must be between 1 and 6, got {input_data.max_level}")

    try:
        source, _kind = _detect_source_type(input_data.doc, config)
        doc = to_ast(source, source_format=cast(DocumentFormat, input_data.format_hint or "auto"))
        if not isinstance(doc, Document):
            raise TypeError(f"Expected Document from to_ast, got {type(doc)}")

        sections = get_all_sections(doc, max_level=input_data.max_level)
        outline = [
            {"index": idx, "level": section.level, "heading": section.get_heading_text()}
            for idx, section in enumerate(sections)
        ]

        logger.info(f"Outline extracted: {len(outline)} headings")
        return GetDocumentOutlineOutput(sections=outline, total=len(outline))

    except All2MdError:
        raise
    except Exception as e:
        logger.error(f"Outline extraction failed: {e}")
        raise All2MdError(f"Outline extraction failed: {e}") from e


def _as_str(value: object) -> str | None:
    """Coerce optional metadata values to str (or None)."""
    if value is None:
        return None
    return str(value)
