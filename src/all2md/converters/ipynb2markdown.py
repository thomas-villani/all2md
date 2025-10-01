#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/ipynb2markdown.py

"""Jupyter Notebook to Markdown conversion module.

This module provides functionality to convert Jupyter Notebooks (.ipynb format)
to Markdown, preserving the structure of code and text cells, and handling
various output types like text and images.

The converter processes the JSON structure of a notebook, converting each cell
to its Markdown equivalent. It supports embedding images, collapsing long
outputs, and follows the unified attachment handling system of the library.

Key Features
------------
- Converts Markdown cells to verbatim Markdown.
- Formats code cells as fenced code blocks with language hints.
- Handles various cell outputs:
  - `stream` and `execute_result` text outputs are formatted as code blocks.
  - Image outputs can be embedded as base64 or saved to files and linked.
- Option to collapse long text outputs to maintain readability.

Dependencies
------------
- json: Standard library for parsing the notebook's JSON structure.
- base64: Standard library for decoding image data.

Examples
--------
Basic conversion from a file path:

    >>> from all2md.converters.ipynb2markdown import ipynb_to_markdown
    >>> markdown = ipynb_to_markdown('notebook.ipynb')
    >>> print(markdown)

Convert with options to save images to a directory:

    >>> from all2md.options import IpynbOptions
    >>> options = IpynbOptions(attachment_mode="download", attachment_output_dir="notebook_images")
    >>> markdown = ipynb_to_markdown('notebook.ipynb', options=options)

"""

import base64
import json
import logging
from pathlib import Path
from typing import IO, Any, Union

from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_MESSAGE, IPYNB_SUPPORTED_IMAGE_MIMETYPES
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import InputError, MarkdownConversionError
from all2md.options import IpynbOptions
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata, prepend_metadata_if_enabled

logger = logging.getLogger(__name__)

# TODO: remove, no longer needed
def _collapse_output(text: str, limit: int | None, message: str) -> str:
    """Collapse a string if it exceeds a specified line limit."""
    if limit is None or not text:
        return text
    lines = text.splitlines()
    if len(lines) > limit:
        return "\n".join(lines[:limit]) + message
    return text


def _get_source(cell: dict[str, Any]) -> str:
    """Safely extract and join the source from a notebook cell."""
    source = cell.get("source", [])
    if isinstance(source, list):
        return "".join(source)
    return str(source)


def extract_ipynb_metadata(notebook: dict) -> DocumentMetadata:
    """Extract metadata from Jupyter notebook.

    Parameters
    ----------
    notebook : dict
        Parsed notebook JSON structure

    Returns
    -------
    DocumentMetadata
        Extracted metadata
    """
    metadata = DocumentMetadata()

    # Extract notebook metadata
    nb_metadata = notebook.get('metadata', {})

    # Common notebook metadata fields
    if 'title' in nb_metadata:
        metadata.title = nb_metadata['title']

    # Kernel information
    kernel_info = nb_metadata.get('kernelspec', {})
    if kernel_info:
        language = kernel_info.get('language', '')
        if language:
            metadata.language = language
        kernel_name = kernel_info.get('display_name', kernel_info.get('name', ''))
        if kernel_name:
            metadata.custom['kernel'] = kernel_name

    # Language info
    lang_info = nb_metadata.get('language_info', {})
    if lang_info:
        if not metadata.language:
            metadata.language = lang_info.get('name', '')
        version = lang_info.get('version', '')
        if version:
            metadata.custom['language_version'] = version

    # Authors (if present in metadata)
    authors = nb_metadata.get('authors', [])
    if authors:
        if isinstance(authors, list) and authors:
            # Take first author as primary
            first_author = authors[0]
            if isinstance(first_author, dict):
                metadata.author = first_author.get('name', '')
            else:
                metadata.author = str(first_author)
            # Store all authors in custom
            if len(authors) > 1:
                metadata.custom['authors'] = authors
        elif isinstance(authors, str):
            metadata.author = authors

    # Creation/modification dates
    if 'created' in nb_metadata:
        metadata.creation_date = nb_metadata['created']
    if 'modified' in nb_metadata:
        metadata.modification_date = nb_metadata['modified']

    # Notebook format version
    nbformat = notebook.get('nbformat', '')
    nbformat_minor = notebook.get('nbformat_minor', '')
    if nbformat:
        metadata.custom['notebook_format'] = f"{nbformat}.{nbformat_minor}" if nbformat_minor else str(nbformat)

    # Cell count
    cells = notebook.get('cells', [])
    if cells:
        metadata.custom['cell_count'] = len(cells)
        # Count by cell type
        code_cells = sum(1 for cell in cells if cell.get('cell_type') == 'code')
        markdown_cells = sum(1 for cell in cells if cell.get('cell_type') == 'markdown')
        if code_cells:
            metadata.custom['code_cells'] = code_cells
        if markdown_cells:
            metadata.custom['markdown_cells'] = markdown_cells

    # Custom notebook metadata (Jupyter extensions often add metadata)
    for key, value in nb_metadata.items():
        if key not in ['kernelspec', 'language_info', 'authors', 'title', 'created', 'modified']:
            # Only include simple types in custom metadata
            if isinstance(value, (str, int, float, bool)):
                metadata.custom[f'notebook_{key}'] = value
            elif isinstance(value, (list, dict)) and key in ['tags', 'keywords']:
                # Special handling for tags/keywords
                if key == 'tags' or key == 'keywords':
                    if isinstance(value, list):
                        metadata.keywords = value
                    else:
                        metadata.custom[key] = value

    # If no title, try to extract from first markdown cell
    if not metadata.title and cells:
        for cell in cells:
            if cell.get('cell_type') == 'markdown':
                source = _get_source(cell)
                lines = source.strip().split('\n')
                for line in lines:
                    if line.strip().startswith('#'):
                        # Found a header, use as title
                        metadata.title = line.lstrip('#').strip()
                        break
                if metadata.title:
                    break

    return metadata


