#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/spreadsheet.py
"""Shared utilities for spreadsheet parsers (XLSX, ODS, CSV).

This module provides common functions used across spreadsheet format parsers
to reduce code duplication and improve maintainability.
"""

from __future__ import annotations

from typing import Any, Literal

from all2md.ast import Alignment, Table, TableCell, TableRow, Text


def sanitize_cell_text(text: Any, preserve_newlines: bool = False) -> str:
    """Convert any cell value to a safe string for AST Text node.

    Note: Markdown escaping is handled by the renderer, not here.
    We only normalize whitespace and convert to string.

    Parameters
    ----------
    text : Any
        Cell value to sanitize
    preserve_newlines : bool, default False
        If True, preserve newlines as <br> tags; if False, replace with spaces

    Returns
    -------
    str
        Sanitized cell text

    """
    if text is None:
        s = ""
    else:
        s = str(text)

    # Handle newlines based on preserve_newlines option
    if preserve_newlines:
        # Keep line breaks as <br> tags
        s = s.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    else:
        # Normalize whitespace/newlines inside cells
        s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    return s


def build_table_ast(header: list[str], rows: list[list[str]], alignments: list[Alignment]) -> Table:
    """Build an AST Table from header, rows, and alignments.

    Parameters
    ----------
    header : list[str]
        Header row cells
    rows : list[list[str]]
        Data rows
    alignments : list[Alignment]
        Column alignments ('left', 'center', 'right')

    Returns
    -------
    Table
        AST Table node

    """
    # Build header row
    header_cells = [
        TableCell(content=[Text(content=cell)], alignment=alignments[i] if i < len(alignments) else "center")
        for i, cell in enumerate(header)
    ]
    header_row = TableRow(cells=header_cells, is_header=True)

    # Build data rows
    data_rows = []
    for row in rows:
        row_cells = [
            TableCell(content=[Text(content=cell)], alignment=alignments[i] if i < len(alignments) else "center")
            for i, cell in enumerate(row)
        ]
        data_rows.append(TableRow(cells=row_cells, is_header=False))

    # Table alignments are already the correct type
    table_alignments: list[Alignment | None] = list(alignments)

    return Table(header=header_row, rows=data_rows, alignments=table_alignments)


def create_table_cell(text: str, alignment: Alignment | None = None, colspan: int = 1, rowspan: int = 1) -> TableCell:
    """Create a table cell with optional spans and alignment.

    Parameters
    ----------
    text : str
        Cell text content
    alignment : Alignment or None, default None
        Cell alignment ('left', 'center', 'right')
    colspan : int, default 1
        Number of columns this cell spans
    rowspan : int, default 1
        Number of rows this cell spans

    Returns
    -------
    TableCell
        AST TableCell node

    """
    return TableCell(
        content=[Text(content=text)], alignment=alignment if alignment else "center", colspan=colspan, rowspan=rowspan
    )


def transform_header_case(header: list[str], case_mode: str) -> list[str]:
    """Transform header case based on case mode.

    Parameters
    ----------
    header : list[str]
        Header row
    case_mode : str
        Case transformation mode: 'preserve', 'title', 'upper', or 'lower'

    Returns
    -------
    list[str]
        Transformed header

    """
    if case_mode == "preserve":
        return header
    elif case_mode == "title":
        return [cell.title() for cell in header]
    elif case_mode == "upper":
        return [cell.upper() for cell in header]
    elif case_mode == "lower":
        return [cell.lower() for cell in header]
    return header


def trim_rows(rows: list[list[str]], trim_mode: Literal["none", "leading", "trailing", "both"]) -> list[list[str]]:
    """Trim empty rows based on trim mode.

    Parameters
    ----------
    rows : list[list[str]]
        Rows to trim
    trim_mode : {'none', 'leading', 'trailing', 'both'}
        Trimming mode

    Returns
    -------
    list[list[str]]
        Trimmed rows

    """
    if not rows or trim_mode == "none":
        return rows

    # Trim leading empty rows
    if trim_mode in ("leading", "both"):
        while rows and all(c == "" for c in rows[0]):
            rows.pop(0)

    # Trim trailing empty rows
    if trim_mode in ("trailing", "both"):
        while rows and all(c == "" for c in rows[-1]):
            rows.pop()

    return rows


def trim_columns(rows: list[list[str]], trim_mode: Literal["none", "leading", "trailing", "both"]) -> list[list[str]]:
    """Trim empty columns based on trim mode.

    Parameters
    ----------
    rows : list[list[str]]
        Rows to trim columns from
    trim_mode : {'none', 'leading', 'trailing', 'both'}
        Trimming mode

    Returns
    -------
    list[list[str]]
        Rows with trimmed columns

    """
    if not rows or trim_mode == "none":
        return rows

    if not rows[0]:
        return rows

    num_cols = len(rows[0])

    # Find leading empty columns
    leading_empty = 0
    if trim_mode in ("leading", "both"):
        for col_idx in range(num_cols):
            if all(row[col_idx] == "" if col_idx < len(row) else True for row in rows):
                leading_empty += 1
            else:
                break

    # Find trailing empty columns
    trailing_empty = 0
    if trim_mode in ("trailing", "both"):
        for col_idx in range(num_cols - 1, -1, -1):
            if all(row[col_idx] == "" if col_idx < len(row) else True for row in rows):
                trailing_empty += 1
            else:
                break

    # Trim columns
    if leading_empty > 0 or trailing_empty > 0:
        end_col = num_cols - trailing_empty
        return [row[leading_empty:end_col] for row in rows]

    return rows
