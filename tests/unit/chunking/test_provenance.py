#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for the AST -> chunk provenance bridge (``chunk_ast``)."""

import pytest

from all2md.ast.nodes import (
    Document,
    Heading,
    Paragraph,
    SourceLocation,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.chunking import chunk_ast
from all2md.chunking.tokenization import tiktoken_available

pytestmark = pytest.mark.unit


def _cell(text):
    """Build a single table cell."""
    return TableCell(content=[Text(content=text)])


def _table(n_rows):
    """Build a small 2-column GFM table with ``n_rows`` body rows."""
    header = TableRow(cells=[_cell("Name"), _cell("Role")])
    rows = [TableRow(cells=[_cell(f"person{i}"), _cell(f"role{i}")]) for i in range(n_rows)]
    return Table(rows=rows, header=header)


@pytest.fixture
def doc():
    """A small document: preamble + two H1 sections."""
    return Document(
        children=[
            Paragraph(content=[Text(content="Preamble text before any heading.")]),
            Heading(level=1, content=[Text(content="Introduction")]),
            Paragraph(content=[Text(content="The introduction explains the motivation and goals.")]),
            Heading(level=1, content=[Text(content="Methods")]),
            Paragraph(content=[Text(content="The methods describe how the study was conducted.")]),
        ]
    )


@pytest.fixture
def paged_doc():
    """A document whose nodes carry PDF-style page provenance."""
    return Document(
        children=[
            Heading(
                level=1,
                content=[Text(content="Chapter")],
                source_location=SourceLocation(format="pdf", page=3),
            ),
            Paragraph(
                content=[Text(content="Body text on a later page of the same section.")],
                source_location=SourceLocation(format="pdf", page=5),
            ),
        ]
    )


class TestFineStrategies:
    """Per-section windowing strategies (count-only here, via whitespace)."""

    @pytest.mark.parametrize("strategy", ["paragraph", "sentence", "word", "line"])
    def test_emits_chunks_with_section_context(self, doc, strategy):
        """Each strategy emits chunks; section chunks carry their heading."""
        chunks = chunk_ast(doc, strategy=strategy, max_tokens=50, token_counter="whitespace", document_id="d")
        assert chunks
        headings = {c.section_heading for c in chunks}
        assert "Introduction" in headings
        assert "Methods" in headings

    def test_preamble_chunk_has_no_section(self, doc):
        """The preamble becomes an unnumbered chunk (section_index -1, no heading)."""
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=50, token_counter="whitespace", document_id="d")
        preamble = chunks[0]
        assert preamble.section_index == -1
        assert preamble.section_heading is None
        assert preamble.chunk_id == "d::preamble-c1"

    def test_include_preamble_false_drops_preamble(self, doc):
        """Disabling preamble omits the pre-heading content."""
        chunks = chunk_ast(
            doc,
            strategy="paragraph",
            max_tokens=50,
            include_preamble=False,
            token_counter="whitespace",
            document_id="d",
        )
        assert all(c.section_index != -1 for c in chunks)

    def test_neighbor_links_and_index(self, doc):
        """Chunks are linked head-to-tail and indexed 0..n-1."""
        chunks = chunk_ast(doc, strategy="word", max_tokens=8, token_counter="whitespace", document_id="d")
        assert chunks[0].prev_chunk_id is None
        assert chunks[-1].next_chunk_id is None
        assert [c.index for c in chunks] == list(range(len(chunks)))
        for i in range(len(chunks) - 1):
            assert chunks[i].next_chunk_id == chunks[i + 1].chunk_id
            assert chunks[i + 1].prev_chunk_id == chunks[i].chunk_id

    def test_heading_merge_toggle(self, doc):
        """With heading-merge off, section text omits the heading line."""
        merged = chunk_ast(doc, strategy="paragraph", max_tokens=200, heading_merge=True, token_counter="whitespace")
        unmerged = chunk_ast(doc, strategy="paragraph", max_tokens=200, heading_merge=False, token_counter="whitespace")
        intro_merged = next(c for c in merged if c.section_heading == "Introduction")
        intro_unmerged = next(c for c in unmerged if c.section_heading == "Introduction")
        assert "Introduction" in intro_merged.text
        assert "Introduction" not in intro_unmerged.text


