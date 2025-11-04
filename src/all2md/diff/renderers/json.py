#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/diff/renderers/json.py
"""JSON diff renderer for structured output.

This renderer parses unified diff format and produces machine-readable
JSON output for programmatic processing.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, Union

from all2md.diff.text_diff import DiffResult


class JsonDiffRenderer:
    """Render unified diff as structured JSON.

    This renderer parses unified diff output and produces JSON suitable
    for programmatic processing, API responses, and further analysis.

    Parameters
    ----------
    pretty_print : bool, default = True
        If True, format JSON with indentation
    indent : int, default = 2
        Number of spaces for indentation (if pretty_print=True)

    Examples
    --------
    Render diff as JSON:
        >>> from all2md.diff import compare_files
        >>> from all2md.diff.renderers import JsonDiffRenderer
        >>> diff_lines = compare_files("old.docx", "new.docx")
        >>> renderer = JsonDiffRenderer()
        >>> json_output = renderer.render(diff_lines)

    """

    def __init__(
        self,
        pretty_print: bool = True,
        indent: int = 2,
    ):
        """Initialize the JSON diff renderer."""
        self.pretty_print = pretty_print
        self.indent = indent

    def render(self, diff: Union[DiffResult, Iterator[str]]) -> str:
        """Render unified diff to JSON string.

        Parameters
        ----------
        diff : DiffResult or iterator of str
            Diff result or lines of unified diff output

        Returns
        -------
        str
            JSON-formatted diff output

        """
        if isinstance(diff, DiffResult):
            data = self._parse_diff(diff.iter_unified_diff())
            self._attach_statistics_from_result(diff, data)
            data["granularity"] = diff.granularity
            data["context_lines"] = diff.context_lines
        else:
            data = self._parse_diff(diff)

        if self.pretty_print:
            return json.dumps(data, indent=self.indent, ensure_ascii=False)
        else:
            return json.dumps(data, ensure_ascii=False)

    def _parse_diff(self, diff_lines: Iterator[str]) -> Dict[str, Any]:
        """Parse unified diff lines into structured data.

        Returns
        -------
        dict
            Structured diff data with headers, hunks, and changes

        """
        result: Dict[str, Any] = {
            "type": "unified_diff",
            "old_file": "",
            "new_file": "",
            "hunks": [],
        }

        current_hunk: Dict[str, Any] | None = None
        lines_added = 0
        lines_deleted = 0
        lines_context = 0

        for line in diff_lines:
            if line.startswith("---"):
                # Old file header
                result["old_file"] = line[4:].strip()
            elif line.startswith("+++"):
                # New file header
                result["new_file"] = line[4:].strip()
            elif line.startswith("@@"):
                # Hunk header - save previous hunk and start new one
                if current_hunk is not None:
                    result["hunks"].append(current_hunk)

                current_hunk = {
                    "header": line,
                    "changes": [],
                }
            elif current_hunk is not None:
                # Change lines within a hunk
                if line.startswith("+"):
                    current_hunk["changes"].append(
                        {
                            "type": "added",
                            "content": line[1:],  # Remove + prefix
                        }
                    )
                    lines_added += 1
                elif line.startswith("-"):
                    current_hunk["changes"].append(
                        {
                            "type": "deleted",
                            "content": line[1:],  # Remove - prefix
                        }
                    )
                    lines_deleted += 1
                elif line.startswith(" "):
                    current_hunk["changes"].append(
                        {
                            "type": "context",
                            "content": line[1:],  # Remove space prefix
                        }
                    )
                    lines_context += 1

        # Add final hunk if any
        if current_hunk is not None:
            result["hunks"].append(current_hunk)

        # Add statistics
        total_changes = lines_added + lines_deleted
        result["statistics"] = {
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "lines_context": lines_context,
            "total_changes": total_changes,
        }

        return result

    def _attach_statistics_from_result(self, diff: DiffResult, result: Dict[str, Any]) -> None:
        """Attach statistics computed from the structured diff result."""
        lines_added = 0
        lines_deleted = 0
        lines_context = 0

        for op in diff.iter_operations():
            if op.tag == "insert":
                lines_added += len(op.new_slice)
            elif op.tag == "delete":
                lines_deleted += len(op.old_slice)
            elif op.tag == "replace":
                lines_added += len(op.new_slice)
                lines_deleted += len(op.old_slice)
            else:  # equal
                lines_context += len(op.old_slice)

        total_changes = lines_added + lines_deleted
        result["statistics"] = {
            "lines_added": lines_added,
            "lines_deleted": lines_deleted,
            "lines_context": lines_context,
            "total_changes": total_changes,
        }


def render_to_file(diff: DiffResult | Iterator[str], output_path: str, **kwargs: Any) -> None:
    """Render unified diff to a JSON file.

    Parameters
    ----------
    diff : DiffResult or iterator of str
        Diff payload to serialise (structured result or raw unified diff lines).
    output_path : str
        Destination path for the generated JSON file.
    **kwargs
        Additional keyword arguments forwarded to :class:`JsonDiffRenderer`.

    """
    renderer = JsonDiffRenderer(**kwargs)
    json_output = renderer.render(diff)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_output)
