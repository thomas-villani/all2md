#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/text_diff.py
"""Simple text-based document comparison using difflib.

This module provides a simplified diff implementation that works like Unix diff
but supports any document format. It extracts plain text from documents and uses
Python's built-in difflib.unified_diff() for symmetric, predictable comparison.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Literal, Sequence, Union

from all2md import to_ast
from all2md.ast.nodes import (
    BlockQuote,
    CodeBlock,
    Document,
    Heading,
    List,
    ListItem,
    Node,
    Paragraph,
    Table,
    Text,
    ThematicBreak,
    get_node_children,
)

Granularity = Literal["block", "sentence", "word"]


@dataclass(slots=True)
class DiffOp:
    """Structured diff operation between two sequences."""

    tag: Literal["replace", "delete", "insert", "equal"]
    old_slice: Sequence[str]
    new_slice: Sequence[str]
    old_range: tuple[int, int]
    new_range: tuple[int, int]


class DiffResult:
    """Bundle diff sequences for multiple renderers.

    Instances behave like an iterator over unified diff lines so existing
    callers can continue to iterate directly, while renderers that need
    richer structure (HTML/JSON) can introspect operations or raw sequences.
    """

    def __init__(
        self,
        old_lines: list[str],
        new_lines: list[str],
        *,
        old_label: str,
        new_label: str,
        context_lines: int,
        granularity: Granularity,
    ) -> None:
        """Store the precomputed diff sequences and metadata.

        Parameters
        ----------
        old_lines : list of str
            Extracted text lines from the original document.
        new_lines : list of str
            Extracted text lines from the updated document.
        old_label : str
            Label that should appear in the diff header for the original file.
        new_label : str
            Label that should appear in the diff header for the updated file.
        context_lines : int
            Number of context lines to include when rendering unified diffs.
        granularity : Granularity
            Tokenisation level used to build ``old_lines`` and ``new_lines``.

        """
        self.old_lines = old_lines
        self.new_lines = new_lines
        self.old_label = old_label
        self.new_label = new_label
        self.context_lines = context_lines
        self.granularity = granularity
        self._ops: list[DiffOp] | None = None

    def __iter__(self) -> Iterator[str]:
        """Iterate over the unified diff output."""
        yield from self.iter_unified_diff()

    def iter_unified_diff(self, context_lines: int | None = None) -> Iterator[str]:
        """Yield unified diff lines using the cached sequences."""
        n = self.context_lines if context_lines is None else context_lines
        yield from difflib.unified_diff(
            self.old_lines,
            self.new_lines,
            fromfile=self.old_label,
            tofile=self.new_label,
            n=n,
            lineterm="",
        )

    def iter_operations(self) -> Iterator[DiffOp]:
        """Yield SequenceMatcher operations for structured renderers."""
        if self._ops is None:
            matcher = difflib.SequenceMatcher(
                None,
                self.old_lines,
                self.new_lines,
                autojunk=False,
            )
            self._ops = [
                DiffOp(
                    tag,
                    self.old_lines[i1:i2],
                    self.new_lines[j1:j2],
                    (i1, i2),
                    (j1, j2),
                )
                for tag, i1, i2, j1, j2 in matcher.get_opcodes()
            ]
        yield from self._ops


def extract_text_content(node: Node) -> str:
    """Extract all text content from a node and its children.

    Parameters
    ----------
    node : Node
        AST node to extract text from

    Returns
    -------
    str
        All text content concatenated

    """
    if isinstance(node, (Text, CodeBlock)):
        return node.content

    parts: list[str] = []
    for child in get_node_children(node):
        child_text = extract_text_content(child)
        if child_text:
            parts.append(child_text)

    return " ".join(parts)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.

    Parameters
    ----------
    text : str
        Text to normalize

    Returns
    -------
    str
        Normalized text with consistent whitespace

    """
    # Replace all whitespace sequences with single space
    normalized = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return normalized.strip()


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_WORD_SPLIT_RE = re.compile(r"\S+")


def _tokenize_text(text: str, granularity: Granularity) -> list[str]:
    """Split text according to requested granularity."""
    if not text:
        return []

    if granularity == "block":
        return [text]

    if granularity == "sentence":
        sentences = [segment.strip() for segment in _SENTENCE_SPLIT_RE.split(text) if segment.strip()]
        return sentences or [text.strip()]

    if granularity == "word":
        return _WORD_SPLIT_RE.findall(text)

    raise ValueError(f"Unsupported granularity: {granularity}")


def _prepare_text(
    text: str,
    *,
    ignore_whitespace: bool,
    treat_as_code: bool,
) -> str:
    """Apply whitespace normalisation rules for the current node."""
    if not ignore_whitespace:
        return text

    if treat_as_code:
        # Preserve indentation but remove trailing whitespace inconsistencies
        return text.rstrip()

    return normalize_whitespace(text)


