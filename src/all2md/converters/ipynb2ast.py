#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/ipynb2ast.py
"""Jupyter Notebook to AST converter.

This module provides conversion from Jupyter Notebooks to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import base64
import logging
from typing import Any

from all2md.ast import CodeBlock, Document, HTMLInline, Image, Node, Paragraph, Text
from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_MESSAGE, IPYNB_SUPPORTED_IMAGE_MIMETYPES
from all2md.options import IpynbOptions
from all2md.utils.attachments import process_attachment

logger = logging.getLogger(__name__)


def _collapse_output(text: str, limit: int | None, message: str) -> str:
    """Collapse a string if it exceeds a specified line limit.

    Parameters
    ----------
    text : str
        Text to potentially collapse
    limit : int | None
        Maximum number of lines
    message : str
        Message to append if truncated

    Returns
    -------
    str
        Original or truncated text

    """
    if limit is None or not text:
        return text
    lines = text.splitlines()
    if len(lines) > limit:
        return "\n".join(lines[:limit]) + message
    return text


class IpynbToAstConverter:
    """Convert Jupyter Notebooks to AST representation.

    This converter processes notebook JSON and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    notebook : dict
        Parsed notebook JSON
    options : IpynbOptions or None
        Conversion options

    """

    def __init__(self, notebook: dict[str, Any], options: IpynbOptions | None = None):
        self.notebook = notebook
        self.options = options or IpynbOptions()
        self.language = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "python")

    def convert_to_ast(self) -> Document:
        """Convert notebook to AST Document.

        Returns
        -------
        Document
            AST document node

        """
        children: list[Node] = []

        cells = self.notebook.get("cells", [])
        for i, cell in enumerate(cells):
            cell_nodes = self._process_cell(cell, cell_index=i)
            if cell_nodes:
                children.extend(cell_nodes)

        return Document(children=children)

    def _process_cell(self, cell: dict[str, Any], cell_index: int) -> list[Node]:
        """Process a notebook cell to AST nodes.

        Parameters
        ----------
        cell : dict
            Cell data
        cell_index : int
            Cell index in notebook

        Returns
        -------
        list[Node]
            List of AST nodes for this cell

        """
        cell_type = cell.get("cell_type")
        nodes: list[Node] = []

        if cell_type == "markdown":
            # Markdown cells: render content as raw markdown using HTMLInline
            # This preserves the original markdown without double-processing
            source = self._get_source(cell)
            if source.strip():
                # Use HTMLInline to preserve markdown syntax
                nodes.append(Paragraph(content=[HTMLInline(content=source)]))

        elif cell_type == "code":
            # Code cells: create CodeBlock
            source = self._get_source(cell)
            if source.strip() and self.options.include_inputs:
                code_content = source.strip()

                # Add execution count if requested
                if self.options.show_execution_count:
                    execution_count = cell.get("execution_count")
                    if execution_count is not None:
                        # Prepend execution count as a comment
                        code_content = f"# In [{execution_count}]:\n{code_content}"

                nodes.append(CodeBlock(language=self.language, content=code_content))

            # Process outputs if enabled
            if self.options.include_outputs:
                for j, output in enumerate(cell.get("outputs", [])):
                    output_node = self._process_output(output, cell_index, j)
                    if output_node:
                        nodes.append(output_node)

        return nodes

    def _get_source(self, cell: dict[str, Any]) -> str:
        """Safely extract and join the source from a notebook cell.

        Parameters
        ----------
        cell : dict
            Cell data

        Returns
        -------
        str
            Cell source code/text

        """
        source = cell.get("source", [])
        if isinstance(source, list):
            return "".join(source)
        return str(source)

    def _process_output(self, output: dict[str, Any], cell_index: int, output_index: int) -> Node | None:
        """Process a cell output to AST node.

        Parameters
        ----------
        output : dict
            Output data
        cell_index : int
            Cell index
        output_index : int
            Output index within cell

        Returns
        -------
        Node or None
            AST node for output

        """
        output_type = output.get("output_type")

        # Filter by output_types if specified
        if self.options.output_types is not None:
            if output_type not in self.options.output_types:
                return None

        if output_type == "stream":
            text = "".join(output.get("text", []))
            if text.strip():
                collapsed_text = _collapse_output(
                    text,
                    self.options.truncate_long_outputs,
                    self.options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
                )
                return CodeBlock(language="", content=collapsed_text.strip())

        elif output_type in ("execute_result", "display_data"):
            data = output.get("data", {})

            # Try to process as image first
            for mime_type in IPYNB_SUPPORTED_IMAGE_MIMETYPES:
                if mime_type in data:
                    b64_data = data[mime_type]
                    try:
                        image_bytes = base64.b64decode(b64_data)
                        ext = mime_type.split("/")[-1].split("+")[0]
                        filename = f"cell_{cell_index + 1}_output_{output_index + 1}.{ext}"

                        markdown_result = process_attachment(
                            attachment_data=image_bytes,
                            attachment_name=filename,
                            alt_text="cell output",
                            attachment_mode=self.options.attachment_mode,
                            attachment_output_dir=self.options.attachment_output_dir,
                            attachment_base_url=self.options.attachment_base_url,
                            is_image=True,
                            alt_text_mode=self.options.alt_text_mode,
                        )

                        # Parse markdown result to extract URL
                        import re

                        match = re.match(r"!\[([^\]]*)\](?:\(([^)]+)\))?", markdown_result)
                        if match:
                            alt_text = match.group(1) or "cell output"
                            url = match.group(2) or ""
                            return Image(url=url, alt_text=alt_text, title=None)

                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not decode base64 image in cell {cell_index + 1}: {e}")
                        continue

            # Fall back to text/plain
            if "text/plain" in data:
                text = "".join(data["text/plain"])
                if text.strip():
                    collapsed_text = _collapse_output(
                        text,
                        self.options.truncate_long_outputs,
                        self.options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
                    )
                    return CodeBlock(language="", content=collapsed_text.strip())

        return None
