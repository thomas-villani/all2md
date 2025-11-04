#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/renderers/html.py
"""HTML diff renderer with full-document visualization.

The renderer highlights additions, deletions, and unchanged context
across the entire document. When provided with a :class:`DiffResult`
it produces a rich HTML page with summary statistics, collapsible
context blocks, and line numbers. It falls back to the legacy
inline-view when called with raw unified diff lines.
"""

from __future__ import annotations

from html import escape
from io import StringIO
from typing import Any, Iterator, List, Sequence, Tuple

from all2md.diff.text_diff import DiffOp, DiffResult


class HtmlDiffRenderer:
    """Render document diffs as visual HTML.

    When supplied with a :class:`DiffResult`, the renderer emits a
    full-document view that preserves ordering, adds line numbers, and
    highlights additions/deletions with GitHub-style colors. Unchanged
    sections can optionally be collapsed when ``show_context`` is
    ``False``. Passing an iterator of unified diff lines is still
    supported for compatibility, using the legacy inline view.

    Parameters
    ----------
    show_context : bool, default = True
        If True, show unchanged sections; when False they are collapsible
    inline_styles : bool, default = True
        If True, include CSS styles in the output

    Examples
    --------
    Render diff as HTML:
        >>> from all2md.diff import compare_files
        >>> from all2md.diff.renderers import HtmlDiffRenderer
        >>> diff_result = compare_files("old.docx", "new.docx")
        >>> renderer = HtmlDiffRenderer()
        >>> html = renderer.render(diff_result)
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

    def render(self, diff: DiffResult | Iterator[str]) -> str:
        """Render diff output to HTML string.

        Parameters
        ----------
        diff : DiffResult or iterator of str
            Structured diff result or unified diff lines

        Returns
        -------
        str
            HTML-formatted diff output

        """
        output = StringIO()
        self._write_html_prefix(output)

        if isinstance(diff, DiffResult):
            self._render_full_document(diff, output)
        else:
            self._render_legacy_inline(diff, output)

        self._write_html_suffix(output)
        return output.getvalue()

    def _write_html_prefix(self, output: StringIO) -> None:
        """Write the static HTML prefix and container."""
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
        output.write("    <div class='diff-content'>\n")

    def _write_html_suffix(self, output: StringIO) -> None:
        """Write the closing HTML tags."""
        output.write("    </div>\n")
        output.write("  </div>\n")
        output.write("</body>\n")
        output.write("</html>\n")

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
        .diff-summary {
            background-color: #f0f4ff;
            border: 1px solid #cbd7f7;
            border-radius: 6px;
            padding: 12px 16px;
            margin-bottom: 20px;
        }
        .diff-summary h2 {
            margin: 0 0 8px 0;
            font-size: 16px;
            color: #1d3c78;
        }
        .diff-summary dl {
            display: grid;
            grid-template-columns: max-content 1fr;
            gap: 4px 16px;
            margin: 0;
        }
        .diff-summary dt {
            font-weight: 600;
            color: #51658a;
        }
        .inline-view {
            border: 1px solid #ddd;
            border-radius: 6px;
            overflow: hidden;
        }
        .inline-line {
            display: grid;
            grid-template-columns: 70px 70px 1fr;
            gap: 12px;
            padding: 4px 12px;
            margin: 0;
            border-left: 4px solid transparent;
            align-items: baseline;
        }
        .inline-line + .inline-line {
            border-top: 1px solid #f1f3f5;
        }
        .line-number {
            color: #7a8699;
            font-size: 12px;
            text-align: right;
        }
        .line-number::before {
            content: attr(data-label);
            display: block;
            font-size: 10px;
            text-transform: uppercase;
            color: #b0b8bf;
            letter-spacing: 0.04em;
        }
        .line-text {
            white-space: pre-wrap;
            word-break: break-word;
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
        details.diff-context-collapsed {
            margin: 8px 0;
            background-color: #fafbfc;
            border: 1px dashed #d0d7de;
            border-radius: 6px;
            padding: 8px 12px;
        }
        details.diff-context-collapsed summary {
            cursor: pointer;
            font-size: 13px;
            color: #5b6b7f;
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

    def _render_legacy_inline(self, diff_lines: Iterator[str], output: StringIO) -> None:
        """Render legacy inline diff (fallback for iterators)."""
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

    def _render_full_document(self, diff: DiffResult, output: StringIO) -> None:
        """Render the complete document using structured diff operations."""
        operations = list(diff.iter_operations())
        if not operations:
            output.write("      <p><em>No differences found.</em></p>\n")
            return

        stats = self._compute_statistics(diff)
        self._render_summary(diff, stats, output)

        output.write("      <div class='inline-view'>\n")

        for op in operations:
            if op.tag == "equal":
                self._render_equal_block(op, output)
            elif op.tag == "insert":
                self._render_line_block(
                    op.new_slice,
                    "inline-added",
                    output,
                    new_start=op.new_range[0],
                )
            elif op.tag == "delete":
                self._render_line_block(
                    op.old_slice,
                    "inline-deleted",
                    output,
                    old_start=op.old_range[0],
                )
            elif op.tag == "replace":
                self._render_line_block(
                    op.old_slice,
                    "inline-deleted",
                    output,
                    old_start=op.old_range[0],
                )
                self._render_line_block(
                    op.new_slice,
                    "inline-added",
                    output,
                    new_start=op.new_range[0],
                )

        output.write("      </div>\n")

    def _render_summary(self, diff: DiffResult, stats: dict[str, int], output: StringIO) -> None:
        """Render diff metadata and statistics."""
        output.write("      <div class='diff-summary'>\n")
        output.write("        <h2>Summary</h2>\n")
        output.write("        <dl>\n")
        output.write(f"          <dt>Old file</dt><dd>{escape(diff.old_label)}</dd>\n")
        output.write(f"          <dt>New file</dt><dd>{escape(diff.new_label)}</dd>\n")
        output.write(f"          <dt>Granularity</dt><dd>{escape(diff.granularity)}</dd>\n")
        output.write(f"          <dt>Context lines</dt><dd>{diff.context_lines}</dd>\n")
        output.write(f"          <dt>Lines added</dt><dd>{stats['lines_added']}</dd>\n")
        output.write(f"          <dt>Lines deleted</dt><dd>{stats['lines_deleted']}</dd>\n")
        output.write(f"          <dt>Total changes</dt><dd>{stats['total_changes']}</dd>\n")
        output.write("        </dl>\n")
        output.write("      </div>\n")

    def _render_equal_block(self, op: DiffOp, output: StringIO) -> None:
        """Render an unchanged block, collapsing if context is hidden."""
        if not op.new_slice:
            return

        line_count = len(op.new_slice)
        if not self.show_context:
            summary = f"{line_count} unchanged line{'s' if line_count != 1 else ''}"
            output.write("        <details class='diff-context-collapsed'>\n")
            output.write(f"          <summary>{escape(summary)}</summary>\n")
            self._render_line_block(
                op.new_slice,
                "inline-context",
                output,
                old_start=op.old_range[0],
                new_start=op.new_range[0],
                indent="          ",
            )
            output.write("        </details>\n")
        else:
            self._render_line_block(
                op.new_slice,
                "inline-context",
                output,
                old_start=op.old_range[0],
                new_start=op.new_range[0],
            )

    def _render_line_block(
        self,
        lines: Sequence[str],
        line_class: str,
        output: StringIO,
        *,
        old_start: int | None = None,
        new_start: int | None = None,
        indent: str = "        ",
    ) -> None:
        """Render a sequence of lines with provided styling."""
        old_index = old_start + 1 if old_start is not None else None
        new_index = new_start + 1 if new_start is not None else None

        for line in lines:
            old_display = str(old_index) if old_index is not None else ""
            new_display = str(new_index) if new_index is not None else ""
            text = escape(line) if line else "&nbsp;"

            output.write(f"{indent}<div class='inline-line {line_class}'>\n")
            output.write(f"{indent}  <span class='line-number' data-label='old'>{old_display or '&nbsp;'}</span>\n")
            output.write(f"{indent}  <span class='line-number' data-label='new'>{new_display or '&nbsp;'}</span>\n")
            output.write(f"{indent}  <span class='line-text'>{text}</span>\n")
            output.write(f"{indent}</div>\n")

            if old_index is not None:
                old_index += 1
            if new_index is not None:
                new_index += 1

    def _compute_statistics(self, diff: DiffResult) -> dict[str, int]:
        """Compute diff statistics for the summary block."""
        lines_added = 0
        lines_deleted = 0

        for op in diff.iter_operations():
            if op.tag == "insert":
                lines_added += len(op.new_slice)
            elif op.tag == "delete":
                lines_deleted += len(op.old_slice)
            elif op.tag == "replace":
                lines_added += len(op.new_slice)
                lines_deleted += len(op.old_slice)

        return {
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "total_changes": lines_added + lines_deleted,
        }


def render_to_file(diff: DiffResult | Iterator[str], output_path: str, **kwargs: Any) -> None:
    """Render unified diff to an HTML file.

    Parameters
    ----------
    diff : DiffResult or iterator of str
        Diff payload to render (structured result or raw unified diff lines).
    output_path : str
        Destination path for the generated HTML file.
    **kwargs
        Additional keyword arguments forwarded to :class:`HtmlDiffRenderer`.

    """
    renderer = HtmlDiffRenderer(**kwargs)
    html = renderer.render(diff)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
