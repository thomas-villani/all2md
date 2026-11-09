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


@pytest.mark.skipif(not tiktoken_available(), reason="tiktoken not installed")
class TestPackingToTheBudgetDoesNotOvershoot:
    """A chunk packed to exactly ``max_tokens`` stays within it under a BPE counter (#686).

    The packing loops summed each unit's own count, but the chunk is the span between units,
    separators included; ``TokenChunker`` re-encoded a re-sliced span, which BPE does not
    round-trip at a cut. Either came out a token over, and CharChunker then cut the chunk
    mid-word, leaving a fragment behind.
    """

    @staticmethod
    def _text() -> str:
        import random

        rng = random.Random(0)
        words = "the quick brown fox jumps over a lazy dog's back, 1,234.5 times; naïve café co-operation e.g. U.S.A. --- 🙂".split()
        paragraphs = (" ".join(rng.choice(words) for _ in range(rng.randint(20, 90))) + "." for _ in range(150))
        return "\n\n".join(paragraphs)

    @pytest.mark.parametrize("method", ["tokens", "sentences", "paragraphs", "lines", "sections"])
    def test_no_chunk_needs_the_char_fallback(self, method: str, caplog: pytest.LogCaptureFixture) -> None:
        counter = get_counter("tiktoken")
        with caplog.at_level("WARNING", logger="all2md.chunking.primitives"):
            chunks = ChunkerFactory.create_chunker(method, 256, 0, counter=counter).chunk(self._text())
        assert not [r for r in caplog.records if "exceeds max_tokens" in r.getMessage()]
        assert all(chunk.tokens <= 256 for chunk in chunks)

    def test_token_windows_leave_no_gap(self) -> None:
        """A window shrunk to fit is followed by one starting where it ended."""
        text = self._text()
        chunks = ChunkerFactory.create_chunker("tokens", 256, 0, counter=get_counter("tiktoken")).chunk(text)
        assert chunks[0].position.start == 0
        assert chunks[-1].position.end == len(text)
        for before, after in zip(chunks, chunks[1:], strict=False):
            assert after.position.start <= before.position.end
