#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/chunking/primitives.py
"""Position-tracking text chunkers.

These chunkers split raw text into windows bounded by a token budget, tracking
each window's exact character and line/column span so the original document can
be reconstructed or highlighted. They are format-agnostic and operate on plain
strings; the AST bridge in :mod:`all2md.chunking.provenance` runs them within
section boundaries and attaches document provenance.

Ported from the ``localvectordb`` sister project (same author) and adapted to
inject an :class:`~all2md.chunking.tokenization.TokenCounter` rather than
constructing a ``tiktoken`` encoder directly, so count-only strategies work
without ``tiktoken`` installed.

Classes
-------
PositionTrackingChunker : Abstract base with position + token-limit machinery
SentenceChunker, TokenChunker, WordChunker, LineChunker, CharChunker,
ParagraphChunker, SectionChunker, CodeBlockChunker : Concrete strategies
ChunkerFactory : Name -> chunker construction

Functions
---------
reconstruct_document : Reassemble original text from its chunks
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from all2md.chunking.tokenization import TokenCounter

logger = logging.getLogger(__name__)


@dataclass
class ChunkPosition:
    """Exact position of a chunk within the text it was split from.

    ``start``/``end`` are character offsets; ``line``/``column`` and
    ``end_line``/``end_column`` are 1-based.
    """

    start: int
    end: int
    line: int
    column: int
    end_line: int
    end_column: int


@dataclass
class TextChunk:
    """A position-tracked text window produced by a chunker."""

    content: str
    position: ChunkPosition
    tokens: int
    index: int


class PositionTrackingChunker(ABC):
    """Base class for chunkers that track exact positions.

    Parameters
    ----------
    max_tokens : int
        Maximum tokens per chunk.
    overlap : int
        Strategy-specific overlap (units depend on the concrete chunker).
    counter : TokenCounter
        Backend used to count tokens. Token-boundary chunkers additionally
        require ``counter.encoding`` (a ``tiktoken`` encoding).

    """

    def __init__(self, max_tokens: int = 500, overlap: int = 0, *, counter: TokenCounter) -> None:
        """Store the token budget, overlap, and counter for this chunker."""
        self.max_tokens = max_tokens
        self.overlap = overlap
        self.counter = counter

    @abstractmethod
    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` into position-tracked chunks."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens in ``text`` using the injected counter."""
        return self.counter.count(text)

    def _calculate_line_column(self, text: str, position: int) -> Tuple[int, int]:
        """Calculate 1-based line and column for a character position."""
        if position > len(text):
            position = len(text)

        before = text[:position]
        lines = before.split("\n")
        line = len(lines)

        last_line = lines[-1]
        column = len(last_line) + 1 if last_line else 1
        return line, column

    def _create_chunk(self, text: str, start: int, end: int, index: int) -> TextChunk:
        """Create a chunk with position tracking."""
        content = text[start:end]
        line, column = self._calculate_line_column(text, start)
        end_line, end_column = self._calculate_line_column(text, end)

        position = ChunkPosition(
            start=start, end=end, line=line, column=column, end_line=end_line, end_column=end_column
        )
        return TextChunk(content=content, position=position, tokens=self.count_tokens(content), index=index)

    def _ensure_chunks_within_limit(self, chunks: List[TextChunk], text: str) -> List[TextChunk]:
        """Split any oversized chunk with :class:`CharChunker`, then renumber."""
        result: List[TextChunk] = []
        for chunk in chunks:
            if chunk.tokens <= self.max_tokens:
                result.append(chunk)
                continue

            logger.warning(
                "Chunk %d exceeds max_tokens (%d > %d). Splitting with CharChunker.",
                chunk.index,
                chunk.tokens,
                self.max_tokens,
            )
            char_chunker = CharChunker(self.max_tokens, overlap=0, counter=self.counter)
            sub_chunks = char_chunker.chunk(chunk.content)

            base_start = chunk.position.start
            base_index = chunk.index
            for i, sub_chunk in enumerate(sub_chunks):
                new_start = base_start + sub_chunk.position.start
                new_end = base_start + sub_chunk.position.end
                line, column = self._calculate_line_column(text, new_start)
                end_line, end_column = self._calculate_line_column(text, new_end)
                sub_chunk.position = ChunkPosition(
                    start=new_start, end=new_end, line=line, column=column, end_line=end_line, end_column=end_column
                )
                sub_chunk.index = base_index + i
            result.extend(sub_chunks)

        for i, chunk in enumerate(result):
            chunk.index = i
        return result


