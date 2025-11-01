"""Shared data structures for the search subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Mapping, MutableMapping


class SearchMode(Enum):
    """Enumerate the supported search strategies."""

    GREP = auto()
    KEYWORD = auto()
    VECTOR = auto()
    HYBRID = auto()


@dataclass(frozen=True)
class Chunk:
    """Represents an indexed text chunk with associated metadata."""

    chunk_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def document_path(self) -> Path | None:
        """Return Path to the originating document when available."""
        raw_path = self.metadata.get("document_path")
        if not raw_path:
            return None
        try:
            return Path(raw_path)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class SearchResult:
    """Search result referencing a chunk and its relevance score."""

    chunk: Chunk
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchQuery:
    """Normalized query inputs for index backends."""

    raw_text: str
    filters: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> MutableMapping[str, Any]:
        """Return a mutable copy suitable for JSON serialization."""
        return {"query": self.raw_text, "filters": dict(self.filters)}
