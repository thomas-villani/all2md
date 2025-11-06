"""Chunk generation utilities for document indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

from all2md.ast.nodes import Document
from all2md.ast.sections import get_all_sections, get_preamble
from all2md.ast.utils import extract_text
from all2md.progress import ProgressCallback, ProgressEvent

from .types import Chunk

_TOKEN_SPLIT_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class ChunkingContext:
    """Describe the document targeted for chunk generation."""

    document_id: str
    document_path: Path | None
    metadata: Mapping[str, object]


def chunk_document(
    doc: Document,
    *,
    context: ChunkingContext,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
    min_chunk_tokens: int,
    include_preamble: bool,
    heading_merge: bool,
    max_heading_level: int | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[Chunk]:
    """Split an AST document into search-friendly text chunks."""
    if max_heading_level is None:
        sections = get_all_sections(doc)
    else:
        sections = get_all_sections(doc, min_level=1, max_level=max_heading_level)

    total_units = len(sections) + (1 if include_preamble and get_preamble(doc) else 0)

    if progress_callback:
        progress_callback(
            ProgressEvent(
                event_type="started",
                message=f"Chunking document {context.document_id}",
                current=0,
                total=total_units,
                metadata={"item_type": "chunking", "document_id": context.document_id},
            )
        )

    chunks: list[Chunk] = []
    running_index = 0

    if include_preamble:
        preamble_nodes = get_preamble(doc)
        if preamble_nodes:
            text = _normalize_text(extract_text(preamble_nodes))
            for chunk_index, text_window in enumerate(
                _split_text(text, chunk_size_tokens, chunk_overlap_tokens, min_chunk_tokens), start=1
            ):
                chunk_id = f"{context.document_id}::preamble-{chunk_index}"
                chunk_metadata: dict[str, Any] = {
                    "document_id": context.document_id,
                    "document_path": context.document_path.as_posix() if context.document_path else None,
                    "section_heading": None,
                    "section_level": None,
                    "section_index": -1,
                    "chunk_index": running_index,
                    "chunk_in_section": chunk_index,
                }
                chunk_metadata.update(cast(dict[str, Any], context.metadata))
                chunks.append(Chunk(chunk_id=chunk_id, text=text_window, metadata=chunk_metadata))
                running_index += 1

            if progress_callback:
                progress_callback(
                    ProgressEvent(
                        event_type="item_done",
                        message="Preamble chunked",
                        current=len(chunks),
                        total=total_units,
                        metadata={"item_type": "section", "section": "preamble"},
                    )
                )

    for section_index, section in enumerate(sections, start=1):
        heading_text = _normalize_text(section.get_heading_text())
        body_raw = extract_text(list(section.content))
        body = _normalize_text(body_raw)
        if not body:
            continue

        include_heading = heading_merge and heading_text
        combined = f"{heading_text}\n\n{body}" if include_heading else body
        text_windows = _split_text(combined, chunk_size_tokens, chunk_overlap_tokens, min_chunk_tokens)
        if not text_windows:
            continue

        for chunk_in_section, text_window in enumerate(text_windows, start=1):
            chunk_id = f"{context.document_id}::s{section_index}-c{chunk_in_section}"
            section_chunk_metadata: dict[str, Any] = {
                "document_id": context.document_id,
                "document_path": context.document_path.as_posix() if context.document_path else None,
                "section_heading": heading_text,
                "section_level": section.level,
                "section_index": section_index,
                "chunk_index": running_index,
                "chunk_in_section": chunk_in_section,
            }
            section_chunk_metadata.update(cast(dict[str, Any], context.metadata))
            chunks.append(Chunk(chunk_id=chunk_id, text=text_window, metadata=section_chunk_metadata))
            running_index += 1

        if progress_callback:
            progress_callback(
                ProgressEvent(
                    event_type="item_done",
                    message=f"Section {section_index} chunked",
                    current=len(chunks),
                    total=total_units,
                    metadata={
                        "item_type": "section",
                        "section": section_index,
                        "heading": heading_text,
                        "level": section.level,
                    },
                )
            )

    if progress_callback:
        progress_callback(
            ProgressEvent(
                event_type="finished",
                message=f"Chunked document {context.document_id}",
                current=len(chunks),
                total=len(chunks),
                metadata={"chunks": len(chunks)},
            )
        )

    return chunks


def _split_text(text: str, max_tokens: int, overlap_tokens: int, min_tokens: int) -> list[str]:
    """Split text into windows using a sliding token window."""
    tokens = [tok for tok in _TOKEN_SPLIT_RE.split(text) if tok]
    if not tokens:
        return []

    if len(tokens) <= max_tokens or max_tokens <= 0:
        return [text]

    stride = max(1, max_tokens - max(0, overlap_tokens))
    windows: list[list[str]] = []
    start = 0
    total = len(tokens)

    while start < total:
        end = min(total, start + max_tokens)
        window = tokens[start:end]
        if not window:
            break
        windows.append(window)
        if end >= total:
            break
        start += stride

    # Merge trailing shards shorter than minimum into previous window if possible
    normalized: list[str] = []
    for window in windows:
        if normalized and len(window) < min_tokens:
            combined = normalized.pop().split()
            combined.extend(window)
            normalized.append(" ".join(combined))
        else:
            normalized.append(" ".join(window))

    return [_normalize_text(chunk) for chunk in normalized if chunk.strip()]


def _normalize_text(text: str) -> str:
    """Collapse whitespace to single spaces and strip edges."""
    text = text.replace("\u00a0", " ")
    collapsed = _TOKEN_SPLIT_RE.sub(" ", text)
    return collapsed.strip()
