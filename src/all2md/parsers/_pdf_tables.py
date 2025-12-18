#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/_pdf_tables.py
"""PDF table detection algorithms.

This private module contains algorithms for detecting tables in PDF documents
using ruling lines (horizontal and vertical lines that form table borders).

"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz

__all__ = ["detect_tables_by_ruling_lines"]


def _extract_ruling_lines(
    drawings: list,
    min_hline_len: float,
    min_vline_len: float,
) -> tuple[list[tuple], list[tuple]]:
    """Extract horizontal and vertical ruling lines from drawing commands.

    Parameters
    ----------
    drawings : list
        Drawing commands from page.get_drawings()
    min_hline_len : float
        Minimum length for horizontal lines
    min_vline_len : float
        Minimum length for vertical lines

    Returns
    -------
    tuple[list[tuple], list[tuple]]
        Tuple of (h_lines, v_lines) where each line is (x0, y0, x1, y1)

    """
    h_lines: list[tuple] = []
    v_lines: list[tuple] = []

    for item in drawings:
        if "items" not in item:
            continue

        for drawing in item["items"]:
            if drawing[0] != "l":  # Not a line command
                continue

            p1, p2 = drawing[1], drawing[2]

            # Check if horizontal line (nearly horizontal)
            if abs(p1.y - p2.y) < 2:
                line_len = abs(p2.x - p1.x)
                if line_len >= min_hline_len:
                    h_lines.append((min(p1.x, p2.x), p1.y, max(p1.x, p2.x), p2.y))

            # Check if vertical line (nearly vertical)
            elif abs(p1.x - p2.x) < 2:
                line_len = abs(p2.y - p1.y)
                if line_len >= min_vline_len:
                    v_lines.append((p1.x, min(p1.y, p2.y), p2.x, max(p1.y, p2.y)))

    return h_lines, v_lines


def _check_table_overlap(table_rect: "fitz.Rect", existing_rects: list["fitz.Rect"]) -> bool:
    """Check if a table rect overlaps significantly with existing tables.

    Returns
    -------
    bool
        True if there's significant overlap with any existing table

    """
    for existing in existing_rects:
        if abs(existing & table_rect) > abs(table_rect) * 0.5:
            return True
    return False


def _find_table_regions(
    h_lines: list[tuple],
    v_lines: list[tuple],
) -> list["fitz.Rect"]:
    """Find table regions from horizontal and vertical lines.

    Parameters
    ----------
    h_lines : list[tuple]
        Horizontal lines sorted by y-coordinate
    v_lines : list[tuple]
        Vertical lines

    Returns
    -------
    list[fitz.Rect]
        List of detected table bounding boxes

    """
    import fitz

    table_rects: list["fitz.Rect"] = []

    if len(h_lines) < 2 or len(v_lines) < 2:
        return table_rects

    # Look for regions with multiple h_lines and v_lines
    for i in range(len(h_lines) - 1):
        for j in range(i + 1, min(i + 10, len(h_lines))):
            y1 = h_lines[i][1]
            y2 = h_lines[j][1]

            # Find v_lines that span between these h_lines
            spanning_vlines = [v for v in v_lines if v[1] <= y1 + 5 and v[3] >= y2 - 5]

            if len(spanning_vlines) < 2:
                continue

            # Found a potential table - calculate bounds
            x_min = min(min(h_lines[i][0], h_lines[j][0]), min(v[0] for v in spanning_vlines))
            x_max = max(max(h_lines[i][2], h_lines[j][2]), max(v[2] for v in spanning_vlines))

            table_rect = fitz.Rect(x_min, y1, x_max, y2)

            if not table_rect.is_empty and not _check_table_overlap(table_rect, table_rects):
                table_rects.append(table_rect)

    return table_rects


def _collect_lines_for_tables(
    table_rects: list["fitz.Rect"],
    h_lines: list[tuple],
    v_lines: list[tuple],
) -> list[tuple[list[tuple], list[tuple]]]:
    """Collect lines that belong to each table region.

    Returns
    -------
    list[tuple[list[tuple], list[tuple]]]
        List of (table_h_lines, table_v_lines) for each table

    """
    table_lines = []
    for table_rect in table_rects:
        table_h_lines = [line for line in h_lines if table_rect.y0 <= line[1] <= table_rect.y1]
        table_v_lines = [line for line in v_lines if table_rect.x0 <= line[0] <= table_rect.x1]
        table_lines.append((table_h_lines, table_v_lines))
    return table_lines


def detect_tables_by_ruling_lines(
    page: "fitz.Page", threshold: float = 0.5
) -> tuple[list["fitz.Rect"], list[tuple[list[tuple], list[tuple]]]]:
    """Fallback table detection using ruling lines and text alignment.

    Uses page drawing commands to detect horizontal and vertical lines
    that form table structures, useful when PyMuPDF's table detection fails.

    Parameters
    ----------
    page : PyMuPDF Page
        PDF page to analyze for tables
    threshold : float, default 0.5
        Minimum line length ratio relative to page size for ruling lines

    Returns
    -------
    tuple[list[PyMuPDF Rect], list[tuple[list, list]]]
        Tuple containing:
            - List of bounding boxes for detected tables
            - List of (h_lines, v_lines) tuples for each table, where each line
              is a tuple of (x0, y0, x1, y1) coordinates

    """
    # Calculate minimum line lengths based on page dimensions
    page_rect = page.rect
    min_hline_len = page_rect.width * threshold
    min_vline_len = page_rect.height * threshold * 0.3

    # Extract ruling lines from drawings
    h_lines, v_lines = _extract_ruling_lines(page.get_drawings(), min_hline_len, min_vline_len)

    # Sort horizontal lines by y-coordinate for region detection
    h_lines.sort(key=lambda line: line[1])

    # Find table regions
    table_rects = _find_table_regions(h_lines, v_lines)

    # Collect lines for each table
    table_lines = _collect_lines_for_tables(table_rects, h_lines, v_lines)

    return table_rects, table_lines
