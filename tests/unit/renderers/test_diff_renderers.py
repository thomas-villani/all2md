"""Unit tests for diff renderers."""

from __future__ import annotations

import json

import pytest

from all2md.ast.nodes import Document, Paragraph, Text
from all2md.diff.renderers.html import HtmlDiffRenderer
from all2md.diff.renderers.json import JsonDiffRenderer
from all2md.diff.text_diff import compare_documents


@pytest.fixture()
def diff_documents() -> tuple[Document, Document]:
    """Provide a pair of documents with simple inline changes."""
    doc_old = Document(children=[Paragraph(content=[Text("Line one."), Text(" Line two.")])])
    doc_new = Document(
        children=[
            Paragraph(content=[Text("Line one."), Text(" Updated line two.")]),
            Paragraph(content=[Text("New third line.")]),
        ]
    )
    return doc_old, doc_new


def test_html_renderer_renders_summary_and_lines(diff_documents: tuple[Document, Document]) -> None:
    """HTML renderer should include summary, numbering, and change highlights."""
    old_doc, new_doc = diff_documents
    diff_result = compare_documents(old_doc, new_doc, granularity="sentence")

    renderer = HtmlDiffRenderer()
    html_output = renderer.render(diff_result)

    assert "<div class='diff-summary'>" in html_output
    assert "Lines added" in html_output
    assert "inline-line inline-added" in html_output
    assert "line-number" in html_output


def test_html_renderer_collapses_context_when_disabled(diff_documents: tuple[Document, Document]) -> None:
    """Setting show_context to False should wrap unchanged blocks in <details>."""
    old_doc, new_doc = diff_documents
    diff_result = compare_documents(old_doc, new_doc)

    renderer = HtmlDiffRenderer(show_context=False)
    html_output = renderer.render(diff_result)

    assert "diff-context-collapsed" in html_output


def test_json_renderer_includes_metadata(diff_documents: tuple[Document, Document]) -> None:
    """JSON renderer should surface structural metadata when given DiffResult."""
    old_doc, new_doc = diff_documents
    diff_result = compare_documents(old_doc, new_doc)

    renderer = JsonDiffRenderer()
    payload = renderer.render(diff_result)
    data = json.loads(payload)

    assert data["granularity"] == "block"
    assert data["context_lines"] == 3
    assert data["statistics"]["lines_added"] > 0
    assert data["statistics"]["lines_deleted"] > 0
