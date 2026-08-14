#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/chunking/records.py
"""The public chunk output record.

:class:`ProvenanceChunk` is the single record type emitted by
:func:`all2md.chunking.chunk_ast`. It carries the chunk text plus the
AST-derived provenance that distinguishes all2md's chunking from flat-text
chunkers: which section a chunk came from, and (where the parser populated it)
the source page and line span.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class ProvenanceChunk:
    """A text chunk with AST-derived provenance.

    Attributes
    ----------
    chunk_id : str
        Stable id, ``{document_id}::s{section}-c{chunk_in_section}`` (or
        ``::preamble-N`` / ``::p{part}`` for preamble / coarse parts).
    index : int
        0-based position of this chunk in the document-wide sequence.
    text : str
        The chunk text.
    token_count : int
        Token count under ``token_counter``.
    token_counter : str
        Name of the counter used (``tiktoken`` or ``whitespace``).
    strategy : str
        The chunking strategy that produced this chunk.
    document_id : str
        Identifier for the source document (defaults to the file stem).
    document_path : str or None
        POSIX path to the source document when known.
    section_heading : str or None
        Heading text of the section this chunk belongs to (None for preamble).
    section_level : int or None
        Heading level (1-6) of that section.
    section_index : int
        1-based section ordinal; ``-1`` marks preamble / non-section content.
    page, page_end : int or None
        Source page span, when the parser populated ``SourceLocation.page``
        (PDF and a few others). None otherwise.
    source_line_start, source_line_end : int or None
        Source line span, when the parser populated ``SourceLocation.line``.
        Rarely available; None otherwise.
    char_start, char_end : int
        Character span of this chunk. By default these index into the
        section's extracted text (see ``char_basis``), not the original binary.
    char_basis : str
        What ``char_start``/``char_end`` index into -- always check it before
        slicing. ``"section_text"`` (the usual value) is the section's rendered
        Markdown, the string you get by rendering the section's nodes.
        ``"segment_text"`` appears only under ``avoid_table_split`` /
        ``avoid_code_split``, for a chunk whose atomic segment could not be
        located in that section text (rendering a fragment is not always a
        substring of rendering the whole); the span is then relative to that
        segment's own rendered Markdown. ``"document"`` is reserved for future
        binary-accurate spans.
    prev_chunk_id, next_chunk_id : str or None
        Neighbor ids, for reconstructing reading order downstream.

    """

    chunk_id: str
    index: int
    text: str
    token_count: int
    token_counter: str
    strategy: str
    document_id: str
    document_path: Optional[str] = None
    section_heading: Optional[str] = None
    section_level: Optional[int] = None
    section_index: int = -1
    page: Optional[int] = None
    page_end: Optional[int] = None
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    char_start: int = 0
    char_end: int = 0
    char_basis: str = "section_text"
    prev_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Return a flat JSON-serializable dict (one object per JSONL line)."""
        return asdict(self)
