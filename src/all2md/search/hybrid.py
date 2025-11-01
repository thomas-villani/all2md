"""Utilities for combining multiple search backends."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .types import SearchResult


def blend_results(
    keyword_results: Iterable[SearchResult],
    vector_results: Iterable[SearchResult],
    *,
    keyword_weight: float = 0.5,
    vector_weight: float = 0.5,
    top_k: int = 10,
) -> list[SearchResult]:
    """Blend keyword and vector results using weighted score aggregation."""
    combined_scores: dict[str, dict[str, float]] = defaultdict(lambda: {"keyword": 0.0, "vector": 0.0})
    chunk_lookup: dict[str, SearchResult] = {}

    for result in keyword_results:
        combined_scores[result.chunk.chunk_id]["keyword"] = result.score
        chunk_lookup[result.chunk.chunk_id] = result

    for result in vector_results:
        combined_scores[result.chunk.chunk_id]["vector"] = result.score
        chunk_lookup[result.chunk.chunk_id] = result

    blended: list[SearchResult] = []
    for chunk_id, score_components in combined_scores.items():
        keyword_score = score_components.get("keyword", 0.0)
        vector_score = score_components.get("vector", 0.0)
        total_score = keyword_weight * keyword_score + vector_weight * vector_score
        base_result = chunk_lookup[chunk_id]
        blended.append(
            SearchResult(
                chunk=base_result.chunk,
                score=total_score,
                metadata={
                    **base_result.metadata,
                    "combined": True,
                    "keyword_score": keyword_score,
                    "vector_score": vector_score,
                    "keyword_weight": keyword_weight,
                    "vector_weight": vector_weight,
                },
            )
        )

    blended.sort(key=lambda result: result.score, reverse=True)
    return blended[:top_k]
