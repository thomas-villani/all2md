#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/utils/chart_helpers.py
"""Chart to table conversion helpers for parsers.

This module provides reusable helper functions for converting chart data
(from XLSX, PPTX, ODS, etc.) into Table AST nodes with consistent structure.

Functions
---------
- build_chart_table: Convert chart series data to AST Table
"""

from __future__ import annotations

from typing import Any, cast

from all2md.ast import Alignment, Table, TableCell, TableRow, Text


def build_chart_table(
    categories: list[str],
    series_data: list[tuple[str, list[Any]]],
    category_header: str = "Category",
    alignments: list[str] | None = None,
) -> Table | None:
    """Convert chart series data to AST Table node.

    This helper provides a unified way to convert chart data from different
    formats (XLSX, PPTX, ODS) into a consistent table structure with:
    - Header row: Category column + one column per series
    - Data rows: One row per category value

    Parameters
    ----------
    categories : list[str]
        List of category labels for the X-axis (e.g., months, product names)
    series_data : list[tuple[str, list[Any]]]
        List of (series_name, values) tuples where each series has values
        corresponding to the categories
    category_header : str, default "Category"
        Header text for the category column
    alignments : list[str] | None, default None
        Optional list of alignment strings for columns. If None, defaults to
        "left" for category column and "center" for value columns.

    Returns
    -------
    Table or None
        AST Table node with chart data, or None if series_data is empty

    Examples
    --------
    Convert simple chart data:

        >>> categories = ["Jan", "Feb", "Mar"]
        >>> series_data = [
        ...     ("Sales", [100, 150, 120]),
        ...     ("Costs", [80, 90, 85])
        ... ]
        >>> table = build_chart_table(categories, series_data)

    With custom header:

        >>> table = build_chart_table(
        ...     categories=["Q1", "Q2", "Q3", "Q4"],
        ...     series_data=[("Revenue", [1000, 1200, 1100, 1300])],
        ...     category_header="Quarter"
        ... )

    Notes
    -----
    This function handles cases where:
    - Series have different lengths (pads with empty strings)
    - No categories provided (generates "Row 1", "Row 2", etc.)
    - Category count doesn't match series value count (uses max length)

    The resulting table structure is:
    ```
    | Category | Series1 | Series2 | ... |
    |----------|---------|---------|-----|
    | Cat1     | Val1    | Val1    | ... |
    | Cat2     | Val2    | Val2    | ... |
    ```

    """
    if not series_data:
        return None

    # Determine maximum number of data points across all series
    max_rows = max(len(values) for _, values in series_data) if series_data else 0
    if max_rows == 0:
        return None

    # Build header row: category column + series columns
    header_cells = [TableCell(content=[Text(content=category_header)])]
    for series_name, _ in series_data:
        header_cells.append(TableCell(content=[Text(content=series_name)]))
    header_row = TableRow(cells=header_cells, is_header=True)

    # Build data rows: one row per category/data point
    data_rows = []
    for i in range(max_rows):
        # Get category label (or generate one)
        if categories and i < len(categories):
            category = categories[i]
        else:
            category = f"Row {i + 1}"

        # Start row with category cell
        row_cells = [TableCell(content=[Text(content=category)])]

        # Add value cells for each series
        for _, values in series_data:
            if i < len(values):
                value = values[i]
                # Convert value to string, handling None
                value_str = "" if value is None else str(value)
            else:
                # Pad with empty string if series is shorter
                value_str = ""

            row_cells.append(TableCell(content=[Text(content=value_str)]))

        data_rows.append(TableRow(cells=row_cells, is_header=False))

    # Set alignments if not provided
    if alignments is None:
        # Default: left for category, center for values

        alignments_list: list[Alignment | None] = [cast(Alignment | None, "left")]
        alignments_list.extend([cast(Alignment | None, "center")] * len(series_data))
    else:
        alignments_list = [cast(Alignment | None, a) for a in alignments]

    return Table(header=header_row, rows=data_rows, alignments=alignments_list)
