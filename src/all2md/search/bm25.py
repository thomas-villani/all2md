"""BM25 keyword search index backed by rank-bm25."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Sequence

from all2md.constants import DEPS_SEARCH_BM25
from all2md.utils.decorators import requires_dependencies

from .index import BaseIndex
from .types import Chunk, SearchMode, SearchQuery, SearchResult


@dataclass
class KeywordIndexConfig:
    """Configuration settings for BM25 indexing."""

    k1: float = 1.5
    b: float = 0.75


def _default_tokenizer(text: str) -> list[str]:
    return [token for token in text.lower().split() if token]


class BM25Index(BaseIndex):
    """Keyword search implementation using BM25 scoring."""

    backend_name = "bm25"

    def __init__(
        self,
        *,
        config: KeywordIndexConfig | None = None,
        tokenizer: Callable[[str], Sequence[str]] | None = None,
        index_id: str | None = None,
        options_snapshot: Mapping[str, object] | None = None,
    ) -> None:
        """Initialise the BM25 index with optional configuration and tokenizer override."""
        cfg = config or KeywordIndexConfig()
        super().__init__(mode=SearchMode.KEYWORD, index_id=index_id, options_snapshot=options_snapshot)
        self.config = cfg
        self._tokenizer = tokenizer or _default_tokenizer
        self._tokenized_corpus: list[list[str]] = []
        self._backend = None
        self._bm25_constructor: type | None = None

    @requires_dependencies("search_bm25", DEPS_SEARCH_BM25)
    def _ensure_backend(self) -> None:
        if self._bm25_constructor is None:
            from rank_bm25 import BM25Okapi

            self._bm25_constructor = BM25Okapi

    def _build_backend(self) -> None:
        """Recompute the BM25 corpus after chunks change."""
        self._ensure_backend()
        if self._bm25_constructor is None:
            return

        self._tokenized_corpus = [list(self._tokenizer(chunk.text)) for chunk in self._chunks]
        if not self._tokenized_corpus:
            self._backend = None
            return
        self._backend = self._bm25_constructor(self._tokenized_corpus, k1=self.config.k1, b=self.config.b)

    @requires_dependencies("search_bm25", DEPS_SEARCH_BM25)
    def search(self, query: SearchQuery, *, top_k: int = 10) -> list[SearchResult]:
        """Return the top ``top_k`` chunks ranked by BM25 score for ``query``."""
        if self._backend is None:
            return []

        tokens = list(self._tokenizer(query.raw_text))  # type: ignore[unreachable]
        if not tokens:
            return []

        scores = self._backend.get_scores(tokens)
        ranked = sorted(
            ((idx, float(score)) for idx, score in enumerate(scores)), key=lambda pair: pair[1], reverse=True
        )
        results: list[SearchResult] = []
        for idx, score in ranked[:top_k]:
            results.append(
                SearchResult(
                    chunk=self._chunks[idx],
                    score=score,
                    metadata={"backend": self.backend_name, "mode": self.mode.name},
                )
            )
        return results

    def save(self, directory: Path) -> None:
        """Persist BM25 corpus, chunks, and configuration to ``directory``."""
        directory.mkdir(parents=True, exist_ok=True)
        payload = {"backend": self.backend_name, "k1": self.config.k1, "b": self.config.b}
        self._write_manifest(directory, backend_payload=payload)

        chunks_path = directory / "chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in self._chunks:
                record = {
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": _serialize_metadata(chunk.metadata),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    @classmethod
    def load(cls, directory: Path) -> "BM25Index":
        """Restore a BM25 index that was previously saved to ``directory``."""
        manifest = cls._read_manifest(directory)
        backend = manifest.backend or {}
        config = KeywordIndexConfig(k1=float(backend.get("k1", 1.5)), b=float(backend.get("b", 0.75)))

        index = cls(config=config, index_id=manifest.index_id, options_snapshot=manifest.options)
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
        index._build_backend()
        return index


def _serialize_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Convert metadata mapping into JSON-serializable values."""
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
