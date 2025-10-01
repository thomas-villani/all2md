#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/converters/spreadsheet2ast.py
"""Spreadsheet to AST converter.

This module provides conversion from spreadsheet formats (XLSX, ODS, CSV, TSV)
to AST representation. It replaces direct markdown string generation with
structured AST building, enabling multiple rendering strategies.

"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import IO, Any, Iterable, Optional, Union

from all2md.ast import Document, Emphasis, Heading, HTMLInline, Paragraph, Table, TableCell, TableRow, Text
from all2md.constants import TABLE_ALIGNMENT_MAPPING
from all2md.options import MarkdownOptions, SpreadsheetOptions

logger = logging.getLogger(__name__)


def _sanitize_cell_text(text: Any, md_options: MarkdownOptions | None = None) -> str:
    """Convert any cell value to a safe string for AST Text node.

    Note: Markdown escaping is handled by the renderer, not here.
    We only normalize whitespace and convert to string.

    Parameters
    ----------
    text : Any
        Cell value to sanitize
    md_options : MarkdownOptions | None
        Markdown options (currently unused, kept for compatibility)

    Returns
    -------
    str
        Sanitized cell text

    """
    if text is None:
        s = ""
    else:
        s = str(text)

    # Normalize whitespace/newlines inside cells
    s = s.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")

    return s


def _format_link_or_text(cell: Any, text: str, md_options: MarkdownOptions | None = None) -> str:
    """Get cell text, checking for hyperlinks.

    Parameters
    ----------
    cell : Any
        Cell object (openpyxl)
    text : str
        Cell text value
    md_options : MarkdownOptions | None
        Markdown options

    Returns
    -------
    str
        Cell text (hyperlinks not yet supported in AST path)

    """
    # TODO: Support hyperlinks in table cells via Link nodes
    # For now, just return sanitized text
    return _sanitize_cell_text(text, md_options)


def _alignment_for_cell(cell: Any) -> str:
    """Map an openpyxl cell alignment to alignment string.

    Parameters
    ----------
    cell : Any
        Cell object

    Returns
    -------
    str
        Alignment: 'left', 'center', 'right', or 'center' (default)

    """
    try:
        align = getattr(cell, "alignment", None)
        if align and getattr(align, "horizontal", None):
            horiz = align.horizontal.lower()
            # Map Excel alignment to our alignment values
            alignment_map = {
                "left": "left",
                "center": "center",
                "centre": "center",
                "right": "right",
                "general": "left",
                "justify": "left",
            }
            return alignment_map.get(horiz, "center")
    except Exception:
        pass

    return "center"


def _build_table_ast(
    header: list[str], rows: list[list[str]], alignments: list[str]
) -> Table:
    """Build an AST Table from header, rows, and alignments.

    Parameters
    ----------
    header : list[str]
        Header row cells
    rows : list[list[str]]
        Data rows
    alignments : list[str]
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

    # Convert alignment strings to the format expected by Table node
    # Table expects Optional[Literal['left', 'center', 'right']]
    table_alignments: list[Optional[str]] = []
    for align in alignments:
        if align in ("left", "center", "right"):
            table_alignments.append(align)
        else:
            table_alignments.append("center")

    return Table(header=header_row, rows=data_rows, alignments=table_alignments)


def _xlsx_iter_rows(sheet: Any, max_rows: int | None, max_cols: int | None) -> Iterable[list[Any]]:
    """Iterate rows of an openpyxl worksheet with optional truncation.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet
    max_rows : int | None
        Maximum rows to read
    max_cols : int | None
        Maximum columns to read

    Yields
    ------
    list[Any]
        Row cells

    """
    row_iter = sheet.iter_rows(values_only=False)
    for r_idx, row in enumerate(row_iter, start=1):
        if max_rows is not None and r_idx > max_rows:
            break
        out_row = []
        for c_idx, cell in enumerate(row, start=1):
            if max_cols is not None and c_idx > max_cols:
                break
            out_row.append(cell)
        yield out_row