def ipynb_to_markdown(
        input_data: Union[str, Path, IO[bytes], IO[str]], options: IpynbOptions | None = None
) -> str:
    """Convert a Jupyter Notebook (.ipynb) to Markdown format.

    Processes a Jupyter Notebook file, converting Markdown cells, code cells,
    and their outputs into a single, well-formatted Markdown document.

    Parameters
    ----------
    input_data : str, Path, or file-like object
        The Jupyter Notebook to convert. Can be:
        - A string path to an .ipynb file.
        - A pathlib.Path object.
        - A file-like object (e.g., from open()) containing the notebook JSON.
    options : IpynbOptions or None, default None
        Configuration options for notebook conversion. If None, uses default settings.

    Returns
    -------
    str
        The Markdown representation of the Jupyter Notebook.

    Raises
    ------
    InputError
        If the input data is not a valid notebook format.
    MarkdownConversionError
        If there is an error during the conversion process.
    """
    if options is None:
        options = IpynbOptions()

    # md_options = options.markdown_options or MarkdownOptions()  # TODO: Use for formatting

    try:
        # Since .ipynb is text-based (JSON), we can handle it as a string
        if isinstance(input_data, (str, Path)):
            with open(input_data, "r", encoding="utf-8") as f:
                notebook = json.load(f)
        elif hasattr(input_data, "read"):
            content = input_data.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            notebook = json.loads(content)
        else:
            raise InputError(f"Unsupported input type: {type(input_data).__name__}")

    except json.JSONDecodeError as e:
        raise InputError(
            "Input is not a valid JSON file. Ensure it is a proper .ipynb notebook.",
            original_error=e,
        ) from e
    except Exception as e:
        if isinstance(e, InputError):
            raise
        raise MarkdownConversionError(
            f"Failed to read or parse Jupyter Notebook: {e}",
            conversion_stage="input_processing",
            original_error=e,
        ) from e

    if "cells" not in notebook or not isinstance(notebook["cells"], list):
        raise InputError("Invalid notebook format: 'cells' key is missing or not a list.")

    # Extract metadata if requested
    metadata = None
    if options.extract_metadata:
        metadata = extract_ipynb_metadata(notebook)

    # Use AST-based conversion path
    from all2md.converters.ipynb2ast import IpynbToAstConverter
    from all2md.ast import MarkdownRenderer
    from all2md.options import MarkdownOptions

    # Convert to AST
    ast_converter = IpynbToAstConverter(notebook, options)
    ast_document = ast_converter.convert_to_ast()

    # Render AST to markdown
    md_opts = options.markdown_options if options.markdown_options else MarkdownOptions()
    renderer = MarkdownRenderer(md_opts)
    result = renderer.render(ast_document)

    # Prepend metadata if enabled
    result = prepend_metadata_if_enabled(result.strip(), metadata, options.extract_metadata)

    return result


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ipynb",
    extensions=[".ipynb"],
    mime_types=["application/json"],
    magic_bytes=[
        (b'{"cells":', 0),
        (b'{ "cells":', 0),
    ],
    converter_module="all2md.converters.ipynb2markdown",
    converter_function="ipynb_to_markdown",
    required_packages=[],
    options_class="IpynbOptions",
    description="Convert Jupyter Notebooks to Markdown",
    priority=7
)
