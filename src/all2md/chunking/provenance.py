#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/chunking/provenance.py
"""The AST -> chunk bridge.

:func:`chunk_ast` is the heart of ``all2md chunk``. It turns a parsed
:class:`~all2md.ast.nodes.Document` into a list of
:class:`~all2md.chunking.records.ProvenanceChunk` records, each carrying the
section context and source page/line span that distinguish all2md's chunking
from flat-text chunkers.

Two strategy families:

- **Coarse** (``heading``/``section``/``auto``) reuse
  :class:`~all2md.ast.splitting.DocumentSplitter` to cut at semantic boundaries;
  each split becomes one chunk, sub-split only when it exceeds the token budget.
- **Fine** (``semantic``/``token``/``sentence``/``paragraph``/``word``/``line``/
  ``char``/``code``) iterate sections (plus the preamble) and run a
  position-tracking chunker over each section's *rendered Markdown*.

Rendering each unit to Markdown (rather than flattening with ``extract_text``)
preserves the blank-line/structure boundaries the paragraph/line/section
chunkers depend on, and yields clean, RAG-friendly chunk text. Character spans
are therefore into that rendered section text (``char_basis="section_text"``),
not the original binary.
"""

from __future__ import annotations

from typing import Iterable, Optional, cast

from all2md.ast.nodes import Document, Node, Table, get_node_children
from all2md.ast.sections import get_all_sections, get_preamble
from all2md.ast.splitting import DocumentSplitter
from all2md.chunking.primitives import ChunkerFactory, PositionTrackingChunker
from all2md.chunking.records import ProvenanceChunk
from all2md.chunking.tokenization import TokenCounter, get_counter
from all2md.constants import DocumentFormat

#: Coarse strategies cut at semantic boundaries (one chunk per unit).
_COARSE_STRATEGIES = frozenset({"heading", "section", "auto"})

#: Fine strategy -> ChunkerFactory method name.
_FINE_METHOD = {
    "semantic": "tokens",
    "token": "tokens",
    "sentence": "sentences",
    "paragraph": "paragraphs",
    "word": "words",
    "line": "lines",
    "char": "characters",
    "code": "code-blocks",
}

STRATEGIES = (
    "semantic",
    "heading",
    "section",
    "token",
    "sentence",
    "paragraph",
    "word",
    "line",
    "char",
    "code",
    "auto",
)


