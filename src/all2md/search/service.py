"""High-level orchestration for indexing and querying documents."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence, cast

from all2md.api import to_ast
from all2md.ast.nodes import Document
from all2md.ast.sections import get_all_sections, get_preamble
from all2md.ast.utils import extract_text
from all2md.constants import DocumentFormat
from all2md.options.search import SearchOptions
from all2md.progress import ProgressCallback, ProgressEvent
from all2md.search.bm25 import BM25Index, KeywordIndexConfig
from all2md.search.chunking import ChunkingContext, chunk_document
from all2md.search.hybrid import blend_results
from all2md.search.types import Chunk, SearchMode, SearchQuery, SearchResult
from all2md.search.vector import VectorIndex, VectorIndexConfig


@dataclass(frozen=True)
class SearchDocumentInput:
    """Represents a document scheduled for indexing."""

    source: str | Path | bytes
    document_id: str | None = None
    source_format: DocumentFormat | str | None = "auto"
    metadata: Mapping[str, object] | None = None


@dataclass
class SearchIndexState:
    """Container for the active index backends."""

    chunks: list[Chunk]
    documents: list[tuple[Document, SearchDocumentInput]] | None = None
    keyword_index: BM25Index | None = None
    vector_index: VectorIndex | None = None

    def available_modes(self) -> set[SearchMode]:
        """Get available modes of search."""
        modes: set[SearchMode] = set()
        if self.chunks:
            modes.add(SearchMode.GREP)
        if self.keyword_index:
            modes.add(SearchMode.KEYWORD)
        if self.vector_index:
            modes.add(SearchMode.VECTOR)
        if self.keyword_index and self.vector_index:
            modes.add(SearchMode.HYBRID)
        return modes

    @property
    def chunk_count(self) -> int:
        """Return number of cached chunks."""
        return len(self.chunks)


class SearchService:
    """Service object coordinating indexing and search execution."""

    def __init__(self, options: SearchOptions | None = None) -> None:
        """Initialise the service with optional search configuration overrides."""
        self.options = options or SearchOptions()
        self._state = SearchIndexState(chunks=[])

    @property
    def state(self) -> SearchIndexState:
        """Return the current in-memory search index state."""
        return self._state

    def build_indexes(
        self,
        documents: Sequence[SearchDocumentInput],
        *,
        modes: Iterable[SearchMode] | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> SearchIndexState:
        """Convert sources into chunks and materialise requested indexes."""
        requested_modes = set(modes or {self._default_mode()})
        if SearchMode.HYBRID in requested_modes:
            requested_modes.update({SearchMode.KEYWORD, SearchMode.VECTOR})

        if progress_callback:
            progress_callback(
                ProgressEvent(
                    event_type="started",
                    message="Indexing documents",
                    current=0,
                    total=len(documents),
                    metadata={"item_type": "indexing"},
                )
            )

        all_chunks: list[Chunk] = []
        parsed_documents: list[tuple[Document, SearchDocumentInput]] = []
        for idx, doc_input in enumerate(documents, start=1):
            document_id = doc_input.document_id or _derive_document_id(doc_input.source)
            document_path = Path(doc_input.source) if isinstance(doc_input.source, (str, Path)) else None
            source_fmt: DocumentFormat = cast(DocumentFormat, doc_input.source_format or "auto")
            ast_doc = to_ast(
                doc_input.source,
                source_format=source_fmt,
                progress_callback=progress_callback,
            )
            parsed_documents.append((ast_doc, doc_input))

            context_metadata: MutableMapping[str, object] = {"document_index": idx}
            if doc_input.metadata:
                context_metadata.update(doc_input.metadata)
            if doc_input.source_format and doc_input.source_format != "auto":
                context_metadata["source_format"] = str(doc_input.source_format)

            chunk_context = ChunkingContext(
                document_id=document_id,
                document_path=document_path,
                metadata=context_metadata,
            )
            chunks = chunk_document(
                ast_doc,
                context=chunk_context,
                chunk_size_tokens=self.options.chunk_size_tokens,
                chunk_overlap_tokens=self.options.chunk_overlap_tokens,
                min_chunk_tokens=self.options.min_chunk_tokens,
                include_preamble=self.options.include_preamble,
                heading_merge=self.options.heading_merge,
                max_heading_level=self.options.max_heading_level,
                progress_callback=progress_callback,
            )
            all_chunks.extend(chunks)
            if progress_callback:
                progress_callback(
                    ProgressEvent(
                        event_type="item_done",
                        message=f"Indexed document {document_id}",
                        current=idx,
                        total=len(documents),
                        metadata={"item_type": "document", "chunks": len(chunks)},
                    )
                )

        keyword_index: BM25Index | None = None
        vector_index: VectorIndex | None = None

        if SearchMode.KEYWORD in requested_modes and all_chunks:
            keyword_index = BM25Index(
                config=KeywordIndexConfig(k1=self.options.bm25_k1, b=self.options.bm25_b),
                options_snapshot=_options_snapshot(self.options),
            )
            keyword_index.add_chunks(all_chunks, progress_callback=progress_callback)

        if SearchMode.VECTOR in requested_modes and all_chunks:
            vector_index = VectorIndex(
                config=VectorIndexConfig(
                    model_name=self.options.vector_model_name,
                    batch_size=self.options.vector_batch_size,
                    device=self.options.vector_device,
                    normalize_embeddings=self.options.vector_normalize_embeddings,
                ),
                options_snapshot=_options_snapshot(self.options),
            )
            vector_index.add_chunks(all_chunks, progress_callback=progress_callback)

        self._state = SearchIndexState(
            chunks=all_chunks, documents=parsed_documents, keyword_index=keyword_index, vector_index=vector_index
        )

        if progress_callback:
            progress_callback(
                ProgressEvent(
                    event_type="finished",
                    message="Indexing completed",
                    current=len(documents),
                    total=len(documents),
                    metadata={"chunks": len(all_chunks)},
                )
            )

        return self._state

    def save(self, directory: Path) -> None:
        """Persist all active indexes to disk."""
        directory.mkdir(parents=True, exist_ok=True)
        chunk_path = directory / "chunks.jsonl"
        _write_chunks(chunk_path, self._state.chunks)

        if self._state.keyword_index:
            self._state.keyword_index.save(directory / "keyword")
        if self._state.vector_index:
            self._state.vector_index.save(directory / "vector")

    @classmethod
    def load(cls, directory: Path, options: SearchOptions | None = None) -> "SearchService":
        """Rehydrate indexes from disk."""
        service = cls(options=options)
        chunks: list[Chunk] = []
        keyword_index: BM25Index | None = None
        vector_index: VectorIndex | None = None

        chunk_file = directory / "chunks.jsonl"
        if chunk_file.exists():
            chunks = _read_chunks(chunk_file)

        keyword_dir = directory / "keyword"
        if keyword_dir.exists():
            keyword_index = BM25Index.load(keyword_dir)
            if not chunks:
                chunks = list(keyword_index.iter_chunks())

        vector_dir = directory / "vector"
        if vector_dir.exists():
            vector_index = VectorIndex.load(vector_dir)
            if not chunks:
                chunks = list(vector_index.iter_chunks())

        service._state = SearchIndexState(chunks=chunks, keyword_index=keyword_index, vector_index=vector_index)
        return service

    def search(
        self,
        query: str,
        *,
        mode: SearchMode | str | None = None,
        top_k: int = 10,
        progress_callback: ProgressCallback | None = None,
    ) -> list[SearchResult]:
        """Execute a query using the configured index backends."""
        resolved_mode = self._resolve_mode(mode)
        if progress_callback:
            progress_callback(
                ProgressEvent(
                    event_type="started",
                    message=f"Searching ({resolved_mode.name.lower()})",
                    current=0,
                    total=1,
                    metadata={"item_type": "search"},
                )
            )

        results: list[SearchResult]
        if resolved_mode is SearchMode.GREP:
            results = self._grep_search(
                query,
                top_k=top_k,
                context_before=self.options.grep_context_before,
                context_after=self.options.grep_context_after,
                regex=self.options.grep_regex,
            )
        elif resolved_mode is SearchMode.KEYWORD:
            if not self._state.keyword_index:
                raise RuntimeError("Keyword index not available. Build indexes with keyword mode first.")
            results = self._keyword_search(query, top_k=top_k)
        elif resolved_mode is SearchMode.VECTOR:
            if not self._state.vector_index:
                raise RuntimeError("Vector index not available. Build indexes with vector mode first.")
            results = self._state.vector_index.search(SearchQuery(raw_text=query), top_k=top_k)
        else:
            if not (self._state.keyword_index and self._state.vector_index):
                raise RuntimeError("Hybrid search requires both keyword and vector indexes.")
            keyword_results = self._state.keyword_index.search(SearchQuery(raw_text=query), top_k=top_k)
            vector_results = self._state.vector_index.search(SearchQuery(raw_text=query), top_k=top_k)
            kw_weight, vec_weight = _normalized_weights(
                self.options.hybrid_keyword_weight, self.options.hybrid_vector_weight
            )
            results = blend_results(
                keyword_results,
                vector_results,
                keyword_weight=kw_weight,
                vector_weight=vec_weight,
                top_k=top_k,
            )

        if progress_callback:
            progress_callback(
                ProgressEvent(
                    event_type="finished",
                    message="Search completed",
                    current=len(results),
                    total=len(results),
                    metadata={"results": len(results)},
                )
            )

        return results

    def _grep_search(
        self,
        query: str,
        *,
        top_k: int,
        context_before: int,
        context_after: int,
        regex: bool,
    ) -> list[SearchResult]:
        # Use AST-based grep if documents are available (preferred)
        if self._state.documents:
            return _grep_ast_documents(
                self._state.documents,
                query,
                regex=regex,
                context_before=context_before,
                context_after=context_after,
                ignore_case=self.options.grep_ignore_case,
                show_line_numbers=self.options.grep_show_line_numbers,
                max_columns=self.options.grep_max_columns,
            )
        # Fallback to chunk-based grep for backward compatibility
        return _match_lines(
            self._state.chunks,
            query,
            backend="grep",
            top_k=top_k,
            context_before=context_before,
            context_after=context_after,
            regex=regex,
        )

    def _keyword_search(self, query: str, *, top_k: int) -> list[SearchResult]:
        assert self._state.keyword_index is not None
        base_results = self._state.keyword_index.search(SearchQuery(raw_text=query), top_k=top_k)
        if not base_results:
            return []

        merged: list[SearchResult] = []
        for result in base_results:
            snippets = _build_snippets(result.chunk.text, query, max_fragments=3)
            if not snippets:
                continue
            chunk = Chunk(chunk_id=result.chunk.chunk_id, text=" … ".join(snippets), metadata=result.chunk.metadata)
            metadata = {**result.metadata, "backend": "keyword", "occurrences": len(snippets)}
            merged.append(SearchResult(chunk=chunk, score=result.score, metadata=metadata))
            if len(merged) >= top_k:
                break
        return merged

    def _resolve_mode(self, mode: SearchMode | str | None) -> SearchMode:
        if mode is None:
            return self._default_mode()
        if isinstance(mode, SearchMode):
            return mode
        normalized = mode.strip().lower()
        mapping = {
            "grep": SearchMode.GREP,
            "keyword": SearchMode.KEYWORD,
            "bm25": SearchMode.KEYWORD,
            "vector": SearchMode.VECTOR,
            "faiss": SearchMode.VECTOR,
            "hybrid": SearchMode.HYBRID,
        }
        if normalized not in mapping:
            raise ValueError(f"Unknown search mode: {mode}")
        return mapping[normalized]

    def _default_mode(self) -> SearchMode:
        return self._resolve_mode(self.options.default_mode)


def _derive_document_id(source: str | Path | bytes) -> str:
    if isinstance(source, bytes):  # Ends up bytes if stdin, no filename
        return "stdin"
    path = Path(source)
    return path.stem if path.name else str(path)


def _normalized_weights(keyword_weight: float, vector_weight: float) -> tuple[float, float]:
    total = keyword_weight + vector_weight
    if total <= 0:
        return (0.5, 0.5)
    return (keyword_weight / total, vector_weight / total)


def _options_snapshot(options: SearchOptions) -> Mapping[str, object]:
    return asdict(options)


def _match_slices(
    chunks: Sequence[Chunk],
    query: str,
    *,
    backend: str,
    top_k: int,
) -> list[SearchResult]:
    matches: list[SearchResult] = []

    for chunk in chunks:
        fragments = _build_snippets(chunk.text, query, max_fragments=max(1, top_k))
        if not fragments:
            continue

        snippet_text = " … ".join(fragments)
        matches.append(
            SearchResult(
                chunk=Chunk(chunk_id=chunk.chunk_id, text=snippet_text, metadata=chunk.metadata),
                score=float(len(fragments)),
                metadata={"backend": backend, "occurrences": len(fragments)},
            )
        )

    matches.sort(key=lambda result: result.score, reverse=True)
    return matches[:top_k]


def _build_snippets(text: str, query: str, *, max_fragments: int, fallback: bool = True) -> list[str]:
    lowered_text = text.lower()
    lowered_query = query.lower()
    fragments: list[str] = []
    cursor = 0
    query_len = len(query)

    while len(fragments) < max_fragments:
        idx = lowered_text.find(lowered_query, cursor)
        if idx == -1:
            break
        snippet = _highlight_fragment(text, idx, idx + query_len)
        fragments.append(snippet)
        cursor = idx + query_len

    if fragments or not fallback:
        return fragments

    tokens = [token for token in query.split() if len(token.strip()) > 2]
    for token in tokens:
        token_matches = _build_snippets(text, token.strip(), max_fragments=max_fragments, fallback=False)
        if token_matches:
            return token_matches

    return fragments


def _highlight_fragment(text: str, start: int, end: int, *, radius: int = 80) -> str:
    begin = max(0, start - radius)
    finish = min(len(text), end + radius)
    prefix = "…" if begin > 0 else ""
    suffix = "…" if finish < len(text) else ""
    highlighted = f"<<{text[start:end]}>>"
    fragment = text[begin:start] + highlighted + text[end:finish]
    return prefix + fragment + suffix


def _truncate_to_match(
    line: str, spans: list[tuple[int, int]], context: int = 40, max_length: int = 0
) -> tuple[str, list[tuple[int, int]]]:
    """Truncate a long line to show context around matches.

    Parameters
    ----------
    line : str
        The full line text
    spans : list[tuple[int, int]]
        List of (start, end) positions of matches in the line
    context : int
        Number of characters to show before/after matches
    max_length : int
        Maximum output length (0 = unlimited). If the natural truncation
        exceeds this, only show context around the first match.

    Returns
    -------
    tuple[str, list[tuple[int, int]]]
        Truncated line with ellipsis and adjusted span positions

    """
    if not spans:
        max_len = max_length if max_length > 0 else 197
        return line[:max_len] + "...", []

    # Find the span of all matches
    first_match_start = min(s[0] for s in spans)
    first_match_end = spans[0][1]  # End of first match
    last_match_end = max(s[1] for s in spans)

    # Calculate natural window (all matches)
    start = max(0, first_match_start - context)
    end = min(len(line), last_match_end + context)

    # Account for ellipsis in length calculation
    ellipsis_len = 3 if start > 0 else 0
    ellipsis_len += 3 if end < len(line) else 0
    natural_length = (end - start) + ellipsis_len

    # If output would exceed max_length, only show first match
    if max_length > 0 and natural_length > max_length:
        # Show context only around first match
        start = max(0, first_match_start - context)
        end = min(len(line), first_match_end + context)

        # If still too long, reduce context symmetrically
        if (end - start) + ellipsis_len > max_length:
            available = max_length - ellipsis_len - (first_match_end - first_match_start)
            half_context = available // 2
            start = max(0, first_match_start - half_context)
            end = min(len(line), first_match_end + half_context)

        # Only include spans that fall within the truncated range
        adjusted_spans = []
        for s_start, s_end in spans:
            if s_start >= start and s_end <= end:
                offset = 3 if start > 0 else 0
                adjusted_spans.append((s_start - start + offset, s_end - start + offset))
    else:
        # Use natural window with all matches
        offset = 3 if start > 0 else 0
        adjusted_spans = [(s[0] - start + offset, s[1] - start + offset) for s in spans]

    # Build truncated string
    result = ""
    if start > 0:
        result += "..."
    result += line[start:end]
    if end < len(line):
        result += "..."

    return result, adjusted_spans


def _grep_ast_documents(
    documents: Sequence[tuple[Document, SearchDocumentInput]],
    query: str,
    *,
    regex: bool,
    context_before: int = 0,
    context_after: int = 0,
    ignore_case: bool = False,
    show_line_numbers: bool = False,
    max_columns: int = 0,
) -> list[SearchResult]:
    """Search directly through AST documents for grep-style matching.

    This function bypasses chunking and searches the AST structure directly,
    providing clean section-based results.

    Parameters
    ----------
    documents : Sequence[tuple[Document, SearchDocumentInput]]
        Documents and their metadata to search
    query : str
        Search query text or regex pattern
    regex : bool
        Whether to interpret query as regex
    context_before : int, default = 0
        Lines of context before matches
    context_after : int, default = 0
        Lines of context after matches
    ignore_case : bool, default = False
        Whether to perform case-insensitive matching
    show_line_numbers : bool, default = False
        Whether to show line numbers for matching lines
    max_columns : int, default = 0
        Maximum display width for long lines (0 = unlimited)

    Returns
    -------
    list[SearchResult]
        Search results with section-based grouping

    """
    matches: list[SearchResult] = []
    pattern = re.compile(query, re.IGNORECASE if ignore_case else 0) if regex else None
    lowered_query = query.lower() if ignore_case else query

    for doc, doc_input in documents:
        document_path = doc_input.source.as_posix() if isinstance(doc_input.source, Path) else str(doc_input.source)
        document_id = doc_input.document_id or document_path

        # Process preamble (content before first heading)
        preamble_nodes = get_preamble(doc)
        if preamble_nodes:
            preamble_text = extract_text(preamble_nodes)
            section_matches = _search_text_block(
                text=preamble_text,
                query=query,
                lowered_query=lowered_query,
                pattern=pattern,
                section_heading=None,
                document_path=document_path,
                document_id=document_id,
                context_before=context_before,
                context_after=context_after,
                ignore_case=ignore_case,
                show_line_numbers=show_line_numbers,
                max_columns=max_columns,
            )
            matches.extend(section_matches)

        # Process each section
        sections = get_all_sections(doc)
        for section in sections:
            heading_text = section.get_heading_text()
            body_text = extract_text(list(section.content))

            section_matches = _search_text_block(
                text=body_text,
                query=query,
                lowered_query=lowered_query,
                pattern=pattern,
                section_heading=heading_text,
                document_path=document_path,
                document_id=document_id,
                context_before=context_before,
                context_after=context_after,
                ignore_case=ignore_case,
                show_line_numbers=show_line_numbers,
                max_columns=max_columns,
            )
            matches.extend(section_matches)

    return matches


def _search_text_block(
    text: str,
    query: str,
    lowered_query: str,
    pattern: re.Pattern[str] | None,
    section_heading: str | None,
    document_path: str,
    document_id: str,
    context_before: int,
    context_after: int,
    ignore_case: bool,
    show_line_numbers: bool,
    max_columns: int,
) -> list[SearchResult]:
    """Search a text block and return matches with context.

    Parameters
    ----------
    text : str
        Text to search
    query : str
        Search query
    lowered_query : str
        Lowercase version of query for case-insensitive search
    pattern : re.Pattern or None
        Compiled regex pattern if regex mode is enabled
    section_heading : str or None
        Section heading for context
    document_path : str
        Path to document
    document_id : str
        Document identifier
    context_before : int
        Lines of context before matches
    context_after : int
        Lines of context after matches
    ignore_case : bool
        Whether to perform case-insensitive matching
    show_line_numbers : bool
        Whether to show line numbers for matching lines
    max_columns : int
        Maximum display width for long lines (0 = unlimited)

    Returns
    -------
    list[SearchResult]
        Matches found in this text block

    """
    lines = text.splitlines()
    if not lines:
        return []

    # Find all matching lines
    line_spans: dict[int, list[tuple[int, int]]] = {}
    for idx, line in enumerate(lines):
        spans = _find_spans(line, query, lowered_query, pattern, ignore_case)
        if spans:
            line_spans[idx] = spans

    if not line_spans:
        return []

    # Build result with context
    matched_indices = sorted(line_spans.keys())
    fragment_lines: list[str] = []
    included: set[int] = set()

    for idx in matched_indices:
        start = max(0, idx - context_before)
        end = min(len(lines), idx + context_after + 1)
        for line_idx in range(start, end):
            if line_idx in included:
                continue
            is_match = line_idx in line_spans
            line_text = lines[line_idx]
            line_spans_to_use = line_spans.get(line_idx) if is_match else None

            # Truncate long lines
            truncate_threshold = max_columns if max_columns > 0 else 200
            if len(line_text) > truncate_threshold and is_match:
                line_text, line_spans_to_use = _truncate_to_match(
                    line_text, line_spans[line_idx], max_length=max_columns
                )
            elif len(line_text) > truncate_threshold:
                max_len = max_columns if max_columns > 0 else 197
                line_text = line_text[:max_len] + "..."

            highlighted = _highlight_line(line_text, line_spans_to_use)

            # Add line numbers if requested
            if show_line_numbers:
                highlighted = f"{line_idx + 1}: {highlighted}"

            fragment_lines.append(highlighted)
            included.add(line_idx)

    snippet = "\n".join(fragment_lines)

    # Create chunk metadata for compatibility
    chunk_metadata = {
        "document_id": document_id,
        "document_path": document_path,
        "section_heading": section_heading,
    }

    # Create a pseudo-chunk for the result
    chunk_id = f"{document_id}::{section_heading or 'preamble'}"
    chunk = Chunk(chunk_id=chunk_id, text=snippet, metadata=chunk_metadata)

    return [
        SearchResult(
            chunk=chunk,
            score=float(len(matched_indices)),
            metadata={
                "backend": "grep",
                "occurrences": len(matched_indices),
            },
        )
    ]


def _match_lines(
    chunks: Sequence[Chunk],
    query: str,
    *,
    backend: str,
    top_k: int,
    context_before: int,
    context_after: int,
    regex: bool,
) -> list[SearchResult]:
    matches: list[SearchResult] = []
    pattern = re.compile(query, re.IGNORECASE) if regex else None
    lowered_query = query.lower()

    for chunk in chunks:
        lines = chunk.text.splitlines()
        if not lines:
            continue

        line_spans: dict[int, list[tuple[int, int]]] = {}
        for idx, line in enumerate(lines):
            spans = _find_spans(line, query, lowered_query, pattern, ignore_case=True)
            if spans:
                line_spans[idx] = spans

        if not line_spans:
            continue

        # Get section info from chunk metadata for better context
        section_heading = chunk.metadata.get("section_heading")
        chunk_index = chunk.metadata.get("chunk_index", 0)

        matched_indices = sorted(line_spans.keys())
        fragment_lines: list[str] = []
        included: set[int] = set()
        for idx in matched_indices:
            start = max(0, idx - context_before)
            end = min(len(lines), idx + context_after + 1)
            for line_idx in range(start, end):
                if line_idx in included:
                    continue
                is_match = line_idx in line_spans
                line_text = lines[line_idx]
                line_spans_to_use = line_spans.get(line_idx) if is_match else None

                # Truncate long lines to show context around matches
                if len(line_text) > 200 and is_match:
                    line_text, line_spans_to_use = _truncate_to_match(line_text, line_spans[line_idx])
                elif len(line_text) > 200:
                    # For context lines, just truncate
                    line_text = line_text[:197] + "..."

                highlighted = _highlight_line(line_text, line_spans_to_use)

                # Format line number to show chunk context
                if section_heading:
                    line_num = f"{chunk_index}:{line_idx + 1}"
                else:
                    line_num = f"{line_idx + 1}"

                fragment_lines.append(f"{line_num}: {highlighted}")
                included.add(line_idx)

        snippet = "\n".join(fragment_lines)
        matches.append(
            SearchResult(
                chunk=Chunk(chunk_id=chunk.chunk_id, text=snippet, metadata=chunk.metadata),
                score=float(len(matched_indices)),
                metadata={
                    "backend": backend,
                    "occurrences": len(matched_indices),
                    "lines": [idx + 1 for idx in matched_indices],
                },
            )
        )

    matches.sort(key=lambda result: result.score, reverse=True)
    # For grep mode, return all matches; otherwise limit to top_k
    if backend == "grep":
        return matches
    return matches[:top_k]


def _find_spans(
    line: str,
    query: str,
    lowered_query: str,
    pattern: re.Pattern[str] | None,
    ignore_case: bool,
) -> list[tuple[int, int]]:
    if pattern is not None:
        spans: list[tuple[int, int]] = []
        for match in pattern.finditer(line):
            start, end = match.span()
            if start == end:
                continue
            spans.append((start, end))
        return spans

    # For non-regex searches, use case-sensitive or case-insensitive comparison
    search_line = line.lower() if ignore_case else line
    search_query = lowered_query if ignore_case else query
    text_spans: list[tuple[int, int]] = []
    cursor = 0
    qlen = len(query)
    if qlen == 0:
        return text_spans

    while True:
        idx = search_line.find(search_query, cursor)
        if idx == -1:
            break
        text_spans.append((idx, idx + qlen))
        cursor = idx + qlen
    return text_spans


def _highlight_line(line: str, spans: list[tuple[int, int]] | None) -> str:
    if not spans:
        return line

    result: list[str] = []
    cursor = 0
    for start, end in sorted(spans):
        result.append(line[cursor:start])
        result.append(f"<<{line[start:end]}>>")
        cursor = end
    result.append(line[cursor:])
    return "".join(result)


def _serialize_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            serialized[key] = value
        elif isinstance(value, Path):
            serialized[key] = str(value)
        else:
            serialized[key] = str(value)
    return serialized


def _write_chunks(path: Path, chunks: Sequence[Chunk]) -> None:
    if not chunks:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            payload = {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": _serialize_metadata(chunk.metadata),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _read_chunks(path: Path) -> list[Chunk]:
    results: list[Chunk] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            metadata = raw.get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            results.append(Chunk(chunk_id=raw["chunk_id"], text=raw["text"], metadata=metadata))
    return results
