#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/options/arxiv.py
"""Configuration options for ArXiv submission package generation.

This module provides the ArxivPackagerOptions dataclass for controlling
how documents are packaged into ArXiv-ready LaTeX submission archives.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from all2md.constants import (
    DEFAULT_ARXIV_BIBLIOGRAPHY_STYLE,
    DEFAULT_ARXIV_DOCUMENT_CLASS,
    DEFAULT_ARXIV_FIGURE_DIR,
    DEFAULT_ARXIV_FIGURE_DPI,
    DEFAULT_ARXIV_FIGURE_FORMAT,
    DEFAULT_ARXIV_MAIN_TEX_FILENAME,
    DEFAULT_ARXIV_OUTPUT_FORMAT,
    DEFAULT_ARXIV_PACKAGES,
    ArxivFigureFormat,
    ArxivOutputFormat,
)
from all2md.options.base import CloneFrozenMixin


@dataclass(frozen=True)
class ArxivPackagerOptions(CloneFrozenMixin):
    r"""Configuration options for ArXiv submission package generation.

    Controls document class, figure extraction settings, output format,
    and bibliography handling for generating ArXiv-ready LaTeX archives.

    Parameters
    ----------
    document_class : str, default "article"
        LaTeX document class to use.
    document_class_options : list[str], default []
        Options for the document class (e.g. ["twocolumn", "12pt"]).
    figure_format : str, default "png"
        Format for extracted figures.
    figure_dpi : int, default 300
        DPI for extracted figures.
    figure_dir : str, default "figures"
        Subdirectory name for figures in the archive.
    output_format : {"tar.gz", "directory"}, default "tar.gz"
        Output format for the submission package.
    bibliography_style : str, default "plain"
        BibTeX bibliography style.
    bib_file : str or None, default None
        Path to a .bib bibliography file to include.
    main_tex_filename : str, default "main.tex"
        Filename for the main LaTeX file in the archive.
    packages : list[str], default ["amsmath", "graphicx", "hyperref", "natbib"]
        LaTeX packages to include in the preamble.

    """

    document_class: str = field(
        default=DEFAULT_ARXIV_DOCUMENT_CLASS,
        metadata={"help": "LaTeX document class (article, report, etc.)", "importance": "core"},
    )
    document_class_options: list[str] = field(
        default_factory=list,
        metadata={"help": "Document class options (e.g. twocolumn, 12pt)", "importance": "core"},
    )
    figure_format: ArxivFigureFormat = field(
        default=DEFAULT_ARXIV_FIGURE_FORMAT,
        metadata={"help": "Format for extracted figures", "choices": ["png", "jpg", "pdf"], "importance": "core"},
    )
    figure_dpi: int = field(
        default=DEFAULT_ARXIV_FIGURE_DPI,
        metadata={"help": "DPI for extracted figures", "importance": "advanced"},
    )
    figure_dir: str = field(
        default=DEFAULT_ARXIV_FIGURE_DIR,
        metadata={"help": "Subdirectory name for figures in the archive", "importance": "core"},
    )
    output_format: ArxivOutputFormat = field(
        default=DEFAULT_ARXIV_OUTPUT_FORMAT,
        metadata={
            "help": "Output format (tar.gz or directory)",
            "choices": ["tar.gz", "directory"],
            "importance": "core",
        },
    )
    bibliography_style: str = field(
        default=DEFAULT_ARXIV_BIBLIOGRAPHY_STYLE,
        metadata={"help": "BibTeX bibliography style", "importance": "advanced"},
    )
    bib_file: str | None = field(
        default=None,
        metadata={"help": "Path to .bib bibliography file", "importance": "core"},
    )
    main_tex_filename: str = field(
        default=DEFAULT_ARXIV_MAIN_TEX_FILENAME,
        metadata={"help": "Filename for the main .tex file", "importance": "advanced"},
    )
    packages: list[str] = field(
        default_factory=lambda: DEFAULT_ARXIV_PACKAGES.copy(),
        metadata={"help": "LaTeX packages to include in preamble", "importance": "advanced"},
    )

    def __post_init__(self) -> None:
        """Validate options."""
        if self.figure_dpi <= 0:
            raise ValueError(f"figure_dpi must be positive, got {self.figure_dpi}")
        # Defensive copy of mutable collections
        if self.packages is not None:
            object.__setattr__(self, "packages", list(self.packages))
        if self.document_class_options is not None:
            object.__setattr__(self, "document_class_options", list(self.document_class_options))