def chunk_ast(
    doc: Document,
    *,
    strategy: str = "semantic",
    max_tokens: int = 512,
    overlap: int = 0,
    document_id: str = "document",
    document_path: Optional[str] = None,
    include_preamble: bool = True,
    heading_merge: bool = True,
    max_heading_level: Optional[int] = None,
    avoid_table_split: bool = False,
    token_counter: str = "auto",
    counter: Optional[TokenCounter] = None,
) -> list[ProvenanceChunk]:
    """Chunk a document AST into provenance-carrying records.

    Parameters
    ----------
    doc : Document
        Parsed document AST.
    strategy : str
        One of :data:`STRATEGIES`. ``semantic`` (default) windows each section by
        real tokens.
    max_tokens : int
        Maximum tokens per chunk.
    overlap : int
        Overlap between consecutive windows (units depend on the strategy; coerced
        to 0 for coarse strategies).
    document_id : str
        Identifier woven into chunk ids and metadata (typically the file stem).
    document_path : str, optional
        POSIX path recorded on each chunk.
    include_preamble : bool
        Whether content before the first heading becomes its own chunk(s).
    heading_merge : bool
        Whether each section's heading line is prepended to its chunk text.
    max_heading_level : int, optional
        For fine strategies, only descend into sections at or above this level.
    avoid_table_split : bool
        For fine strategies, emit each table as its own atomic chunk so a table is
        never split mid-row (it may exceed ``max_tokens``). Coarse strategies never
        split tables regardless.
    token_counter : {"auto", "tiktoken", "whitespace"}
        Token-counting backend (ignored when ``counter`` is provided).
    counter : TokenCounter, optional
        Pre-resolved counter; if omitted one is resolved from ``token_counter``.

    Returns
    -------
    list of ProvenanceChunk
        Chunks in document reading order, with ``prev``/``next`` ids linked.

    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown strategy {strategy!r}. Choose from: {', '.join(STRATEGIES)}")
    if max_tokens < 1:
        raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")

    if counter is None:
        counter = get_counter(token_counter, strategy=strategy)

    if strategy in _COARSE_STRATEGIES:
        chunks = _chunk_coarse(
            doc,
            strategy=strategy,
            max_tokens=max_tokens,
            heading_merge=heading_merge,
            document_id=document_id,
            document_path=document_path,
            counter=counter,
        )
    else:
        chunks = _chunk_fine(
            doc,
            strategy=strategy,
            max_tokens=max_tokens,
            overlap=overlap,
            include_preamble=include_preamble,
            heading_merge=heading_merge,
            max_heading_level=max_heading_level,
            avoid_table_split=avoid_table_split,
            document_id=document_id,
            document_path=document_path,
            counter=counter,
        )

    _link_neighbors(chunks)
    return chunks


# --------------------------------------------------------------------------- #
# Fine strategies: per-section windowing                                       #
# --------------------------------------------------------------------------- #


def _chunk_fine(
    doc: Document,
    *,
    strategy: str,
    max_tokens: int,
    overlap: int,
    include_preamble: bool,
    heading_merge: bool,
    max_heading_level: Optional[int],
    avoid_table_split: bool,
    document_id: str,
    document_path: Optional[str],
    counter: TokenCounter,
) -> list[ProvenanceChunk]:
    method = _FINE_METHOD[strategy]
    chunker = ChunkerFactory.create_chunker(method, max_tokens, overlap, counter=counter)

    sections = get_all_sections(doc, max_level=max_heading_level) if max_heading_level else get_all_sections(doc)

    chunks: list[ProvenanceChunk] = []
    running_index = 0

    # No headings at all: chunk the whole document as a single unnumbered unit
    # (otherwise nothing would be emitted for heading-light documents).
    if not sections:
        running_index = _emit_unit(
            chunks,
            chunker=chunker,
            unit_nodes=list(doc.children),
            provenance_nodes=list(doc.children),
            id_base=f"{document_id}::preamble",
            strategy=strategy,
            running_index=running_index,
            document_id=document_id,
            document_path=document_path,
            section_heading=None,
            section_level=None,
            section_index=-1,
            avoid_table_split=avoid_table_split,
        )
        return chunks

    if include_preamble:
        preamble_nodes = get_preamble(doc)
        if preamble_nodes:
            running_index = _emit_unit(
                chunks,
                chunker=chunker,
                unit_nodes=preamble_nodes,
                provenance_nodes=preamble_nodes,
                id_base=f"{document_id}::preamble",
                strategy=strategy,
                running_index=running_index,
                document_id=document_id,
                document_path=document_path,
                section_heading=None,
                section_level=None,
                section_index=-1,
                avoid_table_split=avoid_table_split,
            )

    for section_index, section in enumerate(sections, start=1):
        provenance_nodes = [section.heading] + list(section.content)
        unit_nodes: list[Node] = provenance_nodes if heading_merge else list(section.content)
        running_index = _emit_unit(
            chunks,
            chunker=chunker,
            unit_nodes=unit_nodes,
            provenance_nodes=provenance_nodes,
            id_base=f"{document_id}::s{section_index}",
            strategy=strategy,
            running_index=running_index,
            document_id=document_id,
            document_path=document_path,
            section_heading=section.get_heading_text() or None,
            section_level=section.level,
            section_index=section_index,
            avoid_table_split=avoid_table_split,
        )

    return chunks


# --------------------------------------------------------------------------- #
# Coarse strategies: one chunk per semantic split                              #
# --------------------------------------------------------------------------- #


def _chunk_coarse(
    doc: Document,
    *,
    strategy: str,
    max_tokens: int,
    heading_merge: bool,
    document_id: str,
    document_path: Optional[str],
    counter: TokenCounter,
) -> list[ProvenanceChunk]:
    if strategy == "section":
        splits = DocumentSplitter.split_by_sections(doc, include_preamble=True)
    elif strategy == "heading":
        splits = DocumentSplitter.split_by_heading_level(doc, level=1, include_preamble=True)
    else:  # auto
        splits = DocumentSplitter.split_auto(doc)

    # Oversized splits are sub-split: real token windows when available, else
    # paragraph windows (count-only) so the whitespace fallback still works.
    sub_method = "tokens" if getattr(counter, "encoding", None) is not None else "paragraphs"
    chunker = ChunkerFactory.create_chunker(sub_method, max_tokens, 0, counter=counter)

    chunks: list[ProvenanceChunk] = []
    running_index = 0
    for split in splits:
        provenance_nodes = list(split.document.children)
        unit_nodes = provenance_nodes if heading_merge else _drop_leading_heading(provenance_nodes)
        running_index = _emit_unit(
            chunks,
            chunker=chunker,
            unit_nodes=unit_nodes,
            provenance_nodes=provenance_nodes,
            id_base=f"{document_id}::p{split.index}",
            strategy=strategy,
            running_index=running_index,
            document_id=document_id,
            document_path=document_path,
            section_heading=split.title,
            section_level=_first_heading_level(provenance_nodes),
            section_index=split.index,
            avoid_table_split=False,
        )
    return chunks


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #


def _emit_unit(
    chunks: list[ProvenanceChunk],
    *,
    chunker: PositionTrackingChunker,
    unit_nodes: list[Node],
    provenance_nodes: list[Node],
    id_base: str,
    strategy: str,
    running_index: int,
    document_id: str,
    document_path: Optional[str],
    section_heading: Optional[str],
    section_level: Optional[int],
    section_index: int,
    avoid_table_split: bool,
) -> int:
    """Render ``unit_nodes`` to Markdown, chunk it, and append provenance chunks.

    With ``avoid_table_split``, the unit is segmented at :class:`Table` boundaries:
    each table becomes one atomic chunk (never split mid-row, may exceed the token
    budget) and prose segments are windowed normally. Chunk numbering stays
    continuous across segments. Returns the new running index.
    """
    pieces = _build_pieces(chunker, unit_nodes, provenance_nodes, avoid_table_split)
    for chunk_in_unit, (text, tokens, char_start, char_end, prov_nodes) in enumerate(pieces, start=1):
        page, page_end, line_start, line_end = _node_provenance(prov_nodes)
        chunks.append(
            ProvenanceChunk(
                chunk_id=f"{id_base}-c{chunk_in_unit}",
                index=running_index,
                text=text,
                token_count=tokens,
                token_counter=chunker.counter.name,
                strategy=strategy,
                document_id=document_id,
                document_path=document_path,
                section_heading=section_heading,
                section_level=section_level,
                section_index=section_index,
                page=page,
                page_end=page_end,
                source_line_start=line_start,
                source_line_end=line_end,
                char_start=char_start,
                char_end=char_end,
                char_basis="section_text",
            )
        )
        running_index += 1
    return running_index


# A renderable chunk before id/provenance assignment:
# (text, token_count, char_start, char_end, provenance_nodes).
_Piece = tuple[str, int, int, int, list[Node]]


def _build_pieces(
    chunker: PositionTrackingChunker,
    unit_nodes: list[Node],
    provenance_nodes: list[Node],
    avoid_table_split: bool,
) -> list[_Piece]:
    """Render and chunk a unit into pieces, keeping tables atomic when asked."""
    pieces: list[_Piece] = []

    if avoid_table_split and any(isinstance(n, Table) for n in unit_nodes):
        for seg_nodes, is_atomic in _segment_at_tables(unit_nodes):
            text = _render_markdown(seg_nodes)
            if not text.strip():
                continue
            if is_atomic:
                # Whole table is one chunk; allowed to exceed max_tokens.
                pieces.append((text, chunker.counter.count(text), 0, len(text), seg_nodes))
            else:
                for window in chunker.chunk(text):
                    pieces.append(
                        (window.content, window.tokens, window.position.start, window.position.end, seg_nodes)
                    )
        return pieces

    text = _render_markdown(unit_nodes)
    if text.strip():
        for window in chunker.chunk(text):
            pieces.append((window.content, window.tokens, window.position.start, window.position.end, provenance_nodes))
    return pieces


def _segment_at_tables(nodes: list[Node]) -> list[tuple[list[Node], bool]]:
    """Split ``nodes`` into ``(segment, is_atomic)`` runs, each Table its own atomic run."""
    segments: list[tuple[list[Node], bool]] = []
    buffer: list[Node] = []
    for node in nodes:
        if isinstance(node, Table):
            if buffer:
                segments.append((buffer, False))
                buffer = []
            segments.append(([node], True))
        else:
            buffer.append(node)
    if buffer:
        segments.append((buffer, False))
    return segments


def _render_markdown(nodes: list[Node]) -> str:
    """Render a list of AST nodes to Markdown (the chunk source text)."""
    if not nodes:
        return ""
    from all2md.api import from_ast

    rendered = from_ast(Document(children=list(nodes)), cast(DocumentFormat, "markdown"))
    return rendered if isinstance(rendered, str) else ""


def _iter_nodes(nodes: Iterable[Node]) -> Iterable[Node]:
    """Yield ``nodes`` and all their descendants (depth-first)."""
    for node in nodes:
        yield node
        yield from _iter_nodes(get_node_children(node))


def _node_provenance(
    nodes: list[Node],
) -> tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """Derive ``(page, page_end, line_start, line_end)`` from nodes' source locations.

    Spans are the min/max of the populated ``SourceLocation.page`` / ``.line`` over
    the contributing nodes (recursively). Returns ``None`` for an axis no node
    populated — common for formats that don't track pages or lines.
    """
    pages: list[int] = []
    lines: list[int] = []
    for node in _iter_nodes(nodes):
        loc = node.source_location
        if loc is None:
            continue
        if loc.page is not None:
            pages.append(loc.page)
        if loc.line is not None:
            lines.append(loc.line)
    page = min(pages) if pages else None
    page_end = max(pages) if pages else None
    line_start = min(lines) if lines else None
    line_end = max(lines) if lines else None
    return page, page_end, line_start, line_end


def _drop_leading_heading(nodes: list[Node]) -> list[Node]:
    """Return ``nodes`` without a leading Heading (for ``--no-heading-merge``)."""
    from all2md.ast.nodes import Heading

    if nodes and isinstance(nodes[0], Heading):
        return list(nodes[1:])
    return list(nodes)


def _first_heading_level(nodes: list[Node]) -> Optional[int]:
    """Return the level of the first Heading among ``nodes``, if any."""
    from all2md.ast.nodes import Heading

    for node in nodes:
        if isinstance(node, Heading):
            return node.level
    return None


def _link_neighbors(chunks: list[ProvenanceChunk]) -> None:
    """Populate ``prev_chunk_id``/``next_chunk_id`` across the sequence."""
    for i, chunk in enumerate(chunks):
        chunk.prev_chunk_id = chunks[i - 1].chunk_id if i > 0 else None
        chunk.next_chunk_id = chunks[i + 1].chunk_id if i + 1 < len(chunks) else None


__all__ = ["chunk_ast", "STRATEGIES"]
