"""Index abstractions and manifest utilities for search backends."""

from __future__ import annotations

import json
import secrets
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping, MutableMapping, Sequence

from all2md.progress import ProgressCallback, ProgressEvent

from .types import Chunk, SearchMode, SearchQuery, SearchResult

INDEX_MANIFEST_VERSION = "1.0"


@dataclass(frozen=True)
class IndexManifest:
    """Metadata stored alongside persisted index backends."""

    version: str
    mode: SearchMode
    index_id: str
    created_at: str
    options: Mapping[str, Any] = field(default_factory=dict)
    backend: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, raw: Mapping[str, Any]) -> "IndexManifest":
        """Create manifest from JSON-compatible mapping."""
        mode_value = raw.get("mode")
        mode = SearchMode[mode_value] if isinstance(mode_value, str) else SearchMode(mode_value)
        return cls(
            version=str(raw.get("version", INDEX_MANIFEST_VERSION)),
            mode=mode,
            index_id=str(raw.get("index_id", "unknown")),
            created_at=str(raw.get("created_at", "")),
            options=dict(raw.get("options", {})),
            backend=dict(raw.get("backend", {})),
        )

    def to_json(self) -> MutableMapping[str, Any]:
        """Return JSON-compatible manifest payload."""
        payload = asdict(self)
        payload["mode"] = self.mode.name
        return payload


class BaseIndex(ABC):
    """Abstract base class for all search index implementations."""

    manifest_name: ClassVar[str] = "manifest.json"

    def __init__(
        self, *, mode: SearchMode, index_id: str | None = None, options_snapshot: Mapping[str, Any] | None = None
    ) -> None:
        """Create a new index base with identifying information and stored options."""
        self.mode = mode
        self.index_id = index_id or secrets.token_urlsafe(8)
        self._options_snapshot = dict(options_snapshot or {})
        self._chunks: list[Chunk] = []

    @property
    def chunk_count(self) -> int:
        """Return number of chunks currently stored."""
        return len(self._chunks)

    @property
    def options_snapshot(self) -> Mapping[str, Any]:
        """Immutable view of options relevant to this index."""
        return dict(self._options_snapshot)

    def add_chunks(self, chunks: Sequence[Chunk], *, progress_callback: ProgressCallback | None = None) -> None:
        """Add chunks to the index and update the backend model."""
        for idx, chunk in enumerate(chunks, start=1):
            self._chunks.append(chunk)
            if progress_callback:
                progress_callback(
                    ProgressEvent(
                        event_type="item_done",
                        message=f"Chunk {idx} added to {self.mode.name.lower()} index",
                        current=self.chunk_count,
                        total=self.chunk_count,
                        metadata={"item_type": "chunk", "chunk_id": chunk.chunk_id, "mode": self.mode.name.lower()},
                    )
                )
        if chunks:
            self._build_backend()

    @abstractmethod
    def _build_backend(self) -> None:
        """Rebuild underlying backend structures after corpus mutation."""

    @abstractmethod
    def search(self, query: SearchQuery, *, top_k: int = 10) -> list[SearchResult]:
        """Execute search query and return ranked results."""

    @abstractmethod
    def save(self, directory: Path) -> None:
        """Persist backend files to the target directory."""

    @classmethod
    @abstractmethod
    def load(cls, directory: Path) -> "BaseIndex":
        """Rehydrate index from persisted files."""

    def _write_manifest(self, directory: Path, backend_payload: Mapping[str, Any]) -> None:
        """Write manifest file describing stored index data."""
        manifest = IndexManifest(
            version=INDEX_MANIFEST_VERSION,
            mode=self.mode,
            index_id=self.index_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            options=self._options_snapshot,
            backend=backend_payload,
        )
        directory.mkdir(parents=True, exist_ok=True)
        (directory / self.manifest_name).write_text(json.dumps(manifest.to_json(), indent=2), encoding="utf-8")

    @classmethod
    def _read_manifest(cls, directory: Path) -> IndexManifest:
        """Read manifest from disk."""
        path = directory / cls.manifest_name
        if not path.exists():
            raise FileNotFoundError(f"Index manifest not found at {path}")
        raw = json.loads(path.read_text(encoding="utf-8"))
        return IndexManifest.from_json(raw)

    def iter_chunks(self) -> Iterable[Chunk]:
        """Yield stored chunks in insertion order."""
        return iter(self._chunks)
