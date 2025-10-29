"""Golden tests for renderer outputs across supported formats."""

from __future__ import annotations

import pytest

from all2md.ast import Document
from all2md.ast.nodes import (
    Comment,
    CommentInline,
    DefinitionDescription,
    DefinitionList,
    DefinitionTerm,
    Heading,
    Link,
    MathBlock,
    MathInline,
    Paragraph,
    Strong,
    Table,
    TableCell,
    TableRow,
    Text,
)
from all2md.renderers.asciidoc import AsciiDocRenderer
from all2md.renderers.latex import LatexRenderer
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer


def _build_renderer_document() -> Document:
    """Return an AST document exercising comments, math, tables, and def-lists."""
    return Document(
        metadata={"title": "Renderer Sample", "author": "Golden Bot", "date": "2025-01-01"},
        children=[
            Comment(
                content="Reviewer note: ensure consistent tone across sections.",
                metadata={"comment_type": "html", "author": "Reviewer", "date": "2025-01-01"},
            ),
            Heading(level=1, content=[Text(content="Renderer Showcase")]),
            Paragraph(
                content=[
                    Text(content="Inline math such as "),
                    MathInline(content="E = mc^2"),
                    Text(content=" pairs with "),
                    Strong(content=[Text(content="bold emphasis")]),
                    Text(content=" and a link to "),
                    Link(url="https://example.com", content=[Text(content="Example")], title="Example Site"),
                    Text(content="."),
                    CommentInline(
                        content="Consider expanding this introduction.",
                        metadata={"comment_type": "docx_review", "author": "Reviewer"},
                    ),
                ]
            ),
            MathBlock(content="\\int_0^1 x^2\\,dx = \\frac{1}{3}"),
            DefinitionList(
                items=[
                    (
                        DefinitionTerm(content=[Text(content="Pipeline")]),
                        [
                            DefinitionDescription(
                                content=[
                                    Paragraph(
                                        content=[Text(content="Processes sources into a shared AST for rendering.")]
                                    )
                                ]
                            )
                        ],
                    ),
                    (
                        DefinitionTerm(content=[Text(content="Renderer")]),
                        [
                            DefinitionDescription(
                                content=[
                                    Paragraph(
                                        content=[
                                            Text(content="Produces target format while honoring "),
                                            Strong(content=[Text(content="comments")]),
                                            Text(content=" and math."),
                                        ]
                                    )
                                ]
                            )
                        ],
                    ),
                ]
            ),
            Table(
                caption="Key Metrics",
                header=TableRow(
                    cells=[
                        TableCell(content=[Text(content="Metric")]),
                        TableCell(content=[Text(content="Value")]),
                    ],
                    is_header=True,
                ),
                rows=[
                    TableRow(
                        cells=[
                            TableCell(content=[Text(content="Velocity")]),
                            TableCell(content=[Text(content="22.5 m/s")]),
                        ]
                    ),
                    TableRow(
                        cells=[
                            TableCell(content=[Text(content="Acceleration")]),
                            TableCell(content=[Text(content="9.8 m/s^2")]),
                        ]
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def renderer_sample_document() -> Document:
    """Provide a reusable complex AST document for renderer golden tests."""
    return _build_renderer_document()


@pytest.mark.golden
@pytest.mark.unit
class TestAsciiDocRendererGolden:
    """Snapshot tests for the AsciiDoc renderer."""

    def test_asciidoc_renderer_complex_document(self, snapshot, renderer_sample_document):
        renderer = AsciiDocRenderer()
        output = renderer.render_to_string(renderer_sample_document)
        assert output == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestLatexRendererGolden:
    """Snapshot tests for the LaTeX renderer."""

    def test_latex_renderer_complex_document(self, snapshot, renderer_sample_document):
        renderer = LatexRenderer()
        output = renderer.render_to_string(renderer_sample_document)
        assert output == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestMediaWikiRendererGolden:
    """Snapshot tests for the MediaWiki renderer."""

    def test_mediawiki_renderer_complex_document(self, snapshot, renderer_sample_document):
        renderer = MediaWikiRenderer()
        output = renderer.render_to_string(renderer_sample_document)
        assert output == snapshot


@pytest.mark.golden
@pytest.mark.unit
class TestMarkdownRendererGolden:
    """Snapshot tests for the Markdown renderer."""

    def test_markdown_renderer_complex_document(self, snapshot, renderer_sample_document):
        renderer = MarkdownRenderer()
        output = renderer.render_to_string(renderer_sample_document)
        assert output == snapshot
