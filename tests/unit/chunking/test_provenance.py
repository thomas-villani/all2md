#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Tests for the AST -> chunk provenance bridge (``chunk_ast``)."""

import pytest

from all2md.ast.nodes import (
    CodeBlock,
    Document,
    Heading,
    Image,
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


class TestAvoidCodeSplit:
    """Atomic code-block handling in the fine path."""

    def _doc_with_code(self):
        """A section containing prose then a multi-line code block."""
        code = "\n".join(f"line_{i} = compute(value_{i}, other_{i})" for i in range(12))
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Code")]),
                Paragraph(content=[Text(content="Intro paragraph before the code block here.")]),
                CodeBlock(content=code, language="python"),
            ]
        )

    def test_code_atomic_with_flag(self):
        """--avoid-code-split keeps the whole code block in one chunk."""
        doc = self._doc_with_code()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_code_split=True, token_counter="whitespace")
        code_chunks = [c for c in chunks if "compute(" in c.text]
        assert len(code_chunks) == 1
        assert code_chunks[0].token_count > 8  # atomic block exceeds the budget

    def test_code_split_without_flag(self):
        """Without the flag, a small budget fragments the code block."""
        doc = self._doc_with_code()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, token_counter="whitespace")
        code_chunks = [c for c in chunks if "compute(" in c.text]
        assert len(code_chunks) >= 2


