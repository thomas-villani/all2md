#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/packagers/arxiv.py
"""ArXiv submission package generator.

Creates a complete ArXiv-ready submission package including:
- main.tex (document content)
- main.bib (bibliography file)
- figures/ (extracted figures)

Output can be a directory or tar.gz archive.
"""

from __future__ import annotations

import tarfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Literal, Union

from all2md.ast.nodes import Bibliography, BibliographyEntry, Document
from all2md.options.latex import LatexRendererOptions
from all2md.renderers.latex import LatexRenderer
from all2md.utils.arxiv_figures import ExtractedFigure, extract_figures, update_image_paths
from all2md.utils.bibliography import generate_bibtex_entry, parse_bibliographic_text


@dataclass
class ArxivPackageOptions:
    r"""Options for ArXiv package generation.

    Parameters
    ----------
    document_class : str, default "article"
        LaTeX document class
    document_class_options : list of str
        Options for document class (e.g., ["12pt", "a4paper"])
    bibliography_style : str, default "plain"
        BibTeX style file
    figure_format : {"png", "pdf", "eps", "jpg"}, default "png"
        Target format for figure conversion
    output_format : {"directory", "tar.gz"}, default "directory"
        Package output format
    convert_footnotes : bool, default True
        Convert bibliographic footnotes to citations
    include_natbib : bool, default True
        Include natbib package for citation formatting
    figure_width : str, default r"\textwidth"
        Default figure width in LaTeX
    main_filename : str, default "main"
        Name for main .tex and .bib files
    figures_dir : str, default "figures"
        Directory name for figures

    """

    document_class: str = "article"
    document_class_options: list[str] = field(default_factory=list)
    bibliography_style: str = "plain"
    figure_format: Literal["png", "pdf", "eps", "jpg"] = "png"
    output_format: Literal["directory", "tar.gz"] = "directory"
    convert_footnotes: bool = True
    include_natbib: bool = True
    figure_width: str = r"\textwidth"
    main_filename: str = "main"
    figures_dir: str = "figures"


