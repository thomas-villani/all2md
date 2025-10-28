"""Renderer for converting AST documents back into Jupyter notebooks."""

from __future__ import annotations

import io
import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Dict, List, Optional, Tuple, Union, cast

from all2md.ast import Document
from all2md.ast.nodes import CodeBlock, Comment, CommentInline, Image, Node
from all2md.options.ipynb import IpynbRendererOptions
from all2md.renderers.base import BaseRenderer
from all2md.renderers.markdown import MarkdownRenderer


@dataclass
class _CellAccumulator:
    """Holds intermediate state while grouping AST nodes into notebook cells."""

    key: Tuple[Optional[int], Optional[str]]
    cell_type: str
    cell_id: Optional[str]
    metadata: Dict[str, Any]
    attachments: Optional[Dict[str, Any]]
    execution_count: Optional[int]
    source_override: Optional[str]
    execution_count_was_inlined: bool
    markdown_plaintext: bool = False
    body_nodes: List[Node] = field(default_factory=list)
    outputs: List[Optional[Dict[str, Any]]] = field(default_factory=list)
    raw_outputs: List[Dict[str, Any]] = field(default_factory=list)


class IpynbRenderer(BaseRenderer):
    """Render an all2md AST document into a Jupyter notebook (ipynb)."""

    def __init__(self, options: IpynbRendererOptions | None = None):
        """Initialize the Jupyter notebook renderer.

        Parameters
        ----------
        options : IpynbRendererOptions or None, optional
            Renderer options for Jupyter notebooks

        """
        BaseRenderer._validate_options_type(options, IpynbRendererOptions, "ipynb")
        options = options or IpynbRendererOptions()
        super().__init__(options)
        self.options: IpynbRendererOptions = options

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def render(self, doc: Document, output: Union[str, Path, IO[bytes], IO[str]]) -> None:
        """Render the AST document to a file path or binary stream."""
        notebook_str = self.render_to_string(doc)
        data = notebook_str.encode("utf-8")

        if isinstance(output, (str, Path)):
            Path(output).write_bytes(data)
            return

        # Handle both binary and text streams
        if isinstance(output, (io.BytesIO, io.BufferedWriter)) or (
            hasattr(output, "mode") and "b" in getattr(output, "mode", "")
        ):
            # Binary stream
            cast(IO[bytes], output).write(data)
        else:
            # Text mode stream
            cast(IO[str], output).write(notebook_str)

    def render_to_string(self, doc: Document) -> str:
        """Render the AST document to an in-memory JSON string."""
        notebook = self._build_notebook(doc)
        return json.dumps(notebook, ensure_ascii=False, indent=2) + "\n"

    # ---------------------------------------------------------------------
    # Notebook assembly
    # ---------------------------------------------------------------------

    def _build_notebook(self, document: Document) -> Dict[str, Any]:
        bundle = self._extract_notebook_bundle(document)
        metadata = self._build_notebook_metadata(document, bundle)
        nbformat = self._resolve_nbformat(bundle)
        nbformat_minor = self._resolve_nbformat_minor(bundle, nbformat)
        cells = self._collect_cells(document)

        return {
            "cells": cells,
            "metadata": metadata,
            "nbformat": nbformat,
            "nbformat_minor": nbformat_minor,
        }

    def _extract_notebook_bundle(self, document: Document) -> Dict[str, Any]:
        meta = document.metadata or {}
        bundle = meta.get("ipynb_notebook")
        if isinstance(bundle, dict):
            # Copy to avoid mutating the document metadata downstream
            return deepcopy(bundle)
        return {}

    def _resolve_nbformat(self, bundle: Dict[str, Any]) -> int:
        option_value = self.options.nbformat
        if option_value == "auto":
            candidate = bundle.get("nbformat")
            if isinstance(candidate, int):
                return candidate
            return 4
        return option_value

    def _resolve_nbformat_minor(self, bundle: Dict[str, Any], nbformat: int) -> int:
        option_value = self.options.nbformat_minor
        if option_value == "auto":
            candidate = bundle.get("nbformat_minor")
            if isinstance(candidate, int):
                return candidate
            # Sensible defaults per major version
            return 5 if nbformat == 4 else 0
        return option_value

    # ------------------------------------------------------------------
    # Metadata handling
    # ------------------------------------------------------------------

    def _build_notebook_metadata(self, document: Document, bundle: Dict[str, Any]) -> Dict[str, Any]:
        """Construct notebook-level metadata with inference heuristics."""
        metadata = bundle.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        else:
            # Deep copy to avoid mutating bundle
            metadata = deepcopy(metadata)

        language = self._resolve_language(document, metadata)
        self._ensure_language_metadata(document, metadata, language)
        self._ensure_kernel_metadata(document, metadata, language)

        return metadata

    def _resolve_language(self, document: Document, metadata: Dict[str, Any]) -> str:
        """Determine preferred programming language for language_info."""
        if isinstance(metadata.get("language_info"), dict):
            lang = metadata["language_info"].get("name")
            if isinstance(lang, str) and lang.strip():
                return lang

        if self.options.infer_language_from_document:
            doc_meta = document.metadata or {}
            for key in ("language", "language_info", "programming_language"):
                value = doc_meta.get(key)
                if isinstance(value, str) and value.strip():
                    return value
            # Older parsers stored version info under language_version
            lang_from_custom = doc_meta.get("custom") if isinstance(doc_meta.get("custom"), dict) else None
            if isinstance(lang_from_custom, dict):
                value = lang_from_custom.get("language")
                if isinstance(value, str) and value.strip():
                    return value

        return self.options.default_language

    def _ensure_language_metadata(
        self,
        document: Document,
        metadata: Dict[str, Any],
        language: str,
    ) -> None:
        lang_info = metadata.get("language_info")
        if not isinstance(lang_info, dict):
            lang_info = {}

        if not lang_info.get("name"):
            lang_info["name"] = language

        if self.options.infer_language_from_document and not lang_info.get("version"):
            doc_meta = document.metadata or {}
            version = doc_meta.get("language_version") or doc_meta.get("language_info_version")
            if isinstance(version, str) and version.strip():
                lang_info["version"] = version

        metadata["language_info"] = lang_info

    def _ensure_kernel_metadata(
        self,
        document: Document,
        metadata: Dict[str, Any],
        language: str,
    ) -> None:
        kernelspec = metadata.get("kernelspec")
        if not isinstance(kernelspec, dict):
            kernelspec = {}

        if self.options.infer_kernel_from_document:
            doc_meta = document.metadata or {}
            kernel_name = doc_meta.get("kernel")
            if isinstance(kernel_name, str) and kernel_name.strip() and not kernelspec.get("name"):
                kernelspec["name"] = kernel_name
            kernel_display = doc_meta.get("kernel_display_name")
            if isinstance(kernel_display, str) and kernel_display.strip() and not kernelspec.get("display_name"):
                kernelspec["display_name"] = kernel_display

        kernelspec.setdefault("name", self.options.default_kernel_name)
        kernelspec.setdefault("display_name", self.options.default_kernel_display_name)
        kernelspec.setdefault("language", language)

        metadata["kernelspec"] = kernelspec

    # ------------------------------------------------------------------
    # Cell assembly
    # ------------------------------------------------------------------

    def _collect_cells(self, document: Document) -> List[Dict[str, Any]]:
        cells: List[Dict[str, Any]] = []
        pending_markdown: List[Node] = []
        current: Optional[_CellAccumulator] = None

        def finalize_current() -> None:
            nonlocal current
            if current is None:
                return
            cells.append(self._finalize_cell(current))
            current = None

        def flush_pending_markdown() -> None:
            nonlocal pending_markdown
            if not pending_markdown:
                return
            cells.append(self._markdown_nodes_to_cell(pending_markdown))
            pending_markdown = []

        for node in document.children:
            info = self._extract_ipynb_info(node)
            if not info:
                finalize_current()
                pending_markdown.append(node)
                continue

            flush_pending_markdown()

            key = self._cell_key_from_info(info)
            if current is None or current.key != key:
                finalize_current()
                current = self._start_cell_from_info(info)

            role = info.get("role")
            if role == "output":
                self._append_output_node(current, node, info)
            else:
                current.body_nodes.append(node)

        finalize_current()
        flush_pending_markdown()

        return cells

    def _cell_key_from_info(self, info: Dict[str, Any]) -> Tuple[Optional[int], Optional[str]]:
        return info.get("cell_index"), info.get("cell_id")

    def _start_cell_from_info(self, info: Dict[str, Any]) -> _CellAccumulator:
        cell_type = info.get("cell_type") or "markdown"
        metadata = info.get("cell_metadata")
        if not isinstance(metadata, dict):
            metadata = {}

        attachments = info.get("attachments")
        if isinstance(attachments, dict) and not attachments:
            attachments = None

        raw_outputs = info.get("raw_outputs")
        if isinstance(raw_outputs, list):
            raw_outputs_copy = deepcopy(raw_outputs)
        else:
            raw_outputs_copy = []

        return _CellAccumulator(
            key=self._cell_key_from_info(info),
            cell_type=cell_type,
            cell_id=info.get("cell_id"),
            metadata=deepcopy(metadata),
            attachments=deepcopy(attachments) if attachments else None,
            execution_count=info.get("execution_count"),
            source_override=info.get("source"),
            execution_count_was_inlined=bool(info.get("execution_count_was_inlined")),
            markdown_plaintext=bool(info.get("markdown_plaintext")),
            raw_outputs=raw_outputs_copy,
        )

    def _append_output_node(self, cell: _CellAccumulator, node: Node, info: Dict[str, Any]) -> None:
        output_data = info.get("output")
        if output_data is not None:
            output_entry = deepcopy(output_data)
        else:
            output_entry = self._fallback_output_from_node(node)
            if output_entry is None:
                return

        index = info.get("output_index")
        if isinstance(index, int) and index >= 0:
            self._ensure_list_size(cell.outputs, index + 1)
            cell.outputs[index] = output_entry
        else:
            cell.outputs.append(output_entry)

    def _fallback_output_from_node(self, node: Node) -> Optional[Dict[str, Any]]:
        if isinstance(node, CodeBlock) and node.content.strip():
            text = node.content
            if not text.endswith("\n"):
                text = f"{text}\n"
            return {
                "output_type": "stream",
                "name": "stdout",
                "text": [text],
            }

        if isinstance(node, Image) and node.url.startswith("data:"):
            # Attempt to preserve data URI images as display_data outputs
            try:
                header, payload = node.url.split(",", 1)
                mime_type = header.split(";")[0].split(":", 1)[1]
            except (ValueError, IndexError):
                return None
            return {
                "output_type": "display_data",
                "data": {mime_type: payload},
                "metadata": {},
            }

        return None

    def _finalize_cell(self, cell: _CellAccumulator) -> Dict[str, Any]:
        cell_type = cell.cell_type or "markdown"
        metadata = self._filter_cell_metadata(cell.metadata)

        source_text = self._derive_cell_source(cell, cell_type)
        attachments = cell.attachments if self.options.inline_attachments else None

        outputs = [entry for entry in cell.outputs if entry is not None]

        result: Dict[str, Any] = {
            "cell_type": cell_type,
            "metadata": metadata,
            "source": self._string_to_source_lines(source_text),
        }

        if cell.cell_id:
            result["id"] = cell.cell_id

        if attachments:
            result["attachments"] = attachments

        if cell_type == "code":
            result["execution_count"] = cell.execution_count
            result["outputs"] = outputs
        elif cell_type == "raw":
            # Raw cells don't require additional fields
            pass
        else:
            # Markdown cells ignore outputs/execution count
            pass

        return result

    def _derive_cell_source(self, cell: _CellAccumulator, cell_type: str) -> str:
        if cell_type == "code":
            code_node = next((n for n in cell.body_nodes if isinstance(n, CodeBlock)), None)
            if code_node is not None:
                metadata = getattr(code_node, "metadata", {}) or {}
                ipynb_value = metadata.get("ipynb")
                ipynb_meta: dict[Any, Any] = ipynb_value if isinstance(ipynb_value, dict) else {}
                original = ipynb_meta.get("source")
                content = code_node.content

                if original is None:
                    return content

                if cell.execution_count_was_inlined and content.startswith("# In ["):
                    parts = content.split("\n", 1)
                    if len(parts) == 2 and parts[1] == original:
                        return original

                if content != original:
                    return content

                return original

            return cell.source_override or ""

        if cell_type == "markdown":
            if cell.markdown_plaintext and cell.source_override is not None:
                return cell.source_override
            if cell.body_nodes:
                rendered = self._render_markdown_nodes(cell.body_nodes)
                if cell.source_override is not None and rendered == cell.source_override:
                    return rendered
                if rendered.strip():
                    return rendered
            return cell.source_override or ""

        if cell_type == "raw":
            raw_block = next((n for n in cell.body_nodes if isinstance(n, CodeBlock)), None)
            if raw_block is not None:
                if cell.source_override is not None and raw_block.content != cell.source_override:
                    return raw_block.content
                if cell.source_override is not None:
                    return cell.source_override
                return raw_block.content
            return cell.source_override or ""

        # Fallback for unknown cell types
        return cell.source_override or ""

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _render_markdown_nodes(self, nodes: List[Node]) -> str:
        if not nodes:
            return ""
        renderer_options = self.options.markdown_options or None
        renderer = MarkdownRenderer(renderer_options)
        temp_doc = Document(children=nodes)
        return renderer.render_to_string(temp_doc)

    def _filter_cell_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if not metadata:
            return {}

        filtered = deepcopy(metadata)

        if not self.options.include_trusted_metadata:
            filtered.pop("trusted", None)

        if not self.options.include_ui_metadata:
            for key in ("collapsed", "scrolled"):
                filtered.pop(key, None)
            jupyter_meta = filtered.get("jupyter")
            if isinstance(jupyter_meta, dict):
                for ui_key in ("source_hidden", "outputs_hidden", "widgets"):
                    jupyter_meta.pop(ui_key, None)
                if not jupyter_meta:
                    filtered.pop("jupyter")

        if not self.options.preserve_unknown_metadata:
            allowed = {"id", "tags", "slideshow", "nbgrader", "name"}
            filtered = {k: v for k, v in filtered.items() if k in allowed}

        return filtered

    def _markdown_nodes_to_cell(self, nodes: List[Node]) -> Dict[str, Any]:
        text = self._render_markdown_nodes(nodes)
        return {
            "cell_type": "markdown",
            "metadata": {},
            "source": self._string_to_source_lines(text),
        }

    def _extract_ipynb_info(self, node: Node) -> Optional[Dict[str, Any]]:
        metadata = getattr(node, "metadata", {}) or {}
        info = metadata.get("ipynb")
        if isinstance(info, dict):
            return info
        return None

    @staticmethod
    def _ensure_list_size(items: List[Optional[Dict[str, Any]]], size: int) -> None:
        while len(items) < size:
            items.append(None)

    @staticmethod
    def _string_to_source_lines(text: str) -> List[str]:
        if not text:
            return []
        if not text.endswith("\n"):
            text = f"{text}\n"
        return text.splitlines(keepends=True)

    def visit_comment(self, node: Comment) -> None:
        """Render a Comment node (no-op, handled by markdown renderer).

        Parameters
        ----------
        node : Comment
            Comment to render

        Notes
        -----
        Comments are handled by the MarkdownRenderer which is used to render
        markdown cell content. This method exists only to satisfy the visitor
        pattern but is never called during normal rendering flow.

        """
        pass

    def visit_comment_inline(self, node: CommentInline) -> None:
        """Render a CommentInline node (no-op, handled by markdown renderer).

        Parameters
        ----------
        node : CommentInline
            Inline comment to render

        Notes
        -----
        Inline comments are handled by the MarkdownRenderer which is used to
        render markdown cell content. This method exists only to satisfy the
        visitor pattern but is never called during normal rendering flow.

        """
        pass
