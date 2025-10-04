#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/ods_spreadsheet.py
"""ODS spreadsheet to AST converter.

This module provides conversion from ODS (OpenDocument Spreadsheet) files
to AST representation. It replaces the combined spreadsheet parser with a
focused ODS parser.

"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import IO, Any, Union

from all2md.exceptions import DependencyError, MalformedFileError
from all2md.ast import Document, Heading, HTMLInline, Paragraph, Table, TableCell, TableRow, Text
from all2md.converter_metadata import ConverterMetadata
from all2md.parsers.base import BaseParser
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _sanitize_cell_text(text: Any, preserve_newlines: bool = False) -> str:
    """Convert any cell value to a safe string for AST Text node.

    Note: Markdown escaping is handled by the renderer, not here.
    We only normalize whitespace and convert to string.

    Parameters
    ----------
    text : Any
        Cell value to sanitize
    preserve_newlines : bool
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

    # Convert alignment strings
    table_alignments = []
    for align in alignments:
        if align in ("left", "center", "right"):
            table_alignments.append(align)
        else:
            table_alignments.append("center")

    return Table(header=header_row, rows=data_rows, alignments=table_alignments)


class OdsSpreadsheetToAstConverter(BaseParser):
    """Convert ODS spreadsheet files to AST representation.

    This converter handles ODS (OpenDocument Spreadsheet) format by building
    Table nodes from spreadsheet data.

    Parameters
    ----------
    options : OdsSpreadsheetOptions or None
        Conversion options

    """

    def __init__(self, options=None):
        # Import here to avoid circular dependency
        from all2md.options import OdsSpreadsheetOptions

        options = options or OdsSpreadsheetOptions()
        super().__init__()

        # Type hint for IDE
        from all2md.options import OdsSpreadsheetOptions
        self.options: OdsSpreadsheetOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], bytes]) -> Document:
        """Parse ODS spreadsheet into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], or bytes
            The input ODS file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed spreadsheet structure

        Raises
        ------
        MarkdownConversionError
            If parsing fails due to invalid format or corruption
        DependencyError
            If required dependencies are not installed
        InputError
            If input data is invalid or inaccessible

        """
        # Import odfpy
        try:
            from odf import opendocument
        except ImportError as e:
            raise DependencyError(
                converter_name="ods",
                missing_packages=[("odfpy", "")]
            ) from e

        # Load ODS document
        try:
            doc_input, input_type = validate_and_convert_input(
                input_data, supported_types=["path-like", "file-like", "bytes"], require_binary=True
            )
            doc = opendocument.load(doc_input)
        except Exception as e:
            raise MalformedFileError(
                f"Failed to parse ODS file: {e!r}",
                original_error=e
            ) from e

        return self.ods_to_ast(doc)

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
        from odf.table import Table as OdfTable
        from odf.table import TableCell, TableRow

        children = []

        # Extract metadata
        metadata = self.extract_metadata(doc)

        body = doc.body
        tables = list(body.getElementsByType(OdfTable)) if body else []

        if not tables:
            return Document(children=[], metadata=metadata.to_dict())

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

            # Apply row/column trimming
            all_rows = [header] + data_rows if header else data_rows
            all_rows = self._trim_rows(all_rows)
            all_rows = self._trim_columns(all_rows)

            if not all_rows:
                continue

            # Sanitize all cell content
            header = [_sanitize_cell_text(cell, self.options.preserve_newlines_in_cells) for cell in all_rows[0]]
            data_rows = [
                [_sanitize_cell_text(cell, self.options.preserve_newlines_in_cells) for cell in row]
                 for row in all_rows[1:]
            ]

            # Apply header case transformation
            header = self._transform_header_case(header)

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

        return Document(children=children, metadata=metadata.to_dict())

    def _trim_rows(self, rows: list[list[str]]) -> list[list[str]]:
        """Trim empty rows based on trim_empty option.

        Parameters
        ----------
        rows : list[list[str]]
            Rows to trim

        Returns
        -------
        list[list[str]]
            Trimmed rows

        """
        if not rows or self.options.trim_empty == "none":
            return rows

        # Trim leading empty rows
        if self.options.trim_empty in ("leading", "both"):
            while rows and all(c == "" for c in rows[0]):
                rows.pop(0)

        # Trim trailing empty rows
        if self.options.trim_empty in ("trailing", "both"):
            while rows and all(c == "" for c in rows[-1]):
                rows.pop()

        return rows

    def _trim_columns(self, rows: list[list[str]]) -> list[list[str]]:
        """Trim empty columns based on trim_empty option.

        Parameters
        ----------
        rows : list[list[str]]
            Rows to trim columns from

        Returns
        -------
        list[list[str]]
            Rows with trimmed columns

        """
        if not rows or self.options.trim_empty == "none":
            return rows

        if not rows[0]:
            return rows

        num_cols = len(rows[0])

        # Find leading empty columns
        leading_empty = 0
        if self.options.trim_empty in ("leading", "both"):
            for col_idx in range(num_cols):
                if all(row[col_idx] == "" if col_idx < len(row) else True for row in rows):
                    leading_empty += 1
                else:
                    break

        # Find trailing empty columns
        trailing_empty = 0
        if self.options.trim_empty in ("trailing", "both"):
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

    def _transform_header_case(self, header: list[str]) -> list[str]:
        """Transform header case based on header_case option.

        Parameters
        ----------
        header : list[str]
            Header row

        Returns
        -------
        list[str]
            Transformed header

        """
        if self.options.header_case == "preserve":
            return header
        elif self.options.header_case == "title":
            return [cell.title() for cell in header]
        elif self.options.header_case == "upper":
            return [cell.upper() for cell in header]
        elif self.options.header_case == "lower":
            return [cell.lower() for cell in header]
        return header

    def extract_metadata(self, document: Any) -> DocumentMetadata:
        """Extract metadata from ODS document.

        Parameters
        ----------
        document : Any
            ODS document object

        Returns
        -------
        DocumentMetadata
            Extracted metadata

        """
        metadata = DocumentMetadata()

        # Try to extract metadata from document properties
        try:
            if hasattr(document, 'meta'):
                from odf.dc import Creator, Description, Title
                from odf.meta import CreationDate

                meta = document.meta

                # Title
                titles = meta.getElementsByType(Title)
                if titles and len(titles) > 0:
                    metadata.title = str(titles[0]).strip()

                # Creator
                creators = meta.getElementsByType(Creator)
                if creators and len(creators) > 0:
                    metadata.author = str(creators[0]).strip()

                # Description
                descriptions = meta.getElementsByType(Description)
                if descriptions and len(descriptions) > 0:
                    metadata.subject = str(descriptions[0]).strip()

                # Creation date
                creation_dates = meta.getElementsByType(CreationDate)
                if creation_dates and len(creation_dates) > 0:
                    metadata.creation_date = str(creation_dates[0]).strip()
        except Exception:
            pass

        return metadata


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="ods",
    extensions=[".ods"],
    mime_types=["application/vnd.oasis.opendocument.spreadsheet"],
    magic_bytes=[
        (b"PK\x03\x04", 0),
    ],
    parser_class=OdsSpreadsheetToAstConverter,
    renderer_class=None,
    parser_required_packages=[("odfpy", "odf", "")],
    renderer_required_packages=[],
    import_error_message="ODS conversion requires 'odfpy'. Install with: pip install odfpy",
    parser_options_class="OdsSpreadsheetOptions",
    renderer_options_class=None,
    description="Convert OpenDocument Spreadsheet files to Markdown tables",
    priority=6
)
