#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ipynb.py
"""Jupyter Notebook to AST converter.

This module provides conversion from Jupyter Notebooks to AST representation.
It replaces direct markdown string generation with structured AST building.

"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import CodeBlock, Document, HTMLInline, Image, Node, Paragraph
from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_MESSAGE, IPYNB_SUPPORTED_IMAGE_MIMETYPES
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError, ParsingError, ValidationError
from all2md.options.ipynb import IpynbOptions
from all2md.parsers.base import BaseParser
from all2md.progress import ProgressCallback
from all2md.utils.attachments import process_attachment
from all2md.utils.metadata import DocumentMetadata

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


class IpynbToAstConverter(BaseParser):
    """Convert Jupyter Notebooks to AST representation.

    This converter processes notebook JSON and builds an AST
    that can be rendered to various markdown flavors.

    Parameters
    ----------
    options : IpynbOptions or None
        Conversion options

    """

    def __init__(self, options: IpynbOptions | None = None, progress_callback: Optional[ProgressCallback] = None):
        """Initialize the IPYNB parser with options and progress callback."""
        options = options or IpynbOptions()
        super().__init__(options, progress_callback)
        self.options: IpynbOptions = options
        self._attachment_footnotes: dict[str, str] = {}  # label -> content for footnote definitions

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse Jupyter Notebook input into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input notebook to parse

        Returns
        -------
        Document
            AST Document node

        Raises
        ------
        ValidationError
            If the input type is not supported
        MalformedFileError
            If the input is not valid notebook JSON
        ParsingError
            If parsing or conversion fails

        """
        try:
            # Load the notebook JSON
            if isinstance(input_data, (str, Path)):
                with open(input_data, "r", encoding="utf-8") as f:
                    notebook = json.load(f)
            elif isinstance(input_data, bytes):
                notebook = json.loads(input_data.decode("utf-8"))
            elif hasattr(input_data, "read"):
                raw_content = input_data.read()
                content = raw_content.decode("utf-8")
                notebook = json.loads(content)
            else:
                raise ValidationError(f"Unsupported input type: {type(input_data).__name__}")

        except ValidationError as e:
            raise e
        except json.JSONDecodeError as e:
            raise MalformedFileError(
                "Input is not a valid JSON file. Ensure it is a proper .ipynb notebook.",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
                original_error=e,
            ) from e
        except Exception as e:
            raise ParsingError(
                f"Failed to read or parse Jupyter Notebook: {e}",
                parsing_stage="input_processing",
                original_error=e,
            ) from e

        if "cells" not in notebook or not isinstance(notebook["cells"], list):
            raise MalformedFileError(
                "Invalid notebook format: 'cells' key is missing or not a list.",
                file_path=str(input_data) if isinstance(input_data, (str, Path)) else None,
            )

        # Extract language from notebook metadata
        language = notebook.get("metadata", {}).get("kernelspec", {}).get("language", "python")

        # Convert to AST
        return self.convert_to_ast(notebook, language)

    def convert_to_ast(self, notebook: dict, language: str) -> Document:
        """Convert notebook to AST Document.

        Returns
        -------
        Document
            AST document node

        """
        if notebook is None:
            raise ParsingError(
                "No notebook data loaded. Call parse() first.",
                parsing_stage="ast_conversion",
            )

        # Reset footnote collection for this conversion
        self._attachment_footnotes = {}

        children: list[Node] = []

        cells = notebook.get("cells", [])
        for i, cell in enumerate(cells):
            cell_nodes = self._process_cell(cell, cell_index=i, language=language)
            if cell_nodes:
                children.extend(cell_nodes)

        # Append attachment footnote definitions if any were collected
        if self._attachment_footnotes and self.options.attachments_footnotes_section:
            # Add section heading
            from all2md.ast.nodes import FootnoteDefinition, Heading, Paragraph as AstParagraph, Text
            children.append(Heading(
                level=2,
                content=[Text(content=self.options.attachments_footnotes_section)]
            ))

            # Add footnote definitions sorted by label
            for label in sorted(self._attachment_footnotes.keys()):
                content_text = self._attachment_footnotes[label]
                definition = FootnoteDefinition(
                    identifier=label,
                    content=[AstParagraph(content=[Text(content=content_text)])]
                )
                children.append(definition)

        # Extract and attach metadata
        metadata = self.extract_metadata(notebook)
        return Document(children=children, metadata=metadata.to_dict())

    def _process_cell(self, cell: dict[str, Any], cell_index: int, language: str) -> list[Node]:
        """Process a notebook cell to AST nodes.

        Parameters
        ----------
        cell : dict
            Cell data
        cell_index : int
            Cell index in notebook
        language : str
            Programming language for code cells

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

                nodes.append(CodeBlock(language=language, content=code_content))

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

                        result = process_attachment(
                            attachment_data=image_bytes,
                            attachment_name=filename,
                            alt_text="cell output",
                            attachment_mode=self.options.attachment_mode,
                            attachment_output_dir=self.options.attachment_output_dir,
                            attachment_base_url=self.options.attachment_base_url,
                            is_image=True,
                            alt_text_mode=self.options.alt_text_mode,
                        )

                        # Collect footnote info if present
                        if result.get("footnote_label") and result.get("footnote_content"):
                            self._attachment_footnotes[result["footnote_label"]] = result["footnote_content"]

                        # Parse markdown result to extract URL
                        import re

                        markdown_result = result.get("markdown", "")
                        match = re.match(r"!\[([^\]]*)\](?:\(([^)]+)\))?", markdown_result)
                        if match:
                            alt_text = match.group(1) or "cell output"
                            url = result.get("url", match.group(2) or "")
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

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from Jupyter notebook.

        Parameters
        ----------
        document : dict
            Parsed notebook JSON structure

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Extract notebook metadata
        nb_metadata = document.get('metadata', {})

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
        nbformat = document.get('nbformat', '')
        nbformat_minor = document.get('nbformat_minor', '')
        if nbformat:
            metadata.custom['notebook_format'] = f"{nbformat}.{nbformat_minor}" if nbformat_minor else str(nbformat)

        # Cell count
        cells = document.get('cells', [])
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
                    source = self._get_source(cell)
                    lines = source.strip().split('\n')
                    for line in lines:
                        if line.strip().startswith('#'):
                            # Found a header, use as title
                            metadata.title = line.lstrip('#').strip()
                            break
                    if metadata.title:
                        break

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ipynb",
    extensions=[".ipynb"],
    mime_types=["application/json"],
    magic_bytes=[
        (b'{"cells":', 0),
        (b'{ "cells":', 0),
    ],
    parser_class="IpynbToAstConverter",
    renderer_class=None,
    parser_required_packages=[],
    renderer_required_packages=[],
    parser_options_class="IpynbOptions",
    renderer_options_class=None,
    description="Convert Jupyter Notebooks to Markdown",
    priority=7
)
