"""Unit tests for Vector search index."""

import importlib.util
from pathlib import Path

import pytest

from all2md.search.types import Chunk, SearchQuery


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Create sample chunks for testing."""
    return [
        Chunk(chunk_id="chunk1", text="The quick brown fox jumps over the lazy dog", metadata={}),
        Chunk(chunk_id="chunk2", text="Python is a great programming language for data science", metadata={}),
        Chunk(chunk_id="chunk3", text="Machine learning and deep learning are popular AI techniques", metadata={}),
        Chunk(chunk_id="chunk4", text="Natural language processing helps computers understand text", metadata={}),
    ]


# Check if all vector dependencies are available
HAS_VECTOR_DEPS = (
    importlib.util.find_spec("numpy") is not None
    and importlib.util.find_spec("faiss") is not None
    and importlib.util.find_spec("sentence_transformers") is not None
)


@pytest.mark.skipif(not HAS_VECTOR_DEPS, reason="Vector search dependencies not installed")
@pytest.mark.unit
class TestVectorIndex:
    """Test VectorIndex class."""

    def test_index_creation(self):
        """Test creating a VectorIndex."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        assert index.backend_name == "vector"
        assert index._chunks == []

    def test_index_with_config(self):
        """Test creating index with custom config."""
        from all2md.search.vector import VectorIndex, VectorIndexConfig

        config = VectorIndexConfig(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            batch_size=16,
            normalize_embeddings=True,
        )
        index = VectorIndex(config=config)
        assert index.config.batch_size == 16
        assert index.config.normalize_embeddings is True

    def test_add_chunks(self, sample_chunks):
        """Test adding chunks to the index."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        index.add_chunks(sample_chunks)
        assert len(index._chunks) == 4

    @pytest.mark.slow
    def test_search_basic(self, sample_chunks):
        """Test basic search functionality."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="machine learning AI")
        results = index.search(query, top_k=2)

        assert len(results) > 0
        # ML/AI chunk should rank high
        assert any("learning" in r.chunk.text.lower() for r in results)

    def test_search_empty_index(self):
        """Test search on empty index."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        query = SearchQuery(raw_text="test query")
        results = index.search(query, top_k=3)

        assert results == []

    @pytest.mark.slow
    def test_search_metadata(self, sample_chunks):
        """Test search result metadata."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        index.add_chunks(sample_chunks)

        query = SearchQuery(raw_text="python programming")
        results = index.search(query, top_k=1)

        assert len(results) > 0
        assert results[0].metadata["backend"] == "vector"
        assert "raw_score" in results[0].metadata

    @pytest.mark.slow
    def test_save_and_load(self, sample_chunks, tmp_path: Path):
        """Test saving and loading the index."""
        from all2md.search.vector import VectorIndex

        index = VectorIndex()
        index.add_chunks(sample_chunks)

        # Save
        save_dir = tmp_path / "vector_index"
        index.save(save_dir)

        # Verify files exist
        assert (save_dir / "manifest.json").exists()
        assert (save_dir / "chunks.jsonl").exists()
        assert (save_dir / "vectors.npy").exists()

        # Load
        loaded_index = VectorIndex.load(save_dir)
        assert len(loaded_index._chunks) == len(sample_chunks)

        # Search on loaded index
        query = SearchQuery(raw_text="python")
        results = loaded_index.search(query, top_k=2)
        assert len(results) > 0


@pytest.mark.unit
class TestVectorIndexConfig:
    """Test VectorIndexConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from all2md.search.vector import VectorIndexConfig

        config = VectorIndexConfig()
        assert config.model_name == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.batch_size == 32
        assert config.device is None
        assert config.normalize_embeddings is True

    def test_custom_config(self):
        """Test custom configuration values."""
        from all2md.search.vector import VectorIndexConfig

        config = VectorIndexConfig(
            model_name="custom-model",
            batch_size=64,
            device="cuda",
            normalize_embeddings=False,
        )
        assert config.model_name == "custom-model"
        assert config.batch_size == 64
        assert config.device == "cuda"
        assert config.normalize_embeddings is False


@pytest.mark.unit
class TestSerializeMetadata:
    """Test _serialize_metadata helper function."""

    def test_serialize_basic_types(self):
        """Test serializing basic types."""
        from all2md.search.vector import _serialize_metadata

        metadata = {"str": "value", "int": 42, "float": 3.14, "bool": True, "none": None}
        result = _serialize_metadata(metadata)

        assert result["str"] == "value"
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["bool"] is True
        assert result["none"] is None

    def test_serialize_path(self):
        """Test serializing Path objects."""
        from all2md.search.vector import _serialize_metadata

        metadata = {"path": Path("/some/path")}
        result = _serialize_metadata(metadata)

        # Path serialization converts to string (platform-dependent separators)
        assert result["path"] == str(Path("/some/path"))

    def test_serialize_enum(self):
        """Test serializing Enum values."""
        from enum import Enum

        from all2md.search.vector import _serialize_metadata

        class TestEnum(Enum):
            VALUE1 = "val1"
            VALUE2 = "val2"

        metadata = {"enum": TestEnum.VALUE1}
        result = _serialize_metadata(metadata)

        assert result["enum"] == "val1"

    def test_serialize_unknown_type(self):
        """Test serializing unknown types falls back to str()."""
        from all2md.search.vector import _serialize_metadata

        class CustomClass:
            def __str__(self):
                return "custom_string"

        metadata = {"custom": CustomClass()}
        result = _serialize_metadata(metadata)

        assert result["custom"] == "custom_string"
