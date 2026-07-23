from __future__ import annotations

from pathlib import Path

import pytest

from all2md.ast import Heading, Image, Paragraph, ThematicBreak
from all2md.ast.utils import extract_text
from all2md.options.fb2 import Fb2Options
from all2md.parsers.fb2 import Fb2ToAstConverter

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "documents"


@pytest.fixture(scope="module")
def sample_fb2_path() -> Path:
    return FIXTURE_DIR / "sample.fb2"


@pytest.fixture(scope="module")
def sample_fb2_zip_path() -> Path:
    return FIXTURE_DIR / "sample.fb2.zip"


def test_fb2_parse_basic_structure(sample_fb2_path: Path) -> None:
    parser = Fb2ToAstConverter()
    document = parser.parse(sample_fb2_path)

    headings = [node for node in document.children if isinstance(node, Heading)]
    assert headings, "Expected at least one heading in parsed FB2 document"

    first_heading_text = extract_text(headings[0], joiner=" ").strip()
    assert first_heading_text == "Chapter One"

    intro_heading = next((h for h in headings if extract_text(h, joiner=" ").strip() == "Introduction"), None)
    assert intro_heading is not None
    assert intro_heading.level == 2

    image_paragraph = next(
        (
            node
            for node in document.children
            if isinstance(node, Paragraph) and any(isinstance(child, Image) for child in node.content)
        ),
        None,
    )
    assert image_paragraph is not None
    image_node = next(child for child in image_paragraph.content if isinstance(child, Image))
    assert image_node.alt_text == "Cover image"
    assert image_node.metadata.get("content_type") == "image/png"


def test_fb2_metadata_extraction(sample_fb2_path: Path) -> None:
    parser = Fb2ToAstConverter()
    document = parser.parse(sample_fb2_path)

    metadata = document.metadata
    assert metadata["title"] == "Sample FB2 Book"
    assert metadata["author"] == "Jane Doe"
    assert metadata["language"] == "en"
    assert metadata["description"].startswith("This is a sample FB2 file")
    assert metadata["keywords"] == ["sample", "fb2", "testing"]
    assert metadata["identifier"] == "urn:uuid:1234-5678-test"


def test_fb2_zip_support(sample_fb2_zip_path: Path) -> None:
    parser = Fb2ToAstConverter()
    document = parser.parse(sample_fb2_zip_path)
    assert any(isinstance(node, Heading) for node in document.children)


def test_fb2_notes_section_included_by_default(sample_fb2_path: Path) -> None:
    parser = Fb2ToAstConverter()
    document = parser.parse(sample_fb2_path)

    notes_heading = next(
        (
            node
            for node in document.children
            if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"
        ),
        None,
    )
    assert notes_heading is not None

    notes_index = document.children.index(notes_heading)
    assert isinstance(document.children[notes_index - 1], ThematicBreak)
    notes_paragraph = document.children[notes_index + 1]
    assert isinstance(notes_paragraph, Paragraph)
    assert "Second note" in extract_text(notes_paragraph, joiner=" ")


def test_fb2_can_exclude_notes(sample_fb2_path: Path) -> None:
    options = Fb2Options(include_notes=False)
    parser = Fb2ToAstConverter(options=options)
    document = parser.parse(sample_fb2_path)

    notes_heading = [
        node
        for node in document.children
        if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"
    ]
    assert not notes_heading
    assert not any(isinstance(node, ThematicBreak) for node in document.children)


def test_fb2_notes_body_without_title_keeps_section_headings() -> None:
    fb2 = b"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <description>
    <title-info>
      <book-title>Notes Title Bug</book-title>
    </title-info>
  </description>
  <body>
    <section>
      <title><p>Chapter</p></title>
      <p>Main text.</p>
    </section>
  </body>
  <body name="notes" type="notes">
    <section id="n1">
      <title><p>Footnote 1</p></title>
      <p>Citation text here</p>
    </section>
    <section id="n2">
      <title><p>Footnote 2</p></title>
      <p>Second note</p>
    </section>
  </body>
</FictionBook>
"""
    document = Fb2ToAstConverter().parse(fb2)
    heading_texts = [extract_text(node, joiner=" ").strip() for node in document.children if isinstance(node, Heading)]
    assert "Notes" in heading_texts
    assert "Footnote 1" in heading_texts
    assert "Footnote 2" in heading_texts
    notes_index = next(
        i
        for i, node in enumerate(document.children)
        if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"
    )
    footnote_one = document.children[notes_index + 1]
    assert isinstance(footnote_one, Heading)
    assert extract_text(footnote_one, joiner=" ").strip() == "Footnote 1"


def test_fb2_notes_body_with_empty_title_keeps_section_headings() -> None:
    fb2 = b"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <description>
    <title-info>
      <book-title>Notes Empty Title Bug</book-title>
    </title-info>
  </description>
  <body>
    <section>
      <title><p>Chapter</p></title>
      <p>Main text.</p>
    </section>
  </body>
  <body name="notes" type="notes">
    <title><p></p></title>
    <section id="n1">
      <title><p>Footnote 1</p></title>
      <p>Citation text here</p>
    </section>
    <section id="n2">
      <title><p>Footnote 2</p></title>
      <p>Second note</p>
    </section>
  </body>
</FictionBook>
"""
    document = Fb2ToAstConverter().parse(fb2)
    heading_texts = [extract_text(node, joiner=" ").strip() for node in document.children if isinstance(node, Heading)]
    assert "Notes" in heading_texts
    assert "Footnote 1" in heading_texts
    assert "Footnote 2" in heading_texts
    notes_index = next(
        i
        for i, node in enumerate(document.children)
        if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"
    )
    footnote_one = document.children[notes_index + 1]
    assert isinstance(footnote_one, Heading)
    assert extract_text(footnote_one, joiner=" ").strip() == "Footnote 1"


def test_fb2_cite_becomes_blockquote_like_epigraph() -> None:
    """<cite> with body + text-author must be a BlockQuote, not concatenated text."""
    from all2md.ast import BlockQuote

    fb2 = b"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body>
    <section>
      <cite>
        <p>quoted</p>
        <text-author>auth</text-author>
      </cite>
    </section>
  </body>
</FictionBook>
"""
    document = Fb2ToAstConverter().parse(fb2)
    assert len(document.children) == 1
    quote = document.children[0]
    assert isinstance(quote, BlockQuote)
    assert len(quote.children) == 2
    assert isinstance(quote.children[0], Paragraph)
    assert isinstance(quote.children[1], Paragraph)
    assert extract_text(quote.children[0], joiner=" ").strip() == "quoted"
    assert extract_text(quote.children[1], joiner=" ").strip() == "auth"


def test_fb2_epigraph_still_blockquote() -> None:
    """Epigraph sibling path remains a BlockQuote with separate paragraphs."""
    from all2md.ast import BlockQuote

    fb2 = b"""<?xml version="1.0" encoding="utf-8"?>
<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">
  <body>
    <section>
      <epigraph>
        <p>epi</p>
        <text-author>auth</text-author>
      </epigraph>
    </section>
  </body>
</FictionBook>
"""
    document = Fb2ToAstConverter().parse(fb2)
    assert isinstance(document.children[0], BlockQuote)
    assert extract_text(document.children[0].children[0], joiner=" ").strip() == "epi"
    assert extract_text(document.children[0].children[1], joiner=" ").strip() == "auth"
