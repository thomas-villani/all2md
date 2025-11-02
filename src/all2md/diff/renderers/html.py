#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/renderers/html.py
"""HTML diff renderer with visual color coding.

This renderer produces visual HTML output with color-coded changes,
suitable for viewing in a web browser. It parses unified diff format
and renders it with GitHub-style inline highlighting.
"""

from __future__ import annotations

from html import escape
from io import StringIO
from typing import Iterator, List, Tuple


class HtmlDiffRenderer:
    """Render unified diff as visual HTML with color coding.

    This renderer produces styled HTML output with:
    - Green highlighting for additions
    - Red highlighting for deletions (with strikethrough)
    - Context lines shown in normal text
    - GitHub-style inline rendering

    Parameters
    ----------
    show_context : bool, default = True
        If True, show context lines around changes
    inline_styles : bool, default = True
        If True, include CSS styles in the output

    Examples
    --------
    Render diff as HTML:
        >>> from all2md.diff import compare_files
        >>> from all2md.diff.renderers import HtmlDiffRenderer
        >>> diff_lines = compare_files("old.docx", "new.docx")
        >>> renderer = HtmlDiffRenderer()
        >>> html = renderer.render(diff_lines)
        >>> with open("diff.html", "w") as f:
        ...     f.write(html)

    """

    def __init__(
        self,
        show_context: bool = True,
        inline_styles: bool = True,
    ):
        """Initialize the HTML diff renderer."""
        self.show_context = show_context
        self.inline_styles = inline_styles

    def render(self, diff_lines: Iterator[str]) -> str:
        """Render unified diff to HTML string.

        Parameters
        ----------
        diff_lines : Iterator[str]
            Lines of unified diff output

        Returns
        -------
        str
            HTML-formatted diff output

        """
        output = StringIO()

        # HTML document structure
        output.write("<!DOCTYPE html>\n")
        output.write("<html lang='en'>\n")
        output.write("<head>\n")
        output.write("  <meta charset='UTF-8'>\n")
        output.write("  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n")
        output.write("  <title>Document Diff</title>\n")

        if self.inline_styles:
            output.write("  <style>\n")
            output.write(self._get_css())
            output.write("  </style>\n")

        output.write("</head>\n")
        output.write("<body>\n")
        output.write("  <div class='container'>\n")
        output.write("    <h1>Document Diff</h1>\n")

        # Parse and render diff content
        output.write("    <div class='diff-content'>\n")
        self._render_diff(diff_lines, output)
        output.write("    </div>\n")

        output.write("  </div>\n")
        output.write("</body>\n")
        output.write("</html>\n")

        return output.getvalue()

    def _get_css(self) -> str:
        """Get CSS styles for the HTML output."""
        return """
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .diff-content {
            margin-top: 30px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 14px;
        }
        .diff-header {
            padding: 8px 12px;
            background-color: #f8f9fa;
            border-radius: 4px;
            margin: 15px 0 5px 0;
            font-weight: bold;
            color: #666;
        }
        .diff-hunk-header {
            padding: 6px 12px;
            background-color: #e9ecef;
            border-radius: 4px;
            margin: 10px 0 5px 0;
            color: #0969da;
            font-weight: bold;
        }
        .diff-line {
            padding: 2px 12px;
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        .diff-context {
            background-color: transparent;
        }
        .diff-added {
            background-color: #e6ffed;
            color: #116329;
        }
        .diff-deleted {
            background-color: #ffeef0;
            color: #82071e;
            text-decoration: line-through;
        }
        .inline-view {
            border: 1px solid #ddd;
            border-radius: 4px;
            overflow: hidden;
        }
        .inline-line {
            padding: 4px 12px;
            margin: 0;
            border-left: 4px solid transparent;
        }
        .inline-added {
            background-color: #e6ffed;
            border-left-color: #28a745;
            color: #116329;
        }
        .inline-deleted {
            background-color: #ffeef0;
            border-left-color: #dc3545;
            color: #82071e;
            text-decoration: line-through;
        }
        .inline-context {
            background-color: #ffffff;
        }
        """

    def _parse_diff_lines(self, diff_lines: Iterator[str]) -> List[Tuple[str, str]]:
        """Parse diff lines into (type, content) tuples.

        Returns
        -------
        list of tuple
            Each tuple is (line_type, content) where line_type is one of:
            'header', 'hunk', 'added', 'deleted', 'context'

        """
        parsed_lines: List[Tuple[str, str]] = []

        for line in diff_lines:
            if line.startswith("---") or line.startswith("+++"):
                parsed_lines.append(("header", line))
            elif line.startswith("@@"):
                parsed_lines.append(("hunk", line))
            elif line.startswith("+"):
                parsed_lines.append(("added", line[1:]))  # Remove + prefix
            elif line.startswith("-"):
                parsed_lines.append(("deleted", line[1:]))  # Remove - prefix
            elif line.startswith(" "):
                parsed_lines.append(("context", line[1:]))  # Remove space prefix
            else:
                # Handle lines without prefix (shouldn't happen in well-formed diff)
                parsed_lines.append(("context", line))

        return parsed_lines

    def _render_diff(self, diff_lines: Iterator[str], output: StringIO) -> None:
        """Render diff content as HTML."""
        # Parse diff lines
        parsed_lines = self._parse_diff_lines(diff_lines)

        if not parsed_lines:
            output.write("      <p><em>No differences found.</em></p>\n")
            return

        # Render as inline view (GitHub-style)
        output.write("      <div class='inline-view'>\n")

        for line_type, content in parsed_lines:
            if line_type == "header":
                # File headers (---, +++)
                output.write(f"        <div class='diff-header'>{escape(content)}</div>\n")
            elif line_type == "hunk":
                # Hunk headers (@@)
                output.write(f"        <div class='diff-hunk-header'>{escape(content)}</div>\n")
            elif line_type == "added":
                # Added lines (green background)
                output.write(f"        <div class='inline-line inline-added'>{escape(content)}</div>\n")
            elif line_type == "deleted":
                # Deleted lines (red background with strikethrough)
                output.write(f"        <div class='inline-line inline-deleted'>{escape(content)}</div>\n")
            elif line_type == "context":
                # Context lines (normal)
                if self.show_context:
                    output.write(f"        <div class='inline-line inline-context'>{escape(content)}</div>\n")

        output.write("      </div>\n")


def render_to_file(diff_lines: Iterator[str], output_path: str, **kwargs) -> None:
    """Render unified diff to HTML file.

    Parameters
    ----------
    diff_lines : Iterator[str]
        Lines of unified diff output
    output_path : str
        Path to write HTML file
    **kwargs
        Additional arguments passed to HtmlDiffRenderer

    """
    renderer = HtmlDiffRenderer(**kwargs)
    html = renderer.render(diff_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
