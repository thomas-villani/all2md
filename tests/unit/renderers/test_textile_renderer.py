#  Copyright (c) 2025 Tom Villani, Ph.D.
"""Unit tests for Textile renderer."""

from all2md.ast import (
    Comment,
    CommentInline,
    Document,
    Paragraph,
    Text,
)
from all2md.renderers.textile import TextileRenderer


class TestTextileRendererComments:
    """Tests for Textile renderer comment support."""

    def test_render_comment_block(self) -> None:
        """Test rendering block-level comment."""
        doc = Document(children=[Comment(content="This is a comment")])
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- This is a comment -->" in output

    def test_render_comment_block_with_metadata(self) -> None:
        """Test rendering block-level comment with author and date metadata."""
        doc = Document(
            children=[
                Comment(
                    content="This is a comment",
                    metadata={"author": "John Doe", "date": "2025-01-15", "label": "1"},
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- Comment 1 by John Doe (2025-01-15): This is a comment -->" in output

    def test_render_comment_inline(self) -> None:
        """Test rendering inline comment."""
        doc = Document(
            children=[
                Paragraph(
                    content=[Text(content="Some text "), CommentInline(content="inline comment"), Text(content=" more text")]
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- inline comment -->" in output
        assert "Some text" in output
        assert "more text" in output

    def test_render_comment_inline_with_metadata(self) -> None:
        """Test rendering inline comment with author metadata."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Some text "),
                        CommentInline(content="needs review", metadata={"author": "Jane Smith"}),
                        Text(content=" more text"),
                    ]
                )
            ]
        )
        renderer = TextileRenderer()
        output = renderer.render_to_string(doc)

        assert "<!-- [Comment by Jane Smith: needs review] -->" in output