class SentenceChunker(PositionTrackingChunker):
    """Chunk by sentences while preserving boundaries."""

    sentence_pattern = re.compile(r'(?<=[.!?])\s+|(?<=[.!?]")(?=\s+[A-Z])|(?<=[.!?])\n+', re.MULTILINE)

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` by sentences, packing up to the token budget."""
        if not text.strip():
            return []

        sentences = self._split_into_sentences(text)
        if not sentences:
            return [self._create_chunk(text, 0, len(text), 0)]

        # Fast path: the whole sentence span fits in one chunk.
        single = self._create_chunk(text, sentences[0][0], sentences[-1][1], 0)
        if single.tokens <= self.max_tokens:
            return [single]

        # Pre-count once; the overlap rewind below can revisit sentences.
        sentence_token_counts = [self.count_tokens(s[2]) for s in sentences]

        chunks: List[TextChunk] = []
        chunk_index = 0
        i = 0

        while i < len(sentences):
            chunk_sentences: list[tuple[int, int, str]] = []
            chunk_tokens = 0
            start_idx = i

            while i < len(sentences):
                sentence_start, sentence_end, sentence_text = sentences[i]
                sentence_tokens = sentence_token_counts[i]

                if sentence_tokens > self.max_tokens and not chunk_sentences:
                    word_chunks = self._split_sentence_by_words(text, sentence_start, sentence_end, chunk_index)
                    chunks.extend(word_chunks)
                    chunk_index += len(word_chunks)
                    i += 1
                    break

                if chunk_tokens + sentence_tokens > self.max_tokens and chunk_sentences:
                    break

                chunk_sentences.append((sentence_start, sentence_end, sentence_text))
                chunk_tokens += sentence_tokens
                i += 1

            if chunk_sentences:
                start_pos = chunk_sentences[0][0]
                end_pos = chunk_sentences[-1][1]
                chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
                chunk_index += 1

                if self.overlap > 0 and i < len(sentences):
                    sentences_processed = i - start_idx
                    overlap_count = min(self.overlap, sentences_processed - 1)
                    i = start_idx + max(1, sentences_processed - overlap_count)

        return self._ensure_chunks_within_limit(chunks, text)

    def _split_into_sentences(self, text: str) -> List[Tuple[int, int, str]]:
        """Split text into ``(start, end, text)`` sentence tuples."""
        sentences = []
        last_end = 0
        for match in self.sentence_pattern.finditer(text):
            start = last_end
            end = match.start()
            if start < end:
                sentence_text = text[start:end].strip()
                if sentence_text:
                    sentences.append((start, end, sentence_text))
            last_end = match.end()
        if last_end < len(text):
            final_text = text[last_end:].strip()
            if final_text:
                sentences.append((last_end, len(text), final_text))
        return sentences

    def _split_sentence_by_words(self, text: str, start: int, end: int, base_index: int) -> List[TextChunk]:
        """Split a single over-long sentence by words."""
        sentence_text = text[start:end]
        word_pattern = re.compile(r"\S+")
        words = [(start + m.start(), start + m.end(), m.group()) for m in word_pattern.finditer(sentence_text)]
        if not words:
            return [self._create_chunk(text, start, end, base_index)]

        chunks: List[TextChunk] = []
        chunk_index = base_index
        i = 0
        while i < len(words):
            chunk_words: list[tuple[int, int, str]] = []
            while i < len(words):
                word_start, word_end, word_text = words[i]
                test_start = chunk_words[0][0] if chunk_words else word_start
                test_end = words[i + 1][0] if i + 1 < len(words) else end
                test_tokens = self.count_tokens(text[test_start:test_end])
                if test_tokens > self.max_tokens and chunk_words:
                    break
                chunk_words.append((word_start, word_end, word_text))
                i += 1
            if chunk_words:
                chunk_start = chunk_words[0][0]
                chunk_end = words[i][0] if i < len(words) else end
                chunks.append(self._create_chunk(text, chunk_start, chunk_end, chunk_index))
                chunk_index += 1
        return chunks


class TokenChunker(PositionTrackingChunker):
    """Chunk on token boundaries with position tracking.

    Requires ``counter.encoding`` (a ``tiktoken`` encoding) for the
    ``encode``/``decode`` round-trip.
    """

    def __init__(self, max_tokens: int = 500, overlap: int = 0, *, counter: TokenCounter) -> None:
        """Require a tiktoken-backed counter and cache its encoding."""
        super().__init__(max_tokens, overlap, counter=counter)
        encoding = getattr(counter, "encoding", None)
        if encoding is None:
            raise ValueError(
                "TokenChunker requires a tiktoken-backed token counter; "
                "use --token-counter tiktoken (pip install all2md[chunk])."
            )
        self.encoding = encoding

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` by token boundaries with sliding overlap."""
        if not text.strip():
            return []

        tokens = self.encoding.encode(text)
        if len(tokens) <= self.max_tokens:
            return [self._create_chunk(text, 0, len(text), 0)]

        chunks: List[TextChunk] = []
        chunk_index = 0
        stride = max(1, self.max_tokens - self.overlap)

        for i in range(0, len(tokens), stride):
            chunk_tokens = tokens[i : i + self.max_tokens]
            chunk_text = self.encoding.decode(chunk_tokens)
            start_pos = self._estimate_position(text, tokens, i)
            end_pos = min(start_pos + len(chunk_text), len(text))
            chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
            chunk_index += 1
            if end_pos >= len(text):
                break

        return self._ensure_chunks_within_limit(chunks, text)

    def _estimate_position(self, text: str, all_tokens: List[int], token_index: int) -> int:
        """Estimate a character position from a token index via decode length."""
        if token_index == 0:
            return 0
        prefix_text = self.encoding.decode(all_tokens[:token_index])
        return min(len(prefix_text), len(text))


class WordChunker(PositionTrackingChunker):
    """Chunk by word boundaries while preserving whitespace."""

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` by words, packing up to the token budget."""
        if not text.strip():
            return []

        word_pattern = re.compile(r"\S+")
        words = [(m.start(), m.end(), m.group()) for m in word_pattern.finditer(text)]
        if not words:
            return [self._create_chunk(text, 0, len(text), 0)]

        chunks: List[TextChunk] = []
        chunk_index = 0
        i = 0
        while i < len(words):
            chunk_words: list[tuple[int, int, str]] = []
            start_idx = i
            while i < len(words):
                word_start, word_end, word_text = words[i]
                test_start = chunk_words[0][0] if chunk_words else word_start
                test_end = words[i + 1][0] if i + 1 < len(words) else len(text)
                if self.count_tokens(text[test_start:test_end]) > self.max_tokens and chunk_words:
                    break
                chunk_words.append((word_start, word_end, word_text))
                i += 1
            if chunk_words:
                start_pos = chunk_words[0][0]
                end_pos = words[i][0] if i < len(words) else len(text)
                chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
                chunk_index += 1
                if self.overlap > 0 and i < len(words):
                    words_processed = i - start_idx
                    overlap_count = min(self.overlap, words_processed - 1)
                    i = start_idx + max(1, words_processed - overlap_count)

        return self._ensure_chunks_within_limit(chunks, text)


