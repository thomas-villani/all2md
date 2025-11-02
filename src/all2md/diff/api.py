#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/api.py
"""Python API for document diff comparison.

This module provides high-level Python functions for comparing documents
and rendering diffs in various formats.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from all2md import to_ast
from all2md.ast.nodes import Document
from all2md.diff.ast_comparator import ASTComparator
from all2md.diff.change_nodes import DiffDocument
from all2md.diff.renderers import HtmlDiffRenderer, JsonDiffRenderer, MarkdownDiffRenderer, UnifiedDiffRenderer
from all2md.diff.strategies import HybridStrategy, LenientTextualStrategy, StructuralStrategy, TextualStrategy


def diff_documents(
    source1: str | Path | Document,
    source2: str | Path | Document,
    strategy: str = "hybrid",
    ignore_formatting: bool = False,
    ignore_whitespace: bool = False,
    moved_detection: str = "basic",
    similarity_threshold: float = 0.8,
    **kwargs: Any,
) -> DiffDocument:
    """Compare two documents and return a diff.

    This function loads two documents (from file paths or Document objects),
    compares them using the specified strategy, and returns a DiffDocument
    containing the changes.

    Parameters
    ----------
    source1 : str, Path, or Document
        First document to compare. Can be a file path or Document AST.
    source2 : str, Path, or Document
        Second document to compare. Can be a file path or Document AST.
    strategy : {"structural", "textual", "lenient", "hybrid"}, default "hybrid"
        Comparison strategy to use:
        - "structural": Focus on document structure
        - "textual": Focus on text content
        - "lenient": Aggressive normalization (lowercase, whitespace)
        - "hybrid": Balanced default
    ignore_formatting : bool, default False
        If True, ignore inline formatting differences
    ignore_whitespace : bool, default False
        If True, ignore whitespace differences
    moved_detection : {"off", "basic", "fuzzy"}, default "basic"
        Level of moved content detection
    similarity_threshold : float, default 0.8
        Threshold for fuzzy matching (0.0-1.0)
    **kwargs : dict
        Additional options passed to ASTComparator

    Returns
    -------
    DiffDocument
        Document containing diff information with change annotations

    Raises
    ------
    ValueError
        If sources cannot be loaded or strategy is invalid
    FileNotFoundError
        If source files do not exist

    Examples
    --------
    Compare two files:
        >>> from all2md.diff.api import diff_documents
        >>> diff = diff_documents("report_v1.pdf", "report_v2.pdf")
        >>> print(f"Changes: {diff.stats.total_changes}")

    Compare with custom strategy:
        >>> diff = diff_documents(
        ...     "doc1.docx",
        ...     "doc2.docx",
        ...     strategy="structural",
        ...     ignore_formatting=True
        ... )

    Compare Document objects directly:
        >>> from all2md import to_ast
        >>> doc1 = to_ast("file1.md")
        >>> doc2 = to_ast("file2.md")
        >>> diff = diff_documents(doc1, doc2)

    """
    # Load documents if they're paths
    if isinstance(source1, (str, Path)):
        source1_path = Path(source1)
        if not source1_path.exists():
            raise FileNotFoundError(f"Source file not found: {source1}")
        doc1 = to_ast(str(source1_path))
        if not isinstance(doc1, Document):
            raise ValueError(f"Failed to parse {source1} as document")
    elif isinstance(source1, Document):
        doc1 = source1
    else:
        raise ValueError(f"source1 must be str, Path, or Document, got {type(source1)}")

    if isinstance(source2, (str, Path)):
        source2_path = Path(source2)
        if not source2_path.exists():
            raise FileNotFoundError(f"Source file not found: {source2}")
        doc2 = to_ast(str(source2_path))
        if not isinstance(doc2, Document):
            raise ValueError(f"Failed to parse {source2} as document")
    elif isinstance(source2, Document):
        doc2 = source2
    else:
        raise ValueError(f"source2 must be str, Path, or Document, got {type(source2)}")

    # Create comparison strategy
    strategy_map = {
        "structural": StructuralStrategy(),
        "textual": TextualStrategy(),
        "lenient": LenientTextualStrategy(),
        "hybrid": HybridStrategy(),
    }
    if strategy not in strategy_map:
        raise ValueError(f"Invalid strategy: {strategy}. Must be one of: {', '.join(strategy_map.keys())}")

    strategy_obj = strategy_map[strategy]

    # Create comparator
    comparator = ASTComparator(
        strategy=strategy_obj,
        ignore_formatting=ignore_formatting,
        ignore_whitespace=ignore_whitespace,
        moved_detection=moved_detection,
        similarity_threshold=similarity_threshold,
        **kwargs,
    )

    # Compare and return diff
    return comparator.compare(doc1, doc2)


def render_diff(
    diff: DiffDocument,
    format: str = "text",
    show_unchanged: bool = False,
    show_stats: bool = True,
    context_lines: int = 3,
    pretty_print: bool = True,
    inline_styles: bool = True,
    side_by_side: bool = False,
    **kwargs: Any,
) -> str:
    """Render a diff in the specified format.

    Parameters
    ----------
    diff : DiffDocument
        Diff document to render
    format : {"text", "visual", "unified", "json"}, default "text"
        Output format:
        - "text": Markdown-style diff
        - "visual": HTML with color-coding
        - "unified": Standard unified diff (patch-compatible)
        - "json": Structured JSON output
    show_unchanged : bool, default False
        If True, show unchanged content
    show_stats : bool, default True
        If True, include statistics in output
    context_lines : int, default 3
        Context lines for unified diff
    pretty_print : bool, default True
        Pretty print JSON output
    inline_styles : bool, default True
        Include inline CSS in HTML output
    side_by_side : bool, default False
        Use side-by-side layout for HTML
    **kwargs : dict
        Additional options passed to renderer

    Returns
    -------
    str
        Rendered diff output

    Raises
    ------
    ValueError
        If format is invalid

    Examples
    --------
    Render as Markdown:
        >>> from all2md.diff.api import diff_documents, render_diff
        >>> diff = diff_documents("v1.md", "v2.md")
        >>> markdown = render_diff(diff, format="text")
        >>> print(markdown)

    Render as HTML and save:
        >>> html = render_diff(diff, format="visual", side_by_side=True)
        >>> with open("diff.html", "w") as f:
        ...     f.write(html)

    Render as unified diff:
        >>> patch = render_diff(diff, format="unified", context_lines=5)

    """
    if format == "text":
        renderer = MarkdownDiffRenderer(show_unchanged=show_unchanged, **kwargs)
    elif format == "visual":
        renderer = HtmlDiffRenderer(
            show_unchanged=show_unchanged,
            inline_styles=inline_styles,
            show_stats=show_stats,
            side_by_side=side_by_side,
            **kwargs,
        )
    elif format == "unified":
        renderer = UnifiedDiffRenderer(context_lines=context_lines, **kwargs)
    elif format == "json":
        renderer = JsonDiffRenderer(pretty_print=pretty_print, **kwargs)
    else:
        raise ValueError(f"Invalid format: {format}. Must be one of: text, visual, unified, json")

    return renderer.render_to_string(diff)
