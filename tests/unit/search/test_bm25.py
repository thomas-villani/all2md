"""Unit tests for BM25 keyword search index."""

import importlib.util
from pathlib import Path

import pytest

from all2md.search.types import Chunk, SearchQuery


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Create sample chunks for testing."""
    return [
        Chunk(chunk_id="chunk1", text="The quick brown fox jumps over the lazy dog", metadata={}),
        Chunk(chunk_id="chunk2", text="Python is a great programming language", metadata={}),
        Chunk(chunk_id="chunk3", text="Machine learning and artificial intelligence", metadata={}),
        Chunk(chunk_id="chunk4", text="The fox is quick and clever", metadata={}),
    ]


@pytest.mark.skipif(importlib.util.find_spec("rank_bm25") is None, reason="rank_bm25 not installed")
@pytest.mark.unit
class TestBM25Index:
    """Test BM25Index class."""

    def test_index_creation(self):
        """Test creating a BM25 index."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        assert index.backend_name == "bm25"
        assert index._chunks == []

    def test_index_with_config(self):
        """Test creating index with custom config."""
        from all2md.search.bm25 import BM25Index, KeywordIndexConfig

        config = KeywordIndexConfig(k1=2.0, b=0.5)
        index = BM25Index(config=config)
        assert index.config.k1 == 2.0
        assert index.config.b == 0.5

    def test_add_chunks(self, sample_chunks):
        """Test adding chunks to the index."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        index.add_chunks(sample_chunks)
        assert len(index._chunks) == 4

    def test_search_basic(self, sample_chunks):
        """Test basic search functionality."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="fox quick")
        results = index.search(query, top_k=3)

        assert len(results) > 0
        # Fox-related chunks should rank higher
        top_result = results[0]
        assert "fox" in top_result.chunk.text.lower() or "quick" in top_result.chunk.text.lower()

    def test_search_empty_query(self, sample_chunks):
        """Test search with empty query."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="")
        results = index.search(query, top_k=3)

        assert results == []

    def test_search_empty_index(self):
        """Test search on empty index."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        query = SearchQuery(raw_text="test query")
        results = index.search(query, top_k=3)

        assert results == []

    def test_search_metadata(self, sample_chunks):
        """Test search result metadata."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="python programming")
        results = index.search(query, top_k=1)

        assert len(results) > 0
        assert results[0].metadata["backend"] == "bm25"

    def test_save_and_load(self, sample_chunks, tmp_path: Path):
        """Test saving and loading the index."""
        from all2md.search.bm25 import BM25Index

        index = BM25Index()
        index.add_chunks(sample_chunks)

        # Save
        save_dir = tmp_path / "bm25_index"
        index.save(save_dir)

        # Verify files exist
        assert (save_dir / "manifest.json").exists()
        assert (save_dir / "chunks.jsonl").exists()

        # Load
        loaded_index = BM25Index.load(save_dir)
        assert len(loaded_index._chunks) == len(sample_chunks)

        # Search on loaded index
        query = SearchQuery(raw_text="fox")
        results = loaded_index.search(query, top_k=2)
        assert len(results) > 0

    def test_custom_tokenizer(self, sample_chunks):
        """Test using a custom tokenizer."""
        from all2md.search.bm25 import BM25Index

        # Custom tokenizer that keeps case
        def custom_tokenizer(text: str) -> list[str]:
            return text.split()

        index = BM25Index(tokenizer=custom_tokenizer)
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="Python")
        results = index.search(query, top_k=3)
        assert len(results) > 0


@pytest.mark.unit
class TestKeywordIndexConfig:
    """Test KeywordIndexConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from all2md.search.bm25 import KeywordIndexConfig

        config = KeywordIndexConfig()
        assert config.k1 == 1.5
        assert config.b == 0.75

    def test_custom_config(self):
        """Test custom configuration values."""
        from all2md.search.bm25 import KeywordIndexConfig

        config = KeywordIndexConfig(k1=2.5, b=0.9)
        assert config.k1 == 2.5
        assert config.b == 0.9


@pytest.mark.unit
class TestDefaultTokenizer:
    """Test default tokenizer function."""

    def test_basic_tokenization(self):
        """Test basic text tokenization."""
        from all2md.search.bm25 import _default_tokenizer

        tokens = _default_tokenizer("Hello World")
        assert tokens == ["hello", "world"]

    def test_empty_string(self):
        """Test tokenizing empty string."""
        from all2md.search.bm25 import _default_tokenizer

        tokens = _default_tokenizer("")
        assert tokens == []

    def test_whitespace_only(self):
        """Test tokenizing whitespace only."""
        from all2md.search.bm25 import _default_tokenizer

        tokens = _default_tokenizer("   \t\n  ")
        assert tokens == []

    def test_lowercase_conversion(self):
        """Test that tokens are lowercased."""
        from all2md.search.bm25 import _default_tokenizer

        tokens = _default_tokenizer("HELLO World MiXeD")
        assert tokens == ["hello", "world", "mixed"]
