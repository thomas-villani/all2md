from __future__ import annotations

from pathlib import Path

import pytest

from all2md.ast import Heading, Image, Paragraph, ThematicBreak
from all2md.ast.utils import extract_text
from all2md.options.fb2 import Fb2Options
from all2md.parsers.fb2 import Fb2ToAstConverter

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "fb2"


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
        (node for node in document.children if isinstance(node, Paragraph) and any(isinstance(child, Image) for child in node.content)),
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
        (node for node in document.children if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"),
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
        node for node in document.children if isinstance(node, Heading) and extract_text(node, joiner=" ").strip() == "Notes"
    ]
    assert not notes_heading
    assert not any(isinstance(node, ThematicBreak) for node in document.children)
