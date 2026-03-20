#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/renderers/arxiv_latex.py
"""ArXiv-specialized LaTeX renderer.

This module provides an ArXiv-specific LaTeX renderer that extends the base
LatexRenderer with figure extraction and proper figure environments for
ArXiv submission packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from all2md.ast.nodes import Document, Image
from all2md.options.arxiv import ArxivPackagerOptions
from all2md.options.latex import LatexRendererOptions
from all2md.renderers.latex import LatexRenderer
from all2md.utils.images import decode_base64_image, is_data_uri


@dataclass
class ExtractedFigure:
    """Represents a figure extracted during rendering.

    Parameters
    ----------
    filename : str
        Target filename in the archive (e.g. "figures/fig1.png").
    data : bytes or None
        Raw image data bytes, or None if from a local file path.
    original_url : str
        Original URL or data URI from the AST node.
    alt_text : str
        Alt text / caption text from the AST node.
    figure_number : int
        Sequential figure number.

    """

    filename: str
    data: bytes | None
    original_url: str
    alt_text: str
    figure_number: int


class ArxivLatexRenderer(LatexRenderer):
    """LaTeX renderer specialized for ArXiv submission packages.

    Extends LatexRenderer to:
    - Wrap images in figure environments with captions and labels
    - Extract image data for bundling into the submission archive
    - Support document class options
    - Include natbib for bibliography support

    Parameters
    ----------
    options : LatexRendererOptions or None
        LaTeX rendering options.
    arxiv_options : ArxivPackagerOptions or None
        ArXiv packager options for figure handling.

    """

    def __init__(
        self,
        options: LatexRendererOptions | None = None,
        arxiv_options: ArxivPackagerOptions | None = None,
    ):
        """Initialize the ArXiv LaTeX renderer."""
        super().__init__(options)
        self._arxiv_options = arxiv_options or ArxivPackagerOptions()
        self._extracted_figures: list[ExtractedFigure] = []
        self._figure_counter: int = 0

    @property
    def extracted_figures(self) -> list[ExtractedFigure]:
        """Return list of figures extracted during rendering."""
        return self._extracted_figures

    def render_to_string(self, document: Document) -> str:
        """Render document, resetting extracted figures first."""
        self._extracted_figures = []
        self._figure_counter = 0
        return super().render_to_string(document)

    def _render_preamble(self, metadata: Dict[str, Any]) -> None:
        """Render LaTeX preamble with document class options and ArXiv packages."""
        opts = self._arxiv_options
        # Document class with optional options
        if opts.document_class_options:
            opts_str = ",".join(opts.document_class_options)
            self._output.append(f"\\documentclass[{opts_str}]{{{self.options.document_class}}}\n\n")
        else:
            self._output.append(f"\\documentclass{{{self.options.document_class}}}\n\n")

        # Add packages
        for package in self.options.packages:
            self._output.append(f"\\usepackage{{{package}}}\n")

        self._output.append("\n")

        # Add metadata commands
        if metadata.get("title"):
            self._output.append(f"\\title{{{self._escape(metadata['title'])}}}\n")
        if metadata.get("author"):
            self._output.append(f"\\author{{{self._escape(metadata['author'])}}}\n")

        date_value = metadata.get("creation_date") or metadata.get("date")
        if date_value:
            self._output.append(f"\\date{{{self._escape(str(date_value))}}}\n")
        else:
            self._output.append("\\date{\\today}\n")

        self._output.append("\n")

    def visit_image(self, node: Image) -> None:
        r"""Render an Image node as a figure environment with extraction.

        Emits a complete figure environment and extracts the image data
        for bundling into the submission archive.

        Parameters
        ----------
        node : Image
            Image to render

        """
        self._figure_counter += 1
        fig_num = self._figure_counter
        figure_dir = self._arxiv_options.figure_dir
        figure_format = self._arxiv_options.figure_format

        # Determine filename and extract data
        image_data: bytes | None = None
        if is_data_uri(node.url):
            decoded_data, detected_format = decode_base64_image(node.url)
            image_data = decoded_data
            ext = detected_format or figure_format
            filename = f"{figure_dir}/fig{fig_num}.{ext}"
        else:
            # Local file path or remote URL — use original extension or default
            from pathlib import Path, PurePosixPath

            orig_ext = PurePosixPath(node.url).suffix.lstrip(".")
            ext = orig_ext if orig_ext else figure_format
            filename = f"{figure_dir}/fig{fig_num}.{ext}"
            # Try to read local file
            local_path = Path(node.url)
            if local_path.is_file():
                image_data = local_path.read_bytes()

        # Store extracted figure
        caption = node.alt_text or ""
        self._extracted_figures.append(
            ExtractedFigure(
                filename=filename,
                data=image_data,
                original_url=node.url,
                alt_text=caption,
                figure_number=fig_num,
            )
        )

        # Emit LaTeX figure environment
        self._output.append("\\begin{figure}[htbp]\n")
        self._output.append("\\centering\n")
        self._output.append(f"\\includegraphics[width=\\textwidth]{{{filename}}}\n")
        if caption:
            self._output.append(f"\\caption{{{self._escape(caption)}}}\n")
        self._output.append(f"\\label{{fig:figure{fig_num}}}\n")
        self._output.append("\\end{figure}")
