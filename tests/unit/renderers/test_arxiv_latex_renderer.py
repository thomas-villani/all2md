#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/renderers/test_arxiv_latex_renderer.py
"""Unit tests for the ArXiv LaTeX renderer.

Tests cover:
- Figure environment generation
- Data URI extraction
- Figure counter
- Caption escaping
- Document class options in preamble
- Extracted figures list
"""

import base64

import pytest

from all2md.ast import Document, Image, Paragraph, Text
from all2md.options.arxiv import ArxivPackagerOptions
from all2md.renderers.arxiv_latex import ArxivLatexRenderer, ExtractedFigure


@pytest.mark.unit
class TestArxivLatexRenderer:
    """Tests for ArxivLatexRenderer."""

    def test_image_renders_figure_environment(self):
        """Image nodes should produce full figure environments."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="photo.png", alt_text="A photo"),
                    ]
                ),
            ]
        )
        renderer = ArxivLatexRenderer()
        result = renderer.render_to_string(doc)

        assert "\\begin{figure}[htbp]" in result
        assert "\\centering" in result
        assert "\\includegraphics[width=\\textwidth]{figures/fig1.png}" in result
        assert "\\caption{A photo}" in result
        assert "\\label{fig:figure1}" in result
        assert "\\end{figure}" in result

    def test_data_uri_extraction(self):
        """Data URI images should be extracted with decoded bytes."""
        # Create a minimal valid PNG-like data URI
        fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
        data_uri = f"data:image/png;base64,{fake_png}"

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url=data_uri, alt_text="Extracted"),
                    ]
                ),
            ]
        )
        renderer = ArxivLatexRenderer()
        renderer.render_to_string(doc)

        assert len(renderer.extracted_figures) == 1
        fig = renderer.extracted_figures[0]
        assert fig.data is not None
        assert fig.filename == "figures/fig1.png"
        assert fig.alt_text == "Extracted"
        assert fig.figure_number == 1

    def test_figure_counter_increments(self):
        """Each image should get a unique figure number."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="img1.png", alt_text="First"),
                    ]
                ),
                Paragraph(
                    content=[
                        Image(url="img2.jpg", alt_text="Second"),
                    ]
                ),
            ]
        )
        renderer = ArxivLatexRenderer()
        result = renderer.render_to_string(doc)

        assert len(renderer.extracted_figures) == 2
        assert renderer.extracted_figures[0].figure_number == 1
        assert renderer.extracted_figures[1].figure_number == 2
        assert "\\label{fig:figure1}" in result
        assert "\\label{fig:figure2}" in result

    def test_caption_escaping(self):
        """Special LaTeX characters in captions should be escaped."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="img.png", alt_text="Price is $10 & 20%"),
                    ]
                ),
            ]
        )
        renderer = ArxivLatexRenderer()
        result = renderer.render_to_string(doc)

        assert r"Price is \$10 \& 20\%" in result

    def test_no_caption_when_alt_empty(self):
        """No caption line should be emitted when alt_text is empty."""
        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="img.png", alt_text=""),
                    ]
                ),
            ]
        )
        renderer = ArxivLatexRenderer()
        result = renderer.render_to_string(doc)

        assert "\\caption" not in result
        assert "\\label{fig:figure1}" in result

    def test_document_class_options_in_preamble(self):
        """Document class options should appear in the preamble."""
        arxiv_opts = ArxivPackagerOptions(document_class_options=["twocolumn", "12pt"])
        renderer = ArxivLatexRenderer(arxiv_options=arxiv_opts)

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Hello")]),
            ]
        )
        result = renderer.render_to_string(doc)

        assert "\\documentclass[twocolumn,12pt]{article}" in result

    def test_default_preamble_no_class_options(self):
        """Without class options, preamble should use plain documentclass."""
        renderer = ArxivLatexRenderer()
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Hello")]),
            ]
        )
        result = renderer.render_to_string(doc)

        assert "\\documentclass{article}" in result

    def test_packages_in_preamble(self):
        """Default ArXiv packages should appear in preamble."""
        renderer = ArxivLatexRenderer()
        doc = Document(
            children=[
                Paragraph(content=[Text(content="Hello")]),
            ]
        )
        result = renderer.render_to_string(doc)

        assert "\\usepackage{amsmath}" in result
        assert "\\usepackage{graphicx}" in result
        assert "\\usepackage{hyperref}" in result

    def test_custom_figure_dir(self):
        """Custom figure directory should be used in paths."""
        arxiv_opts = ArxivPackagerOptions(figure_dir="images")
        renderer = ArxivLatexRenderer(arxiv_options=arxiv_opts)

        doc = Document(
            children=[
                Paragraph(
                    content=[
                        Image(url="photo.png", alt_text="Photo"),
                    ]
                ),
            ]
        )
        renderer.render_to_string(doc)

        assert renderer.extracted_figures[0].filename == "images/fig1.png"

    def test_render_resets_state(self):
        """Calling render_to_string again should reset figures and counter."""
        renderer = ArxivLatexRenderer()

        doc = Document(
            children=[
                Paragraph(content=[Image(url="a.png", alt_text="A")]),
            ]
        )
        renderer.render_to_string(doc)
        assert len(renderer.extracted_figures) == 1

        renderer.render_to_string(doc)
        assert len(renderer.extracted_figures) == 1
        assert renderer.extracted_figures[0].figure_number == 1


@pytest.mark.unit
class TestExtractedFigure:
    """Tests for the ExtractedFigure dataclass."""

    def test_create(self):
        fig = ExtractedFigure(
            filename="figures/fig1.png",
            data=b"fake",
            original_url="http://example.com/img.png",
            alt_text="A figure",
            figure_number=1,
        )
        assert fig.filename == "figures/fig1.png"
        assert fig.data == b"fake"
        assert fig.figure_number == 1

    def test_none_data(self):
        fig = ExtractedFigure(
            filename="figures/fig2.png",
            data=None,
            original_url="missing.png",
            alt_text="",
            figure_number=2,
        )
        assert fig.data is None
