"""Search subsystem exposed to the public API."""

from __future__ import annotations

from typing import Iterable, Sequence

from all2md.options.search import SearchOptions
from all2md.progress import ProgressCallback
from all2md.search.service import SearchDocumentInput, SearchService
from all2md.search.types import SearchMode, SearchResult


# TODO: These functions should have a way to pass the path to an existing index too.
def build_search_service(
    documents: Sequence[SearchDocumentInput],
    *,
    options: SearchOptions | None = None,
    modes: Iterable[SearchMode] | None = None,
    progress_callback: ProgressCallback | None = None,
) -> SearchService:
    """Create a search service pre-indexed with the supplied documents."""
    service = SearchService(options=options)
    service.build_indexes(documents, modes=modes, progress_callback=progress_callback)
    return service


def search_with_service(
    service: SearchService,
    query: str,
    *,
    mode: SearchMode | str | None = None,
    top_k: int = 10,
    progress_callback: ProgressCallback | None = None,
) -> list[SearchResult]:
    """Execute a search query using an existing ``SearchService``."""
    return service.search(query, mode=mode, top_k=top_k, progress_callback=progress_callback)


def search_documents(
    documents: Sequence[SearchDocumentInput],
    query: str,
    *,
    options: SearchOptions | None = None,
    modes: Iterable[SearchMode] | None = None,
    mode: SearchMode | str | None = None,
    top_k: int = 10,
    progress_callback: ProgressCallback | None = None,
) -> list[SearchResult]:
    """Index documents and run a query in a single convenience call."""
    service = build_search_service(
        documents,
        options=options,
        modes=modes,
        progress_callback=progress_callback,
    )
    return search_with_service(
        service,
        query,
        mode=mode,
        top_k=top_k,
        progress_callback=progress_callback,
    )
