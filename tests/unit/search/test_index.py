"""Unit tests for search index base classes and manifest handling."""

import json
from pathlib import Path

import pytest

from all2md.search.index import INDEX_MANIFEST_VERSION, BaseIndex, IndexManifest
from all2md.search.types import Chunk, SearchMode, SearchQuery, SearchResult


class ConcreteIndex(BaseIndex):
    """Concrete implementation of BaseIndex for testing."""

    backend_name = "test"

    def _build_backend(self) -> None:
        pass

    def search(self, query: SearchQuery, *, top_k: int = 10) -> list[SearchResult]:
        # Simple substring search for testing
        results = []
        for chunk in self._chunks[:top_k]:
            if query.raw_text.lower() in chunk.text.lower():
                results.append(SearchResult(chunk=chunk, score=1.0, metadata={}))
        return results

    def save(self, directory: Path) -> None:
        self._write_manifest(directory, {"backend": self.backend_name})

    @classmethod
    def load(cls, directory: Path) -> "ConcreteIndex":
        manifest = cls._read_manifest(directory)
        return cls(mode=manifest.mode, index_id=manifest.index_id, options_snapshot=manifest.options)


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Create sample chunks for testing."""
    return [
        Chunk(chunk_id="chunk1", text="Hello world", metadata={"source": "test"}),
        Chunk(chunk_id="chunk2", text="Goodbye world", metadata={"source": "test"}),
    ]


@pytest.mark.unit
class TestIndexManifest:
    """Test IndexManifest dataclass."""

    def test_from_json_basic(self):
        """Test creating manifest from JSON."""
        raw = {
            "version": "1.0",
            "mode": "KEYWORD",
            "index_id": "test123",
            "created_at": "2024-01-01T00:00:00Z",
            "options": {"key": "value"},
            "backend": {"backend_key": "backend_value"},
        }
        manifest = IndexManifest.from_json(raw)

        assert manifest.version == "1.0"
        assert manifest.mode == SearchMode.KEYWORD
        assert manifest.index_id == "test123"
        assert manifest.created_at == "2024-01-01T00:00:00Z"
        assert manifest.options == {"key": "value"}
        assert manifest.backend == {"backend_key": "backend_value"}

    def test_from_json_defaults(self):
        """Test manifest from JSON with missing fields uses defaults."""
        raw = {"mode": "GREP"}
        manifest = IndexManifest.from_json(raw)

        assert manifest.version == INDEX_MANIFEST_VERSION
        assert manifest.index_id == "unknown"
        assert manifest.options == {}
        assert manifest.backend == {}

    def test_to_json(self):
        """Test converting manifest to JSON."""
        manifest = IndexManifest(
            version="1.0",
            mode=SearchMode.VECTOR,
            index_id="test123",
            created_at="2024-01-01T00:00:00Z",
            options={"key": "value"},
            backend={"backend_key": "value"},
        )
        json_data = manifest.to_json()

        assert json_data["version"] == "1.0"
        assert json_data["mode"] == "VECTOR"
        assert json_data["index_id"] == "test123"
        assert json_data["options"] == {"key": "value"}

    def test_roundtrip(self):
        """Test JSON roundtrip preserves data."""
        original = IndexManifest(
            version="1.0",
            mode=SearchMode.KEYWORD,
            index_id="roundtrip",
            created_at="2024-06-15T12:00:00Z",
            options={"opt1": 42},
            backend={"k1": 1.5},
        )
        json_data = original.to_json()
        restored = IndexManifest.from_json(json_data)

        assert restored.version == original.version
        assert restored.mode == original.mode
        assert restored.index_id == original.index_id
        assert restored.options == original.options


@pytest.mark.unit
class TestBaseIndex:
    """Test BaseIndex abstract class via ConcreteIndex."""

    def test_index_creation(self):
        """Test creating an index."""
        index = ConcreteIndex(mode=SearchMode.GREP)
        assert index.mode == SearchMode.GREP
        assert index.chunk_count == 0
        assert len(index.index_id) > 0

    def test_index_with_id(self):
        """Test creating index with custom ID."""
        index = ConcreteIndex(mode=SearchMode.GREP, index_id="custom_id")
        assert index.index_id == "custom_id"

    def test_index_with_options(self):
        """Test creating index with options snapshot."""
        options = {"option1": "value1", "option2": 42}
        index = ConcreteIndex(mode=SearchMode.GREP, options_snapshot=options)
        assert index.options_snapshot == options

    def test_options_snapshot_immutable(self):
        """Test that options_snapshot returns a copy."""
        options = {"mutable": True}
        index = ConcreteIndex(mode=SearchMode.GREP, options_snapshot=options)

        # Get snapshot and modify it
        snapshot = index.options_snapshot
        snapshot["mutable"] = False

        # Original should be unchanged
        assert index.options_snapshot["mutable"] is True

    def test_add_chunks(self, sample_chunks):
        """Test adding chunks to index."""
        index = ConcreteIndex(mode=SearchMode.GREP)
        index.add_chunks(sample_chunks)

        assert index.chunk_count == 2

    def test_add_chunks_with_progress(self, sample_chunks):
        """Test adding chunks with progress callback."""
        events = []

        def callback(event):
            events.append(event)

        index = ConcreteIndex(mode=SearchMode.GREP)
        index.add_chunks(sample_chunks, progress_callback=callback)

        assert len(events) == 2
        assert events[0].event_type == "item_done"
        assert events[0].metadata["chunk_id"] == "chunk1"

    def test_iter_chunks(self, sample_chunks):
        """Test iterating over chunks."""
        index = ConcreteIndex(mode=SearchMode.GREP)
        index.add_chunks(sample_chunks)

        chunks_list = list(index.iter_chunks())
        assert len(chunks_list) == 2
        assert chunks_list[0].chunk_id == "chunk1"

    def test_save_and_load(self, sample_chunks, tmp_path: Path):
        """Test saving and loading index."""
        index = ConcreteIndex(mode=SearchMode.GREP, index_id="save_test")
        index.add_chunks(sample_chunks)

        # Save
        save_dir = tmp_path / "test_index"
        index.save(save_dir)

        # Verify manifest exists
        manifest_path = save_dir / "manifest.json"
        assert manifest_path.exists()

        # Verify manifest content
        manifest_data = json.loads(manifest_path.read_text())
        assert manifest_data["mode"] == "GREP"
        assert manifest_data["index_id"] == "save_test"

        # Load
        loaded = ConcreteIndex.load(save_dir)
        assert loaded.mode == SearchMode.GREP
        assert loaded.index_id == "save_test"

    def test_load_missing_manifest(self, tmp_path: Path):
        """Test loading from directory without manifest raises error."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="manifest not found"):
            ConcreteIndex.load(empty_dir)


@pytest.mark.unit
class TestManifestVersion:
    """Test manifest version constant."""

    def test_version_string(self):
        """Test version is a valid string."""
        assert isinstance(INDEX_MANIFEST_VERSION, str)
        assert len(INDEX_MANIFEST_VERSION) > 0
