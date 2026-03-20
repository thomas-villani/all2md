#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/packagers/arxiv.py
"""ArXiv submission package generator.

This module provides the ArxivPackager class which converts AST documents
into complete, ArXiv-ready LaTeX submission archives (.tar.gz or directory).
"""

from __future__ import annotations

import io
import logging
import shutil
import tarfile
from pathlib import Path

from all2md.ast.nodes import Document
from all2md.options.arxiv import ArxivPackagerOptions
from all2md.options.latex import LatexRendererOptions
from all2md.renderers.arxiv_latex import ArxivLatexRenderer, ExtractedFigure

logger = logging.getLogger(__name__)


class ArxivPackager:
    """Generate ArXiv-ready LaTeX submission packages from AST documents.

    Parameters
    ----------
    options : ArxivPackagerOptions or None
        Packager configuration options.

    """

    def __init__(self, options: ArxivPackagerOptions | None = None):
        """Initialize packager with options."""
        self.options = options or ArxivPackagerOptions()

    def package(self, doc: Document, output: str | Path, bib_file: str | Path | None = None) -> Path:
        """Generate an ArXiv submission package from an AST document.

        Parameters
        ----------
        doc : Document
            AST document to package.
        output : str or Path
            Output path for the archive or directory.
        bib_file : str, Path, or None
            Optional path to a .bib bibliography file.

        Returns
        -------
        Path
            Path to the created archive or directory.

        """
        output = Path(output)
        bib_file = Path(bib_file) if bib_file else None

        # Build renderer options from packager options
        renderer_options = LatexRendererOptions(
            document_class=self.options.document_class,
            include_preamble=True,
            packages=list(self.options.packages),
        )

        # Render document to LaTeX
        renderer = ArxivLatexRenderer(options=renderer_options, arxiv_options=self.options)
        latex_content = renderer.render_to_string(doc)

        # Inject bibliography commands before \end{document} if bib file provided
        effective_bib = bib_file or (Path(self.options.bib_file) if self.options.bib_file else None)
        if effective_bib is not None:
            bib_name = effective_bib.stem
            bib_commands = (
                f"\n\\bibliographystyle{{{self.options.bibliography_style}}}\n" f"\\bibliography{{{bib_name}}}\n"
            )
            end_doc = "\\end{document}"
            if end_doc in latex_content:
                latex_content = latex_content.replace(end_doc, bib_commands + "\n" + end_doc)

        # Collect extracted figures
        figures = renderer.extracted_figures

        if self.options.output_format == "tar.gz":
            return self._create_targz(output, latex_content, figures, effective_bib)
        else:
            return self._create_directory(output, latex_content, figures, effective_bib)

    def _create_targz(
        self,
        output: Path,
        latex_content: str,
        figures: list[ExtractedFigure],
        bib_file: Path | None,
    ) -> Path:
        """Create a tar.gz archive containing the submission package.

        Parameters
        ----------
        output : Path
            Output path for the archive.
        latex_content : str
            Rendered LaTeX content.
        figures : list
            List of ExtractedFigure objects.
        bib_file : Path or None
            Optional bibliography file to include.

        Returns
        -------
        Path
            Path to the created archive.

        """
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            # Add main.tex
            tex_data = latex_content.encode("utf-8")
            info = tarfile.TarInfo(name=self.options.main_tex_filename)
            info.size = len(tex_data)
            tar.addfile(info, io.BytesIO(tex_data))

            # Add figures
            for fig in figures:
                if fig.data is not None:
                    fig_info = tarfile.TarInfo(name=fig.filename)
                    fig_info.size = len(fig.data)
                    tar.addfile(fig_info, io.BytesIO(fig.data))

            # Add bib file using TarInfo for consistent metadata
            if bib_file is not None and bib_file.is_file():
                bib_data = bib_file.read_bytes()
                bib_info = tarfile.TarInfo(name=bib_file.name)
                bib_info.size = len(bib_data)
                tar.addfile(bib_info, io.BytesIO(bib_data))

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(buf.getvalue())
        return output

    def _create_directory(
        self,
        output: Path,
        latex_content: str,
        figures: list[ExtractedFigure],
        bib_file: Path | None,
    ) -> Path:
        """Create a directory containing the submission package.

        Parameters
        ----------
        output : Path
            Output directory path.
        latex_content : str
            Rendered LaTeX content.
        figures : list
            List of ExtractedFigure objects.
        bib_file : Path or None
            Optional bibliography file to include.

        Returns
        -------
        Path
            Path to the created directory.

        """
        output.mkdir(parents=True, exist_ok=True)

        # Write main.tex
        (output / self.options.main_tex_filename).write_text(latex_content, encoding="utf-8")

        # Write figures
        for fig in figures:
            if fig.data is not None:
                fig_path = output / fig.filename
                fig_path.parent.mkdir(parents=True, exist_ok=True)
                fig_path.write_bytes(fig.data)

        # Copy bib file
        if bib_file is not None and bib_file.is_file():
            shutil.copy2(str(bib_file), str(output / bib_file.name))

        return output