class _DocumentLineExtractor:
    """Walk an AST and emit text lines suitable for diffing."""

    def __init__(self, ignore_whitespace: bool, granularity: Granularity) -> None:
        self.ignore_whitespace = ignore_whitespace
        self.granularity = granularity
        self.lines: list[str] = []

    def extract(self, doc: Document) -> list[str]:
        """Convert a document AST into a flat list of text lines."""
        self.lines.clear()
        for node in doc.children:
            self._process_node(node, prefix="")
        return self.lines

    def _process_node(self, node: Node, prefix: str) -> None:
        if isinstance(node, Heading):
            self._handle_heading(node, prefix)
        elif isinstance(node, Paragraph):
            self._handle_paragraph(node, prefix)
        elif isinstance(node, CodeBlock):
            self._handle_code_block(node, prefix)
        elif isinstance(node, BlockQuote):
            for child in node.children:
                self._process_node(child, prefix=prefix + "> ")
        elif isinstance(node, ThematicBreak):
            self._emit_tokens(["---"], prefix=prefix)
        elif isinstance(node, List):
            self._handle_list(node, prefix)
        elif isinstance(node, Table):
            self._handle_table(node, prefix)
        else:
            for child in get_node_children(node):
                self._process_node(child, prefix=prefix)

    def _handle_heading(self, node: Heading, prefix: str) -> None:
        text = _prepare_text(
            extract_text_content(node),
            ignore_whitespace=self.ignore_whitespace,
            treat_as_code=False,
        )
        tokens = self._tokenize(text)
        if tokens:
            marker = "#" * node.level
            self._emit_tokens(tokens, prefix=prefix, leading_marker=marker)

    def _handle_paragraph(self, node: Paragraph, prefix: str) -> None:
        text = _prepare_text(
            extract_text_content(node),
            ignore_whitespace=self.ignore_whitespace,
            treat_as_code=False,
        )
        tokens = self._tokenize(text)
        if tokens:
            continuation = self._continuation_prefix(prefix)
            self._emit_tokens(tokens, prefix=prefix, continuation_prefix=continuation)

    def _handle_code_block(self, node: CodeBlock, prefix: str) -> None:
        lang = node.language or ""
        continuation = self._continuation_prefix(prefix)

        self._emit_tokens([f"```{lang}"], prefix=prefix)

        content = node.content
        if self.ignore_whitespace:
            code_lines = [
                _prepare_text(line, ignore_whitespace=True, treat_as_code=True) for line in content.split("\n")
            ]
        else:
            code_lines = content.split("\n")

        self._emit_tokens(
            code_lines,
            prefix=prefix,
            continuation_prefix=continuation if prefix else "",
        )
        self._emit_tokens(["```"], prefix=prefix)

    def _handle_list(self, node: List, prefix: str) -> None:
        for index, item in enumerate(node.items):
            if node.ordered:
                number = index + (node.start or 1)
                item_prefix = f"{prefix}{number}. "
            else:
                if item.task_status == "unchecked":
                    bullet = "- [ ] "
                elif item.task_status == "checked":
                    bullet = "- [x] "
                else:
                    bullet = "- "
                item_prefix = f"{prefix}{bullet}"
            self._process_list_item(item, item_prefix)

    def _handle_table(self, node: Table, prefix: str) -> None:
        header_cells = list(node.header.cells) if node.header else []
        header_text = [
            _prepare_text(
                extract_text_content(cell),
                ignore_whitespace=self.ignore_whitespace,
                treat_as_code=False,
            )
            for cell in header_cells
        ]

        if header_text:
            header_line = " | ".join(header_text)
            self._emit_tokens([f"| {header_line} |"], prefix=prefix)

            alignment_cells: list[str] = []
            for alignment in node.alignments or []:
                if alignment == "left":
                    alignment_cells.append(":---")
                elif alignment == "center":
                    alignment_cells.append(":---:")
                elif alignment == "right":
                    alignment_cells.append("---:")
                else:
                    alignment_cells.append("---")
            while len(alignment_cells) < len(header_text):
                alignment_cells.append("---")
            separator = "| " + " | ".join(alignment_cells[: len(header_text)]) + " |"
            self._emit_tokens([separator], prefix=prefix)

        for row in node.rows:
            cell_texts = [
                _prepare_text(
                    extract_text_content(cell),
                    ignore_whitespace=self.ignore_whitespace,
                    treat_as_code=False,
                )
                for cell in row.cells
            ]
            row_line = "| " + " | ".join(cell_texts) + " |"
            self._emit_tokens([row_line], prefix=prefix)

    def _process_list_item(self, item: ListItem, prefix: str) -> None:
        text_parts: list[str] = []
        for child in item.children:
            if isinstance(child, List):
                continue
            text = extract_text_content(child)
            if text:
                prepared = _prepare_text(
                    text,
                    ignore_whitespace=self.ignore_whitespace,
                    treat_as_code=False,
                )
                text_parts.extend(self._tokenize(prepared))

        if text_parts:
            self._emit_tokens(
                text_parts,
                prefix=prefix,
                continuation_prefix=" " * len(prefix),
            )

        for child in item.children:
            if isinstance(child, List):
                nested_prefix = " " * len(prefix)
                self._process_node(child, prefix=nested_prefix)

    def _emit_tokens(
        self,
        tokens: Iterable[str],
        *,
        prefix: str,
        continuation_prefix: str | None = None,
        leading_marker: str | None = None,
    ) -> None:
        if continuation_prefix is None:
            continuation_prefix = prefix

        for index, token in enumerate(tokens):
            current_prefix = prefix if index == 0 else continuation_prefix
            line_content = token
            if leading_marker is not None and index == 0:
                line_content = f"{leading_marker} {line_content}" if line_content else leading_marker
            if current_prefix:
                self.lines.append(f"{current_prefix}{line_content}")
            else:
                self.lines.append(line_content)

    def _continuation_prefix(self, prefix: str) -> str:
        clean_prefix = prefix.strip()
        if not prefix:
            return prefix
        if clean_prefix.startswith(("-", "*", "+", "[")) or (
            clean_prefix.endswith(".") and clean_prefix[:-1].isdigit()
        ):
            return " " * len(prefix)
        return prefix

    def _tokenize(self, text: str) -> list[str]:
        return _tokenize_text(text, self.granularity)