class LineChunker(PositionTrackingChunker):
    """Chunk by line boundaries."""

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` by lines, packing up to the token budget."""
        if not text.strip():
            return []

        lines = text.splitlines(keepends=True)
        line_positions = []
        current_pos = 0
        for line in lines:
            line_positions.append((current_pos, current_pos + len(line), line))
            current_pos += len(line)
        if not line_positions:
            return [self._create_chunk(text, 0, len(text), 0)]

        chunks: List[TextChunk] = []
        chunk_index = 0
        i = 0
        while i < len(line_positions):
            chunk_lines: list[tuple[int, int, str]] = []
            chunk_tokens = 0
            start_idx = i
            while i < len(line_positions):
                line_start, line_end, line_text = line_positions[i]
                line_tokens = self.count_tokens(line_text)
                if line_tokens > self.max_tokens and not chunk_lines:
                    word_chunks = self._split_line_by_words(text, line_start, line_end, chunk_index)
                    chunks.extend(word_chunks)
                    chunk_index += len(word_chunks)
                    i += 1
                    break
                if chunk_tokens + line_tokens > self.max_tokens and chunk_lines:
                    break
                chunk_lines.append((line_start, line_end, line_text))
                chunk_tokens += line_tokens
                i += 1
            if chunk_lines:
                start_pos = chunk_lines[0][0]
                end_pos = chunk_lines[-1][1]
                chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
                chunk_index += 1
                if self.overlap > 0 and i < len(line_positions):
                    lines_processed = i - start_idx
                    overlap_count = min(self.overlap, lines_processed - 1)
                    i = start_idx + max(1, lines_processed - overlap_count)

        return self._ensure_chunks_within_limit(chunks, text)

    def _split_line_by_words(self, text: str, start: int, end: int, base_index: int) -> List[TextChunk]:
        """Split an over-long line by words, rebasing positions to ``text``."""
        line_text = text[start:end]
        word_chunker = WordChunker(self.max_tokens, self.overlap, counter=self.counter)
        word_chunks = word_chunker.chunk(line_text)
        for chunk in word_chunks:
            chunk.position.start += start
            chunk.position.end += start
            chunk.index = base_index
            base_index += 1
        return word_chunks


class CharChunker(PositionTrackingChunker):
    """Chunk by character boundaries with exact position tracking."""

    def chunk(self, text: str) -> List[TextChunk]:
        """Grow chunks character-by-character up to the token budget."""
        if not text.strip():
            return []

        chunks: List[TextChunk] = []
        chunk_index = 0
        start_pos = 0
        while start_pos < len(text):
            end_pos = start_pos
            current_chunk = ""
            while end_pos < len(text):
                test_chunk = current_chunk + text[end_pos]
                if self.count_tokens(test_chunk) > self.max_tokens and current_chunk:
                    break
                current_chunk = test_chunk
                end_pos += 1
            if end_pos == start_pos:
                end_pos = start_pos + 1
            chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
            chunk_index += 1
            if end_pos >= len(text):
                break
            chunk_length = end_pos - start_pos
            start_pos += max(1, chunk_length - self.overlap)

        return chunks


class ParagraphChunker(PositionTrackingChunker):
    """Chunk by paragraph (blank-line) boundaries."""

    paragraph_pattern = re.compile(r"\n\s*\n", re.MULTILINE)

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` by paragraphs, packing up to the token budget."""
        if not text.strip():
            return []

        paragraphs = self._split_into_paragraphs(text)
        if not paragraphs:
            return [self._create_chunk(text, 0, len(text), 0)]

        chunks: List[TextChunk] = []
        chunk_index = 0
        i = 0
        while i < len(paragraphs):
            chunk_paragraphs: list[tuple[int, int, str]] = []
            chunk_tokens = 0
            start_idx = i
            while i < len(paragraphs):
                para_start, para_end, para_text = paragraphs[i]
                para_tokens = self.count_tokens(para_text)
                if para_tokens > self.max_tokens and not chunk_paragraphs:
                    sentence_chunks = self._split_paragraph_by_sentences(text, para_start, para_end, chunk_index)
                    chunks.extend(sentence_chunks)
                    chunk_index += len(sentence_chunks)
                    i += 1
                    break
                if chunk_tokens + para_tokens > self.max_tokens and chunk_paragraphs:
                    break
                chunk_paragraphs.append((para_start, para_end, para_text))
                chunk_tokens += para_tokens
                i += 1
            if chunk_paragraphs:
                start_pos = chunk_paragraphs[0][0]
                end_pos = chunk_paragraphs[-1][1]
                chunks.append(self._create_chunk(text, start_pos, end_pos, chunk_index))
                chunk_index += 1
                if self.overlap > 0 and i < len(paragraphs):
                    paragraphs_processed = i - start_idx
                    overlap_count = min(self.overlap, paragraphs_processed - 1)
                    i = start_idx + max(1, paragraphs_processed - overlap_count)

        return self._ensure_chunks_within_limit(chunks, text)

    def _split_into_paragraphs(self, text: str) -> List[Tuple[int, int, str]]:
        """Split text into ``(start, end, text)`` paragraph tuples."""
        paragraphs = []
        last_end = 0
        for match in self.paragraph_pattern.finditer(text):
            start = last_end
            end = match.start()
            if start < end:
                para_text = text[start:end].strip()
                if para_text:
                    paragraphs.append((start, end, para_text))
            last_end = match.end()
        if last_end < len(text):
            final_text = text[last_end:].strip()
            if final_text:
                paragraphs.append((last_end, len(text), final_text))
        return paragraphs

    def _split_paragraph_by_sentences(self, text: str, start: int, end: int, base_index: int) -> List[TextChunk]:
        """Split an over-long paragraph by sentences, rebasing positions."""
        para_text = text[start:end]
        sentence_chunker = SentenceChunker(self.max_tokens, self.overlap, counter=self.counter)
        sentence_chunks = sentence_chunker.chunk(para_text)
        for chunk in sentence_chunks:
            chunk.position.start += start
            chunk.position.end += start
            chunk.index = base_index
            base_index += 1
        return sentence_chunks


class SectionChunker(PositionTrackingChunker):
    """Chunk by markdown-style section headers, avoiding orphaned headings."""

    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def __init__(self, max_tokens: int = 500, overlap: int = 0, *, counter: TokenCounter) -> None:
        """Construct a section chunker; ``overlap`` must be 0 (sections are logical units)."""
        if overlap != 0:
            raise ValueError("`overlap` must be 0 for SectionChunker")
        super().__init__(max_tokens, 0, counter=counter)

    def chunk(self, text: str) -> List[TextChunk]:
        """Split ``text`` at header boundaries, keeping whole sections when they fit."""
        if not text.strip():
            return []

        headers = list(self.header_pattern.finditer(text))
        header_positions = {h.start() for h in headers}

        if not headers:
            if self.count_tokens(text) <= self.max_tokens:
                return [self._create_chunk(text, 0, len(text), 0)]
            return ParagraphChunker(self.max_tokens, 0, counter=self.counter).chunk(text)

        chunks: List[TextChunk] = []
        chunk_index = 0
        current_pos = 0

        while current_pos < len(text):
            chunk_start = current_pos
            chunk_end = current_pos
            chunk_tokens = 0
            last_good_break = current_pos

            while chunk_end < len(text):
                next_newline = text.find("\n", chunk_end + 1)
                next_break = len(text) if next_newline == -1 else next_newline + 1

                test_tokens = self.count_tokens(text[chunk_start:next_break])
                if test_tokens > self.max_tokens:
                    if chunk_tokens == 0:
                        chunk_end = self._break_oversized_segment(
                            text, chunk_start, chunk_end, next_break, header_positions
                        )
                    elif chunk_end in header_positions and last_good_break > chunk_start:
                        chunk_end = last_good_break
                    else:
                        chunk_end = last_good_break
                    break

                chunk_tokens = test_tokens
                last_good_break = next_break
                chunk_end = next_break

                if chunk_end in header_positions:
                    next_header_pos = next((h.start() for h in headers if h.start() > chunk_end), len(text))
                    section_text = text[chunk_end:next_header_pos]
                    if chunk_tokens + self.count_tokens(section_text) <= self.max_tokens:
                        chunk_end = next_header_pos
                        chunk_tokens = self.count_tokens(text[chunk_start:chunk_end])
                    else:
                        break

            if chunk_end > chunk_start:
                chunks.append(self._create_chunk(text, chunk_start, chunk_end, chunk_index))
                chunk_index += 1
                current_pos = chunk_end
            else:
                current_pos = min(current_pos + 1, len(text))

        return self._ensure_chunks_within_limit(chunks, text)

    def _break_oversized_segment(
        self, text: str, chunk_start: int, chunk_end: int, next_break: int, header_positions: set[int]
    ) -> int:
        """Find a break point inside a first segment that already exceeds the budget."""
        if chunk_end in header_positions:
            header_end_nl = text.find("\n", chunk_end)
            header_end = len(text) if header_end_nl == -1 else header_end_nl + 1
            search_start = header_end
            new_end = chunk_start
            while search_start < len(text):
                search_end_nl = text.find("\n", search_start)
                search_end = len(text) if search_end_nl == -1 else search_end_nl + 1
                if self.count_tokens(text[chunk_start:search_end]) <= self.max_tokens:
                    new_end = search_end
                    search_start = search_end
                else:
                    break
            return new_end if new_end != chunk_start else header_end

        words = text[chunk_start:next_break].split()
        accumulated: list[str] = []
        for word in words:
            accumulated.append(word)
            if self.count_tokens(" ".join(accumulated)) > self.max_tokens:
                accumulated.pop()
                break
        if accumulated:
            return chunk_start + len(" ".join(accumulated))
        return next_break


class CodeBlockChunker(PositionTrackingChunker):
    """Chunk code while preserving logical (function/class/bracket) blocks."""

    def __init__(
        self, max_tokens: int = 500, overlap: int = 0, *, counter: TokenCounter, language: Optional[str] = None
    ) -> None:
        """Construct a code chunker, optionally pinning the language (else auto-detected)."""
        super().__init__(max_tokens, overlap, counter=counter)
        self.language = language

    def chunk(self, text: str) -> List[TextChunk]:
        """Split code into chunks that respect detected block boundaries."""
        if not text.strip():
            return []
        if self.count_tokens(text) <= self.max_tokens:
            return [self._create_chunk(text, 0, len(text), 0)]

        if not self.language:
            self.language = self._detect_language(text)

        lines = text.splitlines()
        start_patterns, end_patterns = self._get_language_patterns(self.language)
        blocks = self._identify_code_blocks(lines, self.language, start_patterns, end_patterns)
        chunks = self._create_chunks_from_blocks(text, lines, blocks)
        return self._ensure_chunks_within_limit(chunks, text)

    def _detect_language(self, text: str) -> str:
        """Heuristically detect the programming language from a sample."""
        sample = text[:1000]
        signatures: Dict[str, Dict[str, List[str]]] = {
            "python": {
                "patterns": [
                    r"^\s*def\s+\w+\s*\(.*\):",
                    r"^\s*class\s+\w+(\s*\(.*\))?:",
                    r"^\s*import\s+\w+",
                    r"^\s*from\s+[\w\.]+\s+import",
                    r"^\s*@\w+",
                ],
                "keywords": ["def", "class", "import", "from", "with", "as", "if", "elif", "else", "for", "while"],
            },
            "javascript": {
                "patterns": [
                    r"function\s+\w+\s*\(.*\)\s*{",
                    r"const\s+\w+\s*=",
                    r"let\s+\w+\s*=",
                    r"var\s+\w+\s*=",
                    r"import\s+.*\s+from",
                    r"=>",
                ],
                "keywords": ["function", "const", "let", "var", "import", "export", "class", "return"],
            },
            "java": {
                "patterns": [
                    r"public\s+class",
                    r"private\s+\w+[\s\w]*\(.*\)\s*{",
                    r"protected\s+\w+[\s\w]*\(.*\)\s*{",
                    r"import\s+[\w\.]+;",
                ],
                "keywords": ["public", "private", "protected", "class", "interface", "extends", "implements"],
            },
            "generic": {"patterns": [], "keywords": []},
        }

        scores = dict.fromkeys(signatures, 0)
        for lang, sig in signatures.items():
            for pattern in sig["patterns"]:
                scores[lang] += len(re.findall(pattern, sample, re.MULTILINE)) * 2
            for keyword in sig.get("keywords", []):
                scores[lang] += len(re.findall(r"\b" + keyword + r"\b", sample))

        if "    " in sample and "{" not in sample[:100]:
            scores["python"] += 5
        if "{" in sample and "}" in sample:
            for lang in ("javascript", "java"):
                scores[lang] += 2

        best_lang = max(scores.items(), key=lambda x: x[1])
        return "generic" if best_lang[1] < 3 else best_lang[0]

    def _get_language_patterns(self, language: str) -> Tuple[List[str], List[str]]:
        """Return ``(start_patterns, end_patterns)`` for ``language``."""
        patterns = {
            "python": {
                "starts": [
                    r"^\s*def\s+\w+\s*\(.*\):",
                    r"^\s*class\s+\w+(\s*\(.*\))?:",
                    r"^\s*if\s+.*:",
                    r"^\s*while\s+.*:",
                    r"^\s*for\s+.*:",
                    r"^\s*try:",
                    r"^\s*except.*:",
                    r"^\s*with.*:",
                ],
                "ends": [],
            },
            "javascript": {
                "starts": [
                    r"function\s+\w+\s*\(.*\)\s*{",
                    r"class\s+\w+(\s+extends\s+\w+)?\s*{",
                    r"if\s*\(.*\)\s*{",
                    r"for\s*\(.*\)\s*{",
                    r"while\s*\(.*\)\s*{",
                ],
                "ends": [r"^(\s*)\}"],
            },
            "java": {
                "starts": [
                    r"(public|private|protected)?\s*\w+(\s+\w+)?\s*\(.*\)\s*{",
                    r"class\s+\w+(\s+extends\s+\w+)?(\s+implements\s+[\w,\s]+)?\s*{",
                    r"interface\s+\w+\s*{",
                    r"if\s*\(.*\)\s*{",
                    r"for\s*\(.*\)\s*{",
                    r"while\s*\(.*\)\s*{",
                ],
                "ends": [r"^(\s*)\}"],
            },
            "generic": {
                "starts": [
                    r"^\s*\w+\s*\(.*\)\s*{",
                    r"^\s*class\s+\w+\s*{",
                    r"^\s*if\s*\(.*\)\s*{",
                    r"^\s*for\s*\(.*\)\s*{",
                    r"^\s*while\s*\(.*\)\s*{",
                ],
                "ends": [r"^(\s*)\}", r"^(\s*)end"],
            },
        }
        lang_patterns = patterns.get(language, patterns["generic"])
        return lang_patterns["starts"], lang_patterns["ends"]

    @staticmethod
    def _identify_code_blocks(
        lines: List[str], language: str, start_patterns: List[str], end_patterns: List[str]
    ) -> List[Dict[str, Any]]:
        """Identify code blocks via indentation (Python) or bracket depth."""
        blocks: List[Dict[str, Any]] = []
        i = 0

        if language == "python":
            while i < len(lines):
                block_start = None
                for pattern in start_patterns:
                    if re.match(pattern, lines[i]):
                        block_start = i
                        break
                if block_start is not None:
                    indent_match = re.match(r"^(\s*)", lines[i])
                    start_indent = indent_match.group(1) if indent_match else ""
                    j = i + 1
                    while j < len(lines):
                        if not lines[j].strip() or lines[j].strip().startswith("#"):
                            j += 1
                            continue
                        indent_match = re.match(r"^(\s*)", lines[j])
                        current_indent = indent_match.group(1) if indent_match else ""
                        if len(current_indent) <= len(start_indent) and j > i + 1:
                            blocks.append({"start": block_start, "end": j - 1, "type": "block"})
                            i = j - 1
                            break
                        j += 1
                    if j == len(lines):
                        blocks.append({"start": block_start, "end": j - 1, "type": "block"})
                        i = j - 1
                i += 1
        else:
            bracket_stack: list[int] = []
            while i < len(lines):
                line = lines[i]
                opening_brackets = line.count("{")
                closing_brackets = line.count("}")
                is_block_start = False
                for pattern in start_patterns:
                    if re.search(pattern, line):
                        is_block_start = True
                        if not bracket_stack:
                            blocks.append({"start": i, "end": None, "bracket_depth": 1, "type": "block"})
                            bracket_stack.append(len(blocks) - 1)
                        break
                if opening_brackets > 0 and not is_block_start:
                    if not bracket_stack:
                        blocks.append({"start": i, "end": None, "bracket_depth": opening_brackets, "type": "block"})
                        bracket_stack.append(len(blocks) - 1)
                    else:
                        blocks[bracket_stack[-1]]["bracket_depth"] += opening_brackets
                if closing_brackets > 0 and bracket_stack:
                    block_idx = bracket_stack[-1]
                    blocks[block_idx]["bracket_depth"] -= closing_brackets
                    if blocks[block_idx]["bracket_depth"] <= 0:
                        blocks[block_idx]["end"] = i
                        bracket_stack.pop()
                i += 1
            for block_idx in bracket_stack:
                if blocks[block_idx]["end"] is None:
                    blocks[block_idx]["end"] = len(lines) - 1

        covered_lines = set()
        for block in blocks:
            for j in range(block["start"], block["end"] + 1):
                covered_lines.add(j)
        i = 0
        while i < len(lines):
            if i not in covered_lines:
                start = i
                while i < len(lines) and i not in covered_lines:
                    i += 1
                if any(line.strip() for line in lines[start:i]):
                    blocks.append({"start": start, "end": i - 1, "type": "non-block"})
                continue
            i += 1

        blocks.sort(key=lambda x: x["start"])
        return blocks

    def _create_chunks_from_blocks(self, text: str, lines: List[str], blocks: List[Dict[str, Any]]) -> List[TextChunk]:
        """Pack identified blocks into chunks under the token budget."""
        if not blocks:
            return []

        chunks: List[TextChunk] = []
        chunk_index = 0
        current_chunk_lines: list[Dict[str, Any]] = []
        current_tokens = 0

        line_positions = []
        current_pos = 0
        for line in lines:
            line_positions.append(current_pos)
            current_pos += len(line) + 1

        def _finalize(chunk_lines: list[Dict[str, Any]], index: int) -> TextChunk:
            start_pos = line_positions[chunk_lines[0]["line_idx"]]
            end_pos = line_positions[chunk_lines[-1]["line_idx"]] + len(chunk_lines[-1]["line"])
            return self._create_chunk(text, start_pos, end_pos, index)

        for block in blocks:
            block_lines = lines[block["start"] : block["end"] + 1]
            block_text = "\n".join(block_lines)
            block_tokens = self.count_tokens(block_text)

            if block_tokens > self.max_tokens:
                if current_chunk_lines:
                    chunks.append(_finalize(current_chunk_lines, chunk_index))
                    chunk_index += 1
                    current_chunk_lines = []
                    current_tokens = 0
                block_start_pos = line_positions[block["start"]]
                block_end_pos = line_positions[block["end"]] + len(lines[block["end"]])
                large_block_text = text[block_start_pos:block_end_pos]
                line_chunker = LineChunker(self.max_tokens, self.overlap, counter=self.counter)
                for line_chunk in line_chunker.chunk(large_block_text):
                    chunk_start = block_start_pos + large_block_text.index(line_chunk.content)
                    chunk_end = chunk_start + len(line_chunk.content)
                    chunks.append(self._create_chunk(text, chunk_start, chunk_end, chunk_index))
                    chunk_index += 1
                continue

            if current_tokens + block_tokens > self.max_tokens and current_chunk_lines:
                chunks.append(_finalize(current_chunk_lines, chunk_index))
                chunk_index += 1
                if self.overlap > 0 and current_chunk_lines:
                    overlap_lines = min(self.overlap, len(current_chunk_lines))
                    current_chunk_lines = current_chunk_lines[-overlap_lines:]
                    current_tokens = self.count_tokens("\n".join(ln["line"] for ln in current_chunk_lines))
                else:
                    current_chunk_lines = []
                    current_tokens = 0

            for offset, line in enumerate(block_lines):
                current_chunk_lines.append({"line": line, "line_idx": block["start"] + offset})
            current_tokens = self.count_tokens("\n".join(ln["line"] for ln in current_chunk_lines))

        if current_chunk_lines:
            chunks.append(_finalize(current_chunk_lines, chunk_index))

        return [chunk for chunk in chunks if chunk.content.strip()]


class ChunkerFactory:
    """Construct chunkers by name."""

    CHUNKERS: dict[str, Type[PositionTrackingChunker]] = {
        "sentences": SentenceChunker,
        "tokens": TokenChunker,
        "words": WordChunker,
        "lines": LineChunker,
        "characters": CharChunker,
        "paragraphs": ParagraphChunker,
        "sections": SectionChunker,
        "code-blocks": CodeBlockChunker,
    }

    @classmethod
    def create_chunker(
        cls,
        method: Union[str, Type[PositionTrackingChunker]],
        max_tokens: int = 500,
        overlap: int = 0,
        *,
        counter: TokenCounter,
        **kwargs: Any,
    ) -> PositionTrackingChunker:
        """Create a chunker instance for ``method`` with the given counter."""
        if isinstance(method, type) and issubclass(method, PositionTrackingChunker):
            return method(max_tokens, overlap=overlap, counter=counter, **kwargs)
        if not isinstance(method, str):
            raise TypeError(f"`method` must be str or PositionTrackingChunker, found: {type(method)}")
        if method not in cls.CHUNKERS:
            raise ValueError(f"Unknown chunking method: {method}. Available: {', '.join(cls.CHUNKERS)}")
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            raise ValueError(f"`max_tokens` must be a positive integer, found: {max_tokens}")

        chunker_class = cls.CHUNKERS[method]
        if method == "sections":
            return chunker_class(max_tokens, overlap=0, counter=counter, **kwargs)
        return chunker_class(max_tokens, overlap=overlap, counter=counter, **kwargs)

    @classmethod
    def list_methods(cls) -> List[str]:
        """List available chunking method names."""
        return list(cls.CHUNKERS.keys())


def reconstruct_document(chunks: List[TextChunk], original_length: int) -> str:
    """Reassemble the original text from non-overlapping ``chunks``."""
    if not chunks:
        return ""
    sorted_chunks = sorted(chunks, key=lambda c: c.position.start)
    result = [""] * original_length
    for chunk in sorted_chunks:
        start = chunk.position.start
        end = min(chunk.position.end, original_length)
        if start < original_length:
            result[start:end] = list(chunk.content[: end - start])
    return "".join(result)
