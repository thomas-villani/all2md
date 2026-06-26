#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for the vendored position-tracking chunkers."""

import pytest

from all2md.chunking.primitives import (
    ChunkerFactory,
    ParagraphChunker,
    SectionChunker,
    SentenceChunker,
    WordChunker,
    reconstruct_document,
)
from all2md.chunking.tokenization import WhitespaceCounter, get_counter, tiktoken_available

pytestmark = pytest.mark.unit

WS = WhitespaceCounter()

LONG_PARAGRAPHS = "\n\n".join(f"Paragraph {i} has several words in it here." for i in range(20))


class TestCountOnlyChunkers:
    """Chunkers that only need token counting work under the whitespace backend."""

    @pytest.mark.parametrize("cls", [WordChunker, SentenceChunker, ParagraphChunker])
    def test_respects_token_budget(self, cls):
        """No emitted chunk exceeds max_tokens (whitespace tokens)."""
        chunker = cls(max_tokens=10, overlap=0, counter=WS)
        chunks = chunker.chunk(LONG_PARAGRAPHS)
        assert chunks
        assert all(c.tokens <= 10 for c in chunks)

    def test_empty_text_yields_no_chunks(self):
        """Whitespace-only input produces no chunks."""
        assert WordChunker(max_tokens=10, counter=WS).chunk("   \n  ") == []

    def test_short_text_single_chunk(self):
        """Text under the budget returns exactly one chunk spanning it."""
        chunks = ParagraphChunker(max_tokens=100, counter=WS).chunk("Just a few words.")
        assert len(chunks) == 1
        assert chunks[0].position.start == 0

    def test_positions_are_consistent(self):
        """Each chunk's content matches the span it reports into the source text."""
        chunker = WordChunker(max_tokens=8, counter=WS)
        chunks = chunker.chunk(LONG_PARAGRAPHS)
        for c in chunks:
            assert LONG_PARAGRAPHS[c.position.start : c.position.end] == c.content


class TestSectionChunker:
    """Section chunker forbids overlap and keeps small sections whole."""

    def test_overlap_must_be_zero(self):
        """Constructing with non-zero overlap raises."""
        with pytest.raises(ValueError, match="overlap"):
            SectionChunker(max_tokens=50, overlap=2, counter=WS)

    def test_splits_on_headers(self):
        """A multi-section markdown body yields multiple chunks."""
        text = "# A\n\nalpha beta gamma\n\n# B\n\ndelta epsilon zeta\n\n# C\n\neta theta iota"
        chunks = SectionChunker(max_tokens=4, counter=WS).chunk(text)
        assert len(chunks) >= 2


class TestWordOverlap:
    """Word-level overlap repeats trailing context and still makes progress."""

    def test_overlap_repeats_context(self):
        """With overlap, total emitted words exceed the unique word count."""
        text = " ".join(f"w{i}" for i in range(40))
        no_overlap = WordChunker(max_tokens=5, overlap=0, counter=WS).chunk(text)
        with_overlap = WordChunker(max_tokens=5, overlap=2, counter=WS).chunk(text)
        assert len(with_overlap) >= len(no_overlap)
        # Progress guarantee: never an infinite number of chunks.
        assert len(with_overlap) < 100


class TestReconstruction:
    """Non-overlapping chunks reconstruct the source exactly."""

    def test_word_chunker_roundtrip(self):
        """WordChunker output reassembles to the original text."""
        chunks = WordChunker(max_tokens=6, overlap=0, counter=WS).chunk(LONG_PARAGRAPHS)
        assert reconstruct_document(chunks, len(LONG_PARAGRAPHS)) == LONG_PARAGRAPHS


class TestFactory:
    """ChunkerFactory construction."""

    def test_lists_methods(self):
        """The factory advertises the expected method names."""
        methods = ChunkerFactory.list_methods()
        assert {"sentences", "tokens", "words", "lines", "paragraphs", "sections", "characters"} <= set(methods)

    def test_unknown_method(self):
        """An unknown method name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chunking method"):
            ChunkerFactory.create_chunker("bogus", 100, counter=WS)

    def test_sections_overlap_coerced(self):
        """Sections strategy is constructed with overlap 0 even if asked otherwise."""
        chunker = ChunkerFactory.create_chunker("sections", 100, overlap=5, counter=WS)
        assert chunker.overlap == 0


@pytest.mark.skipif(not tiktoken_available(), reason="tiktoken not installed")
class TestTokenChunker:
    """Token-boundary chunking requires a real encoder."""

    def test_requires_encoding(self):
        """TokenChunker rejects the whitespace counter (no encoding)."""
        from all2md.chunking.primitives import TokenChunker

        with pytest.raises(ValueError, match="tiktoken-backed"):
            TokenChunker(max_tokens=10, counter=WS)

    def test_token_budget_respected(self):
        """Real token windows never exceed max_tokens."""
        from all2md.chunking.primitives import TokenChunker

        counter = get_counter("tiktoken")
        text = " ".join(f"word{i}" for i in range(500))
        chunks = TokenChunker(max_tokens=32, overlap=4, counter=counter).chunk(text)
        assert chunks
        assert all(c.tokens <= 32 for c in chunks)