class TestCharSpansIndexTheSectionText:
    """``char_start``/``char_end`` must mean what ``char_basis`` says they mean.

    Every chunk is stamped ``char_basis="section_text"``: an index into the section's
    rendered Markdown. The segmented path (``avoid_table_split`` / ``avoid_code_split``)
    used to compute its offsets against each *segment's* text instead -- atomic pieces
    got the constant span ``(0, len(text))`` and each prose segment restarted at 0 -- so
    a consumer slicing the section text by those spans got the wrong text for every
    chunk after the first segment, and the spans overlapped.
    """

    def _section_text(self, nodes):
        """The string the spans are documented to index into."""
        from all2md.chunking.provenance import _render_markdown

        return _render_markdown(list(nodes))

    def _doc_with_table(self):
        """A section shaped prose / table / prose."""
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Data")]),
                Paragraph(content=[Text(content="Intro paragraph with several words to chunk.")]),
                _table(8),
                Paragraph(content=[Text(content="Trailing paragraph after the table here.")]),
            ]
        )

    def _doc_with_code(self):
        """A section shaped prose / code / prose."""
        code = "\n".join(f"line_{i} = compute(value_{i}, other_{i})" for i in range(12))
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Code")]),
                Paragraph(content=[Text(content="Intro paragraph before the code block here.")]),
                CodeBlock(content=code, language="python"),
                Paragraph(content=[Text(content="Trailing paragraph after the code here.")]),
            ]
        )

    @pytest.mark.parametrize("strategy", ["paragraph", "word", "line", "sentence"])
    def test_each_span_slices_its_own_text_out_of_the_section(self, strategy):
        doc = self._doc_with_table()
        section_text = self._section_text(doc.children)

        chunks = chunk_ast(doc, strategy=strategy, max_tokens=8, avoid_table_split=True, token_counter="whitespace")

        assert len(chunks) > 1, "this document must segment for the test to mean anything"
        for chunk in chunks:
            assert chunk.char_basis == "section_text"
            assert section_text[chunk.char_start : chunk.char_end] == chunk.text

    def test_spans_advance_and_do_not_overlap(self):
        doc = self._doc_with_table()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_table_split=True, token_counter="whitespace")

        starts = [c.char_start for c in chunks]
        assert starts == sorted(starts)
        for earlier, later in zip(chunks, chunks[1:], strict=False):
            assert later.char_start >= earlier.char_end

    def test_the_atomic_chunk_is_not_pinned_to_zero(self):
        """The atomic piece used to be stamped ``(0, len(text))`` whatever preceded it."""
        doc = self._doc_with_table()
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_table_split=True, token_counter="whitespace")

        table_chunk = next(c for c in chunks if "|" in c.text)
        assert table_chunk.char_start > 0
        assert self._section_text(doc.children)[table_chunk.char_start : table_chunk.char_end] == table_chunk.text

    def test_code_segmentation_too(self):
        doc = self._doc_with_code()
        section_text = self._section_text(doc.children)

        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_code_split=True, token_counter="whitespace")

        assert any("compute(" in c.text for c in chunks)
        for chunk in chunks:
            assert section_text[chunk.char_start : chunk.char_end] == chunk.text

    def test_two_identical_segments_get_different_spans(self):
        """Searching from the previous segment's end keeps repeats in document order."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Twice")]),
                Paragraph(content=[Text(content="Between the first and second copy.")]),
                _table(2),
                Paragraph(content=[Text(content="Between the first and second copy.")]),
                _table(2),
            ]
        )
        section_text = self._section_text(doc.children)

        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_table_split=True, token_counter="whitespace")

        table_chunks = [c for c in chunks if "|" in c.text]
        assert len(table_chunks) == 2
        assert table_chunks[0].char_start != table_chunks[1].char_start
        for chunk in chunks:
            assert section_text[chunk.char_start : chunk.char_end] == chunk.text

    def test_the_unsegmented_path_is_unchanged(self):
        """Control: the path that already honoured the contract still does."""
        doc = self._doc_with_table()
        section_text = self._section_text(doc.children)

        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, token_counter="whitespace")

        for chunk in chunks:
            assert chunk.char_basis == "section_text"
            assert section_text[chunk.char_start : chunk.char_end] == chunk.text

    def test_an_unlocatable_segment_admits_its_basis(self, monkeypatch):
        """Rendering a fragment is not always a substring of rendering the whole.

        Footnote definitions, for one, are collected at the end of whatever document
        they are rendered in. Rather than report a section offset that is wrong, such a
        chunk keeps its segment-relative span and renames the basis.
        """
        from all2md.chunking import provenance

        doc = self._doc_with_table()
        whole = len(doc.children)
        original = provenance._render_markdown

        def render_fragments_differently(nodes, elide_data_uris=True):
            text = original(nodes, elide_data_uris)
            return text if len(nodes) == whole else f"<<<{text}"

        monkeypatch.setattr(provenance, "_render_markdown", render_fragments_differently)
        chunks = chunk_ast(doc, strategy="paragraph", max_tokens=8, avoid_table_split=True, token_counter="whitespace")

        assert chunks
        assert {c.char_basis for c in chunks} == {"segment_text"}
        assert chunks[0].char_start == 0


class TestDataUriElision:
    """Long base64 data URIs are elided from chunk text by default."""

    def _doc_with_data_uri(self):
        """A section whose image is a long base64 data URI."""
        payload = "A" * 200
        return Document(
            children=[
                Heading(level=1, content=[Text(content="Pic")]),
                Paragraph(content=[Text(content="Before image.")]),
                Image(url=f"data:image/png;base64,{payload}", alt_text="x"),
            ]
        )

    def test_elided_by_default(self):
        """The base64 payload is replaced with a short placeholder."""
        doc = self._doc_with_data_uri()
        joined = " ".join(
            c.text for c in chunk_ast(doc, strategy="section", max_tokens=400, token_counter="whitespace")
        )
        assert "AAAA" not in joined
        assert "elided" in joined

    def test_kept_when_disabled(self):
        """elide_data_uris=False leaves the raw base64 in place."""
        doc = self._doc_with_data_uri()
        joined = " ".join(
            c.text
            for c in chunk_ast(
                doc, strategy="section", max_tokens=400, elide_data_uris=False, token_counter="whitespace"
            )
        )
        assert "AAAA" in joined


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


class TestMinTokens:
    """min_tokens drops small chunks and renumbers the survivors."""

    def test_drops_small_chunks_and_reindexes(self, doc):
        """Chunks below the floor are removed; indices/links stay contiguous."""
        unfiltered = chunk_ast(doc, strategy="word", max_tokens=4, token_counter="whitespace")
        assert any(c.token_count < 4 for c in unfiltered)  # there are small chunks to drop

        filtered = chunk_ast(doc, strategy="word", max_tokens=4, min_tokens=4, token_counter="whitespace")
        assert filtered
        assert all(c.token_count >= 4 for c in filtered)
        assert [c.index for c in filtered] == list(range(len(filtered)))
        assert filtered[0].prev_chunk_id is None
        assert filtered[-1].next_chunk_id is None
        for i in range(len(filtered) - 1):
            assert filtered[i].next_chunk_id == filtered[i + 1].chunk_id


@pytest.mark.skipif(not tiktoken_available(), reason="tiktoken not installed")
class TestSemanticStrategy:
    """The default tiktoken-backed strategy."""

    def test_semantic_respects_token_budget(self, doc):
        """Semantic windows never exceed max_tokens under real tokenization."""
        chunks = chunk_ast(doc, strategy="semantic", max_tokens=16, overlap=2, document_id="d")
        assert chunks
        assert all(c.token_count <= 16 for c in chunks)
        assert all(c.token_counter == "tiktoken" for c in chunks)
