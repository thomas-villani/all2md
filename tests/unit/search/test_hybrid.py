#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for search/hybrid.py blend_results function."""

import pytest

from all2md.search.hybrid import blend_results
from all2md.search.types import Chunk, SearchResult


class TestBlendResults:
    """Tests for the blend_results function."""

    def _make_chunk(self, chunk_id: str, text: str = "test text") -> Chunk:
        """Create a test chunk with given ID."""
        return Chunk(chunk_id=chunk_id, text=text, metadata={"test": True})

    def _make_result(self, chunk_id: str, score: float, text: str = "test text") -> SearchResult:
        """Create a test search result with given ID and score."""
        chunk = self._make_chunk(chunk_id, text)
        return SearchResult(chunk=chunk, score=score, metadata={"source": "test"})

    def test_blend_empty_inputs(self):
        """Test blending with empty inputs."""
        result = blend_results([], [], top_k=5)
        assert result == []

    def test_blend_keyword_only(self):
        """Test blending with only keyword results."""
        keyword_results = [
            self._make_result("chunk-1", 0.9),
            self._make_result("chunk-2", 0.7),
        ]

        result = blend_results(keyword_results, [], keyword_weight=0.5, vector_weight=0.5, top_k=10)

        assert len(result) == 2
        # Scores should be half of original (keyword_weight * score + vector_weight * 0)
        assert result[0].score == pytest.approx(0.45)  # 0.5 * 0.9
        assert result[1].score == pytest.approx(0.35)  # 0.5 * 0.7

    def test_blend_vector_only(self):
        """Test blending with only vector results."""
        vector_results = [
            self._make_result("chunk-1", 0.8),
            self._make_result("chunk-2", 0.6),
        ]

        result = blend_results([], vector_results, keyword_weight=0.5, vector_weight=0.5, top_k=10)

        assert len(result) == 2
        # Scores should be half of original (keyword_weight * 0 + vector_weight * score)
        assert result[0].score == pytest.approx(0.4)  # 0.5 * 0.8
        assert result[1].score == pytest.approx(0.3)  # 0.5 * 0.6

    def test_blend_overlapping_results(self):
        """Test blending when same chunk appears in both result sets."""
        keyword_results = [
            self._make_result("chunk-1", 0.8),
            self._make_result("chunk-2", 0.6),
        ]
        vector_results = [
            self._make_result("chunk-1", 0.7),  # Same chunk as keyword
            self._make_result("chunk-3", 0.9),
        ]

        result = blend_results(keyword_results, vector_results, keyword_weight=0.5, vector_weight=0.5, top_k=10)

        assert len(result) == 3
        # Find chunk-1 and verify combined score
        chunk_1_result = next(r for r in result if r.chunk.chunk_id == "chunk-1")
        assert chunk_1_result.score == pytest.approx(0.75)  # 0.5 * 0.8 + 0.5 * 0.7

    def test_blend_with_weights(self):
        """Test blending with different weights."""
        keyword_results = [self._make_result("chunk-1", 1.0)]
        vector_results = [self._make_result("chunk-1", 1.0)]

        result = blend_results(keyword_results, vector_results, keyword_weight=0.7, vector_weight=0.3, top_k=10)

        assert len(result) == 1
        # Score should be 0.7 * 1.0 + 0.3 * 1.0 = 1.0
        assert result[0].score == pytest.approx(1.0)

    def test_blend_sorts_by_score_descending(self):
        """Test that results are sorted by score in descending order."""
        keyword_results = [
            self._make_result("chunk-low", 0.2),
            self._make_result("chunk-mid", 0.5),
        ]
        vector_results = [
            self._make_result("chunk-high", 0.9),
        ]

        result = blend_results(keyword_results, vector_results, keyword_weight=1.0, vector_weight=1.0, top_k=10)

        scores = [r.score for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_blend_respects_top_k(self):
        """Test that top_k limits the number of results."""
        keyword_results = [self._make_result(f"chunk-{i}", 0.9 - i * 0.1) for i in range(5)]
        vector_results = [self._make_result(f"chunk-{i+5}", 0.85 - i * 0.1) for i in range(5)]

        result = blend_results(keyword_results, vector_results, top_k=3)

        assert len(result) == 3

    def test_blend_metadata_includes_component_scores(self):
        """Test that blended results include component scores in metadata."""
        keyword_results = [self._make_result("chunk-1", 0.8)]
        vector_results = [self._make_result("chunk-1", 0.6)]

        result = blend_results(keyword_results, vector_results, keyword_weight=0.5, vector_weight=0.5, top_k=10)

        assert len(result) == 1
        metadata = result[0].metadata
        assert metadata["combined"] is True
        assert metadata["keyword_score"] == pytest.approx(0.8)
        assert metadata["vector_score"] == pytest.approx(0.6)
        assert metadata["keyword_weight"] == pytest.approx(0.5)
        assert metadata["vector_weight"] == pytest.approx(0.5)

    def test_blend_preserves_chunk_data(self):
        """Test that blending preserves the original chunk data."""
        chunk = Chunk(chunk_id="test-chunk", text="Test content here", metadata={"page": 1})
        keyword_results = [SearchResult(chunk=chunk, score=0.9, metadata={"backend": "bm25"})]

        result = blend_results(keyword_results, [], keyword_weight=1.0, vector_weight=0.0, top_k=10)

        assert len(result) == 1
        assert result[0].chunk.chunk_id == "test-chunk"
        assert result[0].chunk.text == "Test content here"
        assert result[0].chunk.metadata["page"] == 1

    def test_blend_with_zero_weights(self):
        """Test blending with zero weights."""
        keyword_results = [self._make_result("chunk-1", 0.9)]
        vector_results = [self._make_result("chunk-2", 0.8)]

        result = blend_results(keyword_results, vector_results, keyword_weight=0.0, vector_weight=0.0, top_k=10)

        assert len(result) == 2
        # All scores should be 0
        for r in result:
            assert r.score == 0.0

    def test_blend_with_disjoint_results(self):
        """Test blending when keyword and vector have no overlap."""
        keyword_results = [
            self._make_result("chunk-k1", 0.9),
            self._make_result("chunk-k2", 0.7),
        ]
        vector_results = [
            self._make_result("chunk-v1", 0.85),
            self._make_result("chunk-v2", 0.65),
        ]

        result = blend_results(keyword_results, vector_results, keyword_weight=0.5, vector_weight=0.5, top_k=10)

        assert len(result) == 4
        # Check that each chunk appears once
        chunk_ids = [r.chunk.chunk_id for r in result]
        assert set(chunk_ids) == {"chunk-k1", "chunk-k2", "chunk-v1", "chunk-v2"}

    def test_blend_top_k_zero(self):
        """Test that top_k=0 returns empty results."""
        keyword_results = [self._make_result("chunk-1", 0.9)]

        result = blend_results(keyword_results, [], top_k=0)

        assert result == []

    def test_blend_default_weights(self):
        """Test blending with default weights (0.5 each)."""
        keyword_results = [self._make_result("chunk-1", 1.0)]
        vector_results = [self._make_result("chunk-1", 1.0)]

        result = blend_results(keyword_results, vector_results, top_k=10)

        assert len(result) == 1
        assert result[0].score == pytest.approx(1.0)  # 0.5 * 1.0 + 0.5 * 1.0
