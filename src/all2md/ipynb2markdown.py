#  Copyright (c) 2025 Tom Villani, Ph.D.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
#  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
#  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
#  and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all copies or substantial
#  portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
#  BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# src/all2md/ipynb2markdown.py

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

    >>> from all2md.ipynb2markdown import ipynb_to_markdown
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

from ._attachment_utils import process_attachment
from .constants import DEFAULT_TRUNCATE_OUTPUT_MESSAGE, IPYNB_SUPPORTED_IMAGE_MIMETYPES
from .exceptions import MdparseConversionError, MdparseInputError
from .options import IpynbOptions, MarkdownOptions

logger = logging.getLogger(__name__)


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
    MdparseInputError
        If the input data is not a valid notebook format.
    MdparseConversionError
        If there is an error during the conversion process.
    """
    if options is None:
        options = IpynbOptions()

    md_options = options.markdown_options or MarkdownOptions()

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
            raise MdparseInputError(f"Unsupported input type: {type(input_data).__name__}")

    except json.JSONDecodeError as e:
        raise MdparseInputError(
            "Input is not a valid JSON file. Ensure it is a proper .ipynb notebook.",
            original_error=e,
        ) from e
    except Exception as e:
        if isinstance(e, MdparseInputError):
            raise
        raise MdparseConversionError(
            f"Failed to read or parse Jupyter Notebook: {e}",
            conversion_stage="input_processing",
            original_error=e,
        ) from e

    if "cells" not in notebook or not isinstance(notebook["cells"], list):
        raise MdparseInputError("Invalid notebook format: 'cells' key is missing or not a list.")

    output_parts = []
    language = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "python")

    for i, cell in enumerate(notebook["cells"]):
        cell_type = cell.get("cell_type")
        cell_content = []

        if cell_type == "markdown":
            source = _get_source(cell)
            cell_content.append(source)

        elif cell_type == "code":
            source = _get_source(cell)
            if source.strip():
                cell_content.append(f"```{language}\n{source}\n```")

            # Process outputs
            for j, output in enumerate(cell.get("outputs", [])):
                output_md = ""
                output_type = output.get("output_type")

                if output_type == "stream":
                    text = "".join(output.get("text", []))
                    if text.strip():
                        collapsed_text = _collapse_output(
                            text,
                            options.truncate_long_outputs,
                            options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE
                        )
                        output_md = f"```\n{collapsed_text.strip()}\n```"

                elif output_type in ("execute_result", "display_data"):
                    data = output.get("data", {})
                    image_handled = False
                    for mime_type in IPYNB_SUPPORTED_IMAGE_MIMETYPES:
                        if mime_type in data:
                            b64_data = data[mime_type]
                            try:
                                image_bytes = base64.b64decode(b64_data)
                                ext = mime_type.split("/")[-1].split("+")[0]
                                filename = f"cell_{i+1}_output_{j+1}.{ext}"
                                output_md = process_attachment(
                                    attachment_data=image_bytes,
                                    attachment_name=filename,
                                    alt_text="cell output",
                                    attachment_mode=options.attachment_mode,
                                    attachment_output_dir=options.attachment_output_dir,
                                    attachment_base_url=options.attachment_base_url,
                                    is_image=True,
                                )
                                image_handled = True
                                break
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Could not decode base64 image in cell {i+1}: {e}")
                                continue

                    if not image_handled and "text/plain" in data:
                        text = "".join(data["text/plain"])
                        if text.strip():
                            collapsed_text = _collapse_output(
                                text, options.truncate_long_outputs,
                                options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE
                            )
                            output_md = f"```\n{collapsed_text.strip()}\n```"

                if output_md:
                    cell_content.append(output_md)

        if cell_content:
            output_parts.append("\n".join(cell_content))

    return "\n\n".join(output_parts).strip()