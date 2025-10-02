#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/markdown2markdown.py
"""Markdown to Markdown converter (passthrough with optional re-rendering).

This module registers the markdown format in the converter registry, enabling
markdown files to be recognized as valid input. The actual conversion is a
passthrough or re-render via AST.

"""

from __future__ import annotations

from pathlib import Path
from typing import IO, Union

from all2md.converter_metadata import ConverterMetadata
from all2md.options import MarkdownParserOptions


def markdown_to_markdown(
    input: Union[str, Path, IO[bytes]],
    options: MarkdownParserOptions | None = None
) -> str:
    """Convert Markdown to Markdown (passthrough or re-render).

    For markdown input, this simply reads and returns the content,
    optionally re-rendering via AST if transforms are needed.

    Parameters
    ----------
    input : str, Path, or IO[bytes]
        Input markdown file or content
    options : MarkdownParserOptions or None
        Parser options (currently unused for passthrough)

    Returns
    -------
    str
        Markdown content

    """
    # Read markdown content
    if isinstance(input, Path):
        return input.read_text(encoding="utf-8")
    elif isinstance(input, str):
        return Path(input).read_text(encoding="utf-8")
    else:
        # TODO: What is the point of this?
        # File-like object
        input.seek(0)
        content_bytes = input.read()
        if isinstance(content_bytes, bytes):
            return content_bytes.decode("utf-8", errors="replace")
        return content_bytes


# Converter metadata for registry auto-discovery
CONVERTER_METADATA = ConverterMetadata(
    format_name="markdown",
    extensions=[".md", ".markdown", ".mdown", ".mkd", ".mkdn"],
    mime_types=["text/markdown", "text/x-markdown"],
    magic_bytes=[],  # Markdown has no magic bytes
    converter_module="all2md.parsers.markdown2markdown",
    converter_function="markdown_to_markdown",
    required_packages=[("mistune", "mistune", "")],
    optional_packages=[],
    import_error_message="Markdown parsing requires 'mistune'. Install with: pip install 'all2md[markdown]'",
    options_class="MarkdownParserOptions",
)