class ArxivPackager:
    """Generate ArXiv submission packages from AST documents.

    This packager converts document ASTs into complete ArXiv-ready
    submission packages with:
    - LaTeX source file
    - BibTeX bibliography (if citations present)
    - Extracted figures in a subdirectory

    Parameters
    ----------
    options : ArxivPackageOptions or None
        Package generation options

    Examples
    --------
    >>> from all2md import to_ast
    >>> from all2md.packagers.arxiv import ArxivPackager
    >>> doc = to_ast("paper.docx")
    >>> packager = ArxivPackager()
    >>> packager.package(doc, "submission/")

    """

    def __init__(self, options: ArxivPackageOptions | None = None) -> None:
        """Initialize the packager with options.

        Parameters
        ----------
        options : ArxivPackageOptions or None
            Package generation options

        """
        self.options = options or ArxivPackageOptions()

    def package(
        self,
        document: Document,
        output_path: Union[str, Path],
        source_dir: Path | None = None,
    ) -> Path:
        """Generate complete ArXiv package.

        Parameters
        ----------
        document : Document
            AST document to package
        output_path : str or Path
            Output directory or .tar.gz path
        source_dir : Path or None
            Source directory for resolving relative image paths

        Returns
        -------
        Path
            Path to created package

        """
        output_path = Path(output_path)

        # Step 1: Extract and process figures
        figures = extract_figures(document, base_name="figure", base_dir=source_dir)
        document = update_image_paths(document, figures, self.options.figures_dir)

        # Step 2: Generate BibTeX file content
        bibtex_content = self._generate_bibtex(document)

        # Step 3: Configure and render LaTeX
        latex_options = LatexRendererOptions(
            document_class=self.options.document_class,
            include_preamble=True,
            packages=self._get_required_packages(),
        )
        renderer = LatexRenderer(latex_options)
        latex_content = renderer.render_to_string(document)

        # Step 4: Write package
        if self.options.output_format == "tar.gz" or str(output_path).endswith(".tar.gz"):
            return self._write_tarball(output_path, latex_content, bibtex_content, figures)
        else:
            return self._write_directory(output_path, latex_content, bibtex_content, figures)

    def _generate_bibtex(self, document: Document) -> str:
        """Generate BibTeX content from Bibliography node in document.

        Parameters
        ----------
        document : Document
            Document containing Bibliography node

        Returns
        -------
        str
            BibTeX file content, or empty string if no bibliography

        """
        # Find Bibliography node in document
        for child in document.children:
            if isinstance(child, Bibliography):
                return self._bibliography_to_bibtex(child)
        return ""

    def _bibliography_to_bibtex(self, bibliography: Bibliography) -> str:
        """Convert Bibliography node to BibTeX string.

        Parameters
        ----------
        bibliography : Bibliography
            Bibliography node

        Returns
        -------
        str
            BibTeX file content

        """
        entries = []
        for entry in bibliography.entries:
            bibtex = self._entry_to_bibtex(entry)
            if bibtex:
                entries.append(bibtex)
        return "\n\n".join(entries)

    def _entry_to_bibtex(self, entry: BibliographyEntry) -> str:
        """Convert BibliographyEntry node to BibTeX string.

        Parameters
        ----------
        entry : BibliographyEntry
            Bibliography entry node

        Returns
        -------
        str
            BibTeX entry string

        """
        # If we have structured fields, use them directly
        if entry.fields:
            lines = [f"@{entry.entry_type}{{{entry.key},"]
            for field_name, field_value in entry.fields.items():
                lines.append(f"  {field_name} = {{{field_value}}},")
            # Remove trailing comma from last field
            if lines[-1].endswith(","):
                lines[-1] = lines[-1][:-1]
            lines.append("}")
            return "\n".join(lines)

        # Otherwise, try to parse from raw_text
        if entry.raw_text:
            ref = parse_bibliographic_text(entry.raw_text)
            return generate_bibtex_entry(entry.key, ref)

        # Minimal entry
        return f"@{entry.entry_type}{{{entry.key}}}"

    def _get_required_packages(self) -> list[str]:
        """Get list of required LaTeX packages.

        Returns
        -------
        list of str
            Package names

        """
        packages = ["amsmath", "amssymb", "graphicx", "hyperref"]
        if self.options.include_natbib:
            packages.append("natbib")
        return packages

    def _write_directory(
        self,
        path: Path,
        latex: str,
        bibtex: str,
        figures: list[ExtractedFigure],
    ) -> Path:
        """Write package to directory structure.

        Parameters
        ----------
        path : Path
            Output directory path
        latex : str
            LaTeX content
        bibtex : str
            BibTeX content
        figures : list of ExtractedFigure
            Extracted figures

        Returns
        -------
        Path
            Path to created directory

        """
        path.mkdir(parents=True, exist_ok=True)

        # Write main.tex
        tex_file = path / f"{self.options.main_filename}.tex"
        tex_file.write_text(latex, encoding="utf-8")

        # Write main.bib (if there's content)
        if bibtex:
            bib_file = path / f"{self.options.main_filename}.bib"
            bib_file.write_text(bibtex, encoding="utf-8")

        # Write figures
        if figures:
            figures_dir = path / self.options.figures_dir
            figures_dir.mkdir(exist_ok=True)
            for fig in figures:
                fig_file = figures_dir / fig.filename
                fig_file.write_bytes(fig.data)

        return path

    def _write_tarball(
        self,
        path: Path,
        latex: str,
        bibtex: str,
        figures: list[ExtractedFigure],
    ) -> Path:
        """Write package as tar.gz archive.

        Parameters
        ----------
        path : Path
            Output tar.gz path
        latex : str
            LaTeX content
        bibtex : str
            BibTeX content
        figures : list of ExtractedFigure
            Extracted figures

        Returns
        -------
        Path
            Path to created tarball

        """
        # Ensure path has .tar.gz extension
        if not str(path).endswith(".tar.gz"):
            path = path.with_suffix(".tar.gz")

        path.parent.mkdir(parents=True, exist_ok=True)

        with tarfile.open(path, "w:gz") as tar:
            # Add main.tex
            tex_bytes = latex.encode("utf-8")
            tex_info = tarfile.TarInfo(name=f"{self.options.main_filename}.tex")
            tex_info.size = len(tex_bytes)
            tar.addfile(tex_info, BytesIO(tex_bytes))

            # Add main.bib (if there's content)
            if bibtex:
                bib_bytes = bibtex.encode("utf-8")
                bib_info = tarfile.TarInfo(name=f"{self.options.main_filename}.bib")
                bib_info.size = len(bib_bytes)
                tar.addfile(bib_info, BytesIO(bib_bytes))

            # Add figures
            for fig in figures:
                fig_info = tarfile.TarInfo(name=f"{self.options.figures_dir}/{fig.filename}")
                fig_info.size = len(fig.data)
                tar.addfile(fig_info, BytesIO(fig.data))

        return path
