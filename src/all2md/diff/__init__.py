#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/__init__.py
"""Document comparison and diff functionality.

This module provides tools for comparing documents in different formats
and generating unified diffs, similar to the Unix diff command but supporting
any document format (PDF, DOCX, HTML, etc.).

Key Features
------------
- Cross-format document comparison (PDF vs DOCX, etc.)
- Text-based comparison using Python's difflib (guaranteed symmetric)
- Multiple output formats (unified diff, HTML visual, JSON)
- Optional whitespace normalization
- Works exactly like Unix diff but for any document format

Examples
--------
Compare two documents and get unified diff:
    >>> from all2md.diff import compare_files
    >>> diff_lines = compare_files("report_v1.pdf", "report_v2.pdf")
    >>> for line in diff_lines:
    ...     print(line)

Compare with whitespace normalization:
    >>> diff_lines = compare_files("doc1.docx", "doc2.docx", ignore_whitespace=True)

Render as HTML:
    >>> from all2md.diff.renderers import HtmlDiffRenderer
    >>> diff_lines = compare_files("doc1.pdf", "doc2.pdf")
    >>> renderer = HtmlDiffRenderer()
    >>> html = renderer.render(diff_lines)

"""

from all2md.diff.text_diff import DiffResult, compare_documents, compare_files

__all__ = [
    "DiffResult",
    "compare_documents",
    "compare_files",
]
