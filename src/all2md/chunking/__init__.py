#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/chunking/__init__.py
"""Provenance-aware document chunking for RAG workflows.

Public API:

- :func:`chunk_ast` — turn a parsed :class:`~all2md.ast.nodes.Document` into a
  list of :class:`ProvenanceChunk` records (the entry point for ``all2md chunk``).
- :data:`STRATEGIES` — the available chunking strategy names.
- :class:`ProvenanceChunk` — the output record, with section + page/line provenance.
- :func:`get_counter` — resolve a token-counting backend.

Example:
-------
    >>> from all2md import to_ast
    >>> from all2md.chunking import chunk_ast
    >>> doc = to_ast("README.md")
    >>> chunks = chunk_ast(doc, strategy="semantic", max_tokens=256, overlap=32)
    >>> chunks[0].section_heading, chunks[0].token_count  # doctest: +SKIP

"""

from all2md.chunking.provenance import STRATEGIES, chunk_ast
from all2md.chunking.records import ProvenanceChunk
from all2md.chunking.tokenization import TokenCounter, get_counter

__all__ = ["chunk_ast", "STRATEGIES", "ProvenanceChunk", "TokenCounter", "get_counter"]
