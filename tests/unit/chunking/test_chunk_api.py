#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for the top-level ``all2md.chunk`` one-call convenience API."""

import pytest

import all2md
from all2md.chunking import ProvenanceChunk

pytestmark = pytest.mark.unit

SAMPLE = b"""# Intro

Some introductory prose with enough words to chunk a few times over here.

# Body

More body text in a second section, also with a fair number of words to split.
"""


def test_chunk_is_exported():
    """`all2md.chunk` is part of the public API."""
    assert hasattr(all2md, "chunk")
    assert "chunk" in all2md.__all__


def test_one_call_returns_provenance_chunks():
    """chunk(bytes) converts and chunks in a single call."""
    chunks = all2md.chunk(SAMPLE, source_format="markdown", strategy="paragraph", token_counter="whitespace")
    assert chunks
    assert all(isinstance(c, ProvenanceChunk) for c in chunks)
    headings = {c.section_heading for c in chunks}
    assert "Intro" in headings and "Body" in headings


def test_bytes_source_gets_generic_id():
    """A non-file source defaults document_id to 'document' with no path."""
    chunks = all2md.chunk(SAMPLE, source_format="markdown", strategy="section", token_counter="whitespace")
    assert chunks[0].document_id == "document"
    assert chunks[0].document_path is None


def test_document_id_override():
    """An explicit document_id is woven into chunk ids."""
    chunks = all2md.chunk(
        SAMPLE, source_format="markdown", strategy="section", document_id="mydoc", token_counter="whitespace"
    )
    assert all(c.document_id == "mydoc" for c in chunks)
    assert all(c.chunk_id.startswith("mydoc::") for c in chunks)


def test_file_source_derives_id_from_stem(tmp_path):
    """A file path yields document_id=<stem> and a recorded document_path."""
    path = tmp_path / "report.md"
    path.write_bytes(SAMPLE)
    chunks = all2md.chunk(str(path), strategy="section", token_counter="whitespace")
    assert chunks[0].document_id == "report"
    assert chunks[0].document_path is not None and chunks[0].document_path.endswith("report.md")


def test_drop_elements_through_api():
    """drop_elements strips node types before chunking."""
    md = b"# H\n\nText.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    kept = all2md.chunk(md, source_format="markdown", strategy="section", token_counter="whitespace")
    dropped = all2md.chunk(
        md, source_format="markdown", strategy="section", drop_elements=["table"], token_counter="whitespace"
    )
    assert any("|" in c.text for c in kept)
    assert all("|" not in c.text for c in dropped)


def test_min_tokens_through_api():
    """min_tokens filters small chunks via the convenience API."""
    chunks = all2md.chunk(
        SAMPLE, source_format="markdown", strategy="word", max_tokens=4, min_tokens=4, token_counter="whitespace"
    )
    assert chunks
    assert all(c.token_count >= 4 for c in chunks)


def test_converter_options_forwarded():
    """Extra kwargs (e.g. attachment_mode) are forwarded to to_ast without error."""
    md = b"# H\n\n![x](data:image/png;base64,%s)\n" % (b"A" * 80)
    chunks = all2md.chunk(
        md, source_format="markdown", strategy="section", attachment_mode="skip", token_counter="whitespace"
    )
    assert chunks
