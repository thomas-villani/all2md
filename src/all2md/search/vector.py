"""Vector search index built on FAISS and sentence-transformers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

from all2md.utils.decorators import requires_dependencies

from .index import BaseIndex
from .types import Chunk, SearchMode, SearchQuery, SearchResult

VectorDependencySpec = [
    ("faiss-cpu", "faiss", ""),
    ("sentence-transformers", "sentence_transformers", ">=2.2.0"),
    ("numpy", "numpy", ">=1.24.0"),
]


@dataclass
class VectorIndexConfig:
    """Runtime configuration for vector search."""

    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = 32
    device: str | None = None
    normalize_embeddings: bool = True


class VectorIndex(BaseIndex):
    """Approximate nearest-neighbour search powered by FAISS."""

    backend_name = "vector"

    def __init__(
        self,
        *,
        config: VectorIndexConfig | None = None,
        index_id: str | None = None,
        options_snapshot: Mapping[str, object] | None = None,
    ) -> None:
        """Create a vector index using the provided configuration options."""
        super().__init__(mode=SearchMode.VECTOR, index_id=index_id, options_snapshot=options_snapshot)
        self.config = config or VectorIndexConfig()
        self._vectors = None
        self._vector_count = 0
        self._dimension: int | None = None
        self._faiss_index = None
        self._encoder = None
        self._np = None
        self._faiss = None
        self._sentence_transformers = None

    @requires_dependencies("search_vector", VectorDependencySpec)
    def _ensure_backends(self) -> None:
        if self._np is None:
            import numpy as np

            self._np = np  # type: ignore[assignment]
        if self._faiss is None:
            import faiss

            self._faiss = faiss
        if self._sentence_transformers is None:
            from sentence_transformers import SentenceTransformer

            self._sentence_transformers = SentenceTransformer  # type: ignore[assignment]

    def _build_backend(self) -> None:
        """Encode any new chunks and rebuild the FAISS index."""
        self._ensure_backends()
        if self._np is None:
            return

        new_chunks = self._chunks[self._vector_count :]  # type: ignore[unreachable]
        if new_chunks:
            embeddings = self._encode_texts([chunk.text for chunk in new_chunks])
            if self.config.normalize_embeddings:
                embeddings = self._normalize_embeddings(embeddings)

            if self._vectors is None:
                self._vectors = embeddings
            else:
                self._vectors = self._np.vstack([self._vectors, embeddings])
            self._vector_count = len(self._chunks)

        if self._vectors is None or not len(self._chunks):
            self._faiss_index = None
            self._dimension = None
            return

        self._dimension = int(self._vectors.shape[1])
        vectors32 = self._vectors.astype(self._np.float32)
        self._faiss_index = self._create_index(self._dimension)
        self._faiss_index.reset()
        self._faiss_index.add(vectors32)

    def _create_index(self, dimension: int):  # type: ignore[no-untyped-def]
        if self._faiss is None:
            raise RuntimeError("FAISS backend not initialised")
        if self.config.normalize_embeddings:  # type: ignore[unreachable]
            return self._faiss.IndexFlatIP(dimension)
        return self._faiss.IndexFlatL2(dimension)

    def _get_encoder(self):  # type: ignore[no-untyped-def]
        if self._encoder is None:
            self._ensure_backends()
            self._encoder = self._sentence_transformers(self.config.model_name, device=self.config.device)
        return self._encoder

    def _encode_texts(self, texts: Sequence[str]):  # type: ignore[no-untyped-def]
        self._ensure_backends()
        encoder = self._get_encoder()  # type: ignore[no-untyped-call]
        encode_kwargs: dict[str, object] = {
            "batch_size": self.config.batch_size,
            "show_progress_bar": False,
            "convert_to_numpy": True,
        }
        if self.config.device:
            encode_kwargs["device"] = self.config.device
        embeddings = encoder.encode(texts, **encode_kwargs)
        return self._np.asarray(embeddings, dtype=self._np.float32)  # type: ignore[attr-defined]

    def _normalize_embeddings(self, vectors):  # type: ignore[no-untyped-def]
        norms = self._np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1
        return vectors / norms

    @requires_dependencies("search_vector", VectorDependencySpec)
    def search(self, query: SearchQuery, *, top_k: int = 10) -> list[SearchResult]:
        """Return the nearest ``top_k`` chunks to ``query`` in vector space."""
        if self._faiss_index is None or self._np is None or self._dimension is None:  # type: ignore[unreachable]
            return []

        query_vec = self._encode_texts([query.raw_text])  # type: ignore[unreachable]
        if self.config.normalize_embeddings:
            query_vec = self._normalize_embeddings(query_vec)
        query_vec = query_vec.astype(self._np.float32)

        scores, indices = self._faiss_index.search(query_vec, top_k)
        results: list[SearchResult] = []
        for idx, score in zip(indices[0], scores[0], strict=True):
            if idx < 0:
                continue
            relevance = float(score if self.config.normalize_embeddings else -score)
            results.append(
                SearchResult(
                    chunk=self._chunks[idx],
                    score=relevance,
                    metadata={
                        "backend": self.backend_name,
                        "mode": self.mode.name,
                        "raw_score": float(score),
                        "normalized": self.config.normalize_embeddings,
                    },
                )
            )
        return results

    @requires_dependencies("search_vector", VectorDependencySpec)
    def save(self, directory: Path) -> None:
        """Persist FAISS index, embeddings, and configuration to ``directory``."""
        self._ensure_backends()
        directory.mkdir(parents=True, exist_ok=True)

        backend_payload = {
            "backend": self.backend_name,
            "model_name": self.config.model_name,
            "normalize": self.config.normalize_embeddings,
            "batch_size": self.config.batch_size,
            "dimension": self._dimension,
        }
        self._write_manifest(directory, backend_payload=backend_payload)

        chunks_path = directory / "chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in self._chunks:
                record = {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": _serialize_metadata(chunk.metadata),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        vectors_path = directory / "vectors.npy"
        vectors = (
            self._vectors
            if self._vectors is not None
            else self._np.zeros((0, 0), dtype=self._np.float32)  # type: ignore[attr-defined]
        )
        self._np.save(vectors_path, vectors)  # type: ignore[attr-defined]

    @classmethod
    @requires_dependencies("search_vector", VectorDependencySpec)
    def load(cls, directory: Path) -> "VectorIndex":
        """Restore a vector index that was previously saved to ``directory``."""
        manifest = cls._read_manifest(directory)
        backend = manifest.backend or {}
        default_cfg = VectorIndexConfig()
        config = VectorIndexConfig(
            model_name=str(backend.get("model_name", default_cfg.model_name)),
            batch_size=int(backend.get("batch_size", default_cfg.batch_size)),
            normalize_embeddings=bool(backend.get("normalize", default_cfg.normalize_embeddings)),
        )

        index = cls(config=config, index_id=manifest.index_id, options_snapshot=manifest.options)
        index._ensure_backends()

        chunks_path = directory / "chunks.jsonl"
        if chunks_path.exists():
            with chunks_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    raw = json.loads(line)
                    metadata = raw.get("metadata", {}) or {}
                    if not isinstance(metadata, dict):
                        metadata = {}
                    index._chunks.append(Chunk(chunk_id=raw["chunk_id"], text=raw["text"], metadata=metadata))

        vectors_path = directory / "vectors.npy"
        if vectors_path.exists():
            vectors = index._np.load(vectors_path, allow_pickle=False)  # type: ignore[attr-defined]
            if vectors.size:
                if config.normalize_embeddings:
                    vectors = index._normalize_embeddings(vectors)  # type: ignore[no-untyped-call]
                index._vectors = vectors
                index._vector_count = vectors.shape[0]
                index._dimension = vectors.shape[1]
                index._faiss_index = index._create_index(index._dimension)
                index._faiss_index.reset()  # type: ignore[attr-defined]
                index._faiss_index.add(vectors.astype(index._np.float32))  # type: ignore[attr-defined]
        return index


def _serialize_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            serialized[key] = value
        elif isinstance(value, Path):
            serialized[key] = str(value)
        elif isinstance(value, Enum):
            serialized[key] = value.value if hasattr(value, "value") else value.name
        else:
            serialized[key] = str(value)
    return serialized
