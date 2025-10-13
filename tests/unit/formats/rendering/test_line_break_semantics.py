#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/test_line_break_semantics.py
"""Unit tests for line break semantics across all renderers.

Tests verify that soft and hard line breaks are rendered correctly
according to each format's specification:
- Soft breaks: space (except Markdown which uses newline)
- Hard breaks: format-specific syntax

"""

import pytest

from all2md.ast import Document, LineBreak, Paragraph, Text
from all2md.options import (
    AsciiDocRendererOptions,
    HtmlRendererOptions,
    LatexRendererOptions,
    MarkdownOptions,
    MediaWikiOptions,
    RstRendererOptions,
)
from all2md.renderers.asciidoc import AsciiDocRenderer
from all2md.renderers.html import HtmlRenderer
from all2md.renderers.latex import LatexRenderer
from all2md.renderers.markdown import MarkdownRenderer
from all2md.renderers.mediawiki import MediaWikiRenderer
from all2md.renderers.rst import RestructuredTextRenderer as RstRenderer


@pytest.mark.unit
class TestLineBreakSemantics:
    """Test line break rendering across all renderers."""

    def test_asciidoc_soft_break(self) -> None:
        """Test AsciiDoc soft break renders as space."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer(AsciiDocRendererOptions())
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in AsciiDoc
        assert "Line 1 Line 2" in result
        # Should not contain newline between the lines
        assert "Line 1\nLine 2" not in result

    def test_asciidoc_hard_break(self) -> None:
        """Test AsciiDoc hard break renders with ' +\\n'."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = AsciiDocRenderer(AsciiDocRendererOptions())
        result = renderer.render_to_string(doc)
        # Hard breaks should render as space-plus-newline in AsciiDoc
        assert "Line 1 +\nLine 2" in result

    def test_html_soft_break(self) -> None:
        """Test HTML soft break renders as space."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in HTML
        assert "Line 1 Line 2" in result
        # Should not have <br> tag
        assert "<br>" not in result

    def test_html_hard_break(self) -> None:
        """Test HTML hard break renders with <br>."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        # Hard breaks should render as <br> tag
        assert "Line 1<br>" in result
        assert "Line 2" in result

    def test_markdown_soft_break(self) -> None:
        """Test Markdown soft break renders as newline."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer(MarkdownOptions())
        result = renderer.render_to_string(doc)
        # Soft breaks should render as newline in Markdown
        assert "Line 1\nLine 2" in result
        # Should not have two spaces before newline
        assert "Line 1  \n" not in result

    def test_markdown_hard_break(self) -> None:
        """Test Markdown hard break renders with two spaces and newline."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = MarkdownRenderer(MarkdownOptions())
        result = renderer.render_to_string(doc)
        # Hard breaks should render as two-space-newline in Markdown
        assert "Line 1  \nLine 2" in result

    def test_rst_soft_break(self) -> None:
        """Test RST soft break renders as space."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = RstRenderer(RstRendererOptions())
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in RST
        assert "Line 1 Line 2" in result

    def test_rst_hard_break(self) -> None:
        """Test RST hard break renders with line block syntax."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = RstRenderer(RstRendererOptions())
        result = renderer.render_to_string(doc)
        # Hard breaks should render with newline-pipe-space in RST
        assert "\n| " in result

    def test_latex_soft_break(self) -> None:
        """Test LaTeX soft break renders as space."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = LatexRenderer(LatexRendererOptions())
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in LaTeX
        assert "Line 1 Line 2" in result

    def test_latex_hard_break(self) -> None:
        """Test LaTeX hard break renders with \\\\."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = LatexRenderer(LatexRendererOptions())
        result = renderer.render_to_string(doc)
        # Hard breaks should render as double-backslash in LaTeX
        assert "Line 1\\\\" in result
        assert "Line 2" in result

    def test_mediawiki_soft_break(self) -> None:
        """Test MediaWiki soft break renders as space."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = MediaWikiRenderer(MediaWikiOptions())
        result = renderer.render_to_string(doc)
        # Soft breaks should render as space in MediaWiki
        assert "Line 1 Line 2" in result

    def test_mediawiki_hard_break(self) -> None:
        """Test MediaWiki hard break renders with <br />."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=False),
                        Text(content="Line 2"),
                    ]
                )
            ]
        )
        renderer = MediaWikiRenderer(MediaWikiOptions())
        result = renderer.render_to_string(doc)
        # Hard breaks should render as <br /> in MediaWiki
        assert "Line 1<br />" in result
        assert "Line 2" in result


@pytest.mark.unit
class TestComplexLineBreaks:
    """Test line breaks in complex scenarios."""

    def test_multiple_soft_breaks(self) -> None:
        """Test multiple soft breaks in sequence."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="A"),
                        LineBreak(soft=True),
                        Text(content="B"),
                        LineBreak(soft=True),
                        Text(content="C"),
                    ]
                )
            ]
        )
        # Test AsciiDoc
        renderer = AsciiDocRenderer()
        result = renderer.render_to_string(doc)
        assert "A B C" in result

        # Test HTML
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "A B C" in result

    def test_mixed_breaks(self) -> None:
        """Test mixed soft and hard breaks."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Text(content="Line 1"),
                        LineBreak(soft=True),
                        Text(content="Line 2"),
                        LineBreak(soft=False),
                        Text(content="Line 3"),
                    ]
                )
            ]
        )
        # Test Markdown
        renderer = MarkdownRenderer()
        result = renderer.render_to_string(doc)
        assert "Line 1\nLine 2  \nLine 3" in result

        # Test HTML
        renderer = HtmlRenderer(HtmlRendererOptions(standalone=False))
        result = renderer.render_to_string(doc)
        assert "Line 1 Line 2<br>" in result
        assert "Line 3" in result