def extract_document_lines(
    doc: Document,
    *,
    ignore_whitespace: bool = False,
    granularity: Granularity = "block",
) -> list[str]:
    """Extract plain text lines from a document AST.

    This function converts the document structure into a list of text lines,
    one per structural element (heading, paragraph, list item, etc.). This
    preserves document structure while enabling line-based diff comparison.

    Parameters
    ----------
    doc : Document
        Document AST to extract lines from
    ignore_whitespace : bool, default = False
        If True, normalize whitespace in each line
    granularity : {'block', 'sentence', 'word'}, default = 'block'
        Tokenisation level used when splitting paragraph content into lines.

    Returns
    -------
    list of str
        Lines of text, one per structural element

    """
    extractor = _DocumentLineExtractor(ignore_whitespace, granularity)
    return extractor.extract(doc)


def compare_documents(
    old_doc: Document,
    new_doc: Document,
    old_label: str = "old",
    new_label: str = "new",
    context_lines: int = 3,
    ignore_whitespace: bool = False,
    granularity: Granularity = "block",
) -> DiffResult:
    """Compare two document ASTs and generate unified diff.

    This function extracts plain text lines from both documents and uses
    Python's difflib.unified_diff() to generate a standard unified diff.
    The result is guaranteed to be symmetric: comparing A to B produces
    the exact opposite of comparing B to A (with +/- swapped).

    Parameters
    ----------
    old_doc : Document
        Original document AST
    new_doc : Document
        New document AST
    old_label : str, default = "old"
        Label for old version in diff header
    new_label : str, default = "new"
        Label for new version in diff header
    context_lines : int, default = 3
        Number of context lines to show around changes
    ignore_whitespace : bool, default = False
        If True, normalize whitespace before comparison
    granularity : {'block', 'sentence', 'word'}, default = 'block'
        Tokenisation level used when extracting text from each document.
    granularity : {'block', 'sentence', 'word'}, default = 'block'
        Tokenisation level used when extracting lines from the documents.

    Returns
    -------
    DiffResult
        Diff result encapsulating sequences and render helpers

    """
    old_lines = extract_document_lines(
        old_doc,
        ignore_whitespace=ignore_whitespace,
        granularity=granularity,
    )
    new_lines = extract_document_lines(
        new_doc,
        ignore_whitespace=ignore_whitespace,
        granularity=granularity,
    )

    return DiffResult(
        old_lines,
        new_lines,
        old_label=old_label,
        new_label=new_label,
        context_lines=context_lines,
        granularity=granularity,
    )


def compare_files(
    old_path: Union[str, Path],
    new_path: Union[str, Path],
    old_label: str | None = None,
    new_label: str | None = None,
    context_lines: int = 3,
    ignore_whitespace: bool = False,
    granularity: Granularity = "block",
) -> DiffResult:
    """Compare two document files and generate unified diff.

    This is a convenience wrapper that loads documents from files,
    converts them to AST, and compares them using compare_documents().

    Parameters
    ----------
    old_path : str or Path
        Path to original document file
    new_path : str or Path
        Path to new document file
    old_label : str, optional
        Label for old version (defaults to filename)
    new_label : str, optional
        Label for new version (defaults to filename)
    context_lines : int, default = 3
        Number of context lines to show around changes
    ignore_whitespace : bool, default = False
        If True, normalize whitespace before comparison
    granularity : Granularity, default = 'block'
        The level of granularity of details.

    Returns
    -------
    DiffResult
        Diff result encapsulating sequences and render helpers

    """
    # Convert paths to Path objects
    old_path = Path(old_path)
    new_path = Path(new_path)

    # Use filenames as labels if not provided
    if old_label is None:
        old_label = str(old_path)
    if new_label is None:
        new_label = str(new_path)

    # Load documents as AST
    old_doc = to_ast(old_path)
    new_doc = to_ast(new_path)

    # Compare using compare_documents
    return compare_documents(
        old_doc,
        new_doc,
        old_label=old_label,
        new_label=new_label,
        context_lines=context_lines,
        ignore_whitespace=ignore_whitespace,
        granularity=granularity,
    )
