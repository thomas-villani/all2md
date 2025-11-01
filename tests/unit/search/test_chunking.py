from all2md.ast.nodes import Document, Heading, Paragraph, Text
from all2md.search.chunking import ChunkingContext, chunk_document


def _make_doc() -> Document:
    return Document(
        children=[
            Heading(level=1, content=[Text(content="Title")]),
            Paragraph(content=[Text(content="Section one text.")]),
            Heading(level=2, content=[Text(content="Subheading")]),
            Paragraph(content=[Text(content="Section two text with extra words for chunking.")]),
        ]
    )


def test_chunk_document_creates_section_chunks() -> None:
    doc = _make_doc()
    context = ChunkingContext(document_id="doc-1", document_path=None, metadata={})

    chunks = chunk_document(
        doc,
        context=context,
        chunk_size_tokens=50,
        chunk_overlap_tokens=0,
        min_chunk_tokens=5,
        include_preamble=False,
        heading_merge=True,
        max_heading_level=None,
        progress_callback=None,
    )

    assert len(chunks) == 2
    first_chunk = chunks[0]
    assert "Title" in first_chunk.text
    assert first_chunk.metadata["section_index"] == 1
    assert first_chunk.metadata["chunk_in_section"] == 1

    second_chunk = chunks[1]
    assert "Subheading" in second_chunk.text
    assert second_chunk.metadata["section_index"] == 2


def test_chunk_document_includes_preamble_when_enabled() -> None:
    doc = Document(
        children=[
            Paragraph(content=[Text(content="Preamble text before headings.")]),
            Heading(level=1, content=[Text(content="Intro")]),
            Paragraph(content=[Text(content="Body content.")]),
        ]
    )
    context = ChunkingContext(document_id="doc-2", document_path=None, metadata={})

    chunks = chunk_document(
        doc,
        context=context,
        chunk_size_tokens=20,
        chunk_overlap_tokens=0,
        min_chunk_tokens=3,
        include_preamble=True,
        heading_merge=True,
        max_heading_level=None,
        progress_callback=None,
    )

    assert chunks[0].metadata["section_index"] == -1
    assert "preamble text" in chunks[0].text.lower()
    assert any(chunk.metadata.get("section_index") == 1 for chunk in chunks)
