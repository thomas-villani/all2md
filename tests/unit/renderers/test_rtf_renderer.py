"""Unit tests for the RtfRenderer."""

import pytest

try:
    from pyth.plugins.rtf15 import writer  # noqa: F401

    RTF_AVAILABLE = True
except Exception:  # pragma: no cover - dependency guard
    RTF_AVAILABLE = False

from all2md.ast import Comment, CommentInline, Document, Emphasis, Paragraph, Strong, Text
from all2md.options import RtfRendererOptions

if RTF_AVAILABLE:
    from all2md.renderers.rtf import RtfRenderer

pytestmark = pytest.mark.skipif(not RTF_AVAILABLE, reason="pyth3 with six not installed")


@pytest.mark.unit
class TestRtfRendererBasic:
    """Smoke tests for the RTF renderer."""

    def test_render_empty_document_to_string(self) -> None:
        """Render an empty document and ensure RTF header is present."""
        renderer = RtfRenderer()
        output = renderer.render_to_string(Document())
        assert "\\rtf1" in output

    def test_render_formatted_paragraph(self) -> None:
        """Ensure formatted inline nodes appear in the output payload."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Hello "),
                        Strong(content=[Text(content="world")]),
                        Emphasis(content=[Text(content="!")]),
                    ]
                )
            ]
        )
        renderer = RtfRenderer(RtfRendererOptions(font_family="swiss"))
        rtf_output = renderer.render_to_string(doc)
        assert "Hello" in rtf_output
        assert "world" in rtf_output
        assert "!" in rtf_output

    def test_render_block_comment_basic(self) -> None:
        """Render a basic block-level comment."""
        doc = Document(
            children=[
                Comment(content="This is a block comment", metadata={})
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "This is a block comment" in rtf_output

    def test_render_block_comment_with_metadata(self) -> None:
        """Render a block-level comment with author and date metadata."""
        doc = Document(
            children=[
                Comment(
                    content="Review this section",
                    metadata={
                        "author": "John Doe",
                        "date": "2025-01-15",
                        "label": "1"
                    }
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Review this section" in rtf_output
        assert "John Doe" in rtf_output
        assert "2025-01-15" in rtf_output

    def test_render_block_comment_drop_mode(self) -> None:
        """Render a block-level comment with drop render mode."""
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Before comment")]),
                Comment(content="This should be dropped", metadata={"render_mode": "drop"}),
                Paragraph(content=[Text(content="After comment")])
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Before comment" in rtf_output
        assert "After comment" in rtf_output
        assert "This should be dropped" not in rtf_output

    def test_render_inline_comment_basic(self) -> None:
        """Render a basic inline comment."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Before "),
                        CommentInline(content="inline comment", metadata={}),
                        Text(content=" after")
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Before" in rtf_output
        assert "inline comment" in rtf_output
        assert "after" in rtf_output

    def test_render_inline_comment_with_metadata(self) -> None:
        """Render an inline comment with author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Text with "),
                        CommentInline(
                            content="annotated section",
                            metadata={
                                "author": "Jane Smith",
                                "label": "2"
                            }
                        ),
                        Text(content=" here")
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "annotated section" in rtf_output
        assert "Jane Smith" in rtf_output

    def test_render_inline_comment_drop_mode(self) -> None:
        """Render an inline comment with drop render mode."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Start "),
                        CommentInline(content="dropped", metadata={"render_mode": "drop"}),
                        Text(content="end")
                    ]
                )
            ]
        )
        renderer = RtfRenderer()
        rtf_output = renderer.render_to_string(doc)
        assert "Start" in rtf_output
        assert "end" in rtf_output
        assert "dropped" not in rtf_output