def _map_merged_cells(sheet: Any) -> dict[str, str]:
    """Return a map of cell.coordinate -> master.coordinate for merged ranges.

    Parameters
    ----------
    sheet : Any
        Openpyxl worksheet

    Returns
    -------
    dict[str, str]
        Mapping of cell coordinates to master cell coordinates

    """
    merged_map: dict[str, str] = {}
    try:
        ranges = getattr(sheet, "merged_cells", None)
        if not ranges or not getattr(ranges, "ranges", None):
            return merged_map

        for mcr in ranges.ranges:
            min_r, min_c, max_r, max_c = mcr.min_row, mcr.min_col, mcr.max_row, mcr.max_col
            master = sheet.cell(row=min_r, column=min_c).coordinate
            for rr in range(min_r, max_r + 1):
                for cc in range(min_c, max_c + 1):
                    coord = sheet.cell(row=rr, column=cc).coordinate
                    merged_map[coord] = master
    except Exception as e:
        logger.debug(f"Unable to compute merged cell map: {e!r}")
    return merged_map


class SpreadsheetToAstConverter:
    """Convert spreadsheet formats to AST representation.

    This converter handles XLSX, ODS, CSV, and TSV formats by building
    Table nodes from spreadsheet data.

    Parameters
    ----------
    options : SpreadsheetOptions or None
        Conversion options

    """

    def __init__(self, options: SpreadsheetOptions | None = None):
        self.options = options or SpreadsheetOptions()
        self.md_options = self.options.markdown_options or MarkdownOptions()

    def xlsx_to_ast(self, workbook: Any) -> Document:
        """Convert an openpyxl workbook to AST Document.

        Parameters
        ----------
        workbook : Any
            Openpyxl workbook

        Returns
        -------
        Document
            AST document with table nodes

        """
        children = []

        # Select sheets
        sheet_names: list[str] = list(workbook.sheetnames)
        if isinstance(self.options.sheets, list):
            sheet_names = [n for n in sheet_names if n in self.options.sheets]
        elif isinstance(self.options.sheets, str):
            pattern = re.compile(self.options.sheets)
            sheet_names = [n for n in sheet_names if pattern.search(n)]

        if not sheet_names:
            return Document(children=[])

        for sname in sheet_names:
            sheet = workbook[sname]

            # Add sheet title if requested
            if self.options.include_sheet_titles:
                use_hash = self.md_options.use_hash_headings
                # Create heading node
                children.append(Heading(level=2, content=[Text(content=sname)]))

            # Process sheet data
            merged_map = _map_merged_cells(sheet)

            raw_rows: list[list[Any]] = []
            for row in _xlsx_iter_rows(sheet, self.options.max_rows, self.options.max_cols):
                if all((cell.value is None) for cell in row):
                    raw_rows.append(row)
                else:
                    raw_rows.append(row)

            if not raw_rows:
                continue

            # Convert to strings and handle merged cells
            str_rows: list[list[str]] = []
            for row in raw_rows:
                out: list[str] = []
                for cell in row:
                    coord = getattr(cell, "coordinate", None)
                    if coord and coord in merged_map and merged_map[coord] != coord:
                        out.append("")
                    else:
                        out.append(_format_link_or_text(cell, cell.value, self.md_options))
                str_rows.append(out)

            # Trim completely empty trailing rows
            while str_rows and all(c == "" for c in str_rows[-1]):
                str_rows.pop()

            if not str_rows:
                continue

            header = str_rows[0]
            data = str_rows[1:] if len(str_rows) > 1 else []

            # Compute alignments from header cells
            alignments: list[str] = []
            try:
                first_row_cells = next(sheet.iter_rows(min_row=1, max_row=1, values_only=False))
                for c_idx, cell in enumerate(first_row_cells, start=1):
                    if self.options.max_cols is not None and c_idx > self.options.max_cols:
                        break
                    alignments.append(_alignment_for_cell(cell))
            except Exception:
                alignments = ["center"] * len(header)

            # Build table AST
            table = _build_table_ast(header, data, alignments)
            children.append(table)

            # Add truncation indicator as paragraph if needed
            truncated_rows = self.options.max_rows is not None and sheet.max_row > self.options.max_rows
            truncated_cols = self.options.max_cols is not None and sheet.max_column > self.options.max_cols
            if truncated_rows or truncated_cols:
                children.append(
                    Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")])
                )

        return Document(children=children)

    def csv_or_tsv_to_ast(
        self,
        input_data: Union[str, Path, IO[bytes], IO[str]],
        delimiter: str | None = None,
        force_delimiter: bool = False,
    ) -> Document:
        """Convert CSV/TSV to AST Document.

        Parameters
        ----------
        input_data : Union[str, Path, IO[bytes], IO[str]]
            Input data
        delimiter : str | None
            Delimiter character
        force_delimiter : bool
            Force using the delimiter

        Returns
        -------
        Document
            AST document with table node

        """
        from all2md.utils.inputs import validate_and_convert_input

        # Validate and load text
        try:
            doc_input, _ = validate_and_convert_input(input_data, supported_types=["path-like", "file-like", "bytes"])
            if isinstance(doc_input, (str, Path)):
                with open(doc_input, "rb") as f:
                    text_stream = self._read_text_stream_for_csv(f)
            else:
                text_stream = self._read_text_stream_for_csv(doc_input)
        except Exception as e:
            from all2md.exceptions import MarkdownConversionError
            raise MarkdownConversionError(
                f"Failed to read CSV/TSV input: {e}", conversion_stage="input_processing", original_error=e
            ) from e

        # Sniff dialect
        text_stream.seek(0)
        sample = text_stream.read(4096)
        text_stream.seek(0)

        dialect: csv.Dialect
        if self.options.csv_delimiter:
            exc_dialect = csv.excel()
            exc_dialect.delimiter = self.options.csv_delimiter
            dialect = exc_dialect
        elif force_delimiter:
            exc_dialect = csv.excel()
            exc_dialect.delimiter = delimiter or "\t"
            dialect = exc_dialect
        elif self.options.detect_csv_dialect:
            try:
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample, delimiters=",\t;|\x1f")
            except Exception:
                exc_dialect = csv.excel()
                if delimiter:
                    exc_dialect.delimiter = delimiter
                dialect = exc_dialect
        else:
            exc_dialect = csv.excel()
            if delimiter:
                exc_dialect.delimiter = delimiter
            dialect = exc_dialect

        reader = csv.reader(text_stream, dialect=dialect)
        rows: list[list[str]] = []
        for r in reader:
            rows.append(r)

        # Drop leading/trailing fully empty rows
        def is_empty(row: list[str]) -> bool:
            return all((not (c or "").strip()) for c in row)

        while rows and is_empty(rows[0]):
            rows.pop(0)
        while rows and is_empty(rows[-1]):
            rows.pop()

        if not rows:
            return Document(children=[])

        # Handle header
        if self.options.has_header:
            header = rows[0]
            data_rows = rows[1:]
        else:
            if rows:
                num_cols = len(rows[0]) if rows else 0
                header = [f"Column {i+1}" for i in range(num_cols)]
                data_rows = rows
            else:
                return Document(children=[])

        # Truncate columns
        if self.options.max_cols is not None:
            header = header[: self.options.max_cols]
            data_rows = [r[: self.options.max_cols] for r in data_rows]

        # Truncate rows
        truncated = False
        if self.options.max_rows is not None and len(data_rows) > self.options.max_rows:
            data_rows = data_rows[: self.options.max_rows]
            truncated = True

        # Sanitize cells
        if self.options.has_header:
            header = [_sanitize_cell_text(c, self.md_options).lstrip("\ufeff") for c in header]
        else:
            header = [_sanitize_cell_text(c, self.md_options) for c in header]
        data_rows = [[_sanitize_cell_text(c, self.md_options) for c in r] for r in data_rows]

        # Alignments default to center
        alignments = ["center"] * len(header)

        # Build table AST
        table = _build_table_ast(header, data_rows, alignments)

        children = [table]

        if truncated:
            children.append(
                Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")])
            )

        return Document(children=children)

    def _read_text_stream_for_csv(self, input_data: Any) -> io.StringIO:
        """Read binary or text input and return a StringIO for CSV parsing.

        Parameters
        ----------
        input_data : Any
            Input stream or data

        Returns
        -------
        io.StringIO
            Text stream for CSV parsing

        """
        if isinstance(input_data, io.StringIO):
            input_data.seek(0)
            return input_data

        content = None
        if hasattr(input_data, "read"):
            pos = None
            try:
                pos = input_data.tell()
            except Exception:
                pass

            raw = input_data.read()
            if isinstance(raw, bytes):
                try:
                    content = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    content = raw.decode("utf-8", errors="replace")
            else:
                content = str(raw)

            try:
                if pos is not None:
                    input_data.seek(pos)
            except Exception:
                pass
        else:
            content = str(input_data)

        return io.StringIO(content or "")

    def ods_to_ast(self, doc: Any) -> Document:
        """Convert ODS document to AST Document.

        Parameters
        ----------
        doc : Any
            ODS document object

        Returns
        -------
        Document
            AST document with table nodes

        """
        from odf.table import Table as OdfTable, TableCell, TableRow

        children = []

        body = doc.body
        tables = list(body.getElementsByType(OdfTable)) if body else []

        if not tables:
            return Document(children=[])

        # Filter sheets based on options
        sheet_names = [table.getAttribute("name") or f"Sheet{i+1}" for i, table in enumerate(tables)]
        selected_tables = []
        selected_names = []

        if isinstance(self.options.sheets, list):
            for i, name in enumerate(sheet_names):
                if name in self.options.sheets:
                    selected_tables.append(tables[i])
                    selected_names.append(name)
        elif isinstance(self.options.sheets, str):
            pattern = re.compile(self.options.sheets)
            for i, name in enumerate(sheet_names):
                if pattern.search(name):
                    selected_tables.append(tables[i])
                    selected_names.append(name)
        else:
            selected_tables = tables
            selected_names = sheet_names

        # Process each selected sheet
        for table, name in zip(selected_tables, selected_names, strict=False):
            # Add sheet title if requested
            if self.options.include_sheet_titles:
                children.append(Heading(level=2, content=[Text(content=name)]))

            # Extract rows
            rows_elem = list(table.getElementsByType(TableRow))
            if not rows_elem:
                continue

            # Convert to cell data
            raw_rows = []
            for row in rows_elem:
                cells = list(row.getElementsByType(TableCell))
                row_data = []

                for cell in cells:
                    cell_text = ""
                    for node in cell.childNodes:
                        if hasattr(node, 'data'):
                            cell_text += str(node.data)
                        elif hasattr(node, 'childNodes'):
                            for subnode in node.childNodes:
                                if hasattr(subnode, 'data'):
                                    cell_text += str(subnode.data)

                    # Handle cell repetition
                    repeat_count = 1
                    try:
                        repeat_attr = cell.getAttribute("numbercolumnsrepeated")
                        if repeat_attr:
                            repeat_count = int(repeat_attr)
                    except (ValueError, TypeError):
                        pass

                    for _ in range(repeat_count):
                        row_data.append(cell_text.strip() if cell_text else "")

                raw_rows.append(row_data)

            # Remove empty trailing rows
            while raw_rows and all(not cell for cell in raw_rows[-1]):
                raw_rows.pop()

            if not raw_rows:
                continue

            # Apply row limits
            if self.options.max_rows is not None:
                total_available = len(raw_rows) - 1
                if total_available > self.options.max_rows:
                    raw_rows = raw_rows[: self.options.max_rows + 1]

            # Extract header and data
            if self.options.has_header:
                header = raw_rows[0]
                data_rows = raw_rows[1:] if len(raw_rows) > 1 else []
            else:
                if raw_rows:
                    max_cols = max(len(row) for row in raw_rows)
                    if self.options.max_cols is not None:
                        max_cols = min(max_cols, self.options.max_cols)
                    header = [f"Column {i+1}" for i in range(max_cols)]
                    data_rows = raw_rows
                else:
                    header = []
                    data_rows = []

            # Apply column limits
            if self.options.max_cols is not None:
                header = header[: self.options.max_cols]
                data_rows = [row[: self.options.max_cols] for row in data_rows]

            # Sanitize all cell content
            header = [_sanitize_cell_text(cell, self.md_options) for cell in header]
            data_rows = [[_sanitize_cell_text(cell, self.md_options) for cell in row] for row in data_rows]

            # Ensure all rows have same number of columns
            if header:
                max_cols = len(header)
                data_rows = [row + [""] * (max_cols - len(row)) for row in data_rows]

            # Build table
            if header:
                alignments = ["center"] * len(header)
                table_node = _build_table_ast(header, data_rows, alignments)
                children.append(table_node)

            # Add truncation indicator if needed
            truncated = (self.options.max_rows is not None and len(rows_elem) - 1 > self.options.max_rows) or \
                       (self.options.max_cols is not None and any(len(row) > self.options.max_cols for row in raw_rows))
            if truncated:
                children.append(
                    Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")])
                )

        return Document(children=children)
