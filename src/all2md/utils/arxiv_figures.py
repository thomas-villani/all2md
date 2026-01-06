#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/arxiv_figures.py
"""Figure extraction and conversion for ArXiv submissions.

ArXiv requirements:
- PDF, EPS, PNG, or JPEG for figures
- Relative paths from main.tex
- Files in figures/ subdirectory

This module provides functions to:
1. Extract all figures from a document AST
2. Decode base64 data URIs to binary data
3. Update image paths in the AST to use relative paths
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Optional

from all2md.ast.nodes import (
    Document,
    Image,
    Node,
    get_node_children,
    replace_node_children,
)

# Supported ArXiv figure formats
ARXIV_FIGURE_FORMATS = {"png", "jpg", "jpeg", "pdf", "eps"}

# Data URI pattern
_DATA_URI_PATTERN = re.compile(r"data:image/([a-zA-Z0-9+-]+);base64,(.+)", re.DOTALL)


@dataclass
class ExtractedFigure:
    """Extracted figure data for ArXiv packaging.

    Parameters
    ----------
    original_url : str
        Original URL or data URI from the Image node
    filename : str
        Generated filename for the figure (e.g., "figure_1.png")
    data : bytes
        Binary image data
    format : str
        Image format (png, jpg, pdf, etc.)
    alt_text : str
        Alt text from the Image node
    width : int or None
        Image width if specified
    height : int or None
        Image height if specified

    """

    original_url: str
    filename: str
    data: bytes
    format: str
    alt_text: str = ""
    width: Optional[int] = None
    height: Optional[int] = None


def _decode_base64_data_uri(data_uri: str) -> tuple[bytes | None, str]:
    """Decode a base64 data URI to binary data.

    Parameters
    ----------
    data_uri : str
        Data URI string (e.g., "data:image/png;base64,...")

    Returns
    -------
    tuple of (bytes or None, str)
        Binary data and format, or (None, "") if invalid

    """
    match = _DATA_URI_PATTERN.match(data_uri)
    if not match:
        return None, ""

    format_str = match.group(1).lower()
    base64_data = match.group(2)

    # Normalize format
    if format_str == "jpeg":
        format_str = "jpg"

    try:
        data = base64.b64decode(base64_data)
        return data, format_str
    except Exception:
        return None, ""


def _read_file_as_bytes(file_path: str, base_dir: Path | None = None) -> tuple[bytes | None, str]:
    """Read a file and return its contents as bytes.

    Parameters
    ----------
    file_path : str
        Path to the file
    base_dir : Path or None
        Base directory for relative paths

    Returns
    -------
    tuple of (bytes or None, str)
        Binary data and format, or (None, "") if file not found

    """
    path = Path(file_path)
    if not path.is_absolute() and base_dir:
        path = base_dir / path

    if not path.exists():
        return None, ""

    format_str = path.suffix.lstrip(".").lower()
    if format_str == "jpeg":
        format_str = "jpg"

    try:
        return path.read_bytes(), format_str
    except Exception:
        return None, ""


def extract_figures(
    document: Document,
    base_name: str = "figure",
    base_dir: Path | None = None,
) -> list[ExtractedFigure]:
    """Extract all figures from document AST.

    Handles:
    - Base64 data URIs (decode and detect format)
    - File paths (read and include)
    - Skips remote URLs (https://)

    Parameters
    ----------
    document : Document
        AST document to extract figures from
    base_name : str, default "figure"
        Base name for figure files
    base_dir : Path or None
        Base directory for resolving relative file paths

    Returns
    -------
    list of ExtractedFigure
        List of extracted figures with data

    """
    figures: list[ExtractedFigure] = []
    counter = 1

    def visit_node(node: Node) -> None:
        nonlocal counter

        if isinstance(node, Image):
            fig = _extract_single_figure(node, base_name, counter, base_dir)
            if fig:
                figures.append(fig)
                counter += 1

        for child in get_node_children(node):
            visit_node(child)

    visit_node(document)
    return figures


def _extract_single_figure(
    image: Image,
    base_name: str,
    seq: int,
    base_dir: Path | None,
) -> ExtractedFigure | None:
    """Extract a single figure from Image node.

    Parameters
    ----------
    image : Image
        Image node to extract from
    base_name : str
        Base name for the figure file
    seq : int
        Sequence number for the figure
    base_dir : Path or None
        Base directory for relative paths

    Returns
    -------
    ExtractedFigure or None
        Extracted figure data, or None if extraction failed

    """
    url = image.url

    # Handle base64 data URIs
    if url.startswith("data:"):
        data, fmt = _decode_base64_data_uri(url)
        if data:
            filename = f"{base_name}_{seq}.{fmt}"
            return ExtractedFigure(
                original_url=url,
                filename=filename,
                data=data,
                format=fmt,
                alt_text=image.alt_text,
                width=image.width,
                height=image.height,
            )
        return None

    # Skip remote URLs
    if url.startswith(("http://", "https://")):
        return None

    # Handle local file paths
    data, fmt = _read_file_as_bytes(url, base_dir)
    if data:
        filename = f"{base_name}_{seq}.{fmt}"
        return ExtractedFigure(
            original_url=url,
            filename=filename,
            data=data,
            format=fmt,
            alt_text=image.alt_text,
            width=image.width,
            height=image.height,
        )

    return None


def update_image_paths(
    document: Document,
    figures: list[ExtractedFigure],
    figures_dir: str = "figures",
) -> Document:
    """Update Image nodes to use relative paths for the figures directory.

    Parameters
    ----------
    document : Document
        AST document to update
    figures : list of ExtractedFigure
        List of extracted figures with their new filenames
    figures_dir : str, default "figures"
        Directory name for figures

    Returns
    -------
    Document
        Updated document with relative image paths

    """
    # Build a mapping from original URL to new path
    url_to_path: dict[str, str] = {}
    for fig in figures:
        new_path = f"{figures_dir}/{fig.filename}"
        url_to_path[fig.original_url] = new_path

    def transform_node(node: Node) -> Node:
        if isinstance(node, Image):
            if node.url in url_to_path:
                return replace(node, url=url_to_path[node.url])
            return node

        children = get_node_children(node)
        if children:
            new_children = [transform_node(child) for child in children]
            return replace_node_children(node, new_children)

        return node

    return transform_node(document)  # type: ignore[return-value]


def get_latex_figure_environment(
    figure: ExtractedFigure,
    figures_dir: str = "figures",
    default_width: str = r"\textwidth",
) -> str:
    r"""Generate LaTeX figure environment for a figure.

    Parameters
    ----------
    figure : ExtractedFigure
        Extracted figure data
    figures_dir : str, default "figures"
        Directory containing figures
    default_width : str, default r"\textwidth"
        Default width for figures

    Returns
    -------
    str
        LaTeX figure environment code

    """
    path = f"{figures_dir}/{figure.filename}"
    caption = figure.alt_text or ""

    lines = [
        r"\begin{figure}[htbp]",
        r"  \centering",
        f"  \\includegraphics[width={default_width}]{{{path}}}",
    ]

    if caption:
        # Escape LaTeX special characters in caption
        escaped_caption = caption.replace("_", r"\_").replace("&", r"\&")
        lines.append(f"  \\caption{{{escaped_caption}}}")

    lines.append(r"\end{figure}")
    return "\n".join(lines)
