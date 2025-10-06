#  Copyright (c) 2025 Tom Villani, Ph.D.
#
# src/all2md/parsers/csv.py
"""CSV/TSV to AST converter.

This module provides conversion from CSV and TSV files to AST representation.
It replaces the combined spreadsheet parser with a focused delimiter-separated values parser.

"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import IO, Union

from all2md.ast import Document, HTMLInline, Paragraph, Table, TableCell, TableRow, Text
from all2md.converter_metadata import ConverterMetadata
from all2md.exceptions import ParsingError
from all2md.parsers.base import BaseParser
from all2md.utils.inputs import validate_and_convert_input
from all2md.utils.metadata import DocumentMetadata

logger = logging.getLogger(__name__)


def _sanitize_cell_text(text: str) -> str:
    """Convert cell value to a safe string for AST Text node.

    Note: Markdown escaping is handled by the renderer, not here.
    We only normalize whitespace and convert to string.

    Parameters
    ----------
    text : str
        Cell value to sanitize

    Returns
    -------
    str
        Sanitized cell text

    """
    if text is None:
        return ""

    # Simple normalization
    s = str(text)
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

    # Convert alignment strings to the format expected by Table node
    table_alignments = []
    for align in alignments:
        if align in ("left", "center", "right"):
            table_alignments.append(align)
        else:
            table_alignments.append("center")

    return Table(header=header_row, rows=data_rows, alignments=table_alignments)


class CsvToAstConverter(BaseParser):
    """Convert CSV/TSV files to AST representation.

    This converter handles CSV and TSV (tab-separated values) formats
    by building Table nodes from delimited text data.

    Parameters
    ----------
    options : CsvOptions or None
        Conversion options

    """

    def __init__(self, options=None, progress_callback=None):
        # Import here to avoid circular dependency
        from all2md.options import CsvOptions

        options = options or CsvOptions()
        super().__init__(options, progress_callback)

        # Type hint for IDE
        from all2md.options import CsvOptions
        self.options: CsvOptions = options

    def parse(self, input_data: Union[str, Path, IO[bytes], IO[str], bytes]) -> Document:
        """Parse CSV/TSV file into an AST.

        Parameters
        ----------
        input_data : str, Path, IO[bytes], IO[str], or bytes
            The input CSV/TSV file to parse

        Returns
        -------
        Document
            AST Document node representing the parsed spreadsheet structure

        Raises
        ------
        ParsingError
            If parsing fails due to invalid format

        """
        # Determine delimiter
        delimiter = self._determine_delimiter(input_data)

        return self.csv_to_ast(input_data, delimiter)

    def _determine_delimiter(self, input_data) -> str:
        """Determine the delimiter for the CSV/TSV file.

        Parameters
        ----------
        input_data : various
            Input data to analyze

        Returns
        -------
        str
            Delimiter character

        """
        # If explicitly set, use that
        if self.options.csv_delimiter:
            return self.options.csv_delimiter

        # Check file extension for TSV
        if isinstance(input_data, (str, Path)):
            path = Path(input_data)
            if path.suffix.lower() == '.tsv':
                return '\t'
        elif hasattr(input_data, 'name'):
            filename = getattr(input_data, 'name', '')
            if filename and Path(filename).suffix.lower() == '.tsv':
                return '\t'

        # Default to comma
        return ','

    def csv_to_ast(
        self,
        input_data: Union[str, Path, IO[bytes], IO[str]],
        delimiter: str | None = None,
    ) -> Document:
        """Convert CSV/TSV to AST Document.

        Parameters
        ----------
        input_data : Union[str, Path, IO[bytes], IO[str]]
            Input data
        delimiter : str | None
            Delimiter character to use (e.g., ',' for CSV, '\\t' for TSV)

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
            raise ParsingError(
                f"Failed to read CSV/TSV input: {e}", parsing_stage="input_processing", original_error=e
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

        # Calculate maximum rows to read (header + max_rows data rows)
        max_total_rows = None
        if self.options.max_rows is not None:
            # Account for header row if present
            max_total_rows = (self.options.max_rows + 1) if self.options.has_header else self.options.max_rows

        # Read rows with early termination if max_rows is set
        row_count = 0
        for r in reader:
            rows.append(r)
            row_count += 1
            if max_total_rows is not None and row_count >= max_total_rows:
                break

        # Extract metadata (CSV/TSV have no structured metadata)
        metadata = self.extract_metadata(None)

        # Drop leading/trailing fully empty rows
        def is_empty(row: list[str]) -> bool:
            return all((not (c or "").strip()) for c in row)

        # Skip empty rows if requested
        if self.options.skip_empty_rows:
            while rows and is_empty(rows[0]):
                rows.pop(0)
            while rows and is_empty(rows[-1]):
                rows.pop()

        if not rows:
            return Document(children=[], metadata=metadata.to_dict())

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
                return Document(children=[], metadata=metadata.to_dict())

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
            header = [_sanitize_cell_text(c).lstrip("\ufeff") for c in header]
        else:
            header = [_sanitize_cell_text(c) for c in header]
        data_rows = [[_sanitize_cell_text(c) for c in r] for r in data_rows]

        # Strip whitespace if requested
        if self.options.strip_whitespace:
            header = [c.strip() for c in header]
            data_rows = [[c.strip() for c in r] for r in data_rows]

        # Apply header case transformation
        header = self._transform_header_case(header)

        # Alignments default to center
        alignments = ["center"] * len(header)

        # Build table AST
        table = _build_table_ast(header, data_rows, alignments)

        children = [table]

        if truncated:
            children.append(
                Paragraph(content=[HTMLInline(content=f"*{self.options.truncation_indicator}*")])
            )

        return Document(children=children, metadata=metadata.to_dict())

    def _read_text_stream_for_csv(self, input_data) -> io.StringIO:
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

    def extract_metadata(self, document) -> DocumentMetadata:
        """Extract metadata from CSV/TSV document.

        Parameters
        ----------
        document : Any
            Document object (None for CSV/TSV)

        Returns
        -------
        DocumentMetadata
            Empty metadata (CSV/TSV don't have structured metadata)

        """
        return DocumentMetadata()


def _detect_csv_tsv_content(content: bytes) -> bool:
    """Content-based detector for CSV/TSV formats.

    This function is used by the registry to detect CSV/TSV files
    based on content patterns when file extensions are not available.

    Parameters
    ----------
    content : bytes
        File content to analyze

    Returns
    -------
    bool
        True if content appears to be CSV or TSV

    """
    try:
        content_str = content.decode('utf-8', errors='ignore')
        non_empty_lines = [line.strip() for line in content_str.split('\n') if line.strip()]

        if len(non_empty_lines) >= 2:
            comma_count = sum(line.count(',') for line in non_empty_lines)
            tab_count = sum(line.count('\t') for line in non_empty_lines)

            if comma_count >= len(non_empty_lines):
                logger.debug(f"CSV pattern detected: {comma_count} commas in {len(non_empty_lines)} lines")
                return True
            elif tab_count >= len(non_empty_lines):
                logger.debug(f"TSV pattern detected: {tab_count} tabs in {len(non_empty_lines)} lines")
                return True
    except UnicodeDecodeError:
        pass

    return False


# Converter metadata for registration
CONVERTER_METADATA = ConverterMetadata(
    format_name="csv",
    extensions=[".csv", ".tsv"],
    mime_types=[
        "text/csv",
        "application/csv",
        "text/tab-separated-values"
    ],
    magic_bytes=[],
    content_detector=_detect_csv_tsv_content,
    parser_class=CsvToAstConverter,
    renderer_class=None,
    parser_required_packages=[],
    renderer_required_packages=[],
    import_error_message="CSV/TSV conversion uses Python standard library (no dependencies)",
    parser_options_class="CsvOptions",
    renderer_options_class=None,
    description="Convert CSV and TSV files to Markdown tables",
    priority=6
)
