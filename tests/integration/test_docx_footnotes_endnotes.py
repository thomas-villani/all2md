"""Integration tests for DOCX footnote and endnote handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from all2md.ast import FootnoteDefinition, FootnoteReference
from all2md.ast.transforms import extract_nodes
from all2md.options import MarkdownOptions
from all2md.options import DocxOptions
from all2md.parsers.docx import DocxToAstConverter
from all2md.renderers.markdown import MarkdownRenderer

FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent / "fixtures" / "documents" / "footnotes-endnotes-comments.docx"
)


@pytest.mark.integration
def test_docx_fixture_contains_expected_notes() -> None:
    """Footnotes and endnotes in fixture should round-trip into the AST and Markdown."""
    converter = DocxToAstConverter(options=DocxOptions(include_comments=False))
    document = converter.parse(FIXTURE_PATH)

    footnote_refs = extract_nodes(document, FootnoteReference)
    definitions = extract_nodes(document, FootnoteDefinition)

    assert footnote_refs, "Expected at least one footnote/endnote reference"
    assert definitions, "Expected collected footnote/endnote definitions"

    ref_ids = {ref.identifier for ref in footnote_refs}
    def_ids = {definition.identifier for definition in definitions}
    assert ref_ids <= def_ids

    metadata_note_types = {definition.metadata.get("note_type") for definition in definitions}
    assert "footnote" in metadata_note_types
    assert "endnote" in metadata_note_types

    renderer = MarkdownRenderer(MarkdownOptions(flavor="pandoc"))
    markdown_output = renderer.render_to_string(document)

    for identifier in ref_ids:
        reference_marker = f"[^{identifier}]"
        definition_marker = f"[^{identifier}]:"
        assert reference_marker in markdown_output
        assert definition_marker in markdown_output


@pytest.mark.integration
def test_docx_inline_comments_render_inline() -> None:
    """DOCX comments render inline when configured."""
    options = DocxOptions(
        include_comments=True,
        comments_position="inline",
        comment_mode="blockquote",
    )
    converter = DocxToAstConverter(options=options)
    document = converter.parse(FIXTURE_PATH)

    markdown_output = MarkdownRenderer(MarkdownOptions(flavor="pandoc")).render_to_string(document)

    assert "I decided not to think of something funny." in markdown_output
    assert "comment1" in markdown_output
    assert "-->" not in markdown_output
