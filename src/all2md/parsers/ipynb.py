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
from copy import deepcopy
from pathlib import Path
from typing import IO, Any, Optional, Union

from all2md.ast import CodeBlock, Document, Node, Paragraph, Text
from all2md.constants import DEFAULT_TRUNCATE_OUTPUT_MESSAGE, IPYNB_SUPPORTED_IMAGE_MIMETYPES
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import MalformedFileError, ParsingError, ValidationError
from all2md.options.ipynb import IpynbOptions, IpynbRendererOptions
from all2md.options.markdown import MarkdownParserOptions
from all2md.parsers.base import BaseParser
from all2md.parsers.markdown import markdown_to_ast
from all2md.progress import ProgressCallback
from all2md.transforms.builtin import RemoveNodesTransform
from all2md.utils.attachments import process_attachment
from all2md.utils.encoding import normalize_stream_to_bytes
from all2md.utils.metadata import DocumentMetadata
from all2md.utils.parser_helpers import attachment_result_to_image_node

logger = logging.getLogger(__name__)

_IPYNB_MARKDOWN_FALLBACK_FLAG = "_ipynb_plaintext_markdown"


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
        BaseParser._validate_options_type(options, IpynbOptions, "ipynb")
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
                # Normalize stream to bytes (handles both binary and text mode)
                content_bytes = normalize_stream_to_bytes(input_data)
                notebook = json.loads(content_bytes.decode("utf-8"))
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
        if self.options.attachments_footnotes_section:
            self._append_attachment_footnotes(
                children, self._attachment_footnotes, self.options.attachments_footnotes_section
            )

        # Extract and attach metadata
        metadata = self.extract_metadata(notebook)
        metadata_dict = metadata.to_dict()
        notebook_metadata = deepcopy(notebook.get("metadata", {}))
        nbformat = notebook.get("nbformat", 4)
        nbformat_minor = notebook.get("nbformat_minor", 5)

        ipynb_bundle: dict[str, Any] = {
            "metadata": notebook_metadata,
            "nbformat": nbformat,
            "nbformat_minor": nbformat_minor,
        }

        # Merge with any existing ipynb notebook metadata
        existing_bundle = metadata_dict.get("ipynb_notebook")
        if isinstance(existing_bundle, dict):
            merged_bundle = {**existing_bundle, **ipynb_bundle}
        else:
            merged_bundle = ipynb_bundle

        metadata_dict["ipynb_notebook"] = merged_bundle

        return Document(children=children, metadata=metadata_dict)

    def _process_cell(self, cell: dict[str, Any], cell_index: int, language: str) -> list[Node]:
        """Process a notebook cell to AST nodes with metadata for round-tripping."""
        cell_type = cell.get("cell_type")
        nodes: list[Node] = []

        # Skip cells with missing or invalid cell_type
        if not cell_type or not isinstance(cell_type, str):
            logger.debug(
                "Skipping cell at index %s with missing or invalid cell_type",
                cell_index,
            )
            return nodes

        cell_metadata = deepcopy(cell.get("metadata", {})) if cell.get("metadata") else {}
        attachments = cell.get("attachments")
        source = self._get_source(cell)

        base_info: dict[str, Any] = {
            "cell_type": cell_type,
            "cell_index": cell_index,
            "cell_id": cell.get("id") or cell_metadata.get("id") or f"cell-{cell_index + 1}",
            "cell_metadata": deepcopy(cell_metadata),
            "source": source,
        }

        if attachments:
            base_info["attachments"] = deepcopy(attachments)

        if cell_type == "markdown":
            markdown_nodes: list[Node] = []
            if source.strip():
                markdown_nodes = self._parse_markdown_cell(source)

            # Handle empty markdown cells based on skip_empty_cells option
            if not markdown_nodes:
                # If skip_empty_cells is False OR there are attachments, preserve the empty cell
                if not self.options.skip_empty_cells or attachments:
                    markdown_nodes = [Paragraph(content=[Text(content="")])]
                else:
                    # Skip empty cell entirely
                    return nodes

            for segment_index, markdown_node in enumerate(markdown_nodes):
                info = deepcopy(base_info)
                if segment_index > 0 and info.get("attachments") is not None:
                    info.pop("attachments")
                node_meta = getattr(markdown_node, "metadata", {})
                fallback_plain = bool(node_meta.pop(_IPYNB_MARKDOWN_FALLBACK_FLAG, False))
                extras: dict[str, Any] = {"segment_index": segment_index}
                if fallback_plain:
                    extras["markdown_plaintext"] = True
                self._attach_ipynb_metadata(
                    markdown_node,
                    info,
                    role="body",
                    **extras,
                )
            nodes.extend(markdown_nodes)

        elif cell_type == "code":
            base_info["execution_count"] = cell.get("execution_count")
            base_info["language"] = language
            base_info["raw_outputs"] = deepcopy(cell.get("outputs", []))

            # Skip empty code cells if configured (unless they have outputs or attachments)
            has_outputs = cell.get("outputs") and len(cell.get("outputs", [])) > 0
            if self.options.skip_empty_cells and not source.strip() and not has_outputs and not attachments:
                return nodes

            if self.options.include_inputs:
                # Only create input node if source is non-empty OR skip_empty_cells is False
                if source.strip() or not self.options.skip_empty_cells:
                    code_content = source

                    if self.options.show_execution_count:
                        execution_count = cell.get("execution_count")
                        if execution_count is not None:
                            code_content = f"# In [{execution_count}]:\n{source}"
                            base_info["execution_count_was_inlined"] = True

                    code_node = CodeBlock(language=language, content=code_content)
                    self._attach_ipynb_metadata(code_node, base_info, role="input")
                    nodes.append(code_node)

            if self.options.include_outputs:
                for j, output in enumerate(cell.get("outputs", [])):
                    output_node = self._process_output(output, cell_index, j, base_info)
                    if output_node:
                        nodes.append(output_node)

        elif cell_type == "raw":
            if source or attachments:
                raw_node = CodeBlock(language=None, content=source)
                self._attach_ipynb_metadata(raw_node, base_info, role="body")
                nodes.append(raw_node)

        else:
            logger.debug(
                "Encountered unsupported cell type '%s' at index %s; preserving as raw text",
                cell_type,
                cell_index,
            )
            if source:
                fallback_node = Paragraph(content=[Text(content=source)])
                self._attach_ipynb_metadata(fallback_node, base_info, role="body")
                nodes.append(fallback_node)

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

    def _process_output(
        self,
        output: dict[str, Any],
        cell_index: int,
        output_index: int,
        cell_info: dict[str, Any],
    ) -> Node | None:
        """Process a cell output to AST node.

        Parameters
        ----------
        output : dict
            Output data
        cell_index : int
            Cell index
        output_index : int
            Output index within cell
        cell_info : dict
            Cell metadata and information

        Returns
        -------
        Node or None
            AST node for output

        """
        raw_output = deepcopy(output)
        output_type = raw_output.get("output_type")

        # Filter by output_types if specified
        if self.options.output_types is not None:
            if output_type not in self.options.output_types:
                return None

        def attach_metadata(node: Node, **extra: Any) -> Node:
            info_subset = dict(cell_info)
            info_subset.pop("raw_outputs", None)
            self._attach_ipynb_metadata(
                node,
                info_subset,
                role="output",
                output_index=output_index,
                output_type=output_type,
                output=raw_output,
                **extra,
            )
            return node

        if output_type == "stream":
            text = "".join(raw_output.get("text", []))
            if text.strip():
                collapsed_text = _collapse_output(
                    text,
                    self.options.truncate_long_outputs,
                    self.options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
                )
                node = CodeBlock(language="", content=collapsed_text.strip())
                return attach_metadata(node)

        elif output_type in ("execute_result", "display_data"):
            data = raw_output.get("data", {})

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

                        # Convert result to Image node using helper
                        image_node = attachment_result_to_image_node(result, fallback_alt_text="cell output")
                        if image_node:
                            return attach_metadata(image_node, mime_type=mime_type)

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
                    node = CodeBlock(language="", content=collapsed_text.strip())
                    return attach_metadata(node)

        elif output_type == "error":
            traceback_lines = raw_output.get("traceback") or []
            if traceback_lines:
                text = "\n".join(traceback_lines)
                collapsed_text = _collapse_output(
                    text,
                    self.options.truncate_long_outputs,
                    self.options.truncate_output_message or DEFAULT_TRUNCATE_OUTPUT_MESSAGE,
                )
                node = CodeBlock(language="", content=collapsed_text.strip())
                return attach_metadata(node, is_traceback=True)

        # Preserve unhandled outputs for round-trip fidelity
        placeholder = CodeBlock(language="", content="")
        attach_metadata(placeholder, placeholder=True)
        return placeholder

    def _attach_ipynb_metadata(
        self,
        node: Node,
        base_info: dict[str, Any],
        *,
        role: str,
        **extra: Any,
    ) -> None:
        """Attach Jupyter-specific metadata to a node for renderer reconstruction."""
        node_metadata = dict(getattr(node, "metadata", {}) or {})
        ipynb_meta = deepcopy(base_info)
        ipynb_meta["role"] = role
        if extra:
            ipynb_meta.update(extra)
        node_metadata["ipynb"] = ipynb_meta
        node.metadata = node_metadata

    def _parse_markdown_cell(self, source: str) -> list[Node]:
        """Parse markdown cell content into AST nodes safely.

        This method avoids using HTMLInline which bypasses renderer sanitization.
        Instead, it parses the markdown content using the markdown parser to
        get proper AST nodes. When strip_html_from_markdown is True (default),
        HTML elements are removed from the parsed AST for security.

        Parameters
        ----------
        source : str
            Markdown cell content

        Returns
        -------
        list[Node]
            List of AST nodes from parsed markdown

        """
        try:

            # Parse markdown content with appropriate options
            options = MarkdownParserOptions(
                parse_strikethrough=True,
                parse_tables=True,
                parse_footnotes=True,
                parse_math=True,
            )
            doc = markdown_to_ast(source, options=options)

            # Strip HTML nodes for security if configured
            if self.options.strip_html_from_markdown:
                html_stripper = RemoveNodesTransform(node_types=["html_inline", "html_block"])
                transformed = html_stripper.transform(doc)
                if transformed is None:
                    # Should not happen since we don't remove document nodes
                    doc = Document(children=[])
                else:
                    doc = transformed  # type: ignore[assignment]

            # If the markdown parser returns empty document, it likely stripped all HTML
            # In this case, we should still preserve the content as plain text
            if not doc.children and source.strip():
                logger.debug("Markdown parser returned empty document for cell with content, treating as plain text")
                fallback_node = Paragraph(content=[Text(content=source)])
                fallback_node.metadata[_IPYNB_MARKDOWN_FALLBACK_FLAG] = True
                return [fallback_node]

            # Return the children nodes (we don't want the Document wrapper)
            return doc.children if doc.children else []

        except Exception:
            # Fallback to simple text paragraph if markdown parsing fails
            logger.warning("Failed to parse markdown cell, falling back to plain text")
            fallback_node = Paragraph(content=[Text(content=source)])
            fallback_node.metadata[_IPYNB_MARKDOWN_FALLBACK_FLAG] = True
            return [fallback_node]

    def _extract_kernel_metadata(self, nb_metadata: dict, metadata: DocumentMetadata) -> None:
        """Extract kernel and language information from notebook metadata.

        Parameters
        ----------
        nb_metadata : dict
            Notebook metadata dictionary
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        # Kernel information
        kernel_info = nb_metadata.get("kernelspec", {})
        if kernel_info:
            language = kernel_info.get("language", "")
            if language:
                metadata.language = language
            kernel_name = kernel_info.get("display_name", kernel_info.get("name", ""))
            if kernel_name:
                metadata.custom["kernel"] = kernel_name

        # Language info
        lang_info = nb_metadata.get("language_info", {})
        if lang_info:
            if not metadata.language:
                metadata.language = lang_info.get("name", "")
            version = lang_info.get("version", "")
            if version:
                metadata.custom["language_version"] = version

    def _extract_author_metadata(self, nb_metadata: dict, metadata: DocumentMetadata) -> None:
        """Extract author information from notebook metadata.

        Parameters
        ----------
        nb_metadata : dict
            Notebook metadata dictionary
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        authors = nb_metadata.get("authors", [])
        if not authors:
            return

        if isinstance(authors, list) and authors:
            # Take first author as primary
            first_author = authors[0]
            if isinstance(first_author, dict):
                metadata.author = first_author.get("name", "")
            else:
                metadata.author = str(first_author)
            # Store all authors in custom
            if len(authors) > 1:
                metadata.custom["authors"] = authors
        elif isinstance(authors, str):
            metadata.author = authors

    def _extract_date_metadata(self, nb_metadata: dict, metadata: DocumentMetadata) -> None:
        """Extract creation and modification dates from notebook metadata.

        Parameters
        ----------
        nb_metadata : dict
            Notebook metadata dictionary
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        if "created" in nb_metadata:
            metadata.creation_date = nb_metadata["created"]
        if "modified" in nb_metadata:
            metadata.modification_date = nb_metadata["modified"]

    def _extract_cell_statistics(self, cells: list, metadata: DocumentMetadata) -> None:
        """Extract cell count statistics from notebook cells.

        Parameters
        ----------
        cells : list
            List of notebook cells
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        if not cells:
            return

        metadata.custom["cell_count"] = len(cells)
        # Count by cell type
        code_cells = sum(1 for cell in cells if cell.get("cell_type") == "code")
        markdown_cells = sum(1 for cell in cells if cell.get("cell_type") == "markdown")
        if code_cells:
            metadata.custom["code_cells"] = code_cells
        if markdown_cells:
            metadata.custom["markdown_cells"] = markdown_cells

    def _extract_custom_metadata(self, nb_metadata: dict, metadata: DocumentMetadata) -> None:
        """Extract custom metadata from notebook (extensions, tags, etc.).

        Parameters
        ----------
        nb_metadata : dict
            Notebook metadata dictionary
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        excluded_keys = ["kernelspec", "language_info", "authors", "title", "created", "modified"]

        for key, value in nb_metadata.items():
            if key in excluded_keys:
                continue

            # Only include simple types in custom metadata
            if isinstance(value, (str, int, float, bool)):
                metadata.custom[f"notebook_{key}"] = value
            elif isinstance(value, (list, dict)) and key in ["tags", "keywords"]:
                # Special handling for tags/keywords
                if isinstance(value, list):
                    metadata.keywords = value
                else:
                    metadata.custom[key] = value

    def _extract_title_from_cells(self, cells: list, metadata: DocumentMetadata) -> None:
        """Extract title from first markdown cell if not already set.

        Parameters
        ----------
        cells : list
            List of notebook cells
        metadata : DocumentMetadata
            Metadata object to update in-place

        """
        if metadata.title or not cells:
            return

        for cell in cells:
            if cell.get("cell_type") == "markdown":
                source = self._get_source(cell)
                lines = source.strip().split("\n")
                for line in lines:
                    if line.strip().startswith("#"):
                        # Found a header, use as title
                        metadata.title = line.lstrip("#").strip()
                        break
                if metadata.title:
                    break

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
        nb_metadata = document.get("metadata", {})
        cells = document.get("cells", [])

        # Extract title if present
        if "title" in nb_metadata:
            metadata.title = nb_metadata["title"]

        # Extract kernel and language information
        self._extract_kernel_metadata(nb_metadata, metadata)

        # Extract author information
        self._extract_author_metadata(nb_metadata, metadata)

        # Extract creation and modification dates
        self._extract_date_metadata(nb_metadata, metadata)

        # Extract notebook format version
        nbformat = document.get("nbformat", "")
        nbformat_minor = document.get("nbformat_minor", "")
        if nbformat:
            metadata.custom["notebook_format"] = f"{nbformat}.{nbformat_minor}" if nbformat_minor else str(nbformat)

        # Extract cell statistics
        self._extract_cell_statistics(cells, metadata)

        # Extract custom metadata (extensions, tags, etc.)
        self._extract_custom_metadata(nb_metadata, metadata)

        # Extract title from first markdown cell if not already set
        self._extract_title_from_cells(cells, metadata)

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
    parser_class=IpynbToAstConverter,
    renderer_class="IpynbRenderer",
    parser_required_packages=[],
    renderer_required_packages=[],
    parser_options_class=IpynbOptions,
    renderer_options_class=IpynbRendererOptions,
    description="Convert Jupyter Notebooks between AST and .ipynb",
    priority=7,
)
