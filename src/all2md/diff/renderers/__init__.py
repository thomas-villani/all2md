#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/renderers/__init__.py
"""Diff renderers for various output formats.

This module provides renderers for converting unified diff output into various
formats including HTML, JSON, and colorized terminal output.

Available Renderers
-------------------
- HtmlDiffRenderer: Visual HTML output with GitHub-style inline highlighting
- JsonDiffRenderer: Structured JSON output for programmatic access
- UnifiedDiffRenderer: Colorized unified diff output for terminal

Examples
--------
Render diff as HTML:
    >>> from all2md.diff import compare_files
    >>> from all2md.diff.renderers import HtmlDiffRenderer
    >>> diff_lines = compare_files("old.pdf", "new.pdf")
    >>> renderer = HtmlDiffRenderer()
    >>> html = renderer.render(diff_lines)

Render with colors for terminal:
    >>> from all2md.diff.renderers import UnifiedDiffRenderer
    >>> diff_lines = compare_files("old.docx", "new.docx")
    >>> renderer = UnifiedDiffRenderer(use_color=True)
    >>> for line in renderer.render(diff_lines):
    ...     print(line)

"""

from all2md.diff.renderers.html import HtmlDiffRenderer
from all2md.diff.renderers.json import JsonDiffRenderer
from all2md.diff.renderers.unified import UnifiedDiffRenderer

__all__ = [
    "HtmlDiffRenderer",
    "JsonDiffRenderer",
    "UnifiedDiffRenderer",
]