class TestCoarseStrategies:
    """One-chunk-per-boundary strategies."""

    def test_section_strategy_one_chunk_per_section(self, doc):
        """Section strategy yields a preamble part plus one chunk per heading."""
        chunks = chunk_ast(doc, strategy="section", max_tokens=500, token_counter="whitespace", document_id="d")
        headings = [c.section_heading for c in chunks]
        assert "Introduction" in headings
        assert "Methods" in headings
        assert all(c.chunk_id.startswith("d::p") for c in chunks)

    def test_auto_strategy_runs(self, doc):
        """Auto strategy produces chunks without error."""
        chunks = chunk_ast(doc, strategy="auto", max_tokens=500, token_counter="whitespace", document_id="d")
        assert chunks


class TestProvenanceDerivation:
    """Page/line spans are derived from contributing nodes' source locations."""

    def test_page_span_from_nodes(self, paged_doc):
        """A section spanning pages 3-5 reports page=3, page_end=5."""
        chunks = chunk_ast(paged_doc, strategy="paragraph", max_tokens=500, token_counter="whitespace")
        assert chunks
        assert chunks[0].page == 3
        assert chunks[0].page_end == 5

    def test_no_provenance_when_absent(self, doc):
        """Formats without page info leave page fields None."""
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=50, token_counter="whitespace")
        assert all(c.page is None and c.source_line_start is None for c in chunks)


class TestAvoidTableSplit:
    """Atomic-table handling in the fine path."""

    def _doc_with_table(self):
        """A section containing prose, a big table, then more prose."""
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Data")]),
                Paragraph(content=[Text(content="Intro paragraph with several words to chunk.")]),
                _table(8),
                Paragraph(content=[Text(content="Trailing paragraph after the table here.")]),
            ]
        )

    def test_table_split_without_flag(self):
        """A small token budget shreds the table across multiple chunks by default."""
        doc = self._doc_with_table()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, token_counter="whitespace")
        table_chunks = [c for c in chunks if "|" in c.text]
        assert len(table_chunks) >= 2  # table was fragmented

    def test_table_atomic_with_flag(self):
        """With --avoid-table-split, the whole table is exactly one chunk."""
        doc = self._doc_with_table()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_table_split=True, token_counter="whitespace")
        table_chunks = [c for c in chunks if "|" in c.text]
        assert len(table_chunks) == 1
        # The atomic table chunk legitimately exceeds the token budget.
        assert table_chunks[0].token_count > 8
        # Surrounding prose is still present and chunked.
        assert any("Intro" in c.text for c in chunks)
        assert any("Trailing" in c.text for c in chunks)

    def test_ids_stay_unique_across_segments(self):
        """Segmenting a unit around a table must not produce duplicate chunk ids."""
        doc = self._doc_with_table()
        chunks = chunk_ast(
            doc, strategy="word", max_tokens=6, avoid_table_split=True, token_counter="whitespace", document_id="d"
        )
        ids = [c.chunk_id for c in chunks]
        assert len(ids) == len(set(ids))


class TestEdgeCases:
    """Degenerate documents."""

    def test_headingless_document(self):
        """A document with no headings still chunks (whole-doc unit)."""
        doc = Document(children=[Paragraph(content=[Text(content="lonely paragraph with words")])])
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=50, token_counter="whitespace", document_id="d")
        assert len(chunks) == 1
        assert chunks[0].section_index == -1

    def test_invalid_strategy(self, doc):
        """An unknown strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            chunk_ast(doc, strategy="nope")

    def test_invalid_max_tokens(self, doc):
        """max_tokens < 1 raises ValueError."""
        with pytest.raises(ValueError, match="max_tokens"):
            chunk_ast(doc, strategy="paragraph", max_tokens=0, token_counter="whitespace")


@pytest.mark.skipif(not tiktoken_available(), reason="tiktoken not installed")
class TestSemanticStrategy:
    """The default tiktoken-backed strategy."""

    def test_semantic_respects_token_budget(self, doc):
        """Semantic windows never exceed max_tokens under real tokenization."""
        chunks = chunk_ast(doc, strategy="semantic", max_tokens=16, overlap=2, document_id="d")
        assert chunks
        assert all(c.token_count <= 16 for c in chunks)
        assert all(c.token_counter == "tiktoken" for c in chunks)
