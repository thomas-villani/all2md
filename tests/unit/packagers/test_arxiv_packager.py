#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# tests/unit/packagers/test_arxiv_packager.py
"""Unit tests for the ArXiv submission packager.

Tests cover:
- tar.gz archive generation with correct contents
- Directory output mode
- Bibliography injection
- Figure writing
- Options propagation
"""

import tarfile

import pytest

from all2md.ast import Document, Heading, Image, Paragraph, Text
from all2md.options.arxiv import ArxivPackagerOptions
from all2md.packagers.arxiv import ArxivPackager


@pytest.mark.unit
class TestArxivPackagerTarGz:
    """Tests for tar.gz output mode."""

    def test_basic_targz_contains_main_tex(self, tmp_path):
        """Generated tar.gz should contain main.tex."""
        doc = Document(
            children=[
                Heading(level=1, content=[Text(content="Title")]),
                Paragraph(content=[Text(content="Hello world")]),
            ]
        )
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager()
        result = packager.package(doc, output)

        assert result == output
        assert output.exists()

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert "main.tex" in names

            # Verify main.tex content
            tex_content = tar.extractfile("main.tex").read().decode("utf-8")
            assert "\\documentclass{article}" in tex_content
            assert "\\begin{document}" in tex_content
            assert "Hello world" in tex_content

    def test_targz_with_figures(self, tmp_path):
        """Figures from data URIs should be included in tar.gz."""
        import base64

        fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\nfakedata").decode()
        data_uri = f"data:image/png;base64,{fake_png}"

        doc = Document(
            children=[
                Paragraph(content=[Image(url=data_uri, alt_text="Figure 1")]),
            ]
        )
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager()
        packager.package(doc, output)

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("figures/fig1" in n for n in names)

    def test_targz_with_bib_file(self, tmp_path):
        """Bibliography file should be included when provided."""
        bib_content = "@article{key, title={Test}}"
        bib_file = tmp_path / "refs.bib"
        bib_file.write_text(bib_content)

        doc = Document(
            children=[
                Paragraph(content=[Text(content="Text")]),
            ]
        )
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager()
        packager.package(doc, output, bib_file=bib_file)

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert "refs.bib" in names

            # Verify bib commands in tex
            tex_content = tar.extractfile("main.tex").read().decode("utf-8")
            assert "\\bibliographystyle{plain}" in tex_content
            assert "\\bibliography{refs}" in tex_content

    def test_custom_main_tex_filename(self, tmp_path):
        """Custom main tex filename should be used."""
        opts = ArxivPackagerOptions(main_tex_filename="paper.tex")
        doc = Document(children=[Paragraph(content=[Text(content="Text")])])
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager(options=opts)
        packager.package(doc, output)

        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert "paper.tex" in names
            assert "main.tex" not in names


@pytest.mark.unit
class TestArxivPackagerDirectory:
    """Tests for directory output mode."""

    def test_directory_output_structure(self, tmp_path):
        """Directory output should contain main.tex and figures dir."""
        import base64

        fake_png = base64.b64encode(b"\x89PNG\r\n\x1a\nfakedata").decode()
        data_uri = f"data:image/png;base64,{fake_png}"

        opts = ArxivPackagerOptions(output_format="directory")
        doc = Document(
            children=[
                Paragraph(content=[Image(url=data_uri, alt_text="Fig")]),
            ]
        )
        output = tmp_path / "submission"
        packager = ArxivPackager(options=opts)
        packager.package(doc, output)

        assert (output / "main.tex").exists()
        assert (output / "figures" / "fig1.png").exists()

        tex_content = (output / "main.tex").read_text(encoding="utf-8")
        assert "\\documentclass{article}" in tex_content

    def test_directory_with_bib_file(self, tmp_path):
        """Bib file should be copied to output directory."""
        bib_file = tmp_path / "refs.bib"
        bib_file.write_text("@article{key, title={Test}}")

        opts = ArxivPackagerOptions(output_format="directory")
        doc = Document(children=[Paragraph(content=[Text(content="Text")])])
        output = tmp_path / "submission"
        packager = ArxivPackager(options=opts)
        packager.package(doc, output, bib_file=bib_file)

        assert (output / "refs.bib").exists()


@pytest.mark.unit
class TestArxivPackagerOptions:
    """Tests for options propagation."""

    def test_document_class_propagated(self, tmp_path):
        """Document class should be propagated to renderer."""
        opts = ArxivPackagerOptions(document_class="report")
        doc = Document(children=[Paragraph(content=[Text(content="Text")])])
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager(options=opts)
        packager.package(doc, output)

        with tarfile.open(str(output), "r:gz") as tar:
            tex = tar.extractfile("main.tex").read().decode("utf-8")
            assert "\\documentclass{report}" in tex

    def test_bib_from_options(self, tmp_path):
        """Bib file path from options should be used when no explicit bib_file given."""
        bib_file = tmp_path / "auto.bib"
        bib_file.write_text("@article{key, title={Auto}}")

        opts = ArxivPackagerOptions(bib_file=str(bib_file))
        doc = Document(children=[Paragraph(content=[Text(content="Text")])])
        output = tmp_path / "submission.tar.gz"
        packager = ArxivPackager(options=opts)
        packager.package(doc, output)

        with tarfile.open(str(output), "r:gz") as tar:
            tex = tar.extractfile("main.tex").read().decode("utf-8")
            assert "\\bibliography{auto}" in tex
