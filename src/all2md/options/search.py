"""Configuration options for the search subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.options.base import CloneFrozenMixin


@dataclass(frozen=True)
class SearchOptions(CloneFrozenMixin):
    """Search configuration toggles used by the CLI and API."""

    chunk_size_tokens: int = field(
        default=320,
        metadata={
            "help": "Maximum tokens per chunk when indexing documents",
            "type": int,
            "importance": "core",
        },
    )
    chunk_overlap_tokens: int = field(
        default=40,
        metadata={
            "help": "Token overlap between adjacent chunks to preserve context",
            "type": int,
            "importance": "core",
        },
    )
    min_chunk_tokens: int = field(
        default=60,
        metadata={
            "help": "Minimum token length for a chunk before merging with neighbours",
            "type": int,
            "importance": "advanced",
        },
    )
    include_preamble: bool = field(
        default=True,
        metadata={
            "help": "Index document preamble content that appears before the first heading",
            "importance": "core",
        },
    )
    heading_merge: bool = field(
        default=True,
        metadata={
            "help": "Prefix section chunks with their heading text for additional recall",
            "importance": "core",
        },
    )
    max_heading_level: int | None = field(
        default=None,
        metadata={
            "help": "Limit chunking to headings up to the given level (1-6). Use None to include all levels",
            "type": int,
            "importance": "advanced",
        },
    )
    bm25_k1: float = field(
        default=1.5,
        metadata={
            "help": "BM25 k1 parameter controlling term frequency saturation",
            "type": float,
            "importance": "advanced",
        },
    )
    bm25_b: float = field(
        default=0.75,
        metadata={
            "help": "BM25 b parameter controlling document length normalization",
            "type": float,
            "importance": "advanced",
        },
    )
    vector_model_name: str = field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        metadata={
            "help": "Sentence-transformers model to use for embedding generation",
            "importance": "advanced",
        },
    )
    vector_batch_size: int = field(
        default=32,
        metadata={
            "help": "Batch size to use when encoding documents with the embedding model",
            "type": int,
            "importance": "advanced",
        },
    )
    vector_device: str | None = field(
        default=None,
        metadata={
            "help": "Torch device string for embeddings (e.g. 'cuda', 'cpu'). Auto-detected when None",
            "importance": "advanced",
        },
    )
    vector_normalize_embeddings: bool = field(
        default=True,
        metadata={
            "help": "Normalize embedding vectors prior to FAISS indexing (enables cosine similarity)",
            "importance": "advanced",
        },
    )
    hybrid_keyword_weight: float = field(
        default=0.5,
        metadata={
            "help": "Relative contribution of keyword scores when blending hybrid search",
            "type": float,
            "importance": "core",
        },
    )
    hybrid_vector_weight: float = field(
        default=0.5,
        metadata={
            "help": "Relative contribution of vector scores when blending hybrid search",
            "type": float,
            "importance": "core",
        },
    )
    default_mode: str = field(
        default="keyword",
        metadata={
            "help": "Default search mode (grep, keyword, vector, hybrid)",
            "choices": ["grep", "keyword", "vector", "hybrid"],
            "importance": "core",
        },
    )
    grep_context_before: int = field(
        default=0,
        metadata={
            "help": "Number of lines to include before each grep match",
            "type": int,
            "importance": "advanced",
        },
    )
    grep_context_after: int = field(
        default=0,
        metadata={
            "help": "Number of lines to include after each grep match",
            "type": int,
            "importance": "advanced",
        },
    )
    grep_regex: bool = field(
        default=False,
        metadata={
            "help": "Interpret grep queries as regular expressions",
            "importance": "advanced",
        },
    )
    grep_ignore_case: bool = field(
        default=False,
        metadata={
            "help": "Perform case-insensitive matching in grep mode",
            "importance": "advanced",
        },
    )
    grep_show_line_numbers: bool = field(
        default=False,
        metadata={
            "help": "Show line numbers for matching lines in grep mode",
            "importance": "advanced",
        },
    )
    grep_max_columns: int = field(
        default=150,
        metadata={
            "help": "Maximum display width for long lines in grep output (0 = unlimited)",
            "type": int,
            "importance": "advanced",
        },
    )

    def __post_init__(self) -> None:
        """Validate numeric ranges and dependent options at construction time."""
        if self.chunk_size_tokens <= 0:
            raise ValueError("chunk_size_tokens must be positive")
        if self.chunk_overlap_tokens < 0:
            raise ValueError("chunk_overlap_tokens cannot be negative")
        if self.min_chunk_tokens <= 0:
            raise ValueError("min_chunk_tokens must be positive")
        if self.bm25_k1 <= 0:
            raise ValueError("bm25_k1 must be positive")
        if not (0 <= self.bm25_b <= 1):
            raise ValueError("bm25_b must be between 0 and 1")
        if self.vector_batch_size <= 0:
            raise ValueError("vector_batch_size must be positive")
        if self.max_heading_level is not None and not (1 <= self.max_heading_level <= 6):
            raise ValueError("max_heading_level must be between 1 and 6 when provided")
        total_weight = self.hybrid_keyword_weight + self.hybrid_vector_weight
        if total_weight <= 0:
            raise ValueError("Hybrid weights must sum to a positive value")
        if self.grep_context_before < 0 or self.grep_context_after < 0:
            raise ValueError("Grep context values must be non-negative")
        if self.grep_max_columns < 0:
            raise ValueError("grep_max_columns must be non-negative (0 = unlimited)")


__all__ = ["SearchOptions"]
